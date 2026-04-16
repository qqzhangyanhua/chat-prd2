import json
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.agent.types import NextAction, Suggestion, TurnDecision
from app.db.models import AgentTurnDecision
from app.db.models import (
    AssistantReplyGroup,
    AssistantReplyVersion,
    ConversationMessage,
    PrdSnapshot,
    ProjectSession,
    ProjectStateVersion,
    User,
)
from app.repositories import model_configs as model_configs_repository
from app.repositories import prd as prd_repository
from app.repositories import state as state_repository
from app.schemas.session import SessionCreateRequest
from app.services import sessions as session_service


def _create_enabled_model_config(testing_session_local) -> str:
    db = testing_session_local()
    try:
        model_config = model_configs_repository.create_model_config(
            db,
            name="会话测试模型",
            base_url="https://gateway.example.com/v1",
            api_key="secret",
            model="gpt-4o-mini",
            enabled=True,
        )
        db.commit()
        return model_config.id
    finally:
        db.close()


def _mock_gateway_reply(monkeypatch, reply: str = "这是测试回复", **overrides) -> None:
    payload = {
        "observation": "用户补充了具体信息",
        "challenge": "当前信息是否足够聚焦？",
        "suggestion": "先锁定一个最重要的判断维度",
        "question": "你想先确认目标用户还是核心问题？",
        "reply": reply,
        "prd_updates": {
            "target_user": {
                "title": "目标用户",
                "content": "独立开发者",
                "status": "confirmed",
            }
        },
        "confidence": "medium",
        "next_focus": "problem",
    }
    payload.update(overrides)
    monkeypatch.setattr(
        "app.agent.pm_mentor.call_pm_mentor_llm",
        lambda **_: payload,
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
        response_mode="options_first",
        guidance_mode="compare",
        guidance_step="compare",
        focus_dimension="problem",
        transition_reason="当前候选方向不止一个，先做取舍比继续泛问更有效。",
        transition_trigger="high_uncertainty",
        option_cards=[
            {
                "id": "problem-1-independent",
                "label": "A. 先聊独立开发者",
                "title": "A. 先聊独立开发者",
                "content": "我先从独立开发者的真实使用场景开始补充。",
                "description": "更容易快速拿到高频反馈。",
                "type": "direction",
                "priority": 1,
            },
            {
                "id": "problem-2-team-lead",
                "label": "B. 先聊小团队负责人",
                "title": "B. 先聊小团队负责人",
                "content": "我更想先看 3-10 人团队的协作问题。",
                "description": "协作链路更完整，但场景更复杂。",
                "type": "tradeoff",
                "priority": 2,
            },
            {
                "id": "problem-3-pain",
                "label": "C. 先锁定高频痛点",
                "title": "C. 先锁定高频痛点",
                "content": "先别分人群，先确定一个最高频的问题。",
                "description": "可以直接筛掉低价值需求。",
                "type": "recommendation",
                "priority": 3,
            },
            {
                "id": "problem-4-freeform",
                "label": "D. 我直接补充真实案例",
                "title": "D. 我直接补充真实案例",
                "content": "我直接讲一个最近遇到的具体案例。",
                "description": "真实案例能最快暴露需求真假。",
                "type": "warning",
                "priority": 4,
            },
        ],
        freeform_affordance={"label": "都不对，我补充", "value": "freeform", "kind": "freeform"},
        can_switch_mode=True,
        available_mode_switches=[
            {"mode": "confirm", "label": "直接进入确认"},
            {"mode": "freeform", "label": "直接自由补充"},
        ],
    )


def _create_user_and_legacy_session(db_session):
    user = User(
        id="user-legacy-session-1",
        email="legacy-session@example.com",
        password_hash="hash",
    )
    db_session.add(user)
    db_session.commit()
    snapshot = session_service.create_session(
        db_session,
        user.id,
        SessionCreateRequest(
            title="Legacy Workspace Session",
            initial_idea="一个帮助团队补算旧会话状态的系统",
        ),
    )
    return user.id, snapshot.session.id


def _seed_legacy_state(
    db_session,
    session_id: str,
    *,
    sections: dict[str, dict[str, str]],
) -> None:
    latest = state_repository.get_latest_state_version(db_session, session_id)
    assert latest is not None
    legacy_state = {
        **latest.state_json,
        "prd_snapshot": {
            "sections": sections,
        },
    }
    legacy_state.pop("workflow_stage", None)
    legacy_state.pop("prd_draft", None)
    legacy_state.pop("critic_result", None)
    legacy_state.pop("finalization_ready", None)
    state_repository.create_state_version(
        db=db_session,
        session_id=session_id,
        version=latest.version + 1,
        state_json=legacy_state,
    )
    prd_repository.create_prd_snapshot(
        db=db_session,
        session_id=session_id,
        version=latest.version + 1,
        sections=sections,
    )
    db_session.commit()


