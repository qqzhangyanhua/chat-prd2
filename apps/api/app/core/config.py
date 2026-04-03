import os
from dataclasses import dataclass, field
from pathlib import Path


DEFAULT_DATABASE_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/ai_cofounder"
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


@dataclass(frozen=True)
class Settings:
    app_name: str = "AI Co-founder API"
    database_url: str = field(
        default_factory=lambda: os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
    )
    auth_secret_key: str | None = field(
        default_factory=lambda: os.getenv("AUTH_SECRET_KEY")
    )


settings = Settings()
