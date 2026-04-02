def test_message_stream_emits_action_and_done_events(auth_client, seeded_session):
    response = auth_client.post(
        f"/api/sessions/{seeded_session}/messages",
        json={"content": "我想继续聚焦目标用户"},
    )
    assert response.status_code == 200
    body = response.text
    assert "action.decided" in body
    assert "assistant.done" in body
