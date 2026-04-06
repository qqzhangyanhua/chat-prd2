from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AssistantReplyGroup, AssistantReplyVersion


def create_reply_version(
    db: Session,
    reply_group_id: str,
    session_id: str,
    user_message_id: str,
    version_no: int,
    content: str,
    action_snapshot: dict,
    model_meta: dict,
    state_version_id: str | None,
    prd_snapshot_version: int | None,
) -> AssistantReplyVersion:
    reply_group = db.execute(
        select(AssistantReplyGroup).where(AssistantReplyGroup.id == reply_group_id)
    ).scalar_one_or_none()
    if reply_group is None:
        raise ValueError("Reply group does not exist")
    if reply_group.session_id != session_id:
        raise ValueError("Reply version session_id does not match reply group")
    if reply_group.user_message_id != user_message_id:
        raise ValueError("Reply version user_message_id does not match reply group")

    reply_version = AssistantReplyVersion(
        id=str(uuid4()),
        reply_group_id=reply_group_id,
        session_id=session_id,
        user_message_id=user_message_id,
        version_no=version_no,
        content=content,
        action_snapshot=action_snapshot,
        model_meta=model_meta,
        state_version_id=state_version_id,
        prd_snapshot_version=prd_snapshot_version,
    )
    db.add(reply_version)
    db.flush()
    return reply_version


def list_versions_for_group(
    db: Session,
    reply_group_id: str,
) -> list[AssistantReplyVersion]:
    statement = (
        select(AssistantReplyVersion)
        .where(AssistantReplyVersion.reply_group_id == reply_group_id)
        .order_by(AssistantReplyVersion.version_no.asc())
    )
    return list(db.execute(statement).scalars().all())


def get_latest_version_for_group(
    db: Session,
    reply_group_id: str,
) -> AssistantReplyVersion | None:
    reply_group = db.execute(
        select(AssistantReplyGroup).where(AssistantReplyGroup.id == reply_group_id)
    ).scalar_one_or_none()
    if reply_group is None or reply_group.latest_version_id is None:
        return None
    statement = (
        select(AssistantReplyVersion)
        .where(AssistantReplyVersion.id == reply_group.latest_version_id)
        .where(AssistantReplyVersion.reply_group_id == reply_group_id)
    )
    return db.execute(statement).scalar_one_or_none()
