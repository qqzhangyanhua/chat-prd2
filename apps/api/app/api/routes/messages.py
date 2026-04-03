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

    def event_generator() -> Generator[dict[str, str], None, None]:
        result = messages_service.handle_user_message(db, session_id, session, payload.content)
        yield {
            "event": "message.accepted",
            "data": json.dumps({"message_id": result.user_message_id}, ensure_ascii=False),
        }
        yield {
            "event": "action.decided",
            "data": json.dumps(result.action, ensure_ascii=False),
        }
        yield {
            "event": "assistant.delta",
            "data": json.dumps({"delta": result.reply}, ensure_ascii=False),
        }
        yield {
            "event": "assistant.done",
            "data": json.dumps({"message_id": result.assistant_message_id}, ensure_ascii=False),
        }

    return EventSourceResponse(event_generator())
