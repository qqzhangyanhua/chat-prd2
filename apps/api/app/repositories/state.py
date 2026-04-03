from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import ProjectStateVersion


def create_state_version(
    db: Session,
    session_id: str,
    version: int,
    state_json: dict,
) -> ProjectStateVersion:
    state_version = ProjectStateVersion(
        id=str(uuid4()),
        session_id=session_id,
        version=version,
        state_json=state_json,
    )
    db.add(state_version)
    db.flush()
    return state_version


def get_latest_state_version(db: Session, session_id: str) -> ProjectStateVersion | None:
    statement = (
        select(ProjectStateVersion)
        .where(ProjectStateVersion.session_id == session_id)
        .order_by(ProjectStateVersion.version.desc())
        .limit(1)
    )
    return db.execute(statement).scalar_one_or_none()


def delete_state_versions(db: Session, session_id: str) -> None:
    db.execute(
        delete(ProjectStateVersion).where(ProjectStateVersion.session_id == session_id),
    )
