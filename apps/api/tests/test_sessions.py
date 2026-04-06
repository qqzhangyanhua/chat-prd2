import json
from uuid import uuid4

from sqlalchemy import select

from app.db.models import ConversationMessage, PrdSnapshot, ProjectSession, ProjectStateVersion
from app.repositories import model_configs as model_configs_repository
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


def _mock_gateway_reply(monkeypatch, reply: str = "这是测试回复") -> None:
    class FakeReplyStream:
        def __iter__(self):
            yield reply

        def close(self):
            return None

    def fake_open_reply_stream(*, base_url, api_key, model, messages):
        return FakeReplyStream()

    monkeypatch.setattr("app.services.messages.open_reply_stream", fake_open_reply_stream)


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


def test_get_session_returns_latest_snapshot(auth_client, seeded_session):
    response = auth_client.get(f"/api/sessions/{seeded_session}")

    assert response.status_code == 200
    data = response.json()
    assert data["session"]["id"] == seeded_session
    assert data["state"]["idea"]
    assert "sections" in data["prd_snapshot"]
    assert "assistant_reply_groups" in data


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
    assert response.json()["detail"] == "Session snapshot not found"

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
    assert isinstance(data["messages"], list)
    assert len(data["messages"]) >= 1
    assert data["messages"][0]["role"] in ("user", "assistant")
    assert "content" in data["messages"][0]


def test_get_session_returns_assistant_reply_groups_and_latest_projection(
    auth_client,
    seeded_session,
    testing_session_local,
    monkeypatch,
):
    model_config_id = _create_enabled_model_config(testing_session_local)

    class OrderedReplyStream:
        def __init__(self, text: str):
            self._text = text

        def __iter__(self):
            yield self._text

        def close(self):
            return None

    replies = iter(["第一版回复", "第二版回复"])

    def fake_open_reply_stream(*, base_url, api_key, model, messages):
        return OrderedReplyStream(next(replies))

    monkeypatch.setattr("app.services.messages.open_reply_stream", fake_open_reply_stream)

    with auth_client.stream(
        "POST",
        f"/api/sessions/{seeded_session}/messages",
        json={"content": "请回答", "model_config_id": model_config_id},
    ) as response:
        assert response.status_code == 200
        first_body = "".join(response.iter_text())

    user_message_id = next(
        json.loads(line.removeprefix("data: "))["message_id"]
        for line in first_body.splitlines()
        if line.startswith("data: ") and '"message_id"' in line and '"session_id"' in line
    )

    with auth_client.stream(
        "POST",
        f"/api/sessions/{seeded_session}/messages/{user_message_id}/regenerate",
        json={"model_config_id": model_config_id},
    ) as response:
        assert response.status_code == 200
        list(response.iter_text())

    snapshot = auth_client.get(f"/api/sessions/{seeded_session}")
    assert snapshot.status_code == 200
    data = snapshot.json()

    assert len(data["assistant_reply_groups"]) == 1
    group = data["assistant_reply_groups"][0]
    assert group["session_id"] == seeded_session
    assert group["user_message_id"] == user_message_id
    assert isinstance(group["versions"], list)
    assert [version["version_no"] for version in group["versions"]] == [1, 2]
    assert group["latest_version_id"] == group["versions"][1]["id"]
    assert group["versions"][1]["content"] == "第二版回复"
    assert group["versions"][0]["is_latest"] is False
    assert group["versions"][1]["is_latest"] is True

    timeline_user_messages = [message for message in data["messages"] if message["role"] == "user"]
    timeline_assistant_messages = [message for message in data["messages"] if message["role"] == "assistant"]
    assert len(timeline_user_messages) == 1
    assert len(timeline_assistant_messages) == 1
    assert timeline_assistant_messages[0]["id"] == group["latest_version_id"]
    assert timeline_assistant_messages[0]["content"] == "第二版回复"
    assert timeline_assistant_messages[0]["reply_group_id"] == group["id"]
    assert timeline_assistant_messages[0]["version_no"] == 2
    assert timeline_assistant_messages[0]["is_latest"] is True


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


def test_delete_session_removes_owned_session(auth_client, seeded_session):
    response = auth_client.delete(f"/api/sessions/{seeded_session}")

    assert response.status_code == 204

    sessions_response = auth_client.get("/api/sessions")
    assert sessions_response.status_code == 200
    data = sessions_response.json()
    assert [session["id"] for session in data["sessions"]] == []
