import json
from collections.abc import AsyncGenerator
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.agent.runtime import run_agent
from app.api.deps import get_current_user, get_db
from app.db.models import User
from app.repositories import messages as messages_repository
from app.schemas.message import MessageCreateRequest


router = APIRouter(prefix="/api/sessions/{session_id}/messages", tags=["messages"])


@router.post("")
async def create_message(
    session_id: str,
    payload: MessageCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EventSourceResponse:
    session = messages_repository.get_session_for_user(db, session_id, current_user.id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    try:
        state = messages_repository.get_latest_state(db, session_id)
        messages_repository.create_message(
            db=db,
            session_id=session_id,
            role="user",
            content=payload.content,
        )
        agent_result = run_agent(state, payload.content)
        assistant_message = messages_repository.create_message(
            db=db,
            session_id=session_id,
            role="assistant",
            content=agent_result.reply,
            meta={"action": asdict(agent_result.action)},
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    action_data = json.dumps(asdict(agent_result.action), ensure_ascii=False)
    delta_data = json.dumps({"delta": agent_result.reply}, ensure_ascii=False)
    done_data = json.dumps({"message_id": assistant_message.id}, ensure_ascii=False)

    async def event_generator() -> AsyncGenerator[dict[str, str], None]:
        yield {"event": "action.decided", "data": action_data}
        yield {"event": "assistant.delta", "data": delta_data}
        yield {"event": "assistant.done", "data": done_data}

    return EventSourceResponse(event_generator())
