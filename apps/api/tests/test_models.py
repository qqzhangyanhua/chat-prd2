from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from sqlalchemy import create_engine, inspect
from sqlalchemy.pool import StaticPool

from app.db.models import AgentTurnDecision, AssistantReplyGroup, AssistantReplyVersion, Base, LLMModelConfig, ProjectSession, User


def _load_initial_migration_module():
    migration_path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "0001_initial.py"
    )
    spec = spec_from_file_location("alembic_0001_initial", migration_path)
    assert spec is not None
    assert spec.loader is not None

    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_migration_module(filename: str, module_name: str):
    migration_path = Path(__file__).resolve().parents[1] / "alembic" / "versions" / filename
    spec = spec_from_file_location(module_name, migration_path)
    assert spec is not None
    assert spec.loader is not None

    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_models_have_expected_tablenames() -> None:
    assert User.__tablename__ == "users"
    assert ProjectSession.__tablename__ == "project_sessions"
    assert LLMModelConfig.__tablename__ == "llm_model_configs"
    assert AssistantReplyGroup.__tablename__ == "assistant_reply_groups"
    assert AssistantReplyVersion.__tablename__ == "assistant_reply_versions"
    assert AgentTurnDecision.__tablename__ == "agent_turn_decisions"


def test_initial_migration_uses_unique_index_for_user_email_only(monkeypatch) -> None:
    migration = _load_initial_migration_module()
    captured: dict[str, object] = {}

    def fake_create_table(name, *columns, **kwargs):
        if name == "users":
            captured["columns"] = columns
            captured["kwargs"] = kwargs

    def fake_create_index(name, table_name, columns, unique=False, **kwargs):
        if name == "ix_users_email":
            captured["index"] = {
                "table_name": table_name,
                "columns": columns,
                "unique": unique,
                "kwargs": kwargs,
            }

    monkeypatch.setattr(migration.op, "create_table", fake_create_table)
    monkeypatch.setattr(migration.op, "create_index", fake_create_index)

    migration.upgrade()

    users_email_column = next(
        column for column in captured["columns"] if column.name == "email"
    )
    assert users_email_column.unique is None
    assert captured["index"] == {
        "table_name": "users",
        "columns": ["email"],
        "unique": True,
        "kwargs": {},
    }


def test_followup_migration_creates_state_and_prd_tables(monkeypatch) -> None:
    migration = _load_migration_module(
        "0002_add_project_state_and_prd_snapshot.py",
        "alembic_0002_add_project_state_and_prd_snapshot",
    )
    created_tables: list[str] = []
    created_indexes: list[str] = []

    def fake_create_table(name, *columns, **kwargs):
        created_tables.append(name)

    def fake_create_index(name, table_name, columns, unique=False, **kwargs):
        created_indexes.append(name)

    monkeypatch.setattr(migration.op, "create_table", fake_create_table)
    monkeypatch.setattr(migration.op, "create_index", fake_create_index)

    migration.upgrade()

    assert "project_state_versions" in created_tables
    assert "prd_snapshots" in created_tables
    assert "ix_project_state_versions_session_id" in created_indexes
    assert "ix_prd_snapshots_session_id" in created_indexes


def test_followup_migration_creates_conversation_messages_table(monkeypatch) -> None:
    migration = _load_migration_module(
        "0003_add_conversation_messages.py",
        "alembic_0003_add_conversation_messages",
    )
    created_tables: list[str] = []
    created_indexes: list[str] = []

    def fake_create_table(name, *columns, **kwargs):
        created_tables.append(name)

    def fake_create_index(name, table_name, columns, unique=False, **kwargs):
        created_indexes.append(name)

    monkeypatch.setattr(migration.op, "create_table", fake_create_table)
    monkeypatch.setattr(migration.op, "create_index", fake_create_index)

    migration.upgrade()

    assert "conversation_messages" in created_tables
    assert "ix_conversation_messages_session_id" in created_indexes


def test_migration_creates_llm_model_configs_table(monkeypatch) -> None:
    migration = _load_migration_module(
        "0005_add_llm_model_configs.py",
        "alembic_0005_add_llm_model_configs",
    )
    created_tables: list[str] = []

    def fake_create_table(name, *columns, **kwargs):
        created_tables.append(name)

    monkeypatch.setattr(migration.op, "create_table", fake_create_table)

    migration.upgrade()

    assert "llm_model_configs" in created_tables


def test_migration_creates_assistant_reply_group_and_version_tables(monkeypatch) -> None:
    migration = _load_migration_module(
        "0006_add_assistant_reply_versions.py",
        "alembic_0006_add_assistant_reply_versions",
    )
    created_tables: list[str] = []
    created_indexes: list[str] = []

    def fake_create_table(name, *columns, **kwargs):
        created_tables.append(name)

    def fake_create_index(name, table_name, columns, unique=False, **kwargs):
        created_indexes.append(name)

    monkeypatch.setattr(migration.op, "create_table", fake_create_table)
    monkeypatch.setattr(migration.op, "create_index", fake_create_index)

    migration.upgrade()

    assert "assistant_reply_groups" in created_tables
    assert "assistant_reply_versions" in created_tables
    assert "ix_assistant_reply_groups_session_id" in created_indexes
    assert "ix_assistant_reply_versions_reply_group_id" in created_indexes


def test_assistant_reply_migration_avoids_sqlite_unsafe_alter_table_fk() -> None:
    migration_path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "0006_add_assistant_reply_versions.py"
    )
    migration_source = migration_path.read_text(encoding="utf-8")

    assert "create_foreign_key(" not in migration_source
    assert "drop_constraint(" not in migration_source
    assert "fk_arv_group_session_user_message" in migration_source


def test_assistant_reply_tables_include_consistency_constraints_in_sqlite() -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(bind=engine)
    table_inspector = inspect(engine)

    group_foreign_keys = table_inspector.get_foreign_keys("assistant_reply_groups")
    assert not any(
        fk.get("referred_table") == "assistant_reply_versions"
        and "latest_version_id" in fk.get("constrained_columns", [])
        for fk in group_foreign_keys
    )

    version_foreign_keys = table_inspector.get_foreign_keys("assistant_reply_versions")
    assert any(
        set(fk.get("constrained_columns", [])) == {"reply_group_id", "session_id", "user_message_id"}
        and fk.get("referred_table") == "assistant_reply_groups"
        for fk in version_foreign_keys
    )


def test_migration_creates_agent_turn_decisions_table(monkeypatch) -> None:
    migration = _load_migration_module(
        "0007_add_agent_turn_decisions.py",
        "alembic_0007_add_agent_turn_decisions",
    )
    created_tables: list[str] = []
    created_indexes: list[str] = []

    def fake_create_table(name, *columns, **kwargs):
        created_tables.append(name)

    def fake_create_index(name, table_name, columns, unique=False, **kwargs):
        created_indexes.append(name)

    monkeypatch.setattr(migration.op, "create_table", fake_create_table)
    monkeypatch.setattr(migration.op, "create_index", fake_create_index)

    migration.upgrade()

    assert "agent_turn_decisions" in created_tables
    assert "ix_agent_turn_decisions_session_id" in created_indexes
    assert "ix_agent_turn_decisions_user_message_id" in created_indexes
