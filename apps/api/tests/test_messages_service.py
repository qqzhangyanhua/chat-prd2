from pathlib import Path
from types import SimpleNamespace
import json
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.agent.types import NextAction, Suggestion, TurnDecision
from app.db.models import AssistantReplyVersion
from app.db.models import AgentTurnDecision, ProjectStateVersion, User
from app.repositories import agent_turn_decisions as agent_turn_decisions_repository
from app.repositories import assistant_reply_groups as assistant_reply_groups_repository
from app.repositories import assistant_reply_versions as assistant_reply_versions_repository
from app.repositories import messages as messages_repository
from app.repositories import model_configs as model_configs_repository
from app.repositories import prd as prd_repository
from app.repositories import sessions as sessions_repository
from app.repositories import state as state_repository
import app.services.messages as messages_service
from app.services import sessions as sessions_service
from app.services.messages import apply_prd_patch, apply_state_patch, handle_user_message
from app.services.messages import stream_regenerate_message_events
from app.services.model_gateway import ModelGatewayError

PRD_META_CONTRACT_CASES = json.loads(
    Path(__file__).resolve().parents[3].joinpath("docs/contracts/prd-meta-cases.json").read_text(encoding="utf-8")
)


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
        phase="problem",
        phase_goal="你的目标用户是谁？",
        understanding={
            "summary": "用户给了一个模糊方向",
            "candidate_updates": {},
            "ambiguous_points": [],
        },
        assumptions=[],
        gaps=["缺少明确的目标用户"],
        challenges=["目标用户范围过泛，需优先收敛"],
        pm_risk_flags=["user_too_broad"],
        next_move="probe_for_specificity",
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
        reply_brief={"focus": "problem", "must_include": []},
        state_patch={},
        prd_patch={},
        needs_confirmation=[],
        confidence="medium",
        next_best_questions=["你的目标用户是谁？"],
        strategy_reason="先聚焦一个更具体的用户角色。",
        conversation_strategy="clarify",
    )


def _sample_turn_decision_with_four_suggestions() -> TurnDecision:
    return TurnDecision(
        phase="problem",
        phase_goal="先锁定一个最具体的真实用户场景",
        understanding={
            "summary": "当前方向仍然偏宽，需要先选一个落地切口。",
            "candidate_updates": {},
            "ambiguous_points": [],
        },
        assumptions=[],
        gaps=["尚未锁定首个高价值用户场景"],
        challenges=["如果不先收敛场景，后续 PRD 会持续发散"],
        pm_risk_flags=["user_too_broad"],
        next_move="force_rank_or_choose",
        suggestions=[
            Suggestion(
                type="direction",
                label="A. 先聊独立开发者",
                content="我先从独立开发者的真实使用场景开始补充。",
                rationale="更容易快速拿到高频反馈。",
                priority=1,
            ),
            Suggestion(
                type="tradeoff",
                label="B. 先聊小团队负责人",
                content="我更想先看 3-10 人团队的协作问题。",
                rationale="协作链路更完整，但场景更复杂。",
                priority=2,
            ),
            Suggestion(
                type="recommendation",
                label="C. 先锁定高频痛点",
                content="先别分人群，先确定一个最高频的问题。",
                rationale="可以直接筛掉低价值需求。",
                priority=3,
            ),
            Suggestion(
                type="warning",
                label="D. 我直接补充真实案例",
                content="我直接讲一个最近遇到的具体案例。",
                rationale="真实案例能最快暴露需求真假。",
                priority=4,
            ),
        ],
        recommendation={"label": "A. 先聊独立开发者"},
        reply_brief={"focus": "problem", "must_include": []},
        state_patch={"stage_hint": "problem"},
        prd_patch={},
        needs_confirmation=[],
        confidence="medium",
        next_best_questions=[
            "如果只能先选一个，你更想先讲独立开发者还是小团队负责人？",
            "这个问题最近一次发生在什么场景？",
            "你现在最想优先验证用户、问题还是方案？",
            "如果你愿意，也可以直接讲一个真实案例。",
        ],
        strategy_reason="先锁定首个具体场景，再决定后续推进主线。",
        conversation_strategy="choose",
    )


