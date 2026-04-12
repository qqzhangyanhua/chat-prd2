from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import AssistantReplyGroup, AssistantReplyVersion, LLMModelConfig, ProjectSession
from app.repositories import agent_turn_decisions as agent_turn_decisions_repository
from app.repositories import assistant_reply_groups as assistant_reply_groups_repository
from app.repositories import assistant_reply_versions as assistant_reply_versions_repository
from app.repositories import messages as messages_repository
from app.repositories import prd as prd_repository
from app.repositories import state as state_repository
from app.services.message_preparation import get_user_and_mirror_assistant_message, raise_regeneration_conflict
from app.services.message_state import apply_prd_patch, apply_state_patch, merge_state_patch_with_decision


def persist_assistant_reply_and_version(
    db: Session,
    session_id: str,
    session: ProjectSession,
    user_message_id: str,
    reply_group_id: str,
    assistant_version_id: str,
    version_no: int,
    reply: str,
    model_meta: dict[str, str],
    action: dict,
    turn_decision: object,
    state: dict,
    state_patch: dict,
    prd_patch: dict,
    model_config: LLMModelConfig | None = None,
) -> tuple[str, str, int, str, int, str | None]:
    merged_state_patch = merge_state_patch_with_decision(
        state_patch,
        turn_decision,
        model_config=model_config,
        current_state=state,
    )
    new_state = apply_state_patch(state, merged_state_patch)
    new_state = apply_prd_patch(new_state, prd_patch)

    latest_state_version = state_repository.get_latest_state_version(db, session_id)
    next_state_version = (latest_state_version.version + 1) if latest_state_version else 1

    state_version = state_repository.create_state_version(db, session_id, next_state_version, new_state)
    prd_repository.create_prd_snapshot(
        db,
        session_id,
        next_state_version,
        new_state.get("prd_snapshot", {}).get("sections", {}),
    )

    assistant_message = messages_repository.create_message(
        db=db,
        session_id=session_id,
        role="assistant",
        content=reply,
        meta={**model_meta, "action": action},
    )

    reply_group = AssistantReplyGroup(
        id=reply_group_id,
        session_id=session_id,
        user_message_id=user_message_id,
    )
    db.add(reply_group)
    db.flush()

    reply_version = AssistantReplyVersion(
        id=assistant_version_id,
        reply_group_id=reply_group_id,
        session_id=session_id,
        user_message_id=user_message_id,
        version_no=version_no,
        content=reply,
        action_snapshot=action,
        model_meta=model_meta,
        state_version_id=state_version.id,
        prd_snapshot_version=next_state_version,
    )
    db.add(reply_version)
    db.flush()
    reply_group.latest_version_id = assistant_version_id
    db.add(reply_group)
    agent_turn_decisions_repository.create_turn_decision(
        db=db,
        session_id=session_id,
        user_message_id=user_message_id,
        turn_decision=turn_decision,
    )
    messages_repository.touch_session_activity(db, session)
    db.commit()
    return (
        assistant_message.id,
        reply_group_id,
        reply_version.version_no,
        assistant_version_id,
        next_state_version,
        reply_version.created_at.isoformat() if reply_version.created_at is not None else None,
    )


def persist_regenerated_reply_version(
    db: Session,
    session_id: str,
    session: ProjectSession,
    user_message_id: str,
    reply_group_id: str,
    assistant_version_id: str,
    version_no: int,
    reply: str,
    model_meta: dict[str, str],
    action: dict,
    turn_decision: object,
    state: dict,
    state_patch: dict,
    prd_patch: dict,
) -> tuple[str, int, int, str | None]:
    base_state_version = state_repository.get_latest_state_version(db, session_id)
    if base_state_version is None:
        raise_regeneration_conflict("STATE_SNAPSHOT_MISSING", "State snapshot not found")
    latest_prd_snapshot = prd_repository.get_latest_prd_snapshot(db, session_id)
    if latest_prd_snapshot is None:
        raise_regeneration_conflict("PRD_SNAPSHOT_MISSING", "PRD snapshot not found")

    reply_group = assistant_reply_groups_repository.get_reply_group_by_user_message(db=db, user_message_id=user_message_id)
    if reply_group is None:
        raise_regeneration_conflict("REPLY_GROUP_NOT_FOUND", "Reply group not found")
    if reply_group.id != reply_group_id:
        raise_regeneration_conflict("REPLY_GROUP_MISMATCH", "Reply group mismatch")
    latest_version = assistant_reply_versions_repository.get_latest_version_for_group(
        db=db,
        reply_group_id=reply_group.id,
    )
    if latest_version is None:
        raise_regeneration_conflict("REPLY_VERSION_HISTORY_MISSING", "Reply version history not found")
    if latest_version.version_no + 1 != version_no:
        raise_regeneration_conflict("REPLY_VERSION_SEQUENCE_MISMATCH", "Reply version sequence mismatch")

    merged_state_patch = merge_state_patch_with_decision(
        state_patch,
        turn_decision,
        current_state=state,
    )
    new_state = apply_state_patch(state, merged_state_patch)
    new_state = apply_prd_patch(new_state, prd_patch)
    next_state_version = base_state_version.version + 1
    state_version = state_repository.create_state_version(db, session_id, next_state_version, new_state)
    prd_repository.create_prd_snapshot(
        db,
        session_id,
        next_state_version,
        new_state.get("prd_snapshot", {}).get("sections", {}),
    )

    created_version = AssistantReplyVersion(
        id=assistant_version_id,
        reply_group_id=reply_group.id,
        session_id=session_id,
        user_message_id=user_message_id,
        version_no=version_no,
        content=reply,
        action_snapshot=action,
        model_meta=model_meta,
        state_version_id=state_version.id,
        prd_snapshot_version=next_state_version,
    )
    db.add(created_version)
    db.flush()
    reply_group.latest_version_id = assistant_version_id
    db.add(reply_group)
    _, assistant_message = get_user_and_mirror_assistant_message(
        db=db,
        session_id=session_id,
        user_message_id=user_message_id,
    )
    assistant_message.content = reply
    assistant_message.meta = {**model_meta, "action": action}
    db.add(assistant_message)
    agent_turn_decisions_repository.upsert_turn_decision(
        db=db,
        session_id=session_id,
        user_message_id=user_message_id,
        turn_decision=turn_decision,
    )
    messages_repository.touch_session_activity(db, session)
    db.commit()
    return (
        assistant_version_id,
        version_no,
        next_state_version,
        created_version.created_at.isoformat() if created_version.created_at is not None else None,
    )
