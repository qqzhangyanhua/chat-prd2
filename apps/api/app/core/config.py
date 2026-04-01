from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_name: str = "AI Co-founder API"


settings = Settings()
