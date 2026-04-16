import json

from sqlalchemy import select

from app.db.models import AssistantReplyGroup
from app.db.models import AssistantReplyVersion
from app.db.models import AgentTurnDecision
from app.db.models import ConversationMessage
from app.db.models import ProjectSession
from app.db.models import ProjectStateVersion
from app.repositories import model_configs as model_configs_repository
from app.repositories import prd as prd_repository
from app.repositories import state as state_repository
from app.services import sessions as session_service
from app.services.model_gateway import ModelGatewayError


def _parse_sse_events(body: str) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    current_event = None
    for line in body.splitlines():
        if line.startswith("event: "):
            current_event = line.removeprefix("event: ").strip()
            continue
        if line.startswith("data: ") and current_event is not None:
            events.append((current_event, json.loads(line.removeprefix("data: "))))
            current_event = None
    return events


def _fake_pm_mentor_llm_response() -> dict:
    return {
        "observation": "用户在探索目标用户",
        "challenge": "目标用户是否足够聚焦？",
        "suggestion": "先聚焦核心场景",
        "question": "你的目标用户最常遇到的核心问题是什么？",
        "reply": "我注意到你在探索目标用户。目标用户是否足够聚焦？先聚焦核心场景。你的目标用户最常遇到的核心问题是什么？",
        "prd_updates": {},
        "confidence": "medium",
        "next_focus": "problem",
    }


def test_message_stream_emits_progress_and_persists_messages(
    auth_client,
    seeded_session,
    testing_session_local,
    monkeypatch,
):
    db = testing_session_local()
    try:
        model_config = model_configs_repository.create_model_config(
            db,
            name="流式模型",
            base_url="https://gateway.example.com/v1",
            api_key="secret",
            model="gpt-4o-mini",
            enabled=True,
        )
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
        model_config_id = model_config.id
    finally:
        db.close()

    monkeypatch.setattr(
        "app.agent.pm_mentor.call_pm_mentor_llm",
        lambda **_: _fake_pm_mentor_llm_response(),
    )

    with auth_client.stream(
        "POST",
        f"/api/sessions/{seeded_session}/messages",
        json={
            "content": "help me think through the target user",
            "model_config_id": model_config_id,
        },
    ) as response:
        assert response.status_code == 200
        chunks = list(response.iter_text())

    body = "".join(chunks)
    assert "message.accepted" in body
    assert "reply_group.created" in body
    assert "action.decided" in body
    assert "assistant.version.started" in body
    assert "assistant.delta" in body
    assert "assistant.done" in body
    parsed_events = _parse_sse_events(body)
    event_order = [name for name, _ in parsed_events]
    assert event_order[:5] == [
        "message.accepted",
        "reply_group.created",
        "action.decided",
        "decision.ready",
        "assistant.version.started",
    ]
    assert event_order[-1] == "assistant.done"

    db = testing_session_local()
    try:
        messages = db.execute(
            select(ConversationMessage)
            .where(ConversationMessage.session_id == seeded_session)
            .order_by(ConversationMessage.role.asc())
        ).scalars().all()
        decision = db.execute(
            select(AgentTurnDecision).where(
                AgentTurnDecision.session_id == seeded_session
            )
        ).scalar_one_or_none()
    finally:
        db.close()

    assert len(messages) == 2

    user_message = next(message for message in messages if message.role == "user")
    assistant_message = next(message for message in messages if message.role == "assistant")

    assert user_message.content == "help me think through the target user"
    assert user_message.meta == {
        "model_config_id": model_config_id,
        "model_name": "gpt-4o-mini",
        "display_name": "流式模型",
        "base_url": "https://gateway.example.com/v1",
    }
    assert assistant_message.meta["action"]["action"] == "probe_deeper"
    assert assistant_message.meta["model_config_id"] == model_config_id
    assert assistant_message.meta["model_name"] == "gpt-4o-mini"
    assert "我注意到你在探索目标用户" in assistant_message.content

    delta_payloads = [
        payload
        for name, payload in parsed_events
        if name == "assistant.delta"
    ]
    assert delta_payloads
    assert all(payload["assistant_version_id"] for payload in delta_payloads)
    assert all(payload["is_regeneration"] is False for payload in delta_payloads)

    done_payload = next(payload for name, payload in parsed_events if name == "assistant.done")
    assert done_payload["is_regeneration"] is False
    assert done_payload["is_latest"] is True

    assert decision is not None
    assert decision.state_patch_json["diagnostics"]
    assert decision.state_patch_json["diagnostic_summary"]["open_count"] >= 1


