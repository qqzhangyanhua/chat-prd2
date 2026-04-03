from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.repositories import prd as prd_repository
from app.repositories import sessions as sessions_repository
from app.repositories import state as state_repository
from app.schemas.prd import PrdSnapshotResponse
from app.schemas.session import (
    SessionCreateRequest,
    SessionCreateResponse,
    SessionListResponse,
    SessionResponse,
    SessionUpdateRequest,
)
from app.schemas.state import StateSnapshot


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

    return SessionCreateResponse(
        session=SessionResponse.model_validate(session),
        state=StateSnapshot.model_validate(state_version.state_json),
        prd_snapshot=PrdSnapshotResponse.model_validate(prd_snapshot),
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

    return SessionCreateResponse(
        session=SessionResponse.model_validate(session),
        state=StateSnapshot.model_validate(state_version.state_json),
        prd_snapshot=PrdSnapshotResponse.model_validate(prd_snapshot),
    )
