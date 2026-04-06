from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AssistantReplyGroup
from app.repositories import assistant_reply_versions as assistant_reply_versions_repository
from app.repositories import messages as messages_repository
from app.repositories import prd as prd_repository
from app.repositories import sessions as sessions_repository
from app.repositories import state as state_repository
from app.schemas.message import AssistantReplyGroupResponse
from app.schemas.message import AssistantReplyVersionResponse
from app.schemas.message import ConversationMessageResponse
from app.schemas.prd import PrdSnapshotResponse
from app.schemas.session import (
    SessionCreateRequest,
    SessionCreateResponse,
    SessionListResponse,
    SessionResponse,
    SessionUpdateRequest,
)
from app.schemas.state import StateSnapshot


def _list_assistant_reply_groups(db: Session, session_id: str) -> list[AssistantReplyGroupResponse]:
    groups = list(
        db.execute(
            select(AssistantReplyGroup)
            .where(AssistantReplyGroup.session_id == session_id)
            .order_by(AssistantReplyGroup.created_at.asc()),
        ).scalars().all(),
    )
    result: list[AssistantReplyGroupResponse] = []
    for group in groups:
        versions = assistant_reply_versions_repository.list_versions_for_group(
            db=db,
            reply_group_id=group.id,
        )
        group_data = AssistantReplyGroupResponse.model_validate(group)
        group_data.versions = [
            AssistantReplyVersionResponse.model_validate(version).model_copy(
                update={"is_latest": version.id == group.latest_version_id},
            )
            for version in versions
        ]
        result.append(group_data)
    return result


def _build_timeline_messages(
    raw_messages: list,
    assistant_reply_groups: list[AssistantReplyGroupResponse],
) -> list[ConversationMessageResponse]:
    if not assistant_reply_groups:
        return [ConversationMessageResponse.model_validate(message) for message in raw_messages]

    group_by_user_message = {group.user_message_id: group for group in assistant_reply_groups}
    assistant_appended_for_user: set[str] = set()
    timeline: list[ConversationMessageResponse] = []
    current_user_id: str | None = None

    for message in raw_messages:
        if message.role == "user":
            current_user_id = message.id
            timeline.append(ConversationMessageResponse.model_validate(message))
            continue

        if message.role != "assistant":
            timeline.append(ConversationMessageResponse.model_validate(message))
            continue

        if current_user_id is None:
            timeline.append(ConversationMessageResponse.model_validate(message))
            continue

        group = group_by_user_message.get(current_user_id)
        if group is None:
            timeline.append(ConversationMessageResponse.model_validate(message))
            continue

        if current_user_id in assistant_appended_for_user:
            continue

        latest_version = next(
            (version for version in group.versions if version.id == group.latest_version_id),
            None,
        )
        if latest_version is None:
            timeline.append(ConversationMessageResponse.model_validate(message))
            assistant_appended_for_user.add(current_user_id)
            continue

        timeline.append(
            ConversationMessageResponse(
                id=latest_version.id,
                session_id=message.session_id,
                role="assistant",
                content=latest_version.content,
                message_type=message.message_type,
                reply_group_id=group.id,
                version_no=latest_version.version_no,
                is_latest=True,
            ),
        )
        assistant_appended_for_user.add(current_user_id)

    return timeline


def build_initial_state(initial_idea: str) -> dict:
    return {
        "idea": initial_idea,
        "stage_hint": "问题探索",
        "iteration": 0,
        "goal": None,
        "target_user": None,
        "problem": None,
        "solution": None,
        "mvp_scope": [],
        "success_metrics": [],
        "known_facts": {},
        "assumptions": [],
        "risks": [],
        "unexplored_areas": [],
        "options": [],
        "decisions": [],
        "open_questions": [],
        "prd_snapshot": {"sections": {}},
    }


def create_session(
    db: Session,
    user_id: str,
    payload: SessionCreateRequest,
) -> SessionCreateResponse:
    try:
        session = sessions_repository.create_session(
            db=db,
            user_id=user_id,
            title=payload.title,
            initial_idea=payload.initial_idea,
        )

        initial_state = build_initial_state(payload.initial_idea)
        state_repository.create_state_version(
            db=db,
            session_id=session.id,
            version=1,
            state_json=initial_state,
        )
        prd_snapshot = prd_repository.create_prd_snapshot(
            db=db,
            session_id=session.id,
            version=1,
            sections=initial_state["prd_snapshot"]["sections"],
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    return SessionCreateResponse(
        session=SessionResponse.model_validate(session),
        state=StateSnapshot.model_validate(initial_state),
        prd_snapshot=PrdSnapshotResponse.model_validate(prd_snapshot),
        messages=[],
        assistant_reply_groups=[],
    )


def get_session_snapshot(db: Session, session_id: str, user_id: str) -> SessionCreateResponse:
    session = sessions_repository.get_session_for_user(db, session_id, user_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    try:
        sessions_repository.touch_session(db, session)
        db.commit()
        db.refresh(session)
    except Exception:
        db.rollback()
        raise

    state_version = state_repository.get_latest_state_version(db, session_id)
    prd_snapshot = prd_repository.get_latest_prd_snapshot(db, session_id)

    if state_version is None or prd_snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session snapshot not found",
        )

    raw_messages = messages_repository.get_messages_for_session(db, session_id)
    assistant_reply_groups = _list_assistant_reply_groups(db, session_id)

    return SessionCreateResponse(
        session=SessionResponse.model_validate(session),
        state=StateSnapshot.model_validate(state_version.state_json),
        prd_snapshot=PrdSnapshotResponse.model_validate(prd_snapshot),
        messages=_build_timeline_messages(raw_messages, assistant_reply_groups),
        assistant_reply_groups=assistant_reply_groups,
    )


def list_sessions(db: Session, user_id: str) -> SessionListResponse:
    sessions = sessions_repository.list_sessions_for_user(db, user_id)
    return SessionListResponse(
        sessions=[SessionResponse.model_validate(session) for session in sessions],
    )


def update_session(
    db: Session,
    session_id: str,
    user_id: str,
    payload: SessionUpdateRequest,
) -> SessionCreateResponse:
    session = sessions_repository.get_session_for_user(db, session_id, user_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    state_version = state_repository.get_latest_state_version(db, session_id)
    prd_snapshot = prd_repository.get_latest_prd_snapshot(db, session_id)

    if state_version is None or prd_snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session snapshot not found",
        )

    try:
        session = sessions_repository.update_session_title(db, session, payload.title)
        db.commit()
        db.refresh(session)
    except Exception:
        db.rollback()
        raise

    raw_messages = messages_repository.get_messages_for_session(db, session_id)
    assistant_reply_groups = _list_assistant_reply_groups(db, session_id)

    return SessionCreateResponse(
        session=SessionResponse.model_validate(session),
        state=StateSnapshot.model_validate(state_version.state_json),
        prd_snapshot=PrdSnapshotResponse.model_validate(prd_snapshot),
        messages=_build_timeline_messages(raw_messages, assistant_reply_groups),
        assistant_reply_groups=assistant_reply_groups,
    )


def delete_session(db: Session, session_id: str, user_id: str) -> None:
    session = sessions_repository.get_session_for_user(db, session_id, user_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    try:
        db.delete(session)
        db.commit()
    except Exception:
        db.rollback()
        raise
