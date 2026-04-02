from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from app.db.models import ProjectSession, User


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
