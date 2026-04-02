from uuid import uuid4

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
    db.commit()
    db.refresh(prd_snapshot)
    return prd_snapshot