def _fake_pm_mentor_llm_response(**overrides) -> dict:
    payload = {
        "observation": "你已经开始缩小问题空间了。",
        "challenge": "现在最大的风险是目标用户还不够具体。",
        "suggestion": "先聚焦一个最具体的目标用户，再继续推进。",
        "question": "你的目标用户是谁？",
        "reply": "我注意到你已经开始缩小问题空间了。现在最大的风险是目标用户还不够具体。先聚焦一个最具体的目标用户，再继续推进。你的目标用户是谁？",
        "prd_updates": {},
        "confidence": "medium",
        "next_focus": "problem",
    }
    payload.update(overrides)
    return payload


def _patch_pm_mentor(monkeypatch, **overrides) -> None:
    monkeypatch.setattr(
        "app.agent.pm_mentor.call_pm_mentor_llm",
        lambda **_: _fake_pm_mentor_llm_response(**overrides),
    )


def _fake_gateway_agent_result(**overrides):
    payload = {
        "reply": "",
        "action": NextAction(action="probe_deeper", target=None, reason="test"),
        "reply_mode": "gateway",
        "turn_decision": _sample_turn_decision(),
        "state_patch": {},
        "prd_patch": {},
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


def _create_initial_reply(db_session, monkeypatch, session, model_config, *, reply: str = "初版回复"):
    _patch_pm_mentor(monkeypatch, reply=reply)
    return handle_user_message(
        db=db_session,
        session_id=session.id,
        session=session,
        content="请给我一个版本",
        model_config_id=model_config.id,
    )




def test_sample_turn_decision_suggestions_can_be_serialized_for_snapshot_meta():
    normalized = sessions_service._normalize_suggestion_options(
        [
            {
                "label": "独立开发者",
                "content": "先聚焦独立开发者",
                "rationale": "反馈链路更短",
                "priority": 1,
                "type": "direction",
            },
            {"label": "bad"},
        ]
    )

    assert normalized == [
        {
            "label": "独立开发者",
            "content": "先聚焦独立开发者",
            "rationale": "反馈链路更短",
            "priority": 1,
            "type": "direction",
        }
    ]


def test_apply_state_patch_merges_keys():
    state = {"idea": "test", "target_user": None, "problem": None}
    result = apply_state_patch(state, {"target_user": "developers", "problem": "too slow"})
    assert result == {"idea": "test", "target_user": "developers", "problem": "too slow"}


def test_apply_prd_patch_handles_empty_and_merges_sections():
    state = {"prd_snapshot": {"sections": {"target_user": {"content": "old"}}}}
    assert apply_prd_patch(state, {}) is state
    result = apply_prd_patch(state, {"problem": {"content": "new problem"}})
    assert result["prd_snapshot"]["sections"]["target_user"]["content"] == "old"
    assert result["prd_snapshot"]["sections"]["problem"]["content"] == "new problem"
    overwritten = apply_prd_patch(state, {"target_user": {"content": "updated"}})
    assert overwritten["prd_snapshot"]["sections"]["target_user"]["content"] == "updated"


def test_preview_prd_meta_matches_shared_contract():
    for contract_case in PRD_META_CONTRACT_CASES:
        assert messages_service._preview_prd_meta({}, contract_case["state"]) == contract_case["expected"]


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
    assert getattr(exc_info.value, "details", None) == {
        "available_model_configs": [
            {"id": fallback_model.id, "name": "推荐模型", "model": "gpt-4o-mini"},
            {"id": reasoning_model.id, "name": "长文本模型", "model": "claude-3-7-sonnet"},
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
    assert getattr(exc_info.value, "details", None) == {
        "available_model_configs": [
            {"id": fallback_model.id, "name": "推荐模型", "model": "claude-3-7-sonnet"},
            {"id": general_model.id, "name": "通用模型", "model": "gpt-4o-mini"},
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
    disabled_model = model_configs_repository.create_model_config(
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
            model_config_id=disabled_model.id,
        )

    details = getattr(exc_info.value, "details", None)
    assert details is not None
    assert details["recommended_model_config_id"] == same_scene_model.id
    assert details["recommended_model_scene"] == "reasoning"
    assert details["recommended_model_name"] == "长文本候选模型"


def test_handle_user_message_persists_local_pm_mentor_reply_metadata_and_state(db_session, monkeypatch):
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
    _patch_pm_mentor(
        monkeypatch,
        suggestion="先聚焦一个更具体的用户角色。",
        question="你的目标用户是谁？",
        next_focus="problem",
        reply="先别急着谈方案，先把目标用户讲清楚。",
        prd_updates={
            "target_user": {
                "title": "目标用户",
                "content": "独立开发者",
                "status": "draft",
            }
        },
    )

    result = handle_user_message(
        db=db_session,
        session_id=session.id,
        session=session,
        content="我们想服务独立开发者",
        model_config_id=model_config.id,
    )

    assert result.reply == "先别急着谈方案，先把目标用户讲清楚。"
    persisted_messages = messages_repository.get_messages_for_session(db_session, session.id)
    user_message = next(message for message in persisted_messages if message.role == "user")
    assistant_message = next(message for message in persisted_messages if message.role == "assistant")
    latest_state = state_repository.get_latest_state(db_session, session.id)
    latest_prd_snapshot = prd_repository.get_latest_prd_snapshot(db_session, session.id)
    decision = db_session.execute(
        select(AgentTurnDecision).where(AgentTurnDecision.user_message_id == result.user_message_id)
    ).scalar_one()

    assert user_message.meta == {
        "model_config_id": model_config.id,
        "model_name": "claude-3-7-sonnet",
        "display_name": "深度推理模型",
        "base_url": "https://gateway.example.com/v1",
    }
    assert assistant_message.content == "先别急着谈方案，先把目标用户讲清楚。"
    assert assistant_message.meta["action"]["action"] == "probe_deeper"
    assert assistant_message.meta["model_config_id"] == model_config.id
    assert latest_state["iteration"] == 1
    assert latest_state["stage_hint"] == "problem"
    assert latest_state["current_phase"] == "problem"
    assert latest_state["conversation_strategy"] == "clarify"
    assert latest_state["strategy_reason"] == "先聚焦一个更具体的用户角色。"
    assert latest_state["phase_goal"] == "你的目标用户是谁？"
    assert len(latest_state["next_best_questions"]) == 4
    assert "我想先明确，这个产品主要给谁用。" in latest_state["next_best_questions"]
    assert latest_state["current_model_scene"] == "reasoning"
    assert latest_state["collaboration_mode_label"] == "深度推演模式"
    assert latest_prd_snapshot is not None
    assert latest_prd_snapshot.sections["target_user"]["content"] == "独立开发者"
    assert decision.user_message_id == result.user_message_id
    assert decision.phase == "problem"
    assert decision.understanding_summary == "你已经开始缩小问题空间了。"
    assert decision.next_move == "probe_for_specificity"
    assert decision.confidence == "medium"
    assert decision.state_patch_json["stage_hint"] == "problem"


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
        current_state={"prd_snapshot": {"sections": {}}},
    )

    assert merged["workflow_stage"] == "finalize"
    assert merged["idea_parse_result"]["idea_summary"] == "在线 3D 图纸预览平台"
    assert merged["prd_draft"]["version"] == 2
    assert merged["critic_result"]["overall_verdict"] == "pass"
    assert merged["refine_history"] == [{"question": "Q1", "answer": "A1"}]
    assert merged["finalization_ready"] is True
    assert merged["current_phase"] == "refine_loop"
    assert merged["next_best_questions"] == ["下一问"]

def test_handle_user_message_persists_structured_suggestions_and_next_best_questions(db_session, monkeypatch):
    session = _create_session_with_state(db_session)
    model_config = model_configs_repository.create_model_config(
        db_session,
        name="结构化建议模型",
        recommended_scene="general",
        recommended_usage="适合验证结构化透传。",
        base_url="https://gateway.example.com/v1",
        api_key="secret",
        model="gpt-4o-mini",
        enabled=True,
    )
    db_session.commit()
    turn_decision = _sample_turn_decision_with_four_suggestions()
    monkeypatch.setattr(
        "app.services.messages.run_agent",
        lambda state, user_input, **_: SimpleNamespace(
            reply="请先从四个方向里选一个最接近你的真实情况。",
            action=NextAction(action="probe_deeper", target="target_user", reason="test"),
            reply_mode="local",
            turn_decision=turn_decision,
            state_patch={},
            prd_patch={},
        ),
    )

    result = handle_user_message(
        db=db_session,
        session_id=session.id,
        session=session,
        content="我想先明确该跟谁聊",
        model_config_id=model_config.id,
    )

    decision = db_session.execute(
        select(AgentTurnDecision).where(AgentTurnDecision.user_message_id == result.user_message_id)
    ).scalar_one()
    latest_state = state_repository.get_latest_state(db_session, session.id)

    assert [item["label"] for item in decision.suggestions_json] == [
        "A. 先聊独立开发者",
        "B. 先聊小团队负责人",
        "C. 先锁定高频痛点",
        "D. 我直接补充真实案例",
    ]
    assert decision.suggestions_json[0]["content"] == "我先从独立开发者的真实使用场景开始补充。"
    assert len(decision.suggestions_json) == 4
    assert latest_state["next_best_questions"] == turn_decision.next_best_questions
    assert len(latest_state["next_best_questions"]) == 4

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
        current_state={"prd_snapshot": {"sections": {}}},
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
        current_state={"prd_snapshot": {"sections": {}}},
    )

    assert merged["workflow_stage"] == "finalize"
    assert merged["idea_parse_result"]["idea_summary"] == "来自 turn_decision"
    assert merged["prd_draft"]["version"] == 3
    assert merged["critic_result"]["overall_verdict"] == "pass"
    assert merged["refine_history"] == [{"source": "turn_decision"}]
    assert merged["finalization_ready"] is True


def test_handle_user_message_rolls_back_user_message_when_gateway_reply_fails(db_session, monkeypatch):
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
    monkeypatch.setattr("app.services.messages.run_agent", lambda state, user_input, **_: _fake_gateway_agent_result())
    monkeypatch.setattr(
        "app.services.messages.generate_reply",
        lambda **_: (_ for _ in ()).throw(ModelGatewayError("上游不可用")),
    )

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
    assert messages_repository.get_messages_for_session(db_session, session.id) == []
    assert state_repository.get_latest_state_version(db_session, session.id).version == 1


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
    monkeypatch.setattr("app.services.messages.run_agent", lambda state, user_input, **_: _fake_gateway_agent_result())
    monkeypatch.setattr("app.services.messages.generate_reply", lambda **_: "这次会回滚")
    original_touch = messages_repository.touch_session_activity
    calls = {"count": 0}

    def fail_on_second_touch(db, persisted_session):
        calls["count"] += 1
        if calls["count"] == 2:
            raise RuntimeError("持久化链路失败")
        return original_touch(db, persisted_session)

    monkeypatch.setattr("app.services.messages.messages_repository.touch_session_activity", fail_on_second_touch)

    with pytest.raises(RuntimeError, match="持久化链路失败"):
        handle_user_message(
            db=db_session,
            session_id=session.id,
            session=session,
            content="这条消息会触发回滚",
            model_config_id=model_config.id,
        )

    assert messages_repository.get_messages_for_session(db_session, session.id) == []
    decisions = db_session.query(AgentTurnDecision).filter_by(session_id=session.id).all()
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
    monkeypatch.setattr("app.services.messages.run_agent", lambda state, user_input, **_: _fake_gateway_agent_result())
    monkeypatch.setattr(
        "app.services.messages.generate_reply",
        lambda **_: (_ for _ in ()).throw(ModelGatewayError("上游不可用")),
    )

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
    _create_initial_reply(db_session, monkeypatch, session, model_config)

    persisted_messages = messages_repository.get_messages_for_session(db_session, session.id)
    user_message = next(message for message in persisted_messages if message.role == "user")
    reply_group = assistant_reply_groups_repository.get_reply_group_by_user_message(db=db_session, user_message_id=user_message.id)
    db_session.execute(ProjectStateVersion.__table__.delete().where(ProjectStateVersion.session_id == session.id))
    db_session.commit()

    with pytest.raises(HTTPException) as exc_info:
        messages_service._persist_regenerated_reply_version(
            db=db_session,
            session_id=session.id,
            session=session,
            user_message_id=user_message.id,
            reply_group_id=reply_group.id,
            assistant_version_id=str(uuid4()),
            version_no=2,
            reply="重生成版本",
            model_meta={"model_config_id": model_config.id},
            action={"action": "probe_deeper"},
            turn_decision=_sample_turn_decision(),
            state=state_repository.get_latest_state(db_session, session.id),
            state_patch={},
            prd_patch={},
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "State snapshot not found"
    assert getattr(exc_info.value, "code", None) == "STATE_SNAPSHOT_MISSING"


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
    _create_initial_reply(db_session, monkeypatch, session, model_config)

    user_message = next(message for message in messages_repository.get_messages_for_session(db_session, session.id) if message.role == "user")

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


def test_persist_regenerated_reply_version_surfaces_reply_version_sequence_mismatch(db_session, monkeypatch):
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
    _create_initial_reply(db_session, monkeypatch, session, model_config)

    persisted_messages = messages_repository.get_messages_for_session(db_session, session.id)
    user_message = next(message for message in persisted_messages if message.role == "user")
    reply_group = assistant_reply_groups_repository.get_reply_group_by_user_message(db=db_session, user_message_id=user_message.id)

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
    result = _create_initial_reply(db_session, monkeypatch, session, model_config, reply="第一版助手回复")

    persisted_messages = messages_repository.get_messages_for_session(db_session, session.id)
    user_message = next(message for message in persisted_messages if message.role == "user")
    reply_group = assistant_reply_groups_repository.get_reply_group_by_user_message(db=db_session, user_message_id=user_message.id)
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
    assistant_reply_groups_repository.set_latest_version(db=db_session, reply_group=reply_group, latest_version_id=version_2.id)
    db_session.commit()

    latest_version = assistant_reply_versions_repository.get_latest_version_for_group(db=db_session, reply_group_id=reply_group.id)
    user_messages = [message for message in messages_repository.get_messages_for_session(db_session, session.id) if message.role == "user"]

    assert result.user_message_id == user_message.id
    assert latest_version.id == version_2.id
    assert len(user_messages) == 1


def test_repository_consistency_guards_for_reply_groups_turn_decisions_and_versions(db_session, monkeypatch):
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
    _create_initial_reply(db_session, monkeypatch, primary_session, model_config, reply="primary")
    _create_initial_reply(db_session, monkeypatch, secondary_session, model_config, reply="secondary")

    primary_messages = messages_repository.get_messages_for_session(db_session, primary_session.id)
    secondary_messages = messages_repository.get_messages_for_session(db_session, secondary_session.id)
    primary_user_message = next(message for message in primary_messages if message.role == "user")
    secondary_user_message = next(message for message in secondary_messages if message.role == "user")
    primary_group = assistant_reply_groups_repository.get_reply_group_by_user_message(db=db_session, user_message_id=primary_user_message.id)
    assistant_message = messages_repository.create_message(
        db=db_session,
        session_id=primary_session.id,
        role="assistant",
        content="assistant",
    )
    db_session.commit()

    with pytest.raises(ValueError, match="does not belong to session"):
        assistant_reply_groups_repository.create_reply_group(
            db=db_session,
            session_id=primary_session.id,
            user_message_id=secondary_user_message.id,
        )
    with pytest.raises(ValueError, match="does not belong to session"):
        agent_turn_decisions_repository.create_turn_decision(
            db=db_session,
            session_id=primary_session.id,
            user_message_id=secondary_user_message.id,
            turn_decision=_sample_turn_decision(),
        )
    with pytest.raises(ValueError, match="must have user role"):
        agent_turn_decisions_repository.create_turn_decision(
            db=db_session,
            session_id=primary_session.id,
            user_message_id=assistant_message.id,
            turn_decision=_sample_turn_decision(),
        )
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


def test_prepare_regenerate_stream_excludes_current_user_message_from_conversation_history(db_session, monkeypatch):
    session = _create_session_with_state(db_session)
    model_config = model_configs_repository.create_model_config(
        db_session,
        name="重生成历史模型",
        base_url="https://gateway.example.com/v1",
        api_key="secret",
        model="gpt-4o-mini",
        enabled=True,
    )
    db_session.commit()
    _create_initial_reply(db_session, monkeypatch, session, model_config, reply="初版回复")

    persisted_messages = messages_repository.get_messages_for_session(db_session, session.id)
    user_message = next(message for message in persisted_messages if message.role == "user")
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        "app.services.messages.run_agent",
        lambda state, user_input, **kwargs: (
            captured.update({"conversation_history": kwargs["conversation_history"]})
            or _fake_gateway_agent_result()
        ),
    )
    monkeypatch.setattr(
        "app.services.messages.open_reply_stream",
        lambda **_: messages_service.LocalReplyStream("重生成回复"),
    )

    prepared = messages_service._prepare_regenerate_stream(
        db=db_session,
        session_id=session.id,
        user_message_id=user_message.id,
        model_config_id=model_config.id,
    )

    assert prepared.user_message_id == user_message.id
    assert captured["conversation_history"] == []


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
    _create_initial_reply(db_session, monkeypatch, session, model_config, reply="初版回复")

    persisted_messages = messages_repository.get_messages_for_session(db_session, session.id)
    user_message = next(message for message in persisted_messages if message.role == "user")
    assistant_message = next(message for message in persisted_messages if message.role == "assistant")
    existing_group = assistant_reply_groups_repository.get_reply_group_by_user_message(db=db_session, user_message_id=user_message.id)
    version_1 = assistant_reply_versions_repository.get_latest_version_for_group(db=db_session, reply_group_id=existing_group.id)
    captured = {}

    class FakeReplyStream:
        def __iter__(self):
            yield "这是"
            yield "重生成"
            yield "版本"

        def close(self):
            return None

    monkeypatch.setattr(
        "app.services.messages.run_agent",
        lambda state, user_input, **_: _fake_gateway_agent_result(
            state_patch={"workflow_stage": "completed"},
            prd_patch={
                "solution": {"title": "解决方案", "content": "重生成后采用浏览器预览加评论分享。", "status": "confirmed"},
                "constraints": {"title": "约束条件", "content": "首版只支持浏览器端。", "status": "confirmed"},
            },
        ),
    )
    monkeypatch.setattr(
        "app.services.messages.open_reply_stream",
        lambda **kwargs: (captured.update({"messages": kwargs["messages"]}) or FakeReplyStream()),
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
    assert [event.data["delta"] for event in events if event.type == "assistant.delta"] == ["这是", "重生成", "版本"]
    assert started_event.data["version_no"] == 2
    assert started_event.data["reply_group_id"] == existing_group.id
    assert started_event.data["assistant_message_id"] == assistant_message.id
    assert started_event.data["is_regeneration"] is True
    assert done_event.data["assistant_version_id"] == started_event.data["assistant_version_id"]
    assert done_event.data["assistant_message_id"] == assistant_message.id
    assert done_event.data["is_latest"] is True
    assert captured["messages"] == [
        {"role": "system", "content": "你是用户的 AI 产品协作助手，请基于上下文给出简洁、直接的中文回复。"},
        {"role": "user", "content": "请给我一个版本"},
    ]

    versions = assistant_reply_versions_repository.list_versions_for_group(db=db_session, reply_group_id=existing_group.id)
    latest_version = assistant_reply_versions_repository.get_latest_version_for_group(db=db_session, reply_group_id=existing_group.id)
    latest_state_version = state_repository.get_latest_state_version(db_session, session.id)
    latest_messages = messages_repository.get_messages_for_session(db_session, session.id)
    assistant_messages = [message for message in latest_messages if message.role == "assistant"]
    latest_decision = agent_turn_decisions_repository.get_latest_for_user_message(
        db_session,
        user_message.id,
    )

    assert existing_group.latest_version_id != version_1.id or latest_version.id != version_1.id
    assert [version.version_no for version in versions] == [1, 2]
    assert latest_version.content == "这是重生成版本"
    assert latest_state_version.version == 3
    assert latest_messages.count(user_message) == 1
    assert len(assistant_messages) == 1
    assert assistant_messages[0].id == assistant_message.id
    assert assistant_messages[0].content == "这是重生成版本"
    assert latest_decision is not None
    assert latest_state_version.state_json["workflow_stage"] == "completed"


def test_stream_regenerate_message_events_updates_existing_turn_decision(db_session, monkeypatch):
    session = _create_session_with_state(db_session)
    model_config = model_configs_repository.create_model_config(
        db_session,
        name="重生成决策模型",
        base_url="https://gateway.example.com/v1",
        api_key="secret",
        model="gpt-4o-mini",
        enabled=True,
    )
    db_session.commit()
    _create_initial_reply(db_session, monkeypatch, session, model_config, reply="初版回复")

    persisted_messages = messages_repository.get_messages_for_session(db_session, session.id)
    user_message = next(message for message in persisted_messages if message.role == "user")
    original_decision = agent_turn_decisions_repository.get_latest_for_user_message(db_session, user_message.id)
    assert original_decision is not None

    monkeypatch.setattr(
        "app.services.messages.run_agent",
        lambda state, user_input, **_: _fake_gateway_agent_result(
            state_patch={"workflow_stage": "completed"},
            turn_decision=TurnDecision(
                phase="solution",
                phase_goal="确认解决方案",
                understanding={
                    "summary": "重生成后方案已经收敛",
                    "candidate_updates": {},
                    "ambiguous_points": [],
                },
                assumptions=[],
                gaps=[],
                challenges=[],
                pm_risk_flags=[],
                next_move="summarize_and_confirm",
                suggestions=[],
                recommendation={"label": "浏览器预览 + 评论分享"},
                reply_brief={"focus": "solution", "must_include": []},
                state_patch={"workflow_stage": "completed"},
                prd_patch={},
                needs_confirmation=["请确认解决方案"],
                confidence="high",
                next_best_questions=["是否确认这个方案？"],
                strategy_reason="方案已足够具体，可以进入确认。",
                conversation_strategy="confirm",
            ),
        ),
    )
    monkeypatch.setattr(
        "app.services.messages.open_reply_stream",
        lambda **_: messages_service.LocalReplyStream("重生成后的最终回复"),
    )

    list(
        stream_regenerate_message_events(
            db=db_session,
            session_id=session.id,
            session=session,
            user_message_id=user_message.id,
            model_config_id=model_config.id,
        )
    )

    refreshed_decision = agent_turn_decisions_repository.get_latest_for_user_message(db_session, user_message.id)
    decision_count = db_session.execute(
        select(AgentTurnDecision).where(AgentTurnDecision.user_message_id == user_message.id)
    ).scalars().all()

    assert len(decision_count) == 1
    assert refreshed_decision is not None
    assert refreshed_decision.id == original_decision.id
    assert refreshed_decision.phase == "solution"
    assert refreshed_decision.next_move == "summarize_and_confirm"
    assert refreshed_decision.state_patch_json["workflow_stage"] == "completed"


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
    _create_initial_reply(db_session, monkeypatch, session, model_config, reply="初版回复")

    persisted_messages = messages_repository.get_messages_for_session(db_session, session.id)
    user_message = next(message for message in persisted_messages if message.role == "user")
    assistant_message = next(message for message in persisted_messages if message.role == "assistant")
    reply_group = assistant_reply_groups_repository.get_reply_group_by_user_message(db=db_session, user_message_id=user_message.id)
    version_1 = assistant_reply_versions_repository.get_latest_version_for_group(db=db_session, reply_group_id=reply_group.id)

    class BrokenReplyStream:
        def __iter__(self):
            yield "这是"
            raise ModelGatewayError("流式中断")

        def close(self):
            return None

    monkeypatch.setattr("app.services.messages.run_agent", lambda state, user_input, **_: _fake_gateway_agent_result())
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
        "assistant.error",
    ]
    error_event = events[-1]
    assert error_event.data["code"] == "MODEL_STREAM_FAILED"
    assert error_event.data["message"] == "流式中断"
    assert error_event.data["recovery_action"]["type"] == "retry"
    refreshed_group = assistant_reply_groups_repository.get_reply_group_by_user_message(db=db_session, user_message_id=user_message.id)
    versions = assistant_reply_versions_repository.list_versions_for_group(db=db_session, reply_group_id=reply_group.id)
    latest_state_version = state_repository.get_latest_state_version(db_session, session.id)
    assistant_messages = [message for message in messages_repository.get_messages_for_session(db_session, session.id) if message.role == "assistant"]

    assert refreshed_group.latest_version_id == version_1.id
    assert [version.version_no for version in versions] == [1]
    assert latest_state_version.version == 2
    assert len(assistant_messages) == 1
    assert assistant_messages[0].id == assistant_message.id
    assert assistant_messages[0].content == "初版回复"


def test_stream_user_message_events_emits_assistant_error_when_stream_fails(db_session, monkeypatch):
    session = _create_session_with_state(db_session)
    model_config = model_configs_repository.create_model_config(
        db_session,
        name="发送失败模型",
        base_url="https://gateway.example.com/v1",
        api_key="secret",
        model="gpt-4o-mini",
        enabled=True,
    )
    db_session.commit()

    class BrokenReplyStream:
        def __iter__(self):
            yield "这是"
            raise ModelGatewayError("流式中断")

        def close(self):
            return None

    monkeypatch.setattr(
        "app.services.messages.run_agent",
        lambda state, user_input, **_: _fake_gateway_agent_result(),
    )
    monkeypatch.setattr("app.services.messages.open_reply_stream", lambda **_: BrokenReplyStream())

    events = list(
        messages_service.stream_user_message_events(
            db=db_session,
            session_id=session.id,
            session=session,
            content="请继续分析这个方向",
            model_config_id=model_config.id,
        )
    )

    assert [event.type for event in events] == [
        "message.accepted",
        "reply_group.created",
        "action.decided",
        "assistant.version.started",
        "assistant.delta",
        "assistant.error",
    ]

    error_event = events[-1]
    assert error_event.data["code"] == "MODEL_STREAM_FAILED"
    assert error_event.data["message"] == "流式中断"
    assert error_event.data["recovery_action"]["type"] == "retry"

    messages = messages_repository.get_messages_for_session(db_session, session.id)
    versions = db_session.execute(select(AssistantReplyVersion)).scalars().all()

    assert [message.role for message in messages] == ["user"]
    assert versions == []


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
    _create_initial_reply(db_session, monkeypatch, session, model_config, reply="latest 语义测试回复")

    persisted_messages = messages_repository.get_messages_for_session(db_session, session.id)
    user_message = next(message for message in persisted_messages if message.role == "user")
    reply_group = assistant_reply_groups_repository.get_reply_group_by_user_message(db=db_session, user_message_id=user_message.id)
    version_1 = assistant_reply_versions_repository.get_latest_version_for_group(db=db_session, reply_group_id=reply_group.id)
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
    assistant_reply_groups_repository.set_latest_version(db=db_session, reply_group=reply_group, latest_version_id=version_1.id)
    db_session.commit()

    latest_version = assistant_reply_versions_repository.get_latest_version_for_group(db=db_session, reply_group_id=reply_group.id)

    assert latest_version.id == version_1.id
    assert latest_version.id != version_2.id
