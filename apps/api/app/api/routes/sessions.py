from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.db.models import User
from app.schemas.session import (
    SessionCreateRequest,
    SessionCreateResponse,
    SessionListResponse,
    SessionUpdateRequest,
)
from app.services import sessions as session_service


router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.get("", response_model=SessionListResponse)
def list_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SessionListResponse:
    return session_service.list_sessions(db, current_user.id)


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


@router.patch("/{session_id}", response_model=SessionCreateResponse)
def update_session(
    session_id: str,
    payload: SessionUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SessionCreateResponse:
    return session_service.update_session(db, session_id, current_user.id, payload)


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    session_service.delete_session(db, session_id, current_user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
