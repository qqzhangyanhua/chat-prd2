import json

from sqlalchemy import select

from app.db.models import ConversationMessage


def test_message_stream_emits_progress_and_persists_messages(
    auth_client,
    seeded_session,
    testing_session_local,
):
    with auth_client.stream(
        "POST",
        f"/api/sessions/{seeded_session}/messages",
        json={"content": "help me think through the target user"},
    ) as response:
        assert response.status_code == 200
        chunks = list(response.iter_text())

    body = "".join(chunks)
    assert "message.accepted" in body
    assert "action.decided" in body
    assert "assistant.delta" in body
    assert "assistant.done" in body

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
    assert assistant_message.meta["action"]["action"] == "probe_deeper"

    delta_line = next(
        line for line in body.splitlines() if line.startswith("data: ") and "delta" in line
    )
    delta_payload = json.loads(delta_line.removeprefix("data: "))
    assert delta_payload["delta"] == assistant_message.content


def test_message_stream_returns_404_for_other_users_session(client, auth_client, seeded_session):
    intruder_response = client.post(
        "/api/auth/register",
        json={"email": "intruder@example.com", "password": "secret123"},
    )
    assert intruder_response.is_success
    intruder_token = intruder_response.json()["access_token"]

    response = client.post(
        f"/api/sessions/{seeded_session}/messages",
        json={"content": "steal access"},
        headers={"Authorization": f"Bearer {intruder_token}"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Session not found"}
