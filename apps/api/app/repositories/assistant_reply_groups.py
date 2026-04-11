from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AssistantReplyGroup, AssistantReplyVersion, ConversationMessage


def create_reply_group(
    db: Session,
    session_id: str,
    user_message_id: str,
) -> AssistantReplyGroup:
    user_message = db.execute(
        select(ConversationMessage).where(ConversationMessage.id == user_message_id)
    ).scalar_one_or_none()
    if user_message is None:
        raise ValueError("User message does not exist")
    if user_message.session_id != session_id:
        raise ValueError("User message does not belong to session")

    reply_group = AssistantReplyGroup(
        id=str(uuid4()),
        session_id=session_id,
        user_message_id=user_message_id,
    )
    db.add(reply_group)
    db.flush()
    return reply_group


def get_reply_group_by_user_message(
    db: Session,
    user_message_id: str,
) -> AssistantReplyGroup | None:
    statement = select(AssistantReplyGroup).where(
        AssistantReplyGroup.user_message_id == user_message_id,
    )
    return db.execute(statement).scalar_one_or_none()


def set_latest_version(
    db: Session,
    reply_group: AssistantReplyGroup,
    latest_version_id: str,
) -> AssistantReplyGroup:
    version = db.execute(
        select(AssistantReplyVersion).where(AssistantReplyVersion.id == latest_version_id)
    ).scalar_one_or_none()
    if version is None:
        raise ValueError("Latest version does not exist")
    if version.reply_group_id != reply_group.id:
        raise ValueError("Latest version does not belong to reply group")

    reply_group.latest_version_id = latest_version_id
    reply_group.updated_at = datetime.now(timezone.utc)
    db.add(reply_group)
    db.flush()
    return reply_group
