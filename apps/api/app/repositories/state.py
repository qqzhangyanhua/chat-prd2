from uuid import uuid4

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
    db.commit()
    db.refresh(state_version)
    return state_version
