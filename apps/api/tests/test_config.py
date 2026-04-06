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


def test_settings_default_access_token_expire_minutes_is_seven_days(monkeypatch) -> None:
    monkeypatch.delenv("AUTH_ACCESS_TOKEN_EXPIRE_MINUTES", raising=False)

    settings = Settings()

    assert settings.auth_access_token_expire_minutes == 7 * 24 * 60


def test_settings_use_access_token_expire_minutes_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("AUTH_ACCESS_TOKEN_EXPIRE_MINUTES", "2880")

    settings = Settings()

    assert settings.auth_access_token_expire_minutes == 2880
