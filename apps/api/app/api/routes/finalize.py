from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.api_error import raise_api_error
from app.db.models import User
from app.repositories import sessions as sessions_repository
from app.schemas.session import SessionCreateResponse
from app.services import finalize_session as finalize_service


class FinalizeSessionRequest(BaseModel):
    confirmation_source: str = Field(min_length=1)
    preference: str | None = None


router = APIRouter(prefix="/api/sessions/{session_id}/finalize", tags=["finalize"])


@router.post("", response_model=SessionCreateResponse)
def finalize_session(
    session_id: str,
    payload: FinalizeSessionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SessionCreateResponse:
    session = sessions_repository.get_session_for_user(db, session_id, current_user.id)
    if session is None:
        raise_api_error(
            status_code=status.HTTP_404_NOT_FOUND,
            code="SESSION_NOT_FOUND",
            message="Session not found",
            recovery_action={
                "type": "open_workspace_home",
                "label": "返回工作台首页",
                "target": "/workspace",
            },
        )
    return finalize_service.finalize_session(
        db,
        session_id,
        current_user.id,
        confirmation_source=payload.confirmation_source,
        preference=payload.preference,
    )
