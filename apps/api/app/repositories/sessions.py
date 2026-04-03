from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ProjectSession


def create_session(
    db: Session,
    user_id: str,
    title: str,
    initial_idea: str,
) -> ProjectSession:
    session = ProjectSession(
        id=str(uuid4()),
        user_id=user_id,
        title=title,
        initial_idea=initial_idea,
    )
    db.add(session)
    db.flush()
    return session


def get_session_for_user(db: Session, session_id: str, user_id: str) -> ProjectSession | None:
    statement = select(ProjectSession).where(
        ProjectSession.id == session_id,
        ProjectSession.user_id == user_id,
    )
    return db.execute(statement).scalar_one_or_none()
