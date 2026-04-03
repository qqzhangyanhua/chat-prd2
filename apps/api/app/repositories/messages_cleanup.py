from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.db.models import ConversationMessage


def delete_messages(db: Session, session_id: str) -> None:
    db.execute(
        delete(ConversationMessage).where(ConversationMessage.session_id == session_id),
    )
