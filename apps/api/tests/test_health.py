from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

import app.main as main_module
from app.db.models import (
    AgentTurnDecision,
    AssistantReplyGroup,
    AssistantReplyVersion,
    Base,
    ConversationMessage,
    PrdSnapshot,
    ProjectSession,
    ProjectStateVersion,
    User,
)
from app.main import app

client = TestClient(app)


def test_schema_health_returns_ready_when_required_tables_exist():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(bind=engine)

    assert main_module.get_schema_health(engine) == {
        "schema": "ready",
        "missing_tables": [],
    }


def test_schema_health_returns_outdated_when_required_tables_are_missing():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    User.__table__.create(bind=engine)
    ProjectSession.__table__.create(bind=engine)
    ProjectStateVersion.__table__.create(bind=engine)
    PrdSnapshot.__table__.create(bind=engine)
    ConversationMessage.__table__.create(bind=engine)

    assert main_module.get_schema_health(engine) == {
        "schema": "outdated",
        "missing_tables": [
            AssistantReplyGroup.__tablename__,
            AssistantReplyVersion.__tablename__,
            AgentTurnDecision.__tablename__,
        ],
    }


def test_healthcheck_returns_ok_when_schema_is_ready(monkeypatch):
    monkeypatch.setattr(
        main_module,
        "get_schema_health",
        lambda _engine: {"schema": "ready", "missing_tables": []},
    )

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "schema": "ready"}


def test_healthcheck_returns_503_when_schema_is_outdated(monkeypatch):
    monkeypatch.setattr(
        main_module,
        "get_schema_health",
        lambda _engine: {
            "schema": "outdated",
            "missing_tables": ["agent_turn_decisions"],
        },
    )

    response = client.get("/api/health")

    assert response.status_code == 503
    assert response.json() == {
        "status": "degraded",
        "schema": "outdated",
        "detail": "数据库结构版本过旧，请先执行 alembic upgrade head",
        "error": {
            "code": "SCHEMA_OUTDATED",
            "message": "数据库结构版本过旧，请先执行 alembic upgrade head",
            "recovery_action": {
                "type": "run_migration",
                "label": "执行数据库迁移",
                "target": "cd apps/api && alembic upgrade head",
            },
        },
        "missing_tables": ["agent_turn_decisions"],
    }
