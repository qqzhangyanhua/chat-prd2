import os
from pathlib import Path
from uuid import uuid4

from app.core.config import Settings, load_env_file


def test_load_env_file_sets_missing_values(monkeypatch) -> None:
    env_file = Path(__file__).resolve().parent / f".test-config-{uuid4().hex}.env"
    env_file.write_text(
        "DATABASE_URL=postgresql+psycopg://demo:demo@localhost:5432/demo_db\n"
        "AUTH_SECRET_KEY=test-secret\n",
        encoding="utf-8",
    )

    try:
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.delenv("AUTH_SECRET_KEY", raising=False)

        load_env_file(env_file)

        assert os.environ["DATABASE_URL"] == "postgresql+psycopg://demo:demo@localhost:5432/demo_db"
        assert os.environ["AUTH_SECRET_KEY"] == "test-secret"
    finally:
        env_file.unlink(missing_ok=True)


def test_load_env_file_does_not_override_existing_values(monkeypatch) -> None:
    env_file = Path(__file__).resolve().parent / f".test-config-{uuid4().hex}.env"
    env_file.write_text(
        "DATABASE_URL=postgresql+psycopg://demo:demo@localhost:5432/demo_db\n",
        encoding="utf-8",
    )

    try:
        monkeypatch.setenv(
            "DATABASE_URL",
            "postgresql+psycopg://override:override@localhost:5432/override_db",
        )

        load_env_file(env_file)

        assert os.environ["DATABASE_URL"] == (
            "postgresql+psycopg://override:override@localhost:5432/override_db"
        )
    finally:
        env_file.unlink(missing_ok=True)


def test_settings_use_database_url_from_environment(monkeypatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@localhost:5432/ai_cofounder_test",
    )

    settings = Settings()

    assert (
        settings.database_url
        == "postgresql+psycopg://postgres:postgres@localhost:5432/ai_cofounder_test"
    )


def test_settings_parse_admin_emails_to_normalized_tuple(monkeypatch) -> None:
    monkeypatch.setenv(
        "ADMIN_EMAILS",
        "  Admin@Example.com,manager@example.com ,, ADMIN@example.com  ",
    )

    settings = Settings()

    assert settings.admin_emails == ("admin@example.com", "manager@example.com")