def test_message_stream_emits_decision_ready_with_structured_guidance(
    auth_client,
    seeded_session,
    testing_session_local,
    monkeypatch,
):
    db = testing_session_local()
    try:
        model_config = model_configs_repository.create_model_config(
            db,
            name="结构化 guidance 模型",
            base_url="https://gateway.example.com/v1",
            api_key="secret",
            model="gpt-4o-mini",
            enabled=True,
        )
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
        model_config_id = model_config.id
    finally:
        db.close()

    monkeypatch.setattr(
        "app.agent.pm_mentor.call_pm_mentor_llm",
        lambda **_: _fake_pm_mentor_llm_response(),
    )

    with auth_client.stream(
        "POST",
        f"/api/sessions/{seeded_session}/messages",
        json={
            "content": "help me think through the target user",
            "model_config_id": model_config_id,
        },
    ) as response:
        assert response.status_code == 200
        body = "".join(response.iter_text())

    parsed_events = _parse_sse_events(body)
    event_order = [name for name, _ in parsed_events]
    guidance_payload = next(payload for name, payload in parsed_events if name == "decision.ready")

    assert event_order[:5] == [
        "message.accepted",
        "reply_group.created",
        "action.decided",
        "decision.ready",
        "assistant.version.started",
    ]
    assert guidance_payload["phase"] == "problem"
    assert guidance_payload["conversation_strategy"] == "clarify"
    assert guidance_payload["next_move"] == "probe_for_specificity"
    assert guidance_payload["response_mode"] == "options_first"
    assert guidance_payload["guidance_mode"] == "explore"
    assert guidance_payload["guidance_step"] == "choose"
    assert guidance_payload["focus_dimension"] == "problem"
    assert guidance_payload["transition_trigger"] == "high_uncertainty"
    assert guidance_payload["transition_reason"]
    assert len(guidance_payload["option_cards"]) == 4
    assert guidance_payload["freeform_affordance"] == {
        "label": "都不对，我补充",
        "value": "freeform",
        "kind": "freeform",
    }
    assert guidance_payload["available_mode_switches"]
    assert len(guidance_payload["suggestions"]) == 4
    assert guidance_payload["recommendation"]["label"]
    assert guidance_payload["next_best_questions"] == [
        item["content"] for item in guidance_payload["suggestions"]
    ]
    assert guidance_payload["option_cards"][0]["id"]
    assert guidance_payload["diagnostics"]
    assert guidance_payload["diagnostic_summary"]["open_count"] >= 1
    assert guidance_payload["ledger_summary"]["open_count"] >= guidance_payload["diagnostic_summary"]["open_count"]