def test_create_session_returns_initial_state(auth_client):
    response = auth_client.post(
        "/api/sessions",
        json={
            "title": "AI Co-founder",
            "initial_idea": "一个帮助独立开发者梳理产品想法并生成 PRD 的智能体系统",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["session"]["title"] == "AI Co-founder"
    assert data["state"]["stage_hint"] == "问题探索"
    assert data["prd_snapshot"]["sections"] == {}


def test_create_session_persists_phase1_default_state(auth_client, testing_session_local):
    response = auth_client.post(
        "/api/sessions",
        json={
            "title": "AI Co-founder",
            "initial_idea": "一个帮助独立开发者梳理产品想法并生成 PRD 的智能体系统",
        },
    )
    assert response.status_code == 200
    session_id = response.json()["session"]["id"]

    db = testing_session_local()
    try:
        state_version = db.execute(
            select(ProjectStateVersion).where(ProjectStateVersion.session_id == session_id)
        ).scalar_one()
    finally:
        db.close()

    assert state_version.state_json["current_phase"] == "idea_clarification"
    assert state_version.state_json["conversation_strategy"] == "clarify"
    assert state_version.state_json["current_model_scene"] == "general"
    assert state_version.state_json["collaboration_mode_label"] == "通用协作模式"
    assert state_version.state_json["working_hypotheses"] == []
    assert state_version.state_json["recommended_directions"] == []
    assert state_version.state_json["pending_confirmations"] == []


def test_build_turn_decision_sections_includes_draft_update_meta():
    decision = AgentTurnDecision(
        id="decision-1",
        session_id="session-1",
        user_message_id="message-1",
        phase="problem",
        phase_goal="先沉淀结构化首稿",
        understanding_summary="用户已经补充了明确目标用户",
        assumptions_json=[],
        risk_flags_json=[],
        next_move="probe_for_specificity",
        suggestions_json=[],
        recommendation_json=None,
        needs_confirmation_json=[],
        confidence="medium",
        state_patch_json={
            "next_best_questions": ["下一步先补成功标准。"],
            "prd_draft": {
                "version": 2,
                "status": "drafting",
                "sections": {
                    "target_user": {
                        "title": "目标用户",
                        "completeness": "partial",
                        "entries": [
                            {
                                "id": "entry-target-user-1",
                                "text": "第一版先服务独立开发者。",
                                "assertion_state": "confirmed",
                                "evidence_ref_ids": ["evidence-user-1"],
                            }
                        ],
                    }
                },
                "summary": {
                    "section_keys": ["target_user"],
                    "entry_ids": ["entry-target-user-1"],
                    "evidence_ids": ["evidence-user-1"],
                },
            },
            "evidence": [
                {
                    "id": "evidence-user-1",
                    "kind": "user_message",
                    "excerpt": "我想先服务独立开发者。",
                    "section_keys": ["target_user"],
                }
            ],
        },
        prd_patch_json={},
    )

    sections = session_service._build_turn_decision_sections(decision)
    next_step = next(section for section in sections if section.key == "next_step")

    assert next_step.meta["draft_updates"]["entry_ids"] == ["entry-target-user-1"]
    assert next_step.meta["draft_updates"]["section_keys"] == ["target_user"]
    assert next_step.meta["evidence_ref_ids"] == ["evidence-user-1"]


def test_create_session_rejects_blank_title_and_initial_idea(auth_client):
    response = auth_client.post(
        "/api/sessions",
        json={
            "title": "   ",
            "initial_idea": "   ",
        },
    )

    assert response.status_code == 422


def test_create_session_rolls_back_all_writes_when_prd_creation_fails(
    db_session,
    monkeypatch,
):
    def fail_create_prd_snapshot(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(
        session_service.prd_repository,
        "create_prd_snapshot",
        fail_create_prd_snapshot,
    )

    payload = SessionCreateRequest(title="AI Co-founder", initial_idea="idea")

    try:
        session_service.create_session(db_session, "user-1", payload)
    except RuntimeError as exc:
        assert str(exc) == "boom"
    else:
        raise AssertionError("expected create_session to raise RuntimeError")

    assert db_session.execute(select(ProjectSession)).scalars().all() == []
    assert db_session.execute(select(ProjectStateVersion)).scalars().all() == []
    assert db_session.execute(select(PrdSnapshot)).scalars().all() == []


def test_export_returns_markdown(auth_client, seeded_session):
    response = auth_client.post(
        f"/api/sessions/{seeded_session}/export",
        json={"format": "md"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["file_name"] == "ai-cofounder-prd.md"
    assert data["content"].startswith("# PRD")


def test_get_session_snapshot_backfills_legacy_state_when_explicit_closure_fields_missing(db_session):
    user_id, session_id = _create_user_and_legacy_session(db_session)
    _seed_legacy_state(
        db_session,
        session_id,
        sections={
            "target_user": {"title": "目标用户", "content": "产品团队", "status": "confirmed"},
            "problem": {"title": "核心问题", "content": "需求收敛慢", "status": "confirmed"},
            "solution": {"title": "解决方案", "content": "按需补算闭环字段", "status": "confirmed"},
            "mvp_scope": {"title": "MVP 范围", "content": "单 session 读取补算", "status": "confirmed"},
        },
    )

    result = session_service.get_session_snapshot(db_session, session_id, user_id)

    assert result.state.workflow_stage == "refine_loop"
    assert result.state.prd_draft is not None
    assert result.state.critic_result is not None
    assert result.state.finalization_ready is False


def test_get_session_snapshot_backfills_ready_legacy_state_to_finalize_only(db_session):
    user_id, session_id = _create_user_and_legacy_session(db_session)
    _seed_legacy_state(
        db_session,
        session_id,
        sections={
            "target_user": {"title": "目标用户", "content": "产品团队", "status": "confirmed"},
            "problem": {"title": "核心问题", "content": "需求收敛慢", "status": "confirmed"},
            "solution": {"title": "解决方案", "content": "按需补算闭环字段", "status": "confirmed"},
            "mvp_scope": {"title": "MVP 范围", "content": "单 session 读取补算", "status": "confirmed"},
            "constraints": {"title": "约束条件", "content": "不做批量迁移", "status": "confirmed"},
            "success_metrics": {"title": "成功指标", "content": "旧会话可稳定进入终稿前态", "status": "confirmed"},
        },
    )

    result = session_service.get_session_snapshot(db_session, session_id, user_id)

    assert result.state.workflow_stage == "finalize"
    assert result.state.finalization_ready is True
    assert result.state.prd_draft is not None
    assert result.state.prd_draft["status"] != "finalized"


def test_get_session_snapshot_rolls_back_legacy_backfill_failure(db_session, monkeypatch):
    user_id, session_id = _create_user_and_legacy_session(db_session)
    _seed_legacy_state(
        db_session,
        session_id,
        sections={
            "target_user": {"title": "目标用户", "content": "产品团队", "status": "confirmed"},
            "problem": {"title": "核心问题", "content": "需求收敛慢", "status": "confirmed"},
            "solution": {"title": "解决方案", "content": "按需补算闭环字段", "status": "confirmed"},
            "mvp_scope": {"title": "MVP 范围", "content": "单 session 读取补算", "status": "confirmed"},
            "constraints": {"title": "约束条件", "content": "不做批量迁移", "status": "confirmed"},
            "success_metrics": {"title": "成功指标", "content": "旧会话可稳定进入终稿前态", "status": "confirmed"},
        },
    )
    before_count = len(
        db_session.execute(
            select(ProjectStateVersion).where(ProjectStateVersion.session_id == session_id)
        ).scalars().all()
    )

    def fail_create_state_version(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(
        "app.services.legacy_session_backfill.state_repository.create_state_version",
        fail_create_state_version,
    )

    result = session_service.get_session_snapshot(db_session, session_id, user_id)

    after_count = len(
        db_session.execute(
            select(ProjectStateVersion).where(ProjectStateVersion.session_id == session_id)
        ).scalars().all()
    )
    assert result.state.workflow_stage == "idea_parser"
    assert result.state.prd_draft is None
    assert result.state.critic_result is None
    assert result.state.finalization_ready is False
    assert after_count == before_count


def test_export_returns_real_prd_content_after_message_updates_snapshot(
    auth_client,
    seeded_session,
    testing_session_local,
    monkeypatch,
):
    model_config_id = _create_enabled_model_config(testing_session_local)
    _mock_gateway_reply(monkeypatch)

    db = testing_session_local()
    try:
        session = db.get(ProjectSession, seeded_session)
        assert session is not None
        state_repository.create_state_version(
            db=db,
            session_id=seeded_session,
            version=2,
            state_json={
                **session_service.build_initial_state(session.initial_idea),
                "workflow_stage": "prd_draft",
            },
        )
        prd_repository.create_prd_snapshot(
            db=db,
            session_id=seeded_session,
            version=2,
            sections={},
        )
        db.commit()
    finally:
        db.close()

    with auth_client.stream(
        "POST",
        f"/api/sessions/{seeded_session}/messages",
        json={
            "content": "独立开发者",
            "model_config_id": model_config_id,
        },
    ) as response:
        assert response.status_code == 200
        list(response.iter_text())

    response = auth_client.post(
        f"/api/sessions/{seeded_session}/export",
        json={"format": "md"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "独立开发者" in data["content"]




def test_get_session_exposes_suggestion_options_in_turn_decision_meta(
    auth_client,
    seeded_session,
    testing_session_local,
    monkeypatch,
):
    model_config_id = _create_enabled_model_config(testing_session_local)
    _mock_gateway_reply(
        monkeypatch,
        suggestions=[
            {
                "type": "direction",
                "label": "先聊独立开发者",
                "content": "我想先从独立开发者的场景开始聊。",
                "rationale": "更容易快速举出真实例子。",
                "priority": 1,
            },
            {
                "type": "tradeoff",
                "label": "先聊目标用户",
                "content": "我想先明确，这个产品主要给谁用。",
                "rationale": "先锁定用户，后面的需求判断才不会发散。",
                "priority": 2,
            },
            {
                "type": "recommendation",
                "label": "先聊核心痛点",
                "content": "我想先判断用户最痛的那个问题是什么。",
                "rationale": "先确认痛点，才能快速判断主线。",
                "priority": 3,
            },
            {
                "type": "warning",
                "label": "直接补充真实案例",
                "content": "我可以直接讲一个最近发生的真实案例。",
                "rationale": "真实案例最容易暴露信息缺口。",
                "priority": 4,
            },
        ],
    )

    with auth_client.stream(
        "POST",
        f"/api/sessions/{seeded_session}/messages",
        json={
            "content": "我有个想法，但不知道怎么说",
            "model_config_id": model_config_id,
        },
    ) as response:
        assert response.status_code == 200
        list(response.iter_text())

    response = auth_client.get(f"/api/sessions/{seeded_session}")

    assert response.status_code == 200
    data = response.json()
    latest_decision = data["turn_decisions"][-1]
    next_step = next(
        section for section in latest_decision["decision_sections"] if section["key"] == "next_step"
    )
    suggestion_options = next_step["meta"]["suggestion_options"]

    assert len(suggestion_options) == 4
    assert suggestion_options == [
        {
            "label": "先聊独立开发者",
            "content": "我想先从独立开发者的场景开始聊。",
            "rationale": "更容易快速举出真实例子。",
            "priority": 1,
            "type": "direction",
        },
        {
            "label": "先聊目标用户",
            "content": "我想先明确，这个产品主要给谁用。",
            "rationale": "先锁定用户，后面的需求判断才不会发散。",
            "priority": 2,
            "type": "tradeoff",
        },
        {
            "label": "先聊核心痛点",
            "content": "我想先判断用户最痛的那个问题是什么。",
            "rationale": "先确认痛点，才能快速判断主线。",
            "priority": 3,
            "type": "recommendation",
        },
        {
            "label": "直接补充真实案例",
            "content": "我可以直接讲一个最近发生的真实案例。",
            "rationale": "真实案例最容易暴露信息缺口。",
            "priority": 4,
            "type": "warning",
        },
    ]


def test_get_session_snapshot_preserves_all_four_suggestion_options(
    auth_client,
    seeded_session,
    testing_session_local,
    monkeypatch,
):
    model_config_id = _create_enabled_model_config(testing_session_local)
    turn_decision = _sample_turn_decision_with_four_suggestions()
    monkeypatch.setattr(
        "app.services.messages.run_agent",
        lambda state, user_input, **_: type(
            "FakeAgentResult",
            (),
            {
                "reply": "先从这四个结构化选项里选一个最接近你的情况。",
                "action": NextAction(action="probe_deeper", target="target_user", reason="test"),
                "reply_mode": "local",
                "turn_decision": turn_decision,
                "state_patch": {},
                "prd_patch": {},
            },
        )(),
    )

    with auth_client.stream(
        "POST",
        f"/api/sessions/{seeded_session}/messages",
        json={
            "content": "我现在还不确定先从哪条主线开始",
            "model_config_id": model_config_id,
        },
    ) as response:
        assert response.status_code == 200
        list(response.iter_text())

    response = auth_client.get(f"/api/sessions/{seeded_session}")

    assert response.status_code == 200
    data = response.json()
    latest_decision = data["turn_decisions"][-1]
    next_step = next(
        section for section in latest_decision["decision_sections"] if section["key"] == "next_step"
    )
    suggestion_options = next_step["meta"]["suggestion_options"]
    judgement = next(
        section for section in latest_decision["decision_sections"] if section["key"] == "judgement"
    )

    assert len(suggestion_options) == 4
    assert [item["label"] for item in suggestion_options] == [
        "A. 先聊独立开发者",
        "B. 先聊小团队负责人",
        "C. 先锁定高频痛点",
        "D. 我直接补充真实案例",
    ]
    assert [item["priority"] for item in suggestion_options] == [1, 2, 3, 4]
    assert next_step["meta"]["next_best_questions"]
    assert next_step["meta"]["guidance_mode"] == "compare"
    assert next_step["meta"]["guidance_step"] == "compare"
    assert next_step["meta"]["focus_dimension"] == "problem"
    assert next_step["meta"]["transition_reason"]
    assert next_step["meta"]["option_cards"][0]["id"] == "problem-1-independent"
    assert next_step["meta"]["freeform_affordance"] == {
        "label": "都不对，我补充",
        "value": "freeform",
        "kind": "freeform",
    }
    assert next_step["meta"]["available_mode_switches"]
    assert judgement["meta"]["strategy_label"]
    assert judgement["meta"]["guidance_mode"] == "compare"
    assert judgement["meta"]["focus_dimension"] == "problem"

    assert data["state"]["guidance_mode"] == "compare"
    assert data["state"]["guidance_step"] == "compare"
    assert data["state"]["focus_dimension"] == "problem"
    assert data["state"]["transition_reason"]
    assert data["state"]["freeform_affordance"] == {
        "label": "都不对，我补充",
        "value": "freeform",
        "kind": "freeform",
    }
    assert data["state"]["available_mode_switches"]


def test_stream_guidance_matches_session_snapshot_guidance(
    auth_client,
    seeded_session,
    testing_session_local,
    monkeypatch,
):
    model_config_id = _create_enabled_model_config(testing_session_local)
    _mock_gateway_reply(
        monkeypatch,
        suggestions=[
            {
                "type": "direction",
                "label": "先聊独立开发者",
                "content": "我想先从独立开发者的场景开始聊。",
                "rationale": "更容易快速举出真实例子。",
                "priority": 1,
            },
            {
                "type": "tradeoff",
                "label": "先聊目标用户",
                "content": "我想先明确，这个产品主要给谁用。",
                "rationale": "先锁定用户，后面的需求判断才不会发散。",
                "priority": 2,
            },
            {
                "type": "recommendation",
                "label": "先聊核心痛点",
                "content": "我想先判断用户最痛的那个问题是什么。",
                "rationale": "先确认痛点，才能快速判断主线。",
                "priority": 3,
            },
            {
                "type": "warning",
                "label": "直接补充真实案例",
                "content": "我可以直接讲一个最近发生的真实案例。",
                "rationale": "真实案例最容易暴露信息缺口。",
                "priority": 4,
            },
        ],
    )

    with auth_client.stream(
        "POST",
        f"/api/sessions/{seeded_session}/messages",
        json={
            "content": "我有个想法，但不知道怎么说",
            "model_config_id": model_config_id,
        },
    ) as response:
        assert response.status_code == 200
        body = "".join(response.iter_text())

    parsed_events = []
    current_event = None
    for line in body.splitlines():
        if line.startswith("event: "):
            current_event = line.removeprefix("event: ").strip()
            continue
        if line.startswith("data: ") and current_event is not None:
            parsed_events.append((current_event, json.loads(line.removeprefix("data: "))))
            current_event = None

    guidance_payload = next(payload for name, payload in parsed_events if name == "decision.ready")

    response = auth_client.get(f"/api/sessions/{seeded_session}")
    assert response.status_code == 200
    data = response.json()
    latest_decision = data["turn_decisions"][-1]
    next_step = next(
        section for section in latest_decision["decision_sections"] if section["key"] == "next_step"
    )

    assert guidance_payload["suggestions"] == next_step["meta"]["suggestion_options"]
    assert guidance_payload["next_best_questions"] == next_step["meta"]["next_best_questions"]
    assert guidance_payload["guidance_mode"] == next_step["meta"]["guidance_mode"]
    assert guidance_payload["guidance_step"] == next_step["meta"]["guidance_step"]
    assert guidance_payload["focus_dimension"] == next_step["meta"]["focus_dimension"]
    assert guidance_payload["transition_reason"] == next_step["meta"]["transition_reason"]
    assert guidance_payload["option_cards"] == next_step["meta"]["option_cards"]
    assert guidance_payload["freeform_affordance"] == next_step["meta"]["freeform_affordance"]
    assert guidance_payload["available_mode_switches"] == next_step["meta"]["available_mode_switches"]
    assert guidance_payload["diagnostics"] == next_step["meta"]["diagnostics"]
    assert guidance_payload["diagnostic_summary"] == next_step["meta"]["diagnostic_summary"]
    assert data["state"]["diagnostics"]
    assert data["state"]["diagnostic_summary"]["open_count"] >= guidance_payload["diagnostic_summary"]["open_count"]


def test_get_session_returns_explicit_503_when_turn_decision_table_is_missing():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    User.__table__.create(bind=engine)
    ProjectSession.__table__.create(bind=engine)
    ProjectStateVersion.__table__.create(bind=engine)
    PrdSnapshot.__table__.create(bind=engine)
    ConversationMessage.__table__.create(bind=engine)
    AssistantReplyGroup.__table__.create(bind=engine)
    AssistantReplyVersion.__table__.create(bind=engine)

    db = session_local()
    try:
        user = User(
            id="user-1",
            email="schema-check@example.com",
            password_hash="hashed",
        )
        session = ProjectSession(
            id="session-1",
            user_id=user.id,
            title="AI Co-founder",
            initial_idea="idea",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        state_version = ProjectStateVersion(
            id="state-1",
            session_id=session.id,
            version=1,
            state_json=session_service.build_initial_state("idea"),
        )
        prd_snapshot = PrdSnapshot(
            id="prd-1",
            session_id=session.id,
            version=1,
            sections={},
        )
        db.add_all([user, session, state_version, prd_snapshot])
        db.commit()

        try:
            session_service.get_session_snapshot(db, session.id, user.id)
        except HTTPException as exc:
            assert exc.status_code == 503
            assert exc.detail == "数据库结构版本过旧，请先执行 alembic upgrade head"
        else:
            raise AssertionError("expected get_session_snapshot to raise HTTPException")
    finally:
        db.close()


def test_get_session_marks_session_as_recently_active(auth_client):
    first_response = auth_client.post(
        "/api/sessions",
        json={"title": "First Session", "initial_idea": "idea one"},
    )
    assert first_response.status_code == 200

    second_response = auth_client.post(
        "/api/sessions",
        json={"title": "Second Session", "initial_idea": "idea two"},
    )
    assert second_response.status_code == 200

    response = auth_client.get(f"/api/sessions/{first_response.json()['session']['id']}")
    assert response.status_code == 200

    sessions_response = auth_client.get("/api/sessions")
    assert sessions_response.status_code == 200
    data = sessions_response.json()
    assert [session["title"] for session in data["sessions"]] == [
        "First Session",
        "Second Session",
    ]


def test_get_session_does_not_touch_activity_when_snapshot_missing(
    auth_client,
    testing_session_local,
):
    create_response = auth_client.post(
        "/api/sessions",
        json={"title": "Broken Session", "initial_idea": "idea one"},
    )
    assert create_response.status_code == 200
    session_id = create_response.json()["session"]["id"]
    original_updated_at = create_response.json()["session"]["updated_at"]

    db = testing_session_local()
    try:
        session = db.execute(
            select(ProjectSession).where(ProjectSession.id == session_id),
        ).scalar_one()
        db.execute(
            ProjectStateVersion.__table__.delete().where(ProjectStateVersion.session_id == session_id),
        )
        db.commit()
        db.refresh(session)
        broken_updated_at = session.updated_at
    finally:
        db.close()

    assert broken_updated_at.isoformat() == original_updated_at

    response = auth_client.get(f"/api/sessions/{session_id}")
    assert response.status_code == 404
    assert response.json() == {
        "detail": "Session snapshot not found",
        "error": {
            "code": "SESSION_SNAPSHOT_MISSING",
            "message": "Session snapshot not found",
            "recovery_action": {
                "type": "open_workspace_home",
                "label": "返回工作台首页",
                "target": "/workspace",
            },
        },
    }

    db = testing_session_local()
    try:
        session = db.execute(
            select(ProjectSession).where(ProjectSession.id == session_id),
        ).scalar_one()
        assert session.updated_at == broken_updated_at
    finally:
        db.close()


def test_list_sessions_returns_only_current_user_sessions(client):
    first_user = client.post(
        "/api/auth/register",
        json={"email": "first@example.com", "password": "secret123"},
    )
    assert first_user.status_code == 200
    first_token = first_user.json()["access_token"]

    second_user = client.post(
        "/api/auth/register",
        json={"email": "second@example.com", "password": "secret123"},
    )
    assert second_user.status_code == 200
    second_token = second_user.json()["access_token"]

    first_session = client.post(
        "/api/sessions",
        headers={"Authorization": f"Bearer {first_token}"},
        json={"title": "First Session", "initial_idea": "idea one"},
    )
    assert first_session.status_code == 200

    second_session = client.post(
        "/api/sessions",
        headers={"Authorization": f"Bearer {second_token}"},
        json={"title": "Second Session", "initial_idea": "idea two"},
    )
    assert second_session.status_code == 200

    response = client.get(
        "/api/sessions",
        headers={"Authorization": f"Bearer {first_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["sessions"]) == 1
    assert data["sessions"][0]["title"] == "First Session"


def test_list_sessions_returns_most_recently_active_session_first(
    auth_client,
    testing_session_local,
    monkeypatch,
):
    model_config_id = _create_enabled_model_config(testing_session_local)
    _mock_gateway_reply(monkeypatch)

    first_response = auth_client.post(
        "/api/sessions",
        json={"title": "Old Session", "initial_idea": "idea one"},
    )
    assert first_response.status_code == 200

    second_response = auth_client.post(
        "/api/sessions",
        json={"title": "New Session", "initial_idea": "idea two"},
    )
    assert second_response.status_code == 200

    with auth_client.stream(
        "POST",
        f"/api/sessions/{first_response.json()['session']['id']}/messages",
        json={
            "content": "make this active again",
            "model_config_id": model_config_id,
        },
    ) as response:
        assert response.status_code == 200
        list(response.iter_text())

    response = auth_client.get("/api/sessions")

    assert response.status_code == 200
    data = response.json()
    assert [session["title"] for session in data["sessions"]] == [
        "Old Session",
        "New Session",
    ]


def test_update_session_title_renames_owned_session(auth_client, seeded_session):
    response = auth_client.patch(
        f"/api/sessions/{seeded_session}",
        json={"title": "Renamed Session"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["session"]["id"] == seeded_session
    assert data["session"]["title"] == "Renamed Session"


def test_update_session_title_rejects_blank_title(auth_client, seeded_session):
    response = auth_client.patch(
        f"/api/sessions/{seeded_session}",
        json={"title": "   "},
    )

    assert response.status_code == 422


def test_get_session_includes_messages_in_snapshot(
    auth_client,
    seeded_session,
    testing_session_local,
    monkeypatch,
):
    model_config_id = _create_enabled_model_config(testing_session_local)
    _mock_gateway_reply(monkeypatch)

    with auth_client.stream(
        "POST",
        f"/api/sessions/{seeded_session}/messages",
        json={
            "content": "你好",
            "model_config_id": model_config_id,
        },
    ) as response:
        assert response.status_code == 200
        list(response.iter_text())

    response = auth_client.get(f"/api/sessions/{seeded_session}")
    assert response.status_code == 200
    data = response.json()
    assert "messages" in data
    assert "assistant_reply_groups" in data
    assert "turn_decisions" in data
    assert isinstance(data["messages"], list)
    assert len(data["messages"]) >= 1
    assert data["messages"][0]["role"] in ("user", "assistant")
    assert "content" in data["messages"][0]
    assert isinstance(data["turn_decisions"], list)
    assert len(data["turn_decisions"]) == 1
    assert data["turn_decisions"][0]["session_id"] == seeded_session
    assert data["turn_decisions"][0]["user_message_id"] == data["messages"][0]["id"]
    assert data["turn_decisions"][0]["next_move"]
    assert data["turn_decisions"][0]["decision_summary"]
    assert isinstance(data["turn_decisions"][0]["decision_sections"], list)


def test_get_session_keeps_legacy_messages_when_reply_groups_missing(
    auth_client,
    seeded_session,
    testing_session_local,
):
    db = testing_session_local()
    try:
        user_message = ConversationMessage(
            id=str(uuid4()),
            session_id=seeded_session,
            role="user",
            content="legacy user",
            meta={},
        )
        assistant_message = ConversationMessage(
            id=str(uuid4()),
            session_id=seeded_session,
            role="assistant",
            content="legacy assistant",
            meta={},
        )
        db.add(user_message)
        db.add(assistant_message)
        db.commit()
    finally:
        db.close()

    snapshot = auth_client.get(f"/api/sessions/{seeded_session}")
    assert snapshot.status_code == 200
    data = snapshot.json()

    assert data["assistant_reply_groups"] == []
    assert [message["role"] for message in data["messages"]] == ["user", "assistant"]
    assert data["messages"][1]["content"] == "legacy assistant"
    assert data["messages"][1]["reply_group_id"] is None
    assert data["messages"][1]["version_no"] is None
    assert data["messages"][1]["is_latest"] is None


def test_export_prefers_finalized_prd_draft_over_legacy_snapshot(
    auth_client,
    seeded_session,
    testing_session_local,
):
    db = testing_session_local()
    try:
        session = db.get(ProjectSession, seeded_session)
        assert session is not None

        state_repository.create_state_version(
            db=db,
            session_id=seeded_session,
            version=2,
            state_json={
                **session_service.build_initial_state(session.initial_idea),
                "workflow_stage": "completed",
                "prd_draft": {
                    "version": 3,
                    "status": "finalized",
                    "sections": {
                        "summary": {"title": "一句话概述", "content": "最终版概述", "status": "confirmed"},
                        "target_user": {"title": "目标用户", "content": "最终版用户", "status": "confirmed"},
                        "problem": {"title": "核心问题", "content": "最终版问题", "status": "confirmed"},
                        "solution": {"title": "解决方案", "content": "最终版方案", "status": "confirmed"},
                        "mvp_scope": {"title": "MVP 范围", "content": "最终版范围", "status": "confirmed"},
                    },
                },
                "critic_result": {"overall_verdict": "pass", "question_queue": []},
                "finalization_ready": True,
            },
        )
        prd_repository.create_prd_snapshot(
            db=db,
            session_id=seeded_session,
            version=2,
            sections={
                "target_user": {"title": "目标用户", "content": "旧快照用户", "status": "confirmed"},
            },
        )
        db.commit()
    finally:
        db.close()

    response = auth_client.post(
        f"/api/sessions/{seeded_session}/export",
        json={"format": "md"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "状态：终稿" in data["content"]
    assert "最终版用户" in data["content"]
    assert "旧快照用户" not in data["content"]


def test_export_returns_draft_status_when_not_finalized(
    auth_client,
    seeded_session,
    testing_session_local,
):
    db = testing_session_local()
    try:
        session = db.get(ProjectSession, seeded_session)
        assert session is not None

        state_repository.create_state_version(
            db=db,
            session_id=seeded_session,
            version=2,
            state_json={
                **session_service.build_initial_state(session.initial_idea),
                "workflow_stage": "refine_loop",
                "prd_draft": {
                    "version": 2,
                    "status": "draft_refined",
                    "sections": {
                        "target_user": {"title": "目标用户", "content": "草稿用户", "status": "confirmed"},
                        "problem": {"title": "核心问题", "content": "草稿问题", "status": "confirmed"},
                    },
                },
                "critic_result": {"overall_verdict": "revise", "question_queue": ["还缺成功指标"]},
                "finalization_ready": False,
            },
        )
        db.commit()
    finally:
        db.close()

    response = auth_client.post(
        f"/api/sessions/{seeded_session}/export",
        json={"format": "md"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "状态：草稿" in data["content"]
    assert "草稿用户" in data["content"]


def test_finalize_route_moves_ready_session_to_completed(
    auth_client,
    seeded_session,
    testing_session_local,
):
    db = testing_session_local()
    try:
        session = db.get(ProjectSession, seeded_session)
        assert session is not None
        state_repository.create_state_version(
            db=db,
            session_id=seeded_session,
            version=2,
            state_json={
                **session_service.build_initial_state(session.initial_idea),
                "workflow_stage": "finalize",
                "finalization_ready": True,
                "prd_draft": {
                    "version": 2,
                    "status": "draft_refined",
                    "sections": {
                        "summary": {"title": "一句话概述", "content": "最终版概述", "status": "draft"},
                        "target_user": {"title": "目标用户", "content": "产品经理", "status": "confirmed"},
                        "problem": {"title": "核心问题", "content": "需求沟通低效", "status": "confirmed"},
                        "solution": {"title": "解决方案", "content": "结构化协作", "status": "confirmed"},
                        "mvp_scope": {"title": "MVP 范围", "content": "会话 + 导出", "status": "confirmed"},
                    },
                },
            },
        )
        prd_repository.create_prd_snapshot(
            db=db,
            session_id=seeded_session,
            version=2,
            sections={},
        )
        db.commit()
    finally:
        db.close()

    response = auth_client.post(
        f"/api/sessions/{seeded_session}/finalize",
        json={"confirmation_source": "button", "preference": "business"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["state"]["workflow_stage"] == "completed"
    assert data["state"]["prd_draft"]["status"] == "finalized"
    assert data["state"]["finalize_confirmation_source"] == "button"
    assert data["state"]["finalize_preference"] == "business"

    db = testing_session_local()
    try:
        latest_state = state_repository.get_latest_state_version(db, seeded_session)
        assert latest_state is not None
        assert latest_state.state_json["finalize_confirmation_source"] == "button"
    finally:
        db.close()


def test_finalize_route_rejects_invalid_confirmation_source(
    auth_client,
    seeded_session,
    testing_session_local,
):
    db = testing_session_local()
    try:
        session = db.get(ProjectSession, seeded_session)
        assert session is not None
        state_repository.create_state_version(
            db=db,
            session_id=seeded_session,
            version=2,
            state_json={
                **session_service.build_initial_state(session.initial_idea),
                "workflow_stage": "finalize",
                "finalization_ready": True,
            },
        )
        prd_repository.create_prd_snapshot(
            db=db,
            session_id=seeded_session,
            version=2,
            sections={},
        )
        db.commit()
    finally:
        db.close()

    response = auth_client.post(
        f"/api/sessions/{seeded_session}/finalize",
        json={"confirmation_source": "invalid"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "FINALIZE_CONFIRMATION_REQUIRED"


def test_delete_session_removes_owned_session(auth_client, seeded_session):
    response = auth_client.delete(f"/api/sessions/{seeded_session}")

    assert response.status_code == 204

    sessions_response = auth_client.get("/api/sessions")
    assert sessions_response.status_code == 200
    data = sessions_response.json()
    assert [session["id"] for session in data["sessions"]] == []
