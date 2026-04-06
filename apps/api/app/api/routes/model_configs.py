from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.db.models import User
from app.repositories import model_configs as model_configs_repository
from app.schemas.model_config import EnabledModelConfigListResponse


router = APIRouter(prefix="/api/model-configs", tags=["model-configs"])


@router.get("/enabled", response_model=EnabledModelConfigListResponse)
def list_enabled_model_configs(
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EnabledModelConfigListResponse:
    items = model_configs_repository.list_enabled_model_configs(db)
    return EnabledModelConfigListResponse(items=items)
