from sqlalchemy import select

from app.db.models import PrdSnapshot, ProjectSession, ProjectStateVersion
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
    def fake_generate_reply(*, base_url, api_key, model, messages):
        return reply

    monkeypatch.setattr("app.services.messages.generate_reply", fake_generate_reply)


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
    assert isinstance(data["messages"], list)
    assert len(data["messages"]) >= 1
    assert data["messages"][0]["role"] in ("user", "assistant")
    assert "content" in data["messages"][0]


def test_delete_session_removes_owned_session(auth_client, seeded_session):
    response = auth_client.delete(f"/api/sessions/{seeded_session}")

    assert response.status_code == 204

    sessions_response = auth_client.get("/api/sessions")
    assert sessions_response.status_code == 200
    data = sessions_response.json()
    assert [session["id"] for session in data["sessions"]] == []
