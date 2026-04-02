from uuid import uuid4

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
    db.commit()
    db.refresh(session)
    return session
