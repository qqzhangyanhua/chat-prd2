import json
from collections.abc import Generator

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.api.deps import get_current_user, get_db
from app.db.models import User
from app.repositories import sessions as sessions_repository
from app.schemas.message import MessageCreateRequest
from app.services import messages as messages_service


router = APIRouter(prefix="/api/sessions/{session_id}/messages", tags=["messages"])


@router.post("")
def create_message(
    session_id: str,
    payload: MessageCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EventSourceResponse:
    session = sessions_repository.get_session_for_user(db, session_id, current_user.id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    event_stream = messages_service.stream_user_message_events(
        db,
        session_id,
        session,
        payload.content,
        payload.model_config_id,
    )

    def event_generator() -> Generator[dict[str, str], None, None]:
        for event in event_stream:
            yield {
                "event": event.type,
                "data": json.dumps(event.data, ensure_ascii=False),
            }

    return EventSourceResponse(event_generator())
