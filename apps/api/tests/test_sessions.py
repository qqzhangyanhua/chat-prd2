import json
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

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
            }
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
    assert next_step["meta"]["suggestion_options"] == [
        {
            "label": "先聊独立开发者",
            "content": "我想先从独立开发者的场景开始聊。",
            "rationale": "更容易快速举出真实例子。",
            "priority": 1,
            "type": "direction",
        }
    ]


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


def test_delete_session_removes_owned_session(auth_client, seeded_session):
    response = auth_client.delete(f"/api/sessions/{seeded_session}")

    assert response.status_code == 204

    sessions_response = auth_client.get("/api/sessions")
    assert sessions_response.status_code == 200
    data = sessions_response.json()
    assert [session["id"] for session in data["sessions"]] == []