def test_message_stream_emits_draft_updated_without_polluting_prd_updated(
    auth_client,
    seeded_session,
    testing_session_local,
    monkeypatch,
):
    db = testing_session_local()
    try:
        model_config = model_configs_repository.create_model_config(
            db,
            name="首稿事件模型",
            base_url="https://gateway.example.com/v1",
            api_key="secret",
            model="gpt-4o-mini",
            enabled=True,
        )
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
        model_config_id = model_config.id
    finally:
        db.close()

    monkeypatch.setattr(
        "app.agent.pm_mentor.call_pm_mentor_llm",
        lambda **_: {
            **_fake_pm_mentor_llm_response(),
            "prd_updates": {
                "target_user": {"content": "独立开发者", "status": "confirmed"},
                "success_metrics": {"content": "7 天内完成一次 PRD 初稿", "status": "draft"},
            },
        },
    )

    with auth_client.stream(
        "POST",
        f"/api/sessions/{seeded_session}/messages",
        json={
            "content": "我想先服务独立开发者。",
            "model_config_id": model_config_id,
        },
    ) as response:
        assert response.status_code == 200
        body = "".join(response.iter_text())

    parsed_events = _parse_sse_events(body)
    event_order = [name for name, _ in parsed_events]
    draft_payload = next(payload for name, payload in parsed_events if name == "draft.updated")
    prd_payload = next(payload for name, payload in parsed_events if name == "prd.updated")

    assert event_order[:6] == [
        "message.accepted",
        "reply_group.created",
        "action.decided",
        "decision.ready",
        "draft.updated",
        "assistant.version.started",
    ]
    assert draft_payload["sections"]["target_user"]["entries"][0]["assertion_state"] == "confirmed"
    assert draft_payload["evidence_registry"][0]["kind"] in {"user_message", "system_inference"}
    assert draft_payload["sections_changed"] == ["target_user", "success_metrics"]
    assert draft_payload["entry_ids"]
    assert "evidence_registry" not in prd_payload
    assert prd_payload["sections_changed"] == ["target_user", "success_metrics"]
    assert "problem" in prd_payload["missing_sections"]
    assert isinstance(prd_payload["gap_prompts"], list)
    assert prd_payload["ready_for_confirmation"] is False
    assert "risks_to_validate" in prd_payload["sections"]
    assert "open_questions" in prd_payload["sections"]
    assert prd_payload["sections"]["target_user"]["title"] == "目标用户"
    assert prd_payload["sections"]["success_metrics"]["title"] == "成功指标"


def test_message_stream_finalize_action_moves_session_to_completed(
    auth_client,
    seeded_session,
    testing_session_local,
):
    db = testing_session_local()
    try:
        model_config = model_configs_repository.create_model_config(
            db,
            name="终稿确认模型",
            base_url="https://gateway.example.com/v1",
            api_key="secret",
            model="gpt-4o-mini",
            enabled=True,
        )
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
                        "summary": {"title": "一句话概述", "content": "智能需求助手", "status": "draft"},
                        "target_user": {"title": "目标用户", "content": "产品经理", "status": "confirmed"},
                        "problem": {"title": "核心问题", "content": "需求沟通效率低", "status": "confirmed"},
                        "solution": {"title": "解决方案", "content": "结构化澄清流程", "status": "confirmed"},
                        "mvp_scope": {"title": "MVP 范围", "content": "会话、总结、导出", "status": "confirmed"},
                        "constraints": {"title": "约束条件", "content": "两周内上线", "status": "confirmed"},
                        "success_metrics": {"title": "成功指标", "content": "7 天内完成可确认初稿", "status": "confirmed"},
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
        model_config_id = model_config.id
    finally:
        db.close()

    with auth_client.stream(
        "POST",
        f"/api/sessions/{seeded_session}/messages",
        json={
            "content": "确认设计，按技术版输出最终版",
            "model_config_id": model_config_id,
        },
    ) as response:
        assert response.status_code == 200
        chunks = list(response.iter_text())

    parsed_events = _parse_sse_events("".join(chunks))
    action_payload = next(payload for name, payload in parsed_events if name == "action.decided")
    done_payload = next(payload for name, payload in parsed_events if name == "assistant.done")
    prd_payload = next(payload for name, payload in parsed_events if name == "prd.updated")
    assert action_payload["action"] == "finalize"

    db = testing_session_local()
    try:
        latest_state = state_repository.get_latest_state_version(db, seeded_session)
        reply_group = db.execute(
            select(AssistantReplyGroup).where(AssistantReplyGroup.session_id == seeded_session)
        ).scalar_one()
        latest_reply_version = db.execute(
            select(AssistantReplyVersion).where(AssistantReplyVersion.id == reply_group.latest_version_id)
        ).scalar_one()
        state_versions = db.execute(
            select(ProjectStateVersion).where(ProjectStateVersion.session_id == seeded_session)
        ).scalars().all()
        assert latest_state is not None
        assert latest_state.state_json["workflow_stage"] == "completed"
        assert latest_state.state_json["finalize_confirmation_source"] == "message"
        assert latest_state.state_json["prd_draft"]["status"] == "finalized"
        assert latest_reply_version.state_version_id == latest_state.id
        assert latest_reply_version.prd_snapshot_version == latest_state.version
        assert len(state_versions) == 3
        assert done_payload["prd_snapshot_version"] == latest_state.version
    finally:
        db.close()

    assert prd_payload["meta"]["stageLabel"] == "已生成终稿"
    assert prd_payload["meta"]["stageTone"] == "final"
    assert "最终版" in prd_payload["meta"]["criticSummary"]
    assert prd_payload["meta"]["draftVersion"] == done_payload["prd_snapshot_version"]


