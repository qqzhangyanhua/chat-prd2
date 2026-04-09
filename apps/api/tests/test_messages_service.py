from uuid import uuid4
from types import SimpleNamespace
import json
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.agent.types import NextAction, Suggestion, TurnDecision
from app.db.models import User
from app.db.models import AgentTurnDecision
from app.db.models import ProjectStateVersion
from app.repositories import agent_turn_decisions as agent_turn_decisions_repository
from app.repositories import assistant_reply_groups as assistant_reply_groups_repository
from app.repositories import assistant_reply_versions as assistant_reply_versions_repository
from app.repositories import messages as messages_repository
from app.repositories import model_configs as model_configs_repository
from app.repositories import prd as prd_repository
from app.repositories import sessions as sessions_repository
from app.repositories import state as state_repository
from app.services import sessions as session_service
import app.services.messages as messages_service
from app.services.messages import apply_prd_patch, apply_state_patch, handle_user_message
from app.services.messages import stream_regenerate_message_events
from app.services.messages import stream_user_message_events
from app.services.model_gateway import ModelGatewayError

PRD_META_CONTRACT_CASES = json.loads(
    Path(__file__).resolve().parents[3].joinpath("docs/contracts/prd-meta-cases.json").read_text(encoding="utf-8")
)


def test_apply_state_patch_empty_patch_returns_original():
    state = {"idea": "test", "target_user": None}
    result = apply_state_patch(state, {})
    assert result is state


def test_apply_state_patch_merges_keys():
    state = {"idea": "test", "target_user": None, "problem": None}
    result = apply_state_patch(state, {"target_user": "developers", "problem": "too slow"})
    assert result["target_user"] == "developers"
    assert result["problem"] == "too slow"
    assert result["idea"] == "test"


def test_apply_prd_patch_empty_patch_returns_original():
    state = {"prd_snapshot": {"sections": {}}}
    result = apply_prd_patch(state, {})
    assert result is state


def test_apply_prd_patch_merges_sections():
    state = {
        "prd_snapshot": {
            "sections": {"target_user": {"content": "old"}}
        }
    }
    result = apply_prd_patch(state, {"problem": {"content": "new problem"}})
    assert result["prd_snapshot"]["sections"]["target_user"]["content"] == "old"
    assert result["prd_snapshot"]["sections"]["problem"]["content"] == "new problem"


def test_apply_prd_patch_overwrites_existing_section():
    state = {
        "prd_snapshot": {
            "sections": {"target_user": {"content": "old"}}
        }
    }
    result = apply_prd_patch(state, {"target_user": {"content": "updated"}})
    assert result["prd_snapshot"]["sections"]["target_user"]["content"] == "updated"


def test_preview_prd_meta_matches_shared_contract():
    for contract_case in PRD_META_CONTRACT_CASES:
        assert messages_service._preview_prd_meta({}, contract_case["state"]) == contract_case["expected"]


def _create_session_with_state(db_session):
    user = User(
        id=str(uuid4()),
        email=f"messages-service-{uuid4()}@example.com",
        password_hash="hashed",
    )
    db_session.add(user)
    session = sessions_repository.create_session(
        db=db_session,
        user_id=user.id,
        title="消息测试",
        initial_idea="做一个 AI 产品经理",
    )
    state_repository.create_state_version(
        db=db_session,
        session_id=session.id,
        version=1,
        state_json={"target_user": None, "prd_snapshot": {"sections": {}}},
    )
    db_session.commit()
    return session


def _sample_turn_decision() -> TurnDecision:
    return TurnDecision(
        phase="idea_clarification",
        phase_goal="收敛目标用户",
        understanding={
            "summary": "用户给了一个模糊方向",
            "candidate_updates": {},
            "ambiguous_points": [],
        },
        assumptions=[],
        gaps=["缺少明确的目标用户"],
        challenges=["目标用户范围过泛，需优先收敛"],
        pm_risk_flags=["user_too_broad"],
        next_move="force_rank_or_choose",
        suggestions=[
            Suggestion(
                type="direction",
                label="独立开发者",
                content="先聚焦独立开发者",
                rationale="反馈链路更短",
                priority=1,
            ),
        ],
        recommendation={"label": "独立开发者"},
        reply_brief={"focus": "force_rank_or_choose", "must_include": []},
        state_patch={},
        prd_patch={},
        needs_confirmation=["是否先聚焦独立开发者"],
        confidence="medium",
        next_best_questions=["如果只能先选一个主线，你更愿意先收敛用户还是问题？"],
        strategy_reason="目标用户仍然过泛，当前先推动你做主线取舍。",
    )


def _phase1_state(**overrides):
    base = {
        "idea": "做一个 AI 产品经理",
        "stage_hint": "问题探索",
        "iteration": 0,
        "goal": None,
        "target_user": None,
        "problem": None,
        "solution": None,
        "mvp_scope": [],
        "success_metrics": [],
        "known_facts": {},
        "assumptions": [],
        "risks": [],
        "unexplored_areas": [],
        "options": [],
        "decisions": [],
        "open_questions": [],
        "prd_snapshot": {"sections": {}},
        "current_phase": "idea_clarification",
        "phase_goal": None,
        "current_model_scene": "general",
        "collaboration_mode_label": "通用协作模式",
        "working_hypotheses": [],
        "evidence": [],
        "decision_readiness": None,
        "pm_risk_flags": [],
        "recommended_directions": [],
        "pending_confirmations": [],
        "rejected_options": [],
        "next_best_questions": [],
    }
    base.update(overrides)
    return base


