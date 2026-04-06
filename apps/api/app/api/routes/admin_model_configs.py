from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.admin import is_admin_email
from app.core.config import settings
from app.db.models import User
from app.repositories import model_configs as model_configs_repository
from app.schemas.model_config import (
    AdminModelConfigCreateRequest,
    AdminModelConfigListResponse,
    AdminModelConfigUpdateRequest,
    ModelConfigAdminResponse,
)


router = APIRouter(prefix="/api/admin/model-configs", tags=["admin-model-configs"])


def _require_admin(current_user: User = Depends(get_current_user)) -> User:
    if not is_admin_email(current_user.email, settings.admin_emails):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    return current_user


@router.get("", response_model=AdminModelConfigListResponse)
def list_model_configs(
    db: Session = Depends(get_db),
    _: User = Depends(_require_admin),
) -> AdminModelConfigListResponse:
    items = model_configs_repository.list_model_configs(db)
    return AdminModelConfigListResponse(items=items)


@router.post("", response_model=ModelConfigAdminResponse)
def create_model_config(
    payload: AdminModelConfigCreateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(_require_admin),
) -> ModelConfigAdminResponse:
    model_config = model_configs_repository.create_model_config(
        db,
        name=payload.name,
        base_url=payload.base_url,
        api_key=payload.api_key,
        model=payload.model,
        enabled=payload.enabled,
    )
    db.commit()
    return model_config


@router.patch("/{config_id}", response_model=ModelConfigAdminResponse)
def update_model_config(
    config_id: str,
    payload: AdminModelConfigUpdateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(_require_admin),
) -> ModelConfigAdminResponse:
    model_config = model_configs_repository.get_model_config_by_id(db, config_id)
    if model_config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model config not found")

    updated = model_configs_repository.update_model_config(
        db,
        model_config,
        name=payload.name,
        base_url=payload.base_url,
        api_key=payload.api_key,
        model=payload.model,
        enabled=payload.enabled,
    )
    db.commit()
    return updated


@router.delete("/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_model_config(
    config_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(_require_admin),
) -> Response:
    model_config = model_configs_repository.get_model_config_by_id(db, config_id)
    if model_config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model config not found")

    model_configs_repository.delete_model_config(db, model_config)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