def test_message_stream_returns_404_for_other_users_session(client, auth_client, seeded_session):
    intruder_response = client.post(
        "/api/auth/register",
        json={"email": "intruder@example.com", "password": "secret123"},
    )
    assert intruder_response.is_success
    intruder_token = intruder_response.json()["access_token"]

    response = client.post(
        f"/api/sessions/{seeded_session}/messages",
        json={"content": "steal access", "model_config_id": "config-1"},
        headers={"Authorization": f"Bearer {intruder_token}"},
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Session not found",
        "error": {
            "code": "SESSION_NOT_FOUND",
            "message": "Session not found",
            "recovery_action": {
                "type": "open_workspace_home",
                "label": "返回工作台首页",
                "target": "/workspace",
            },
        },
    }


def test_message_stream_rejects_missing_model_config_id(auth_client, seeded_session):
    response = auth_client.post(
        f"/api/sessions/{seeded_session}/messages",
        json={"content": "missing model config"},
    )

    assert response.status_code == 422
    assert any(
        error["loc"][-1] == "model_config_id"
        for error in response.json()["detail"]
    )


def test_message_stream_rejects_disabled_model_config(
    auth_client,
    seeded_session,
    testing_session_local,
):
    db = testing_session_local()
    try:
        model_config = model_configs_repository.create_model_config(
            db,
            name="禁用流式模型",
            recommended_scene="reasoning",
            recommended_usage="适合承接长文本推理。",
            base_url="https://gateway.example.com/v1",
            api_key="secret",
            model="gpt-4o-mini",
            enabled=False,
        )
        general_model = model_configs_repository.create_model_config(
            db,
            name="通用候选模型",
            recommended_scene="general",
            recommended_usage="适合继续通用产品对话。",
            base_url="https://gateway.example.com/v1",
            api_key="secret",
            model="gpt-4o-mini",
            enabled=True,
        )
        fallback_model = model_configs_repository.create_model_config(
            db,
            name="推荐流式模型",
            recommended_scene="reasoning",
            recommended_usage="适合承接长文本推理。",
            base_url="https://gateway.example.com/v1",
            api_key="secret",
            model="claude-3-7-sonnet",
            enabled=True,
        )
        db.commit()
        model_config_id = model_config.id
        general_model_id = general_model.id
        fallback_model_id = fallback_model.id
    finally:
        db.close()

    response = auth_client.post(
        f"/api/sessions/{seeded_session}/messages",
        json={"content": "should fail", "model_config_id": model_config_id},
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Model config is disabled",
        "error": {
            "code": "MODEL_CONFIG_DISABLED",
            "message": "Model config is disabled",
                "details": {
                    "available_model_configs": [
                        {
                            "id": fallback_model_id,
                            "name": "推荐流式模型",
                            "model": "claude-3-7-sonnet",
                        },
                        {
                            "id": general_model_id,
                            "name": "通用候选模型",
                            "model": "gpt-4o-mini",
                        },
                    ],
                    "recommended_model_config_id": fallback_model_id,
                    "recommended_model_scene": "reasoning",
                    "recommended_model_name": "推荐流式模型",
                "recommended_model_reason": "原先选择的模型已停用，建议先切换到这个可用模型继续对话。适合承接长文本推理。",
                "requested_model_config_id": model_config_id,
                "requested_model_name": "禁用流式模型",
            },
            "recovery_action": {
                "type": "select_available_model",
                "label": "选择可用模型",
                "target": None,
            },
        },
    }


