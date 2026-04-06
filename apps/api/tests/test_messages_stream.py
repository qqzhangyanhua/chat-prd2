import json

from sqlalchemy import select

from app.db.models import ConversationMessage
from app.repositories import model_configs as model_configs_repository


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
    assert "action.decided" in body
    assert "assistant.delta" in body
    assert "assistant.done" in body
    assert body.count("event: assistant.delta") == 3

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
        json.loads(line.removeprefix("data: "))
        for line in body.splitlines()
        if line.startswith("data: ") and "delta" in line
    ]
    assert [payload["delta"] for payload in delta_payloads] == ["这是", "流式", "回复"]
    assert assistant_message.content == "这是流式回复"


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