def test_handle_user_message_rejects_missing_model_config(db_session):
    session = _create_session_with_state(db_session)
    reasoning_model = model_configs_repository.create_model_config(
        db_session,
        name="长文本模型",
        recommended_scene="reasoning",
        recommended_usage="适合承接长文本推理。",
        base_url="https://gateway.example.com/v1",
        api_key="secret",
        model="claude-3-7-sonnet",
        enabled=True,
    )
    fallback_model = model_configs_repository.create_model_config(
        db_session,
        name="推荐模型",
        recommended_scene="general",
        recommended_usage="适合继续通用产品对话。",
        base_url="https://gateway.example.com/v1",
        api_key="secret",
        model="gpt-4o-mini",
        enabled=True,
    )
    db_session.commit()

    with pytest.raises(HTTPException) as exc_info:
        handle_user_message(
            db=db_session,
            session_id=session.id,
            session=session,
            content="帮我分析用户画像",
            model_config_id="missing-config",
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Model config not found"
    assert getattr(exc_info.value, "code", None) == "MODEL_CONFIG_NOT_FOUND"
    assert getattr(exc_info.value, "recovery_action", None) == {
        "type": "select_available_model",
        "label": "选择可用模型",
        "target": None,
    }
    assert getattr(exc_info.value, "details", None) == {
        "available_model_configs": [
            {
                "id": fallback_model.id,
                "name": "推荐模型",
                "model": "gpt-4o-mini",
            },
            {
                "id": reasoning_model.id,
                "name": "长文本模型",
                "model": "claude-3-7-sonnet",
            },
        ],
        "recommended_model_config_id": fallback_model.id,
        "recommended_model_scene": "general",
        "recommended_model_name": "推荐模型",
        "recommended_model_reason": "原先选择的模型已不存在，建议先切换到这个可用模型继续对话。适合继续通用产品对话。",
        "requested_model_config_id": "missing-config",
    }


def test_handle_user_message_missing_model_prefers_general_scene_recommendation_over_latest(db_session):
    session = _create_session_with_state(db_session)
    general_model = model_configs_repository.create_model_config(
        db_session,
        name="通用对话模型",
        recommended_scene="general",
        recommended_usage="适合继续通用产品对话。",
        base_url="https://gateway.example.com/v1",
        api_key="secret",
        model="gpt-4o-mini",
        enabled=True,
    )
    model_configs_repository.create_model_config(
        db_session,
        name="长文本模型",
        recommended_scene="reasoning",
        recommended_usage="适合承接长文本推理。",
        base_url="https://gateway.example.com/v1",
        api_key="secret",
        model="claude-3-7-sonnet",
        enabled=True,
    )
    db_session.commit()

    with pytest.raises(HTTPException) as exc_info:
        handle_user_message(
            db=db_session,
            session_id=session.id,
            session=session,
            content="帮我分析用户画像",
            model_config_id="missing-config",
        )

    details = getattr(exc_info.value, "details", None)
    assert details is not None
    assert details["recommended_model_config_id"] == general_model.id
    assert details["recommended_model_scene"] == "general"
    assert details["recommended_model_name"] == "通用对话模型"


def test_handle_user_message_rejects_disabled_model_config(db_session):
    session = _create_session_with_state(db_session)
    model_config = model_configs_repository.create_model_config(
        db_session,
        name="禁用模型",
        recommended_scene="reasoning",
        recommended_usage="适合承接长文本推理。",
        base_url="https://gateway.example.com/v1",
        api_key="secret",
        model="gpt-4o-mini",
        enabled=False,
    )
    general_model = model_configs_repository.create_model_config(
        db_session,
        name="通用模型",
        recommended_scene="general",
        recommended_usage="适合继续通用产品对话。",
        base_url="https://gateway.example.com/v1",
        api_key="secret",
        model="gpt-4o-mini",
        enabled=True,
    )
    fallback_model = model_configs_repository.create_model_config(
        db_session,
        name="推荐模型",
        recommended_scene="reasoning",
        recommended_usage="适合承接长文本推理。",
        base_url="https://gateway.example.com/v1",
        api_key="secret",
        model="claude-3-7-sonnet",
        enabled=True,
    )
    db_session.commit()

    with pytest.raises(HTTPException) as exc_info:
        handle_user_message(
            db=db_session,
            session_id=session.id,
            session=session,
            content="帮我分析用户画像",
            model_config_id=model_config.id,
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Model config is disabled"
    assert getattr(exc_info.value, "code", None) == "MODEL_CONFIG_DISABLED"
    assert getattr(exc_info.value, "recovery_action", None) == {
        "type": "select_available_model",
        "label": "选择可用模型",
        "target": None,
    }
    assert getattr(exc_info.value, "details", None) == {
        "available_model_configs": [
            {
                "id": fallback_model.id,
                "name": "推荐模型",
                "model": "claude-3-7-sonnet",
            },
            {
                "id": general_model.id,
                "name": "通用模型",
                "model": "gpt-4o-mini",
            },
        ],
        "recommended_model_config_id": fallback_model.id,
        "recommended_model_scene": "reasoning",
        "recommended_model_name": "推荐模型",
        "recommended_model_reason": "原先选择的模型已停用，建议先切换到这个可用模型继续对话。适合承接长文本推理。",
        "requested_model_config_id": model_config.id,
        "requested_model_name": "禁用模型",
    }


def test_handle_user_message_disabled_model_prefers_same_scene_recommendation(db_session):
    session = _create_session_with_state(db_session)
    model_config = model_configs_repository.create_model_config(
        db_session,
        name="禁用长文本模型",
        recommended_scene="reasoning",
        recommended_usage="适合承接长文本推理。",
        base_url="https://gateway.example.com/v1",
        api_key="secret",
        model="claude-3-7-sonnet",
        enabled=False,
    )
    model_configs_repository.create_model_config(
        db_session,
        name="通用模型",
        recommended_scene="general",
        recommended_usage="适合继续通用产品对话。",
        base_url="https://gateway.example.com/v1",
        api_key="secret",
        model="gpt-4o-mini",
        enabled=True,
    )
    same_scene_model = model_configs_repository.create_model_config(
        db_session,
        name="长文本候选模型",
        recommended_scene="reasoning",
        recommended_usage="适合承接长文本推理。",
        base_url="https://gateway.example.com/v1",
        api_key="secret",
        model="claude-3-5-sonnet",
        enabled=True,
    )
    db_session.commit()

    with pytest.raises(HTTPException) as exc_info:
        handle_user_message(
            db=db_session,
            session_id=session.id,
            session=session,
            content="帮我分析用户画像",
            model_config_id=model_config.id,
        )

    details = getattr(exc_info.value, "details", None)
    assert details is not None
    assert details["recommended_model_config_id"] == same_scene_model.id
    assert details["recommended_model_scene"] == "reasoning"
    assert details["recommended_model_name"] == "长文本候选模型"


def test_handle_user_message_uses_selected_model_and_persists_model_metadata(db_session, monkeypatch):
    session = _create_session_with_state(db_session)
    model_config = model_configs_repository.create_model_config(
        db_session,
        name="OpenAI 兼容模型",
        base_url="https://gateway.example.com/v1",
        api_key="secret",
        model="gpt-4o-mini",
        enabled=True,
    )
    db_session.commit()

    captured = {}

    def fake_generate_reply(*, base_url, api_key, model, messages):
        captured["base_url"] = base_url
        captured["api_key"] = api_key
        captured["model"] = model
        captured["messages"] = messages
        return "这是网关生成的回复"

    monkeypatch.setattr("app.services.messages.generate_reply", fake_generate_reply)

    result = handle_user_message(
        db=db_session,
        session_id=session.id,
        session=session,
        content="帮我梳理目标用户",
        model_config_id=model_config.id,
    )

    assert result.reply == "这是网关生成的回复"
    assert captured == {
        "base_url": "https://gateway.example.com/v1",
        "api_key": "secret",
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": "你是用户的 AI 产品协作助手，请基于上下文给出简洁、直接的中文回复。"},
            {"role": "user", "content": "帮我梳理目标用户"},
        ],
    }

    persisted_messages = messages_repository.get_messages_for_session(db_session, session.id)
    assert len(persisted_messages) == 2

    user_message = next(message for message in persisted_messages if message.role == "user")
    assistant_message = next(message for message in persisted_messages if message.role == "assistant")

    expected_model_meta = {
        "model_config_id": model_config.id,
        "model_name": "gpt-4o-mini",
        "display_name": "OpenAI 兼容模型",
        "base_url": "https://gateway.example.com/v1",
    }
    assert user_message.meta == expected_model_meta
    assert assistant_message.meta["action"]["action"] == "probe_deeper"
    assert assistant_message.meta["model_config_id"] == model_config.id
    assert assistant_message.meta["model_name"] == "gpt-4o-mini"
    assert assistant_message.meta["display_name"] == "OpenAI 兼容模型"
    assert assistant_message.meta["base_url"] == "https://gateway.example.com/v1"


def test_handle_user_message_persists_turn_decision_audit(db_session, monkeypatch):
    session = _create_session_with_state(db_session)
    model_config = model_configs_repository.create_model_config(
        db_session,
        name="审计模型",
        base_url="https://gateway.example.com/v1",
        api_key="secret",
        model="gpt-4o-mini",
        enabled=True,
    )
    db_session.commit()

    monkeypatch.setattr("app.services.messages.generate_reply", lambda **_: "审计回复")

    result = handle_user_message(
        db=db_session,
        session_id=session.id,
        session=session,
        content="请继续推进这个产品想法",
        model_config_id=model_config.id,
    )

    decision = db_session.execute(
        select(AgentTurnDecision).where(
            AgentTurnDecision.user_message_id == result.user_message_id
        )
    ).scalar_one_or_none()
    assert decision is not None
    assert decision.user_message_id == result.user_message_id
    assert decision.session_id == session.id
    assert decision.phase
    assert isinstance(decision.understanding_summary, str)
    assert decision.next_move
    assert decision.confidence in {"high", "medium", "low"}
    assert isinstance(decision.assumptions_json, list)
    assert isinstance(decision.risk_flags_json, list)
    assert isinstance(decision.suggestions_json, list)
    assert isinstance(decision.needs_confirmation_json, list)
    assert isinstance(decision.state_patch_json, dict)
    assert isinstance(decision.prd_patch_json, dict)
    assert isinstance(decision.recommendation_json, (dict, type(None)))


def test_handle_user_message_persists_workflow_stage_and_critic_result(db_session, monkeypatch):
    session = _create_session_with_state(db_session)
    state_repository.create_state_version(
        db=db_session,
        session_id=session.id,
        version=2,
        state_json=session_service.build_initial_state(session.initial_idea),
    )
    model_config = model_configs_repository.create_model_config(
        db_session,
        name="闭环持久化模型",
        base_url="https://gateway.example.com/v1",
        api_key="secret",
        model="gpt-4o-mini",
        enabled=True,
    )
    db_session.commit()

    monkeypatch.setattr("app.services.messages.generate_reply", lambda **_: "忽略这条网关回复")

    result = handle_user_message(
        db=db_session,
        session_id=session.id,
        session=session,
        content="我想做一个在线3D图纸预览平台",
        model_config_id=model_config.id,
    )

    latest_state = state_repository.get_latest_state(db_session, session.id)
    latest_prd_snapshot = prd_repository.get_latest_prd_snapshot(db_session, session.id)
    decision = db_session.execute(
        select(AgentTurnDecision).where(
            AgentTurnDecision.user_message_id == result.user_message_id
        )
    ).scalar_one()

    assert latest_state["workflow_stage"] == "refine_loop"
    assert latest_state["idea_parse_result"]["idea_summary"]
    assert latest_state["prd_draft"]["version"] == 1
    assert latest_state["critic_result"]["question_queue"]
    assert latest_state["refine_history"] in ([], None)
    assert latest_state["finalization_ready"] is False
    assert latest_state["current_phase"] == "initial_draft"
    assert latest_state["conversation_strategy"] == "clarify"
    assert latest_state["next_best_questions"] == latest_state["critic_result"]["question_queue"]
    assert decision.state_patch_json["workflow_stage"] == "refine_loop"
    assert decision.state_patch_json["idea_parse_result"]["idea_summary"]
    assert decision.state_patch_json["prd_draft"]["version"] == 1
    assert decision.state_patch_json["critic_result"]["question_queue"]
    assert decision.state_patch_json.get("finalization_ready") in (None, False)


def test_handle_user_message_persists_prd_v2_after_refine_answer(db_session, monkeypatch):
    session = _create_session_with_state(db_session)
    model_config = model_configs_repository.create_model_config(
        db_session,
        name="refine 持久化模型",
        base_url="https://gateway.example.com/v1",
        api_key="secret",
        model="gpt-4o-mini",
        enabled=True,
    )
    state_repository.create_state_version(
        db=db_session,
        session_id=session.id,
        version=2,
        state_json={
            **_phase1_state(),
            "workflow_stage": "refine_loop",
            "prd_draft": {
                "version": 1,
                "status": "draft_hypothesis",
                "sections": {"positioning": {"content": "在线3D图纸预览平台"}},
                "assumptions": [],
                "missing_information": ["未明确核心文件格式"],
                "critic_ready": True,
            },
            "critic_result": {
                "overall_verdict": "block",
                "question_queue": ["第一版要支持哪些 3D/CAD 文件格式？"],
            },
            "finalization_ready": False,
        },
    )
    db_session.commit()

    def fail_generate_reply(**_kwargs):
        raise AssertionError("refine loop local reply should not call generate_reply")

    monkeypatch.setattr("app.services.messages.generate_reply", fail_generate_reply)

    result = handle_user_message(
        db=db_session,
        session_id=session.id,
        session=session,
        content="第一版先支持 STEP 和 OBJ",
        model_config_id=model_config.id,
    )

    latest_state = state_repository.get_latest_state(db_session, session.id)
    latest_prd_snapshot = prd_repository.get_latest_prd_snapshot(db_session, session.id)
    decision = db_session.execute(
        select(AgentTurnDecision).where(
            AgentTurnDecision.user_message_id == result.user_message_id
        )
    ).scalar_one()

    assert latest_state["prd_draft"]["version"] == 2
    assert latest_state["prd_draft"]["status"] == "draft_refined"
    assert "STEP" in str(latest_state["prd_draft"]["sections"])
    assert "OBJ" in str(latest_state["prd_draft"]["sections"])
    assert latest_state["critic_result"]["overall_verdict"] == "pass"
    assert latest_state["critic_result"]["question_queue"] == []
    assert latest_state["finalization_ready"] is True
    assert latest_state["workflow_stage"] == "finalize"
    assert decision.state_patch_json["prd_draft"]["version"] == 2
    assert decision.state_patch_json["critic_result"]["overall_verdict"] == "pass"
    assert latest_prd_snapshot is not None
    assert "STEP" in str(latest_prd_snapshot.sections)
    assert "OBJ" in str(latest_prd_snapshot.sections)


def test_merge_state_patch_with_decision_reads_workflow_fields_from_turn_decision_top_level():
    turn_decision = SimpleNamespace(
        phase="refine_loop",
        conversation_strategy="clarify",
        strategy_reason=None,
        phase_goal="补齐关键缺口",
        assumptions=[],
        pm_risk_flags=[],
        suggestions=[],
        recommendation=None,
        needs_confirmation=[],
        next_best_questions=["下一问"],
        workflow_stage="finalize",
        idea_parse_result={"idea_summary": "在线 3D 图纸预览平台"},
        prd_draft={"version": 2, "status": "draft_refined"},
        critic_result={"overall_verdict": "pass", "question_queue": []},
        refine_history=[{"question": "Q1", "answer": "A1"}],
        finalization_ready=True,
        state_patch={},
    )

    merged = messages_service._merge_state_patch_with_decision(
        state_patch={},
        turn_decision=turn_decision,
        current_state=_phase1_state(),
    )

    assert merged["workflow_stage"] == "finalize"
    assert merged["idea_parse_result"]["idea_summary"] == "在线 3D 图纸预览平台"
    assert merged["prd_draft"]["version"] == 2
    assert merged["critic_result"]["overall_verdict"] == "pass"
    assert merged["refine_history"] == [{"question": "Q1", "answer": "A1"}]
    assert merged["finalization_ready"] is True
    assert merged["current_phase"] == "refine_loop"
    assert merged["next_best_questions"] == ["下一问"]


def test_merge_state_patch_with_decision_prefers_turn_decision_workflow_fields_over_state_patch_conflicts():
    turn_decision = SimpleNamespace(
        phase="refine_loop",
        conversation_strategy="clarify",
        strategy_reason=None,
        phase_goal="补齐关键缺口",
        assumptions=[],
        pm_risk_flags=[],
        suggestions=[],
        recommendation=None,
        needs_confirmation=[],
        next_best_questions=["来自 turn_decision 的下一问"],
        workflow_stage="finalize",
        idea_parse_result={"idea_summary": "来自 turn_decision"},
        prd_draft={"version": 3},
        critic_result={"overall_verdict": "pass", "question_queue": []},
        refine_history=[{"source": "turn_decision"}],
        finalization_ready=True,
        state_patch={},
    )

    merged = messages_service._merge_state_patch_with_decision(
        state_patch={
            "workflow_stage": "refine_loop",
            "idea_parse_result": {"idea_summary": "来自 agent_result.state_patch"},
            "prd_draft": {"version": 1},
            "critic_result": {"overall_verdict": "block", "question_queue": ["旧问题"]},
            "refine_history": [{"source": "agent_result.state_patch"}],
            "finalization_ready": False,
        },
        turn_decision=turn_decision,
        current_state=_phase1_state(),
    )

    assert merged["workflow_stage"] == "finalize"
    assert merged["idea_parse_result"]["idea_summary"] == "来自 turn_decision"
    assert merged["prd_draft"]["version"] == 3
    assert merged["critic_result"]["overall_verdict"] == "pass"
    assert merged["refine_history"] == [{"source": "turn_decision"}]
    assert merged["finalization_ready"] is True


def test_handle_user_message_prefers_model_structured_extraction_when_available(
    db_session,
    monkeypatch,
):
    session = _create_session_with_state(db_session)
    model_config = model_configs_repository.create_model_config(
        db_session,
        name="结构化提取模型",
        base_url="https://gateway.example.com/v1",
        api_key="secret",
        model="gpt-4o-mini",
        enabled=True,
    )
    db_session.commit()

    monkeypatch.setattr("app.services.messages.generate_reply", lambda **_: "这是网关生成的回复")
    monkeypatch.setattr(
        "app.services.messages.generate_structured_extraction",
        lambda **_: {
            "should_update": True,
            "confidence": "high",
            "reasoning_summary": "识别到更具体的目标用户",
            "state_patch": {
                "target_user": "独立开发者团队负责人",
                "iteration": 1,
                "stage_hint": "问题定义",
            },
            "prd_patch": {
                "target_user": {
                    "title": "目标用户",
                    "content": "独立开发者团队负责人",
                    "status": "confirmed",
                }
            },
        },
    )

    handle_user_message(
        db=db_session,
        session_id=session.id,
        session=session,
        content="我们主要服务独立开发者团队负责人",
        model_config_id=model_config.id,
    )

    latest_state = state_repository.get_latest_state(db_session, session.id)
    latest_prd_snapshot = prd_repository.get_latest_prd_snapshot(db_session, session.id)

    assert latest_state["target_user"] == "独立开发者团队负责人"
    assert latest_prd_snapshot is not None
    assert latest_prd_snapshot.sections["target_user"]["content"] == "独立开发者团队负责人"


def test_handle_user_message_persists_phase1_state_fields(db_session, monkeypatch):
    session = _create_session_with_state(db_session)
    model_config = model_configs_repository.create_model_config(
        db_session,
        name="阶段字段模型",
        base_url="https://gateway.example.com/v1",
        api_key="secret",
        model="gpt-4o-mini",
        enabled=True,
    )
    state_repository.create_state_version(
        db=db_session,
        session_id=session.id,
        version=2,
        state_json=_phase1_state(
            target_user="独立创业者",
            problem="不知道先验证哪个需求",
            solution="通过连续追问沉淀结构化 PRD",
            mvp_scope=["创建会话", "持续追问", "导出 PRD"],
            iteration=3,
            stage_hint="MVP 收敛",
        ),
    )
    prd_repository.create_prd_snapshot(
        db=db_session,
        session_id=session.id,
        version=2,
        sections={},
    )
    db_session.commit()

    monkeypatch.setattr("app.services.messages.generate_reply", lambda **_: "进入总结")

    handle_user_message(
        db=db_session,
        session_id=session.id,
        session=session,
        content="继续",
        model_config_id=model_config.id,
    )

    latest_state = state_repository.get_latest_state(db_session, session.id)

    assert latest_state["current_phase"]
    assert latest_state["phase_goal"] == "总结共识并确认下一步"
    assert latest_state["conversation_strategy"] == "confirm"
    assert "核心信息已基本齐备" in latest_state["strategy_reason"]
    assert latest_state["current_model_scene"] == "general"
    assert latest_state["collaboration_mode_label"] == "通用协作模式"
    assert latest_state["recommended_directions"]
    assert latest_state["pending_confirmations"] == ["请确认当前理解是否准确"]
    assert latest_state["next_best_questions"] == ["请确认当前理解是否准确"]
    assert latest_state["working_hypotheses"] == []
    assert latest_state["pm_risk_flags"] == []


def test_handle_user_message_persists_runtime_model_scene_for_reasoning_model(
    db_session,
    monkeypatch,
):
    session = _create_session_with_state(db_session)
    model_config = model_configs_repository.create_model_config(
        db_session,
        name="深度推理模型",
        recommended_scene="reasoning",
        recommended_usage="适合承接长文本推理。",
        base_url="https://gateway.example.com/v1",
        api_key="secret",
        model="claude-3-7-sonnet",
        enabled=True,
    )
    db_session.commit()

    monkeypatch.setattr("app.services.messages.generate_reply", lambda **_: "继续深挖")

    handle_user_message(
        db=db_session,
        session_id=session.id,
        session=session,
        content="请继续拆解这个复杂输入",
        model_config_id=model_config.id,
    )

    latest_state = state_repository.get_latest_state(db_session, session.id)

    assert latest_state["current_model_scene"] == "reasoning"
    assert latest_state["collaboration_mode_label"] == "深度推演模式"


def test_handle_user_message_persists_conversation_strategy_converge(
    db_session,
    monkeypatch,
):
    session = _create_session_with_state(db_session)
    model_config = model_configs_repository.create_model_config(
        db_session,
        name="策略收敛模型",
        base_url="https://gateway.example.com/v1",
        api_key="secret",
        model="gpt-4o-mini",
        enabled=True,
    )
    state_repository.create_state_version(
        db=db_session,
        session_id=session.id,
        version=2,
        state_json=_phase1_state(
            target_user="独立创业者",
            iteration=1,
            stage_hint="问题定义",
        ),
    )
    prd_repository.create_prd_snapshot(
        db=db_session,
        session_id=session.id,
        version=2,
        sections={},
    )
    db_session.commit()

    monkeypatch.setattr("app.services.messages.generate_reply", lambda **_: "继续推进")

    handle_user_message(
        db=db_session,
        session_id=session.id,
        session=session,
        content="他们现在最大的问题是不知道先验证哪个需求",
        model_config_id=model_config.id,
    )

    latest_state = state_repository.get_latest_state(db_session, session.id)

    assert latest_state["conversation_strategy"] == "converge"
    assert "已有方向信号" in latest_state["strategy_reason"]
    assert latest_state["next_best_questions"]
    assert "最想先验证" in latest_state["next_best_questions"][0]


def test_handle_user_message_preserves_confirm_strategy_on_vague_continue(
    db_session,
    monkeypatch,
):
    session = _create_session_with_state(db_session)
    model_config = model_configs_repository.create_model_config(
        db_session,
        name="确认保护模型",
        base_url="https://gateway.example.com/v1",
        api_key="secret",
        model="gpt-4o-mini",
        enabled=True,
    )
    state_repository.create_state_version(
        db=db_session,
        session_id=session.id,
        version=2,
        state_json=_phase1_state(
            target_user="独立创业者",
            problem="不知道先验证哪个需求",
            solution="通过连续追问沉淀结构化 PRD",
            mvp_scope=["创建会话", "持续追问", "导出 PRD"],
            conversation_strategy="confirm",
            pending_confirmations=["请确认当前理解是否准确"],
            iteration=4,
            stage_hint="总结共识",
        ),
    )
    prd_repository.create_prd_snapshot(
        db=db_session,
        session_id=session.id,
        version=2,
        sections={},
    )
    db_session.commit()

    monkeypatch.setattr("app.services.messages.generate_reply", lambda **_: "继续确认")

    handle_user_message(
        db=db_session,
        session_id=session.id,
        session=session,
        content="继续",
        model_config_id=model_config.id,
    )

    latest_state = state_repository.get_latest_state(db_session, session.id)

    assert latest_state["conversation_strategy"] == "confirm"
    assert "没有新增风险" in latest_state["strategy_reason"]
    assert latest_state["pending_confirmations"] == ["请确认当前理解是否准确"]


def test_handle_user_message_falls_back_to_rule_extraction_when_model_extraction_fails(
    db_session,
    monkeypatch,
):
    session = _create_session_with_state(db_session)
    model_config = model_configs_repository.create_model_config(
        db_session,
        name="结构化提取失败模型",
        base_url="https://gateway.example.com/v1",
        api_key="secret",
        model="gpt-4o-mini",
        enabled=True,
    )
    db_session.commit()

    monkeypatch.setattr("app.services.messages.generate_reply", lambda **_: "这是网关生成的回复")

    def fail_generate_structured_extraction(**_kwargs):
        raise ModelGatewayError("结构化提取失败")

    monkeypatch.setattr(
        "app.services.messages.generate_structured_extraction",
        fail_generate_structured_extraction,
    )

    handle_user_message(
        db=db_session,
        session_id=session.id,
        session=session,
        content="独立开发者",
        model_config_id=model_config.id,
    )

    latest_state = state_repository.get_latest_state(db_session, session.id)
    latest_prd_snapshot = prd_repository.get_latest_prd_snapshot(db_session, session.id)

    assert latest_state["target_user"] == "独立开发者"
    assert latest_prd_snapshot is not None
    assert latest_prd_snapshot.sections["target_user"]["content"] == "独立开发者"


def test_handle_user_message_uses_local_correction_reply_and_rolls_back_target_user(
    db_session,
    monkeypatch,
):
    session = _create_session_with_state(db_session)
    model_config = model_configs_repository.create_model_config(
        db_session,
        name="修正模型",
        base_url="https://gateway.example.com/v1",
        api_key="secret",
        model="gpt-4o-mini",
        enabled=True,
    )
    state_repository.create_state_version(
        db=db_session,
        session_id=session.id,
        version=2,
        state_json=_phase1_state(
            target_user="独立创业者",
            problem="不知道先验证哪个需求",
            solution="通过连续追问沉淀结构化 PRD",
            mvp_scope=["创建会话", "持续追问", "导出 PRD"],
            conversation_strategy="confirm",
            pending_confirmations=["目标用户是否准确"],
        ),
    )
    prd_repository.create_prd_snapshot(
        db=db_session,
        session_id=session.id,
        version=2,
        sections={
            "target_user": {"title": "目标用户", "content": "独立创业者", "status": "confirmed"},
            "problem": {"title": "核心问题", "content": "不知道先验证哪个需求", "status": "confirmed"},
        },
    )
    db_session.commit()

    def fail_generate_reply(**_kwargs):
        raise AssertionError("correction command should not call generate_reply")

    monkeypatch.setattr("app.services.messages.generate_reply", fail_generate_reply)

    result = handle_user_message(
        db=db_session,
        session_id=session.id,
        session=session,
        content="不对，先改目标用户",
        model_config_id=model_config.id,
    )

    latest_state = state_repository.get_latest_state(db_session, session.id)
    latest_prd_snapshot = prd_repository.get_latest_prd_snapshot(db_session, session.id)

    assert "我先回滚当前关于目标用户及其后续共识" in result.reply
    assert latest_state["target_user"] is None
    assert latest_state["problem"] is None
    assert latest_state["solution"] is None
    assert latest_state["mvp_scope"] == []
    assert latest_state["pending_confirmations"] == []
    assert latest_prd_snapshot is not None
    assert latest_prd_snapshot.sections["target_user"]["status"] == "missing"
    assert latest_prd_snapshot.sections["problem"]["status"] == "missing"


def test_handle_user_message_uses_local_confirm_continue_reply_without_generate_reply(
    db_session,
    monkeypatch,
):
    session = _create_session_with_state(db_session)
    model_config = model_configs_repository.create_model_config(
        db_session,
        name="确认推进模型",
        base_url="https://gateway.example.com/v1",
        api_key="secret",
        model="gpt-4o-mini",
        enabled=True,
    )
    state_repository.create_state_version(
        db=db_session,
        session_id=session.id,
        version=2,
        state_json=_phase1_state(
            target_user="独立创业者",
            problem="不知道先验证哪个需求",
            solution="通过连续追问沉淀结构化 PRD",
            mvp_scope=["创建会话", "持续追问", "导出 PRD"],
            conversation_strategy="confirm",
            pending_confirmations=["目标用户是否准确"],
        ),
    )
    prd_repository.create_prd_snapshot(
        db=db_session,
        session_id=session.id,
        version=2,
        sections={
            "target_user": {"title": "目标用户", "content": "独立创业者", "status": "confirmed"},
            "problem": {"title": "核心问题", "content": "不知道先验证哪个需求", "status": "confirmed"},
            "solution": {"title": "解决方案", "content": "通过连续追问沉淀结构化 PRD", "status": "confirmed"},
            "mvp_scope": {"title": "MVP 范围", "content": "创建会话、持续追问、导出 PRD", "status": "confirmed"},
        },
    )
    db_session.commit()

    def fail_generate_reply(**_kwargs):
        raise AssertionError("confirm continue command should not call generate_reply")

    monkeypatch.setattr("app.services.messages.generate_reply", fail_generate_reply)

    result = handle_user_message(
        db=db_session,
        session_id=session.id,
        session=session,
        content="确认，继续下一步",
        model_config_id=model_config.id,
    )

    latest_state = state_repository.get_latest_state(db_session, session.id)

    assert "我先锁定当前关于目标用户、核心问题、解决方案、MVP 范围的共识" in result.reply
    assert latest_state["conversation_strategy"] == "converge"
    assert latest_state["pending_confirmations"] == []
    assert latest_state["phase_goal"] == "明确首轮验证优先级"
    assert latest_state["next_best_questions"] == [
        "为了继续推进，请直接回答你现在最想先验证的是频率、付费意愿，还是转化阻力？"
    ]


def test_handle_user_message_uses_specific_local_confirm_reply_without_generate_reply(
    db_session,
    monkeypatch,
):
    session = _create_session_with_state(db_session)
    model_config = model_configs_repository.create_model_config(
        db_session,
        name="确认细分推进模型",
        base_url="https://gateway.example.com/v1",
        api_key="secret",
        model="gpt-4o-mini",
        enabled=True,
    )
    state_repository.create_state_version(
        db=db_session,
        session_id=session.id,
        version=2,
        state_json=_phase1_state(
            target_user="独立创业者",
            problem="不知道先验证哪个需求",
            solution="通过连续追问沉淀结构化 PRD",
            mvp_scope=["创建会话", "持续追问", "导出 PRD"],
            conversation_strategy="confirm",
            pending_confirmations=["目标用户是否准确"],
        ),
    )
    db_session.commit()

    def fail_generate_reply(**_kwargs):
        raise AssertionError("specific confirm command should not call generate_reply")

    monkeypatch.setattr("app.services.messages.generate_reply", fail_generate_reply)

    result = handle_user_message(
        db=db_session,
        session_id=session.id,
        session=session,
        content="确认，先看付费意愿",
        model_config_id=model_config.id,
    )

    latest_state = state_repository.get_latest_state(db_session, session.id)

    assert "我会先把讨论推进到“付费意愿验证”" in result.reply
    assert latest_state["conversation_strategy"] == "converge"
    assert latest_state["phase_goal"] == "明确付费意愿是否成立"
    assert latest_state["next_best_questions"] == [
        "为了继续推进，请直接回答这类用户现在有没有为替代方案付费，或者愿不愿意为更好结果付费。"
    ]


def test_handle_user_message_keeps_frequency_validation_in_local_stable_flow(
    db_session,
    monkeypatch,
):
    session = _create_session_with_state(db_session)
    model_config = model_configs_repository.create_model_config(
        db_session,
        name="频率验证模型",
        base_url="https://gateway.example.com/v1",
        api_key="secret",
        model="gpt-4o-mini",
        enabled=True,
    )
    state_repository.create_state_version(
        db=db_session,
        session_id=session.id,
        version=2,
        state_json=_phase1_state(
            target_user="独立创业者",
            problem="不知道先验证哪个需求",
            solution="通过连续追问沉淀结构化 PRD",
            mvp_scope=["创建会话", "持续追问", "导出 PRD"],
            conversation_strategy="converge",
            phase_goal="明确问题发生频率是否足够高",
            stage_hint="推进频率验证",
            validation_focus="frequency",
            validation_step=1,
        ),
    )
    db_session.commit()

    def fail_generate_reply(**_kwargs):
        raise AssertionError("frequency validation follow-up should not call generate_reply")

    monkeypatch.setattr("app.services.messages.generate_reply", fail_generate_reply)

    result = handle_user_message(
        db=db_session,
        session_id=session.id,
        session=session,
        content="最近几乎每天都会发生，尤其在准备新需求评审时",
        model_config_id=model_config.id,
    )

    latest_state = state_repository.get_latest_state(db_session, session.id)

    assert "我先按你的描述把当前判断收成“这是一个高频信号候选”" in result.reply
    assert latest_state["validation_focus"] == "frequency"
    assert latest_state["validation_step"] == 2
    assert latest_state["phase_goal"] == "确认高频问题是否造成真实损失"
    assert latest_state["next_best_questions"] == [
        "为了继续推进，请直接回答如果这件事持续发生，实际会多花什么时间、错过什么机会，或者带来什么损失。"
    ]


def test_handle_user_message_keeps_conversion_resistance_validation_in_local_stable_flow(
    db_session,
    monkeypatch,
):
    session = _create_session_with_state(db_session)
    model_config = model_configs_repository.create_model_config(
        db_session,
        name="转化阻力验证模型",
        base_url="https://gateway.example.com/v1",
        api_key="secret",
        model="gpt-4o-mini",
        enabled=True,
    )
    state_repository.create_state_version(
        db=db_session,
        session_id=session.id,
        version=2,
        state_json=_phase1_state(
            target_user="独立创业者",
            problem="不知道先验证哪个需求",
            solution="通过连续追问沉淀结构化 PRD",
            mvp_scope=["创建会话", "持续追问", "导出 PRD"],
            conversation_strategy="converge",
            phase_goal="明确转化阻力集中在哪一环",
            stage_hint="推进转化阻力验证",
            validation_focus="conversion_resistance",
            validation_step=1,
        ),
    )
    db_session.commit()

    def fail_generate_reply(**_kwargs):
        raise AssertionError("conversion resistance follow-up should not call generate_reply")

    monkeypatch.setattr("app.services.messages.generate_reply", fail_generate_reply)

    result = handle_user_message(
        db=db_session,
        session_id=session.id,
        session=session,
        content="大多数人会卡在第一次接入，不知道要准备什么资料",
        model_config_id=model_config.id,
    )

    latest_state = state_repository.get_latest_state(db_session, session.id)

    assert "我先按你的描述把当前阻力判断收成“首要阻力候选已经出现”" in result.reply
    assert latest_state["validation_focus"] == "conversion_resistance"
    assert latest_state["validation_step"] == 2
    assert latest_state["phase_goal"] == "确认首要阻力是否直接打断转化"
    assert latest_state["next_best_questions"] == [
        "为了继续推进，请直接回答一旦卡在这里，用户最常见的结果是放弃、延后，还是转去其他替代方案。"
    ]


def test_handle_user_message_closes_frequency_validation_with_local_verdict_and_confirm_gate(
    db_session,
    monkeypatch,
):
    session = _create_session_with_state(db_session)
    model_config = model_configs_repository.create_model_config(
        db_session,
        name="频率出口模型",
        base_url="https://gateway.example.com/v1",
        api_key="secret",
        model="gpt-4o-mini",
        enabled=True,
    )
    state_repository.create_state_version(
        db=db_session,
        session_id=session.id,
        version=2,
        state_json=_phase1_state(
            target_user="独立创业者",
            problem="不知道先验证哪个需求",
            solution="通过连续追问沉淀结构化 PRD",
            mvp_scope=["创建会话", "持续追问", "导出 PRD"],
            conversation_strategy="converge",
            phase_goal="确认高频问题是否造成真实损失",
            stage_hint="频率影响确认",
            validation_focus="frequency",
            validation_step=2,
            evidence=["频率线索：最近几乎每天都会发生"],
        ),
    )
    db_session.commit()

    def fail_generate_reply(**_kwargs):
        raise AssertionError("frequency verdict should not call generate_reply")

    monkeypatch.setattr("app.services.messages.generate_reply", fail_generate_reply)

    result = handle_user_message(
        db=db_session,
        session_id=session.id,
        session=session,
        content="如果一直这样，团队每周都会多花半天时间，而且经常错过最佳验证窗口",
        model_config_id=model_config.id,
    )

    latest_state = state_repository.get_latest_state(db_session, session.id)

    assert "基于你刚才补的频率和损失，我现在倾向判断这是一个值得优先推进的问题" in result.reply
    assert latest_state["conversation_strategy"] == "confirm"
    assert latest_state["validation_focus"] == "frequency"
    assert latest_state["validation_step"] == 3
    assert latest_state["phase_goal"] == "确认是否把该问题作为当前优先验证对象"
    assert latest_state["pending_confirmations"] == ["是否把这个问题定义为当前最值得优先验证的问题"]


def test_handle_user_message_closes_conversion_resistance_validation_with_local_verdict_and_confirm_gate(
    db_session,
    monkeypatch,
):
    session = _create_session_with_state(db_session)
    model_config = model_configs_repository.create_model_config(
        db_session,
        name="转化阻力出口模型",
        base_url="https://gateway.example.com/v1",
        api_key="secret",
        model="gpt-4o-mini",
        enabled=True,
    )
    state_repository.create_state_version(
        db=db_session,
        session_id=session.id,
        version=2,
        state_json=_phase1_state(
            target_user="独立创业者",
            problem="不知道先验证哪个需求",
            solution="通过连续追问沉淀结构化 PRD",
            mvp_scope=["创建会话", "持续追问", "导出 PRD"],
            conversation_strategy="converge",
            phase_goal="确认首要阻力是否直接打断转化",
            stage_hint="转化阻力影响确认",
            validation_focus="conversion_resistance",
            validation_step=2,
            evidence=["转化阻力线索：大多数人会卡在第一次接入"],
        ),
    )
    db_session.commit()

    def fail_generate_reply(**_kwargs):
        raise AssertionError("conversion resistance verdict should not call generate_reply")

    monkeypatch.setattr("app.services.messages.generate_reply", fail_generate_reply)

    result = handle_user_message(
        db=db_session,
        session_id=session.id,
        session=session,
        content="一旦卡住，大多数人就会先放弃，等以后再说，少数人会直接去找人工替代",
        model_config_id=model_config.id,
    )

    latest_state = state_repository.get_latest_state(db_session, session.id)

    assert "基于你刚才补的阻力和流失结果，我现在倾向判断这是一个值得优先处理的转化阻力" in result.reply
    assert latest_state["conversation_strategy"] == "confirm"
    assert latest_state["validation_focus"] == "conversion_resistance"
    assert latest_state["validation_step"] == 3
    assert latest_state["phase_goal"] == "确认是否把该阻力作为当前优先验证对象"
    assert latest_state["pending_confirmations"] == ["是否把这个阻力定义为当前最值得优先验证的问题"]


def test_handle_user_message_keeps_frequency_validation_step_when_reply_is_too_vague(
    db_session,
    monkeypatch,
):
    session = _create_session_with_state(db_session)
    model_config = model_configs_repository.create_model_config(
        db_session,
        name="频率模糊兜底模型",
        base_url="https://gateway.example.com/v1",
        api_key="secret",
        model="gpt-4o-mini",
        enabled=True,
    )
    state_repository.create_state_version(
        db=db_session,
        session_id=session.id,
        version=2,
        state_json=_phase1_state(
            target_user="独立创业者",
            problem="不知道先验证哪个需求",
            solution="通过连续追问沉淀结构化 PRD",
            mvp_scope=["创建会话", "持续追问", "导出 PRD"],
            conversation_strategy="converge",
            phase_goal="明确问题发生频率是否足够高",
            stage_hint="推进频率验证",
            validation_focus="frequency",
            validation_step=1,
        ),
    )
    db_session.commit()

    def fail_generate_reply(**_kwargs):
        raise AssertionError("vague frequency reply should not call generate_reply")

    monkeypatch.setattr("app.services.messages.generate_reply", fail_generate_reply)

    result = handle_user_message(
        db=db_session,
        session_id=session.id,
        session=session,
        content="差不多吧",
        model_config_id=model_config.id,
    )

    latest_state = state_repository.get_latest_state(db_session, session.id)

    assert "这轮回答还不足以支持我判断频率" in result.reply
    assert latest_state["validation_focus"] == "frequency"
    assert latest_state["validation_step"] == 1
    assert latest_state["phase_goal"] == "明确问题发生频率是否足够高"
    assert latest_state["next_best_questions"] == [
        "为了继续推进，请直接回答这个问题是每天、每周，还是偶发出现，并补一个最近一次真实场景。"
    ]


def test_handle_user_message_keeps_conversion_resistance_validation_step_when_reply_is_too_vague(
    db_session,
    monkeypatch,
):
    session = _create_session_with_state(db_session)
    model_config = model_configs_repository.create_model_config(
        db_session,
        name="转化阻力模糊兜底模型",
        base_url="https://gateway.example.com/v1",
        api_key="secret",
        model="gpt-4o-mini",
        enabled=True,
    )
    state_repository.create_state_version(
        db=db_session,
        session_id=session.id,
        version=2,
        state_json=_phase1_state(
            target_user="独立创业者",
            problem="不知道先验证哪个需求",
            solution="通过连续追问沉淀结构化 PRD",
            mvp_scope=["创建会话", "持续追问", "导出 PRD"],
            conversation_strategy="converge",
            phase_goal="明确转化阻力集中在哪一环",
            stage_hint="推进转化阻力验证",
            validation_focus="conversion_resistance",
            validation_step=1,
        ),
    )
    db_session.commit()

    def fail_generate_reply(**_kwargs):
        raise AssertionError("vague conversion resistance reply should not call generate_reply")

    monkeypatch.setattr("app.services.messages.generate_reply", fail_generate_reply)

    result = handle_user_message(
        db=db_session,
        session_id=session.id,
        session=session,
        content="还行吧",
        model_config_id=model_config.id,
    )

    latest_state = state_repository.get_latest_state(db_session, session.id)

    assert "这轮回答还不足以支持我判断转化阻力" in result.reply
    assert latest_state["validation_focus"] == "conversion_resistance"
    assert latest_state["validation_step"] == 1
    assert latest_state["phase_goal"] == "明确转化阻力集中在哪一环"
    assert latest_state["next_best_questions"] == [
        "为了继续推进，请直接回答用户最容易卡在哪一步，并补一句卡住后通常是放弃、延后，还是转去其他替代方案。"
    ]


def test_handle_user_message_can_switch_from_frequency_to_conversion_resistance_locally(
    db_session,
    monkeypatch,
):
    session = _create_session_with_state(db_session)
    model_config = model_configs_repository.create_model_config(
        db_session,
        name="改道模型",
        base_url="https://gateway.example.com/v1",
        api_key="secret",
        model="gpt-4o-mini",
        enabled=True,
    )
    state_repository.create_state_version(
        db=db_session,
        session_id=session.id,
        version=2,
        state_json=_phase1_state(
            target_user="独立创业者",
            problem="不知道先验证哪个需求",
            solution="通过连续追问沉淀结构化 PRD",
            mvp_scope=["创建会话", "持续追问", "导出 PRD"],
            conversation_strategy="converge",
            phase_goal="确认高频问题是否造成真实损失",
            stage_hint="频率影响确认",
            validation_focus="frequency",
            validation_step=2,
            evidence=["频率线索：最近几乎每天都会发生"],
        ),
    )
    db_session.commit()

    def fail_generate_reply(**_kwargs):
        raise AssertionError("focus switch should not call generate_reply")

    monkeypatch.setattr("app.services.messages.generate_reply", fail_generate_reply)

    result = handle_user_message(
        db=db_session,
        session_id=session.id,
        session=session,
        content="先别看频率，改看转化阻力",
        model_config_id=model_config.id,
    )

    latest_state = state_repository.get_latest_state(db_session, session.id)

    assert "我先停止继续看频率，切到“转化阻力验证”" in result.reply
    assert latest_state["validation_focus"] == "conversion_resistance"
    assert latest_state["validation_step"] == 1
    assert latest_state["phase_goal"] == "明确转化阻力集中在哪一环"
    assert latest_state["stage_hint"] == "推进转化阻力验证"


def test_handle_user_message_rolls_back_user_message_when_generate_reply_fails(db_session, monkeypatch):
    session = _create_session_with_state(db_session)
    model_config = model_configs_repository.create_model_config(
        db_session,
        name="失败模型",
        base_url="https://gateway.example.com/v1",
        api_key="secret",
        model="gpt-4o-mini",
        enabled=True,
    )
    db_session.commit()

    def fake_generate_reply(*, base_url, api_key, model, messages):
        raise ModelGatewayError("上游不可用")

    monkeypatch.setattr("app.services.messages.generate_reply", fake_generate_reply)

    with pytest.raises(HTTPException) as exc_info:
        handle_user_message(
            db=db_session,
            session_id=session.id,
            session=session,
            content="这轮消息必须回滚",
            model_config_id=model_config.id,
        )

    assert exc_info.value.status_code == 502
    assert exc_info.value.detail == "上游不可用"
    assert getattr(exc_info.value, "code", None) == "MODEL_GATEWAY_UNAVAILABLE"
    assert getattr(exc_info.value, "recovery_action", None) == {
        "type": "retry",
        "label": "稍后重试",
        "target": None,
    }
    assert messages_repository.get_messages_for_session(db_session, session.id) == []
    latest_state_version = state_repository.get_latest_state_version(db_session, session.id)
    assert latest_state_version is not None
    assert latest_state_version.version == 1


def test_handle_user_message_rolls_back_turn_decision_when_persist_chain_fails(db_session, monkeypatch):
    session = _create_session_with_state(db_session)
    model_config = model_configs_repository.create_model_config(
        db_session,
        name="回滚模型",
        base_url="https://gateway.example.com/v1",
        api_key="secret",
        model="gpt-4o-mini",
        enabled=True,
    )
    db_session.commit()

    monkeypatch.setattr("app.services.messages.generate_reply", lambda **_: "这次会回滚")
    original_touch = messages_repository.touch_session_activity
    calls = {"count": 0}

    def fail_on_second_touch(db, persisted_session):
        calls["count"] += 1
        if calls["count"] == 2:
            raise RuntimeError("持久化链路失败")
        return original_touch(db, persisted_session)

    monkeypatch.setattr(
        "app.services.messages.messages_repository.touch_session_activity",
        fail_on_second_touch,
    )

    with pytest.raises(RuntimeError, match="持久化链路失败"):
        handle_user_message(
            db=db_session,
            session_id=session.id,
            session=session,
            content="这条消息会触发回滚",
            model_config_id=model_config.id,
        )

    assert messages_repository.get_messages_for_session(db_session, session.id) == []
    decisions = [
        item
        for item in db_session.query(AgentTurnDecision).filter_by(session_id=session.id).all()
    ]
    assert decisions == []


def test_handle_user_message_logs_model_gateway_context(db_session, monkeypatch, caplog):
    session = _create_session_with_state(db_session)
    model_config = model_configs_repository.create_model_config(
        db_session,
        name="失败模型",
        base_url="https://gateway.example.com/v1",
        api_key="secret",
        model="gpt-4o-mini",
        enabled=True,
    )
    db_session.commit()

    def fake_generate_reply(*, base_url, api_key, model, messages):
        raise ModelGatewayError("上游不可用")

    monkeypatch.setattr("app.services.messages.generate_reply", fake_generate_reply)

    with caplog.at_level("WARNING"):
        with pytest.raises(HTTPException):
            handle_user_message(
                db=db_session,
                session_id=session.id,
                session=session,
                content="这轮消息必须记录日志",
                model_config_id=model_config.id,
            )

    assert session.id in caplog.text
    assert model_config.id in caplog.text
    assert "上游不可用" in caplog.text


def test_persist_regenerated_reply_version_surfaces_structured_conflict_errors(db_session, monkeypatch):
    session = _create_session_with_state(db_session)
    model_config = model_configs_repository.create_model_config(
        db_session,
        name="重生成冲突模型",
        base_url="https://gateway.example.com/v1",
        api_key="secret",
        model="gpt-4o-mini",
        enabled=True,
    )
    db_session.commit()

    monkeypatch.setattr("app.services.messages.generate_reply", lambda **_: "初版回复")
    handle_user_message(
        db=db_session,
        session_id=session.id,
        session=session,
        content="请给我一个版本",
        model_config_id=model_config.id,
    )

    persisted_messages = messages_repository.get_messages_for_session(db_session, session.id)
    user_message = next(message for message in persisted_messages if message.role == "user")
    reply_group = assistant_reply_groups_repository.get_reply_group_by_user_message(
        db=db_session,
        user_message_id=user_message.id,
    )
    assert reply_group is not None

    base_kwargs = {
        "db": db_session,
        "session_id": session.id,
        "session": session,
        "user_message_id": user_message.id,
        "reply_group_id": reply_group.id,
        "assistant_version_id": str(uuid4()),
        "version_no": 2,
        "reply": "重生成版本",
        "model_meta": {
            "model_config_id": model_config.id,
            "model_name": model_config.model,
            "display_name": model_config.name,
            "base_url": model_config.base_url,
        },
        "action": {"action": "probe_deeper"},
        "turn_decision": _sample_turn_decision(),
        "state": state_repository.get_latest_state(db_session, session.id),
        "state_patch": {},
        "prd_patch": {},
    }

    db_session.execute(
        ProjectStateVersion.__table__.delete().where(
            ProjectStateVersion.session_id == session.id,
        ),
    )
    db_session.commit()

    with pytest.raises(HTTPException) as exc_info:
        messages_service._persist_regenerated_reply_version(**base_kwargs)

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "State snapshot not found"
    assert getattr(exc_info.value, "code", None) == "STATE_SNAPSHOT_MISSING"
    assert getattr(exc_info.value, "recovery_action", None) == {
        "type": "reload_session",
        "label": "重新加载会话",
        "target": None,
    }


def test_persist_regenerated_reply_version_surfaces_reply_group_mismatch(db_session, monkeypatch):
    session = _create_session_with_state(db_session)
    model_config = model_configs_repository.create_model_config(
        db_session,
        name="重生成冲突模型",
        base_url="https://gateway.example.com/v1",
        api_key="secret",
        model="gpt-4o-mini",
        enabled=True,
    )
    db_session.commit()

    monkeypatch.setattr("app.services.messages.generate_reply", lambda **_: "初版回复")
    handle_user_message(
        db=db_session,
        session_id=session.id,
        session=session,
        content="请给我一个版本",
        model_config_id=model_config.id,
    )

    persisted_messages = messages_repository.get_messages_for_session(db_session, session.id)
    user_message = next(message for message in persisted_messages if message.role == "user")

    with pytest.raises(HTTPException) as exc_info:
        messages_service._persist_regenerated_reply_version(
            db=db_session,
            session_id=session.id,
            session=session,
            user_message_id=user_message.id,
            reply_group_id=str(uuid4()),
            assistant_version_id=str(uuid4()),
                version_no=2,
                reply="重生成版本",
                model_meta={},
                action={"action": "probe_deeper"},
                turn_decision=_sample_turn_decision(),
                state=state_repository.get_latest_state(db_session, session.id),
                state_patch={},
                prd_patch={},
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "Reply group mismatch"
    assert getattr(exc_info.value, "code", None) == "REPLY_GROUP_MISMATCH"
    assert getattr(exc_info.value, "recovery_action", None) == {
        "type": "reload_session",
        "label": "重新加载会话",
        "target": None,
    }


def test_persist_regenerated_reply_version_surfaces_reply_version_sequence_mismatch(
    db_session,
    monkeypatch,
):
    session = _create_session_with_state(db_session)
    model_config = model_configs_repository.create_model_config(
        db_session,
        name="重生成冲突模型",
        base_url="https://gateway.example.com/v1",
        api_key="secret",
        model="gpt-4o-mini",
        enabled=True,
    )
    db_session.commit()

    monkeypatch.setattr("app.services.messages.generate_reply", lambda **_: "初版回复")
    handle_user_message(
        db=db_session,
        session_id=session.id,
        session=session,
        content="请给我一个版本",
        model_config_id=model_config.id,
    )

    persisted_messages = messages_repository.get_messages_for_session(db_session, session.id)
    user_message = next(message for message in persisted_messages if message.role == "user")
    reply_group = assistant_reply_groups_repository.get_reply_group_by_user_message(
        db=db_session,
        user_message_id=user_message.id,
    )
    assert reply_group is not None

    with pytest.raises(HTTPException) as exc_info:
        messages_service._persist_regenerated_reply_version(
            db=db_session,
            session_id=session.id,
            session=session,
            user_message_id=user_message.id,
            reply_group_id=reply_group.id,
            assistant_version_id=str(uuid4()),
                version_no=99,
                reply="重生成版本",
                model_meta={},
                action={"action": "probe_deeper"},
                turn_decision=_sample_turn_decision(),
                state=state_repository.get_latest_state(db_session, session.id),
                state_patch={},
                prd_patch={},
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "Reply version sequence mismatch"
    assert getattr(exc_info.value, "code", None) == "REPLY_VERSION_SEQUENCE_MISMATCH"
    assert getattr(exc_info.value, "recovery_action", None) == {
        "type": "reload_session",
        "label": "重新加载会话",
        "target": None,
    }


def test_stream_user_message_events_yields_multiple_deltas_and_persists_reply(db_session, monkeypatch):
    session = _create_session_with_state(db_session)
    model_config = model_configs_repository.create_model_config(
        db_session,
        name="流式模型",
        base_url="https://gateway.example.com/v1",
        api_key="secret",
        model="gpt-4o-mini",
        enabled=True,
    )
    db_session.commit()

    class FakeReplyStream:
        def __iter__(self):
            yield "先把"
            yield "目标用户"
            yield "讲清楚。"

        def close(self):
            return None

    def fake_open_reply_stream(*, base_url, api_key, model, messages):
        assert base_url == "https://gateway.example.com/v1"
        assert api_key == "secret"
        assert model == "gpt-4o-mini"
        assert messages == [
            {"role": "system", "content": "你是用户的 AI 产品协作助手，请基于上下文给出简洁、直接的中文回复。"},
            {"role": "user", "content": "帮我梳理目标用户"},
        ]
        return FakeReplyStream()

    monkeypatch.setattr("app.services.messages.open_reply_stream", fake_open_reply_stream)

    events = list(
        stream_user_message_events(
            db=db_session,
            session_id=session.id,
            session=session,
            content="帮我梳理目标用户",
            model_config_id=model_config.id,
        )
    )

    assert [event.type for event in events] == [
        "message.accepted",
        "reply_group.created",
        "action.decided",
        "assistant.version.started",
        "assistant.delta",
        "assistant.delta",
        "assistant.delta",
        "prd.updated",
        "assistant.done",
    ]
    accepted_event = next(event for event in events if event.type == "message.accepted")
    group_event = next(event for event in events if event.type == "reply_group.created")
    started_event = next(event for event in events if event.type == "assistant.version.started")
    delta_events = [event for event in events if event.type == "assistant.delta"]
    done_event = next(event for event in events if event.type == "assistant.done")
    prd_updated_event = next(event for event in events if event.type == "prd.updated")

    assert accepted_event.data["message_id"]
    assert group_event.data["reply_group_id"]
    assert group_event.data["user_message_id"] == accepted_event.data["message_id"]
    assert started_event.data["assistant_version_id"]
    assert started_event.data["is_regeneration"] is False
    assert started_event.data["is_latest"] is False
    assert started_event.data["version_no"] == 1
    assert [event.data["delta"] for event in delta_events] == [
        "先把",
        "目标用户",
        "讲清楚。",
    ]
    assert all(event.data["assistant_version_id"] == started_event.data["assistant_version_id"] for event in delta_events)
    assert all(event.data["is_regeneration"] is False for event in delta_events)
    assert all(event.data["is_latest"] is False for event in delta_events)
    assert done_event.data["assistant_version_id"] == started_event.data["assistant_version_id"]
    assert done_event.data["is_regeneration"] is False
    assert done_event.data["is_latest"] is True
    assert prd_updated_event.data["sections"]["target_user"]["content"] == "帮我梳理目标用户"
    assert prd_updated_event.data["meta"]["stageLabel"] == "探索中"
    assert prd_updated_event.data["meta"]["stageTone"] == "draft"
    assert prd_updated_event.data["meta"]["criticSummary"] == "系统正在持续沉淀当前 PRD 草稿。"

    persisted_messages = messages_repository.get_messages_for_session(db_session, session.id)
    assert len(persisted_messages) == 2
    assert persisted_messages[1].content == "先把目标用户讲清楚。"
    reply_group = assistant_reply_groups_repository.get_reply_group_by_user_message(
        db=db_session,
        user_message_id=persisted_messages[0].id,
    )
    assert reply_group is not None
    versions = assistant_reply_versions_repository.list_versions_for_group(
        db=db_session,
        reply_group_id=reply_group.id,
    )
    assert [version.version_no for version in versions] == [1]
    assert versions[0].content == "先把目标用户讲清楚。"
    assert reply_group.latest_version_id == versions[0].id
    latest_state = state_repository.get_latest_state(db_session, session.id)
    latest_prd_snapshot = prd_repository.get_latest_prd_snapshot(db_session, session.id)
    assert latest_state["target_user"] == "帮我梳理目标用户"
    assert latest_state["stage_hint"] == "问题定义"
    assert latest_state["current_phase"]
    assert latest_state["recommended_directions"]
    assert latest_prd_snapshot is not None
    assert latest_prd_snapshot.sections["target_user"]["content"] == "帮我梳理目标用户"


def test_reply_version_writes_do_not_create_new_user_messages(db_session, monkeypatch):
    session = _create_session_with_state(db_session)
    model_config = model_configs_repository.create_model_config(
        db_session,
        name="版本测试模型",
        base_url="https://gateway.example.com/v1",
        api_key="secret",
        model="gpt-4o-mini",
        enabled=True,
    )
    db_session.commit()

    monkeypatch.setattr(
        "app.services.messages.generate_reply",
        lambda **_: "第一版助手回复",
    )

    result = handle_user_message(
        db=db_session,
        session_id=session.id,
        session=session,
        content="请先给我一个初始回复",
        model_config_id=model_config.id,
    )

    persisted_messages = messages_repository.get_messages_for_session(db_session, session.id)
    user_message = next(message for message in persisted_messages if message.role == "user")
    reply_group = assistant_reply_groups_repository.get_reply_group_by_user_message(
        db=db_session,
        user_message_id=user_message.id,
    )
    assert reply_group is not None
    version_1 = assistant_reply_versions_repository.get_latest_version_for_group(
        db=db_session,
        reply_group_id=reply_group.id,
    )
    assert version_1 is not None
    assert version_1.version_no == 1

    version_2 = assistant_reply_versions_repository.create_reply_version(
        db=db_session,
        reply_group_id=reply_group.id,
        session_id=session.id,
        user_message_id=user_message.id,
        version_no=2,
        content="第二版助手回复",
        action_snapshot={"action": "probe_deeper"},
        model_meta={"model_config_id": model_config.id},
        state_version_id=None,
        prd_snapshot_version=None,
    )
    assistant_reply_groups_repository.set_latest_version(
        db=db_session,
        reply_group=reply_group,
        latest_version_id=version_2.id,
    )
    db_session.commit()

    refreshed_group = assistant_reply_groups_repository.get_reply_group_by_user_message(
        db=db_session,
        user_message_id=user_message.id,
    )
    versions = assistant_reply_versions_repository.list_versions_for_group(
        db=db_session,
        reply_group_id=reply_group.id,
    )
    latest_version = assistant_reply_versions_repository.get_latest_version_for_group(
        db=db_session,
        reply_group_id=reply_group.id,
    )
    persisted_messages_after_version_append = messages_repository.get_messages_for_session(
        db_session,
        session.id,
    )
    user_messages_after_version_append = [
        message for message in persisted_messages_after_version_append if message.role == "user"
    ]

    assert result.user_message_id == user_message.id
    assert refreshed_group is not None
    assert refreshed_group.latest_version_id == version_2.id
    assert [version.version_no for version in versions] == [1, 2]
    assert latest_version is not None
    assert latest_version.id == version_2.id
    assert all(version.user_message_id == user_message.id for version in versions)
    assert all(version.reply_group_id == reply_group.id for version in versions)
    assert len(user_messages_after_version_append) == 1


def test_create_reply_group_rejects_user_message_from_other_session(db_session, monkeypatch):
    primary_session = _create_session_with_state(db_session)
    secondary_session = _create_session_with_state(db_session)
    model_config = model_configs_repository.create_model_config(
        db_session,
        name="group 一致性测试模型",
        base_url="https://gateway.example.com/v1",
        api_key="secret",
        model="gpt-4o-mini",
        enabled=True,
    )
    db_session.commit()

    monkeypatch.setattr(
        "app.services.messages.generate_reply",
        lambda **_: "group 一致性测试回复",
    )

    handle_user_message(
        db=db_session,
        session_id=primary_session.id,
        session=primary_session,
        content="primary",
        model_config_id=model_config.id,
    )
    handle_user_message(
        db=db_session,
        session_id=secondary_session.id,
        session=secondary_session,
        content="secondary",
        model_config_id=model_config.id,
    )

    secondary_messages = messages_repository.get_messages_for_session(db_session, secondary_session.id)
    secondary_user_message = next(message for message in secondary_messages if message.role == "user")

    with pytest.raises(ValueError, match="does not belong to session"):
        assistant_reply_groups_repository.create_reply_group(
            db=db_session,
            session_id=primary_session.id,
            user_message_id=secondary_user_message.id,
        )


def test_create_turn_decision_rejects_user_message_from_other_session(db_session):
    primary_session = _create_session_with_state(db_session)
    secondary_session = _create_session_with_state(db_session)

    secondary_user_message = messages_repository.create_message(
        db=db_session,
        session_id=secondary_session.id,
        role="user",
        content="secondary",
    )
    db_session.commit()

    with pytest.raises(ValueError, match="does not belong to session"):
        agent_turn_decisions_repository.create_turn_decision(
            db=db_session,
            session_id=primary_session.id,
            user_message_id=secondary_user_message.id,
            turn_decision=_sample_turn_decision(),
        )


def test_create_turn_decision_rejects_non_user_message(db_session):
    session = _create_session_with_state(db_session)
    assistant_message = messages_repository.create_message(
        db=db_session,
        session_id=session.id,
        role="assistant",
        content="assistant",
    )
    db_session.commit()

    with pytest.raises(ValueError, match="must have user role"):
        agent_turn_decisions_repository.create_turn_decision(
            db=db_session,
            session_id=session.id,
            user_message_id=assistant_message.id,
            turn_decision=_sample_turn_decision(),
        )


def test_create_reply_version_rejects_group_session_or_user_message_mismatch(db_session, monkeypatch):
    primary_session = _create_session_with_state(db_session)
    secondary_session = _create_session_with_state(db_session)
    model_config = model_configs_repository.create_model_config(
        db_session,
        name="一致性测试模型",
        base_url="https://gateway.example.com/v1",
        api_key="secret",
        model="gpt-4o-mini",
        enabled=True,
    )
    db_session.commit()

    monkeypatch.setattr(
        "app.services.messages.generate_reply",
        lambda **_: "一致性测试回复",
    )

    handle_user_message(
        db=db_session,
        session_id=primary_session.id,
        session=primary_session,
        content="primary",
        model_config_id=model_config.id,
    )
    handle_user_message(
        db=db_session,
        session_id=secondary_session.id,
        session=secondary_session,
        content="secondary",
        model_config_id=model_config.id,
    )

    primary_messages = messages_repository.get_messages_for_session(db_session, primary_session.id)
    secondary_messages = messages_repository.get_messages_for_session(db_session, secondary_session.id)
    primary_user_message = next(message for message in primary_messages if message.role == "user")
    secondary_user_message = next(message for message in secondary_messages if message.role == "user")

    primary_group = assistant_reply_groups_repository.get_reply_group_by_user_message(
        db=db_session,
        user_message_id=primary_user_message.id,
    )
    assert primary_group is not None

    with pytest.raises(ValueError, match="session_id does not match"):
        assistant_reply_versions_repository.create_reply_version(
            db=db_session,
            reply_group_id=primary_group.id,
            session_id=secondary_session.id,
            user_message_id=primary_user_message.id,
            version_no=1,
            content="不合法版本",
            action_snapshot={},
            model_meta={},
            state_version_id=None,
            prd_snapshot_version=None,
        )

    with pytest.raises(ValueError, match="user_message_id does not match"):
        assistant_reply_versions_repository.create_reply_version(
            db=db_session,
            reply_group_id=primary_group.id,
            session_id=primary_session.id,
            user_message_id=secondary_user_message.id,
            version_no=1,
            content="不合法版本",
            action_snapshot={},
            model_meta={},
            state_version_id=None,
            prd_snapshot_version=None,
        )


def test_stream_regenerate_message_events_appends_version_without_new_user_message(db_session, monkeypatch):
    session = _create_session_with_state(db_session)
    model_config = model_configs_repository.create_model_config(
        db_session,
        name="重生成模型",
        base_url="https://gateway.example.com/v1",
        api_key="secret",
        model="gpt-4o-mini",
        enabled=True,
    )
    db_session.commit()

    monkeypatch.setattr("app.services.messages.generate_reply", lambda **_: "初版回复")
    handle_user_message(
        db=db_session,
        session_id=session.id,
        session=session,
        content="请给我一个版本",
        model_config_id=model_config.id,
    )

    persisted_messages = messages_repository.get_messages_for_session(db_session, session.id)
    user_message = next(message for message in persisted_messages if message.role == "user")
    assistant_message = next(message for message in persisted_messages if message.role == "assistant")
    existing_group = assistant_reply_groups_repository.get_reply_group_by_user_message(
        db=db_session,
        user_message_id=user_message.id,
    )
    assert existing_group is not None
    existing_versions = assistant_reply_versions_repository.list_versions_for_group(
        db=db_session,
        reply_group_id=existing_group.id,
    )
    assert [version.version_no for version in existing_versions] == [1]
    version_1 = existing_versions[0]

    class FakeReplyStream:
        def __iter__(self):
            yield "这是"
            yield "重生成"
            yield "版本"

        def close(self):
            return None

    captured = {}

    def fake_open_reply_stream(*, base_url, api_key, model, messages):
        captured["messages"] = messages
        return FakeReplyStream()

    monkeypatch.setattr("app.services.messages.open_reply_stream", fake_open_reply_stream)
    monkeypatch.setattr(
        "app.services.messages.run_agent",
        lambda state, user_input: SimpleNamespace(
            action=NextAction(
                action="summarize_understanding",
                target=None,
                reason="重生成后同步更新 PRD 预览。",
            ),
            turn_decision=_sample_turn_decision(),
            state_patch={
                "workflow_stage": "refine_loop",
                "prd_draft": {
                    "version": 2,
                    "status": "draft_refined",
                    "sections": {
                        "solution": {
                            "title": "解决方案",
                            "content": "重生成后采用浏览器预览加评论分享。",
                            "status": "confirmed",
                        },
                        "constraints": {
                            "title": "约束条件",
                            "content": "首版只支持浏览器端。",
                            "status": "confirmed",
                        },
                    },
                },
            },
            prd_patch={
                "solution": {
                    "title": "解决方案",
                    "content": "重生成后采用浏览器预览加评论分享。",
                    "status": "confirmed",
                },
                "constraints": {
                    "title": "约束条件",
                    "content": "首版只支持浏览器端。",
                    "status": "confirmed",
                },
            },
        ),
    )

    events = list(
        stream_regenerate_message_events(
            db=db_session,
            session_id=session.id,
            session=session,
            user_message_id=user_message.id,
            model_config_id=model_config.id,
        )
    )

    assert [event.type for event in events] == [
        "action.decided",
        "assistant.version.started",
        "assistant.delta",
        "assistant.delta",
        "assistant.delta",
        "prd.updated",
        "assistant.done",
    ]
    started_event = next(event for event in events if event.type == "assistant.version.started")
    done_event = next(event for event in events if event.type == "assistant.done")
    prd_updated_event = next(event for event in events if event.type == "prd.updated")
    assert started_event.data["session_id"] == session.id
    assert started_event.data["user_message_id"] == user_message.id
    assert started_event.data["version_no"] == 2
    assert started_event.data["reply_group_id"] == existing_group.id
    assert started_event.data["assistant_version_id"]
    assert started_event.data["is_regeneration"] is True
    assert started_event.data["is_latest"] is False
    assert [event.data["delta"] for event in events if event.type == "assistant.delta"] == [
        "这是",
        "重生成",
        "版本",
    ]
    assert all(event.data["assistant_version_id"] == started_event.data["assistant_version_id"] for event in events if event.type == "assistant.delta")
    assert all(event.data["is_regeneration"] is True for event in events if event.type == "assistant.delta")
    assert all(event.data["is_latest"] is False for event in events if event.type == "assistant.delta")
    assert done_event.data["session_id"] == session.id
    assert done_event.data["user_message_id"] == user_message.id
    assert done_event.data["version_no"] == 2
    assert done_event.data["reply_group_id"] == existing_group.id
    assert done_event.data["assistant_message_id"] == assistant_message.id
    assert done_event.data["version_id"]
    assert done_event.data["assistant_version_id"] == started_event.data["assistant_version_id"]
    assert done_event.data["is_regeneration"] is True
    assert done_event.data["is_latest"] is True
    assert prd_updated_event.data["sections"]["solution"]["content"] == "重生成后采用浏览器预览加评论分享。"
    assert prd_updated_event.data["sections"]["constraints"]["content"] == "首版只支持浏览器端。"
    assert captured["messages"] == [
        {"role": "system", "content": "你是用户的 AI 产品协作助手，请基于上下文给出简洁、直接的中文回复。"},
        {"role": "user", "content": "请给我一个版本"},
    ]

    refreshed_group = assistant_reply_groups_repository.get_reply_group_by_user_message(
        db=db_session,
        user_message_id=user_message.id,
    )
    versions = assistant_reply_versions_repository.list_versions_for_group(
        db=db_session,
        reply_group_id=existing_group.id,
    )
    latest_version = assistant_reply_versions_repository.get_latest_version_for_group(
        db=db_session,
        reply_group_id=existing_group.id,
    )
    latest_state_version = state_repository.get_latest_state_version(db_session, session.id)
    latest_messages = messages_repository.get_messages_for_session(db_session, session.id)
    user_messages = [message for message in latest_messages if message.role == "user"]
    assistant_messages = [message for message in latest_messages if message.role == "assistant"]

    assert refreshed_group is not None
    assert refreshed_group.latest_version_id != version_1.id
    assert [version.version_no for version in versions] == [1, 2]
    assert latest_version is not None
    assert latest_version.content == "这是重生成版本"
    assert latest_version.state_version_id is not None
    assert latest_version.state_version_id != version_1.state_version_id
    assert latest_version.prd_snapshot_version != version_1.prd_snapshot_version
    assert latest_state_version is not None
    assert latest_state_version.version == 3
    assert latest_state_version.state_json["workflow_stage"] == "refine_loop"
    assert latest_state_version.state_json["prd_snapshot"]["sections"]["solution"]["content"] == "重生成后采用浏览器预览加评论分享。"
    latest_prd_snapshot = prd_repository.get_latest_prd_snapshot(db_session, session.id)
    assert latest_prd_snapshot is not None
    assert latest_prd_snapshot.version == 3
    assert latest_prd_snapshot.sections["constraints"]["content"] == "首版只支持浏览器端。"
    assert len(user_messages) == 1
    assert len(assistant_messages) == 1
    assert assistant_messages[0].id == assistant_message.id
    assert assistant_messages[0].content == "这是重生成版本"


def test_stream_regenerate_message_events_keeps_latest_version_when_stream_fails(db_session, monkeypatch):
    session = _create_session_with_state(db_session)
    model_config = model_configs_repository.create_model_config(
        db_session,
        name="重生成失败模型",
        base_url="https://gateway.example.com/v1",
        api_key="secret",
        model="gpt-4o-mini",
        enabled=True,
    )
    db_session.commit()

    monkeypatch.setattr("app.services.messages.generate_reply", lambda **_: "初版回复")
    handle_user_message(
        db=db_session,
        session_id=session.id,
        session=session,
        content="请给我一个版本",
        model_config_id=model_config.id,
    )

    persisted_messages = messages_repository.get_messages_for_session(db_session, session.id)
    user_message = next(message for message in persisted_messages if message.role == "user")
    assistant_message = next(message for message in persisted_messages if message.role == "assistant")
    reply_group = assistant_reply_groups_repository.get_reply_group_by_user_message(
        db=db_session,
        user_message_id=user_message.id,
    )
    assert reply_group is not None
    versions_before = assistant_reply_versions_repository.list_versions_for_group(
        db=db_session,
        reply_group_id=reply_group.id,
    )
    assert [version.version_no for version in versions_before] == [1]
    version_1 = versions_before[0]

    class BrokenReplyStream:
        def __iter__(self):
            yield "这是"
            raise ModelGatewayError("流式中断")

        def close(self):
            return None

    monkeypatch.setattr("app.services.messages.open_reply_stream", lambda **_: BrokenReplyStream())

    events = list(
        stream_regenerate_message_events(
            db=db_session,
            session_id=session.id,
            session=session,
            user_message_id=user_message.id,
            model_config_id=model_config.id,
        )
    )

    assert [event.type for event in events] == [
        "action.decided",
        "assistant.version.started",
        "assistant.delta",
    ]
    started_event = next(event for event in events if event.type == "assistant.version.started")
    delta_event = next(event for event in events if event.type == "assistant.delta")
    assert started_event.data["assistant_version_id"]
    assert started_event.data["is_regeneration"] is True
    assert started_event.data["is_latest"] is False
    assert delta_event.data["assistant_version_id"] == started_event.data["assistant_version_id"]
    assert delta_event.data["is_regeneration"] is True
    assert delta_event.data["is_latest"] is False

    refreshed_group = assistant_reply_groups_repository.get_reply_group_by_user_message(
        db=db_session,
        user_message_id=user_message.id,
    )
    versions = assistant_reply_versions_repository.list_versions_for_group(
        db=db_session,
        reply_group_id=reply_group.id,
    )
    latest_state_version = state_repository.get_latest_state_version(db_session, session.id)

    assert refreshed_group is not None
    assert refreshed_group.latest_version_id == version_1.id
    assert [version.version_no for version in versions] == [1]
    assert latest_state_version is not None
    assert latest_state_version.version == 2
    latest_messages = messages_repository.get_messages_for_session(db_session, session.id)
    assistant_messages = [message for message in latest_messages if message.role == "assistant"]
    assert len(assistant_messages) == 1
    assert assistant_messages[0].id == assistant_message.id
    assert assistant_messages[0].content == "初版回复"

def test_get_latest_version_for_group_uses_group_latest_pointer(db_session, monkeypatch):
    session = _create_session_with_state(db_session)
    model_config = model_configs_repository.create_model_config(
        db_session,
        name="latest 语义模型",
        base_url="https://gateway.example.com/v1",
        api_key="secret",
        model="gpt-4o-mini",
        enabled=True,
    )
    db_session.commit()

    monkeypatch.setattr(
        "app.services.messages.generate_reply",
        lambda **_: "latest 语义测试回复",
    )
    handle_user_message(
        db=db_session,
        session_id=session.id,
        session=session,
        content="latest",
        model_config_id=model_config.id,
    )

    persisted_messages = messages_repository.get_messages_for_session(db_session, session.id)
    user_message = next(message for message in persisted_messages if message.role == "user")
    reply_group = assistant_reply_groups_repository.get_reply_group_by_user_message(
        db=db_session,
        user_message_id=user_message.id,
    )
    assert reply_group is not None
    version_1 = assistant_reply_versions_repository.get_latest_version_for_group(
        db=db_session,
        reply_group_id=reply_group.id,
    )
    assert version_1 is not None
    assert version_1.version_no == 1
    version_2 = assistant_reply_versions_repository.create_reply_version(
        db=db_session,
        reply_group_id=reply_group.id,
        session_id=session.id,
        user_message_id=user_message.id,
        version_no=2,
        content="候选但非 latest",
        action_snapshot={"action": "probe_deeper"},
        model_meta={"model_config_id": model_config.id},
        state_version_id=None,
        prd_snapshot_version=None,
    )
    assistant_reply_groups_repository.set_latest_version(
        db=db_session,
        reply_group=reply_group,
        latest_version_id=version_1.id,
    )
    db_session.commit()

    latest_version = assistant_reply_versions_repository.get_latest_version_for_group(
        db=db_session,
        reply_group_id=reply_group.id,
    )

    assert latest_version is not None
    assert latest_version.id == version_1.id
    assert latest_version.id != version_2.id


def test_handle_user_message_persists_completed_stage_after_finalize(db_session, monkeypatch):
    session = _create_session_with_state(db_session)
    model_config = model_configs_repository.create_model_config(
        db_session,
        name="finalize 持久化模型",
        base_url="https://gateway.example.com/v1",
        api_key="secret",
        model="gpt-4o-mini",
        enabled=True,
    )
    state_repository.create_state_version(
        db=db_session,
        session_id=session.id,
        version=2,
        state_json={
            **_phase1_state(),
            "workflow_stage": "finalize",
            "prd_draft": {
                "version": 2,
                "status": "draft_refined",
                "sections": {
                    "summary": {"title": "一句话概述", "content": "AI PRD 助手", "status": "confirmed"},
                    "target_user": {"title": "目标用户", "content": "独立开发者", "status": "confirmed"},
                    "problem": {"title": "核心问题", "content": "需求难收敛", "status": "confirmed"},
                    "solution": {"title": "解决方案", "content": "对话生成 PRD", "status": "confirmed"},
                    "mvp_scope": {"title": "MVP 范围", "content": "追问、沉淀、导出", "status": "confirmed"},
                },
                "assumptions": [],
                "missing_information": [],
                "critic_ready": True,
            },
            "critic_result": {
                "overall_verdict": "pass",
                "question_queue": [],
                "major_gaps": [],
            },
            "finalization_ready": True,
        },
    )
    db_session.commit()

    def fail_generate_reply(**_kwargs):
        raise AssertionError("finalize local reply should not call generate_reply")

    monkeypatch.setattr("app.services.messages.generate_reply", fail_generate_reply)

    result = handle_user_message(
        db=db_session,
        session_id=session.id,
        session=session,
        content="确认设计，按业务版输出",
        model_config_id=model_config.id,
    )

    latest_state = state_repository.get_latest_state(db_session, session.id)
    decision = db_session.execute(
        select(AgentTurnDecision).where(AgentTurnDecision.user_message_id == result.user_message_id)
    ).scalar_one()

    assert latest_state["workflow_stage"] == "completed"
    assert latest_state["prd_draft"]["status"] == "finalized"
    assert latest_state["prd_draft"]["finalize_preferences"] == "business"
    assert decision.state_patch_json["workflow_stage"] == "completed"


def test_handle_user_message_persists_snapshot_from_finalized_sections(db_session, monkeypatch):
    session = _create_session_with_state(db_session)
    model_config = model_configs_repository.create_model_config(
        db_session,
        name="snapshot 派生模型",
        base_url="https://gateway.example.com/v1",
        api_key="secret",
        model="gpt-4o-mini",
        enabled=True,
    )
    state_repository.create_state_version(
        db=db_session,
        session_id=session.id,
        version=2,
        state_json={
            **_phase1_state(),
            "workflow_stage": "finalize",
            "prd_draft": {
                "version": 2,
                "status": "draft_refined",
                "sections": {
                    "target_user": {"title": "目标用户", "content": "独立开发者", "status": "confirmed"},
                    "problem": {"title": "核心问题", "content": "需求难收敛", "status": "confirmed"},
                    "solution": {"title": "解决方案", "content": "AI 辅助沉淀 PRD", "status": "confirmed"},
                    "mvp_scope": {"title": "MVP 范围", "content": "创建会话、追问、导出", "status": "confirmed"},
                    "refine_notes": {"title": "补充记录", "content": "- 内部备注", "status": "draft"},
                },
                "assumptions": [],
                "missing_information": [],
                "critic_ready": True,
            },
            "critic_result": {
                "overall_verdict": "pass",
                "question_queue": [],
                "major_gaps": [],
            },
            "finalization_ready": True,
        },
    )
    db_session.commit()

    monkeypatch.setattr("app.services.messages.generate_reply", lambda **_: "ignore")

    handle_user_message(
        db=db_session,
        session_id=session.id,
        session=session,
        content="确认设计",
        model_config_id=model_config.id,
    )

    latest_prd_snapshot = prd_repository.get_latest_prd_snapshot(db_session, session.id)

    assert latest_prd_snapshot is not None
    assert latest_prd_snapshot.sections["target_user"]["content"] == "独立开发者"
    assert "refine_notes" not in latest_prd_snapshot.sections