def test_regenerate_stream_emits_regenerate_events_and_does_not_create_user_message(
    auth_client,
    seeded_session,
    testing_session_local,
    monkeypatch,
):
    db = testing_session_local()
    try:
        model_config = model_configs_repository.create_model_config(
            db,
            name="重生成流式模型",
            base_url="https://gateway.example.com/v1",
            api_key="secret",
            model="gpt-4o-mini",
            enabled=True,
        )
        db.commit()
        model_config_id = model_config.id
    finally:
        db.close()

    monkeypatch.setattr(
        "app.agent.pm_mentor.call_pm_mentor_llm",
        lambda **_: _fake_pm_mentor_llm_response(),
    )

    with auth_client.stream(
        "POST",
        f"/api/sessions/{seeded_session}/messages",
        json={
            "content": "请先生成第一版",
            "model_config_id": model_config_id,
        },
    ) as response:
        assert response.status_code == 200
        list(response.iter_text())

    db = testing_session_local()
    try:
        user_message = db.execute(
            select(ConversationMessage)
            .where(ConversationMessage.session_id == seeded_session)
            .where(ConversationMessage.role == "user")
        ).scalar_one()
    finally:
        db.close()

    with auth_client.stream(
        "POST",
        f"/api/sessions/{seeded_session}/messages/{user_message.id}/regenerate",
        json={"model_config_id": model_config_id},
    ) as response:
        assert response.status_code == 200
        chunks = list(response.iter_text())

    body = "".join(chunks)
    assert "regenerate.accepted" not in body
    assert "action.decided" in body
    assert "assistant.version.started" in body
    assert "assistant.delta" in body
    assert "assistant.done" in body
    assert "prd.updated" in body
    assert "message.accepted" not in body
    parsed_events = _parse_sse_events(body)
    event_order = [name for name, _ in parsed_events]
    assert event_order[:3] == ["action.decided", "decision.ready", "assistant.version.started"]
    assert event_order[-2:] == ["prd.updated", "assistant.done"]
    delta_payloads = [
        payload
        for name, payload in parsed_events
        if name == "assistant.delta"
    ]
    assert delta_payloads
    assert all(payload["assistant_version_id"] for payload in delta_payloads)


def test_message_stream_emits_assistant_error_event_when_gateway_stream_breaks(
    auth_client,
    seeded_session,
    testing_session_local,
    monkeypatch,
):
    db = testing_session_local()
    try:
        model_config = model_configs_repository.create_model_config(
            db,
            name="流式异常模型",
            base_url="https://gateway.example.com/v1",
            api_key="secret",
            model="gpt-4o-mini",
            enabled=True,
        )
        db.commit()
        model_config_id = model_config.id
    finally:
        db.close()

    monkeypatch.setattr(
        "app.agent.pm_mentor.call_pm_mentor_llm",
        lambda **_: _fake_pm_mentor_llm_response(),
    )

    class BrokenReplyStream:
        def __init__(self, _reply: str):
            self._reply = _reply

        def __iter__(self):
            yield "这是"
            raise ModelGatewayError("流式中断")

        def close(self):
            return None

    monkeypatch.setattr("app.services.message_preparation.LocalReplyStream", BrokenReplyStream)

    with auth_client.stream(
        "POST",
        f"/api/sessions/{seeded_session}/messages",
        json={
            "content": "请继续分析这个方向",
            "model_config_id": model_config_id,
        },
    ) as response:
        assert response.status_code == 200
        chunks = list(response.iter_text())

    body = "".join(chunks)
    assert "assistant.error" in body
    parsed_events = _parse_sse_events(body)
    assert parsed_events[-1][0] == "assistant.error"
    assert parsed_events[-1][1]["code"] == "MODEL_STREAM_FAILED"
    assert parsed_events[-1][1]["message"] == "流式中断"
    assert parsed_events[-1][1]["recovery_action"]["type"] == "retry"

    db = testing_session_local()
    try:
        messages = db.execute(
            select(ConversationMessage)
            .where(ConversationMessage.session_id == seeded_session)
        ).scalars().all()
        versions = db.execute(
            select(AssistantReplyVersion)
            .where(AssistantReplyVersion.session_id == seeded_session)
        ).scalars().all()
    finally:
        db.close()

    assert len([message for message in messages if message.role == "user"]) == 1
    assert len([message for message in messages if message.role == "assistant"]) == 0
    assert versions == []
