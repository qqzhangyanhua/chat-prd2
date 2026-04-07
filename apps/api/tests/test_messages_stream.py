import json

from sqlalchemy import select

from app.db.models import AssistantReplyGroup
from app.db.models import AssistantReplyVersion
from app.db.models import AgentTurnDecision
from app.db.models import ConversationMessage
from app.repositories import model_configs as model_configs_repository


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
    assert response.json() == {"detail": "Session not found"}


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
            base_url="https://gateway.example.com/v1",
            api_key="secret",
            model="gpt-4o-mini",
            enabled=False,
        )
        db.commit()
        model_config_id = model_config.id
    finally:
        db.close()

    response = auth_client.post(
        f"/api/sessions/{seeded_session}/messages",
        json={"content": "should fail", "model_config_id": model_config_id},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Model config is disabled"}


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
