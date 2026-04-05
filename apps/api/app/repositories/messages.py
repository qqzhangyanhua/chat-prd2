from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
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


def get_messages_for_session(db: Session, session_id: str) -> list[ConversationMessage]:
    statement = (
        select(ConversationMessage)
        .where(ConversationMessage.session_id == session_id)
        .order_by(ConversationMessage.created_at.asc())
    )
    return list(db.execute(statement).scalars().all())
