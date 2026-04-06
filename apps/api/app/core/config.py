import os
from dataclasses import dataclass, field
from pathlib import Path


DEFAULT_DATABASE_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/ai_cofounder"
DEFAULT_AUTH_ACCESS_TOKEN_EXPIRE_MINUTES = 7 * 24 * 60
ENV_FILE_PATH = Path(__file__).resolve().parents[4] / ".env"


def load_env_file(env_file_path: Path = ENV_FILE_PATH) -> None:
    if not env_file_path.exists():
        return

    for raw_line in env_file_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


load_env_file()


def parse_admin_emails(raw: str | None) -> tuple[str, ...]:
    if raw is None:
        return ()

    normalized_emails: list[str] = []
    seen: set[str] = set()
    for part in raw.split(","):
        email = part.strip().lower()
        if not email or email in seen:
            continue
        seen.add(email)
        normalized_emails.append(email)
    return tuple(normalized_emails)


def parse_int_env(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    value = int(raw_value)
    if value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


@dataclass(frozen=True)
class Settings:
    app_name: str = "AI Co-founder API"
    database_url: str = field(
        default_factory=lambda: os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
    )
    auth_secret_key: str | None = field(
        default_factory=lambda: os.getenv("AUTH_SECRET_KEY")
    )
    auth_access_token_expire_minutes: int = field(
        default_factory=lambda: parse_int_env(
            "AUTH_ACCESS_TOKEN_EXPIRE_MINUTES",
            DEFAULT_AUTH_ACCESS_TOKEN_EXPIRE_MINUTES,
        )
    )
    admin_emails: tuple[str, ...] = field(
        default_factory=lambda: parse_admin_emails(os.getenv("ADMIN_EMAILS"))
    )


settings = Settings()
