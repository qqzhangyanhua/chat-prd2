from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.db.models import User
from app.schemas.session import SessionCreateRequest, SessionCreateResponse
from app.services import sessions as session_service


router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.post("", response_model=SessionCreateResponse)
def create_session(
    payload: SessionCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SessionCreateResponse:
    return session_service.create_session(db, current_user.id, payload)


@router.get("/{session_id}", response_model=SessionCreateResponse)
def get_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SessionCreateResponse:
    return session_service.get_session_snapshot(db, session_id, current_user.id)
