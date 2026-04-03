from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ConversationMessage, ProjectSession, ProjectStateVersion


def get_session_for_user(
    db: Session,
    session_id: str,
    user_id: str,
) -> ProjectSession | None:
    statement = select(ProjectSession).where(
        ProjectSession.id == session_id,
        ProjectSession.user_id == user_id,
    )
    return db.execute(statement).scalar_one_or_none()


def get_latest_state(
    db: Session,
    session_id: str,
) -> dict:
    statement = (
        select(ProjectStateVersion.state_json)
        .where(ProjectStateVersion.session_id == session_id)
        .order_by(ProjectStateVersion.version.desc())
        .limit(1)
    )
    state = db.execute(statement).scalar_one_or_none()
    return state or {}


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
