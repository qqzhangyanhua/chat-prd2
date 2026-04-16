from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.db.models import User
from app.services import exports as export_service


router = APIRouter(prefix="/api/sessions/{session_id}/export", tags=["exports"])


@router.post("")
def export_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    return export_service.export_markdown(db, session_id, current_user.id)
