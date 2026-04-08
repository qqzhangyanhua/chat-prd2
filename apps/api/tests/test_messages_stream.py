import json

from sqlalchemy import select

from app.db.models import AssistantReplyGroup
from app.db.models import AssistantReplyVersion
from app.db.models import AgentTurnDecision
from app.db.models import ConversationMessage
from app.db.models import ProjectSession
from app.repositories import model_configs as model_configs_repository
from app.repositories import prd as prd_repository
from app.repositories import state as state_repository
from app.services import sessions as session_service


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
        db.commit()
        model_config_id = model_config.id
    finally:
        db.close()

    class FakeReplyStream:
        def __iter__(self):
            yield "这是"
            yield "流式"
            yield "回复"

        def close(self):
            return None

    def fake_open_reply_stream(*, base_url, api_key, model, messages):
        assert base_url == "https://gateway.example.com/v1"
        assert api_key == "secret"
        assert model == "gpt-4o-mini"
        assert messages == [
            {"role": "system", "content": "你是用户的 AI 产品协作助手，请基于上下文给出简洁、直接的中文回复。"},
            {"role": "user", "content": "help me think through the target user"},
        ]
        return FakeReplyStream()

    monkeypatch.setattr("app.services.messages.open_reply_stream", fake_open_reply_stream)

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
    assert body.count("event: assistant.delta") == 3
    parsed_events = _parse_sse_events(body)
    event_order = [name for name, _ in parsed_events]
    assert event_order[:4] == [
        "message.accepted",
        "reply_group.created",
        "action.decided",
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
    assert assistant_message.meta["display_name"] == "流式模型"
    assert assistant_message.meta["base_url"] == "https://gateway.example.com/v1"

    delta_payloads = [
        payload
        for name, payload in parsed_events
        if name == "assistant.delta"
    ]
    assert [payload["delta"] for payload in delta_payloads] == ["这是", "流式", "回复"]
    assert all(payload["assistant_version_id"] for payload in delta_payloads)
    assert all(payload["is_regeneration"] is False for payload in delta_payloads)
    assert all(payload["is_latest"] is False for payload in delta_payloads)
    started_payload = next(payload for name, payload in parsed_events if name == "assistant.version.started")
    done_payload = next(payload for name, payload in parsed_events if name == "assistant.done")
    assert started_payload["assistant_version_id"] == done_payload["assistant_version_id"]
    assert done_payload["is_regeneration"] is False
    assert done_payload["is_latest"] is True
    assert assistant_message.content == "这是流式回复"
    decision = db.execute(
        select(AgentTurnDecision).where(
            AgentTurnDecision.user_message_id == user_message.id
        )
    ).scalar_one_or_none()
    assert decision is not None
    assert assistant_message.meta["action"]["action"] == decision.next_move or decision.next_move in {
        "probe_for_specificity",
        "assume_and_advance",
        "challenge_and_reframe",
        "summarize_and_confirm",
        "force_rank_or_choose",
    }


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


def test_message_stream_uses_local_correction_reply_without_opening_gateway_stream(
    auth_client,
    seeded_session,
    testing_session_local,
    monkeypatch,
):
    db = testing_session_local()
    try:
        model_config = model_configs_repository.create_model_config(
            db,
            name="修正流式模型",
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
                "target_user": "独立创业者",
                "problem": "不知道先验证哪个需求",
                "solution": "通过连续追问沉淀结构化 PRD",
                "mvp_scope": ["创建会话", "持续追问", "导出 PRD"],
                "conversation_strategy": "confirm",
                "pending_confirmations": ["目标用户是否准确"],
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

    def fail_open_reply_stream(**_kwargs):
        raise AssertionError("correction command should not call open_reply_stream")

    monkeypatch.setattr("app.services.messages.open_reply_stream", fail_open_reply_stream)

    with auth_client.stream(
        "POST",
        f"/api/sessions/{seeded_session}/messages",
        json={
            "content": "不对，先改目标用户",
            "model_config_id": model_config_id,
        },
    ) as response:
        assert response.status_code == 200
        body = "".join(response.iter_text())

    parsed_events = _parse_sse_events(body)
    delta_payloads = [payload for name, payload in parsed_events if name == "assistant.delta"]
    assert delta_payloads
    assert "我先回滚当前关于目标用户及其后续共识" in "".join(
        payload["delta"] for payload in delta_payloads
    )


def test_message_stream_uses_local_confirm_continue_reply_without_opening_gateway_stream(
    auth_client,
    seeded_session,
    testing_session_local,
    monkeypatch,
):
    db = testing_session_local()
    try:
        model_config = model_configs_repository.create_model_config(
            db,
            name="确认推进流式模型",
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
                "target_user": "独立创业者",
                "problem": "不知道先验证哪个需求",
                "solution": "通过连续追问沉淀结构化 PRD",
                "mvp_scope": ["创建会话", "持续追问", "导出 PRD"],
                "conversation_strategy": "confirm",
                "pending_confirmations": ["目标用户是否准确"],
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

    def fail_open_reply_stream(**_kwargs):
        raise AssertionError("confirm continue command should not call open_reply_stream")

    monkeypatch.setattr("app.services.messages.open_reply_stream", fail_open_reply_stream)

    with auth_client.stream(
        "POST",
        f"/api/sessions/{seeded_session}/messages",
        json={
            "content": "确认，继续下一步",
            "model_config_id": model_config_id,
        },
    ) as response:
        assert response.status_code == 200
        body = "".join(response.iter_text())

    parsed_events = _parse_sse_events(body)
    delta_payloads = [payload for name, payload in parsed_events if name == "assistant.delta"]
    assert delta_payloads
    assert "我先锁定当前关于目标用户、核心问题、解决方案、MVP 范围的共识" in "".join(
        payload["delta"] for payload in delta_payloads
    )


def test_message_stream_uses_specific_local_confirm_reply_without_opening_gateway_stream(
    auth_client,
    seeded_session,
    testing_session_local,
    monkeypatch,
):
    db = testing_session_local()
    try:
        model_config = model_configs_repository.create_model_config(
            db,
            name="确认细分推进流式模型",
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
                "target_user": "独立创业者",
                "problem": "不知道先验证哪个需求",
                "solution": "通过连续追问沉淀结构化 PRD",
                "mvp_scope": ["创建会话", "持续追问", "导出 PRD"],
                "conversation_strategy": "confirm",
                "pending_confirmations": ["目标用户是否准确"],
            },
        )
        db.commit()
        model_config_id = model_config.id
    finally:
        db.close()

    def fail_open_reply_stream(**_kwargs):
        raise AssertionError("specific confirm command should not call open_reply_stream")

    monkeypatch.setattr("app.services.messages.open_reply_stream", fail_open_reply_stream)

    with auth_client.stream(
        "POST",
        f"/api/sessions/{seeded_session}/messages",
        json={
            "content": "确认，先看转化阻力",
            "model_config_id": model_config_id,
        },
    ) as response:
        assert response.status_code == 200
        body = "".join(response.iter_text())

    parsed_events = _parse_sse_events(body)
    delta_payloads = [payload for name, payload in parsed_events if name == "assistant.delta"]
    assert delta_payloads
    assert "我会先把讨论推进到“转化阻力验证”" in "".join(
        payload["delta"] for payload in delta_payloads
    )


def test_message_stream_keeps_frequency_validation_in_local_stable_flow(
    auth_client,
    seeded_session,
    testing_session_local,
    monkeypatch,
):
    db = testing_session_local()
    try:
        model_config = model_configs_repository.create_model_config(
            db,
            name="频率验证流式模型",
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
                "target_user": "独立创业者",
                "problem": "不知道先验证哪个需求",
                "solution": "通过连续追问沉淀结构化 PRD",
                "mvp_scope": ["创建会话", "持续追问", "导出 PRD"],
                "conversation_strategy": "converge",
                "phase_goal": "明确问题发生频率是否足够高",
                "stage_hint": "推进频率验证",
                "validation_focus": "frequency",
                "validation_step": 1,
            },
        )
        db.commit()
        model_config_id = model_config.id
    finally:
        db.close()

    def fail_open_reply_stream(**_kwargs):
        raise AssertionError("frequency validation follow-up should not call open_reply_stream")

    monkeypatch.setattr("app.services.messages.open_reply_stream", fail_open_reply_stream)

    with auth_client.stream(
        "POST",
        f"/api/sessions/{seeded_session}/messages",
        json={
            "content": "最近几乎每天都会发生，尤其在准备新需求评审时",
            "model_config_id": model_config_id,
        },
    ) as response:
        assert response.status_code == 200
        body = "".join(response.iter_text())

    parsed_events = _parse_sse_events(body)
    delta_payloads = [payload for name, payload in parsed_events if name == "assistant.delta"]
    assert delta_payloads
    assert "我先按你的描述把当前判断收成“这是一个高频信号候选”" in "".join(
        payload["delta"] for payload in delta_payloads
    )


def test_message_stream_keeps_conversion_resistance_validation_in_local_stable_flow(
    auth_client,
    seeded_session,
    testing_session_local,
    monkeypatch,
):
    db = testing_session_local()
    try:
        model_config = model_configs_repository.create_model_config(
            db,
            name="转化阻力验证流式模型",
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
                "target_user": "独立创业者",
                "problem": "不知道先验证哪个需求",
                "solution": "通过连续追问沉淀结构化 PRD",
                "mvp_scope": ["创建会话", "持续追问", "导出 PRD"],
                "conversation_strategy": "converge",
                "phase_goal": "明确转化阻力集中在哪一环",
                "stage_hint": "推进转化阻力验证",
                "validation_focus": "conversion_resistance",
                "validation_step": 1,
            },
        )
        db.commit()
        model_config_id = model_config.id
    finally:
        db.close()

    def fail_open_reply_stream(**_kwargs):
        raise AssertionError("conversion resistance follow-up should not call open_reply_stream")

    monkeypatch.setattr("app.services.messages.open_reply_stream", fail_open_reply_stream)

    with auth_client.stream(
        "POST",
        f"/api/sessions/{seeded_session}/messages",
        json={
            "content": "大多数人会卡在第一次接入，不知道要准备什么资料",
            "model_config_id": model_config_id,
        },
    ) as response:
        assert response.status_code == 200
        body = "".join(response.iter_text())

    parsed_events = _parse_sse_events(body)
    delta_payloads = [payload for name, payload in parsed_events if name == "assistant.delta"]
    assert delta_payloads
    assert "我先按你的描述把当前阻力判断收成“首要阻力候选已经出现”" in "".join(
        payload["delta"] for payload in delta_payloads
    )


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

    class InitialReplyStream:
        def __iter__(self):
            yield "初始"
            yield "回复"

        def close(self):
            return None

    monkeypatch.setattr("app.services.messages.open_reply_stream", lambda **_: InitialReplyStream())
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

    class RegenerateReplyStream:
        def __iter__(self):
            yield "重生"
            yield "成"
            yield "版本"

        def close(self):
            return None

    monkeypatch.setattr("app.services.messages.open_reply_stream", lambda **_: RegenerateReplyStream())
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
    assert "prd.updated" not in body
    assert "message.accepted" not in body
    parsed_events = _parse_sse_events(body)
    event_order = [name for name, _ in parsed_events]
    assert event_order[:2] == ["action.decided", "assistant.version.started"]
    assert event_order[-1] == "assistant.done"
    delta_payloads = [
        payload
        for name, payload in parsed_events
        if name == "assistant.delta"
    ]
    assert all(payload["assistant_version_id"] for payload in delta_payloads)
    assert all(payload["is_regeneration"] is True for payload in delta_payloads)
    assert all(payload["is_latest"] is False for payload in delta_payloads)
    done_payload = next(payload for name, payload in parsed_events if name == "assistant.done")
    assert done_payload["assistant_version_id"]
    assert done_payload["is_regeneration"] is True
    assert done_payload["is_latest"] is True

    db = testing_session_local()
    try:
        decisions_before = db.execute(
            select(AgentTurnDecision).where(
                AgentTurnDecision.session_id == seeded_session
            )
        ).scalars().all()
        messages = db.execute(
            select(ConversationMessage)
            .where(ConversationMessage.session_id == seeded_session)
        ).scalars().all()
        reply_group = db.execute(
            select(AssistantReplyGroup)
            .where(AssistantReplyGroup.session_id == seeded_session)
            .where(AssistantReplyGroup.user_message_id == user_message.id)
        ).scalar_one()
        versions = db.execute(
            select(AssistantReplyVersion)
            .where(AssistantReplyVersion.reply_group_id == reply_group.id)
            .order_by(AssistantReplyVersion.version_no.asc())
        ).scalars().all()
        decisions_after = db.execute(
            select(AgentTurnDecision).where(
                AgentTurnDecision.session_id == seeded_session
            )
        ).scalars().all()
    finally:
        db.close()

    assert len([message for message in messages if message.role == "user"]) == 1
    assert len([message for message in messages if message.role == "assistant"]) == 1
    assert len(versions) == 2
    assert [version.version_no for version in versions] == [1, 2]
    assert versions[1].content == "重生成版本"
    assert len(decisions_before) == 1
    assert len(decisions_after) == 1
