from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import LLMModelConfig


def list_model_configs(db: Session) -> list[LLMModelConfig]:
    statement = select(LLMModelConfig).order_by(LLMModelConfig.created_at.desc())
    return list(db.execute(statement).scalars().all())


def list_enabled_model_configs(db: Session) -> list[LLMModelConfig]:
    statement = (
        select(LLMModelConfig)
        .where(LLMModelConfig.enabled.is_(True))
        .order_by(LLMModelConfig.created_at.desc())
    )
    return list(db.execute(statement).scalars().all())


def get_model_config_by_id(db: Session, config_id: str) -> LLMModelConfig | None:
    statement = select(LLMModelConfig).where(LLMModelConfig.id == config_id)
    return db.execute(statement).scalar_one_or_none()


def create_model_config(
    db: Session,
    *,
    name: str,
    base_url: str,
    api_key: str,
    model: str,
    enabled: bool,
) -> LLMModelConfig:
    entity = LLMModelConfig(
        id=str(uuid4()),
        name=name,
        base_url=base_url,
        api_key=api_key,
        model=model,
        enabled=enabled,
        updated_at=datetime.now(timezone.utc),
    )
    db.add(entity)
    db.flush()
    return entity


def update_model_config(
    db: Session,
    entity: LLMModelConfig,
    *,
    name: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
    enabled: bool | None = None,
) -> LLMModelConfig:
    if name is not None:
        entity.name = name
    if base_url is not None:
        entity.base_url = base_url
    if api_key is not None:
        entity.api_key = api_key
    if model is not None:
        entity.model = model
    if enabled is not None:
        entity.enabled = enabled

    entity.updated_at = datetime.now(timezone.utc)
    db.add(entity)
    db.flush()
    return entity


def delete_model_config(db: Session, entity: LLMModelConfig) -> None:
    db.delete(entity)
    db.flush()
