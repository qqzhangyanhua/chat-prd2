from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.orm import Session

from app.db.models import ConversationMessage, ProjectSession


def create_message(
    db: Session,
    session_id: str,
    role: str,
    content: str,
    message_type: str = "chat",
    meta: dict | None = None,
) -> ConversationMessage:
    message = ConversationMessage(
        id=str(uuid4()),
        session_id=session_id,
        role=role,
        content=content,
        message_type=message_type,
        meta=meta or {},
    )
    db.add(message)
    db.flush()
    return message


def touch_session_activity(db: Session, session: ProjectSession) -> ProjectSession:
    session.updated_at = datetime.now(timezone.utc)
    db.add(session)
    db.flush()
    return session
