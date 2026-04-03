from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import PrdSnapshot


def create_prd_snapshot(
    db: Session,
    session_id: str,
    version: int,
    sections: dict,
) -> PrdSnapshot:
    prd_snapshot = PrdSnapshot(
        id=str(uuid4()),
        session_id=session_id,
        version=version,
        sections=sections,
    )
    db.add(prd_snapshot)
    db.flush()
    return prd_snapshot


def get_latest_prd_snapshot(db: Session, session_id: str) -> PrdSnapshot | None:
    statement = (
        select(PrdSnapshot)
        .where(PrdSnapshot.session_id == session_id)
        .order_by(PrdSnapshot.version.desc())
        .limit(1)
    )
    return db.execute(statement).scalar_one_or_none()


def delete_prd_snapshots(db: Session, session_id: str) -> None:
    db.execute(
        delete(PrdSnapshot).where(PrdSnapshot.session_id == session_id),
    )
