from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from fastapi import status
from sqlalchemy.orm import Session

from app.agent.finalize_flow import FINALIZE_PREFERENCES, build_finalized_sections, normalize_finalize_preference
from app.agent.readiness import evaluate_finalize_readiness
from app.core.api_error import raise_api_error
from app.repositories import prd as prd_repository
from app.repositories import state as state_repository
from app.services import sessions as session_service

ALLOWED_CONFIRMATION_SOURCES = {"button", "message"}
ALLOWED_FINALIZE_PREFERENCES = set(FINALIZE_PREFERENCES)


@dataclass(frozen=True)
class FinalizeSessionTransition:
    state: dict
    state_version_id: str
    prd_snapshot_version: int


def build_finalize_delivery_milestone(state: dict) -> dict[str, Any]:
    prd_draft = state.get("prd_draft") if isinstance(state.get("prd_draft"), dict) else {}
    prd_snapshot = state.get("prd_snapshot") if isinstance(state.get("prd_snapshot"), dict) else {}
    version = prd_draft.get("version")
    if not isinstance(version, int):
        snapshot_version = prd_snapshot.get("version")
        version = snapshot_version if isinstance(snapshot_version, int) else None

    return {
        "status": "finalized" if prd_draft.get("status") == "finalized" else "draft",
        "prd_snapshot_version": version,
        "confirmation_source": state.get("finalize_confirmation_source"),
        "finalize_preference": state.get("finalize_preference"),
    }


def _resolve_next_state_version(db: Session, session_id: str, current_state: dict) -> int:
    get_latest_state_version = getattr(state_repository, "get_latest_state_version", None)
    if callable(get_latest_state_version):
        latest = get_latest_state_version(db, session_id)
        if latest is not None:
            return int(latest.version) + 1
    current_version = current_state.get("version")
    if isinstance(current_version, int) and current_version >= 0:
        return current_version + 1
    return 1


def _require_finalize_ready(state: dict) -> None:
    readiness = evaluate_finalize_readiness(state)
    ready_for_confirmation = bool(readiness.get("ready_for_confirmation"))
    if state.get("workflow_stage") != "finalize" or not ready_for_confirmation:
        raise_api_error(
            status_code=status.HTTP_409_CONFLICT,
            code="FINALIZE_NOT_READY",
            message="Finalize is not ready",
            recovery_action={
                "type": "continue_refine",
                "label": "继续完善草稿",
                "target": None,
            },
        )


def _validate_confirmation_source(confirmation_source: str) -> str:
    normalized = (confirmation_source or "").strip().lower()
    if normalized not in ALLOWED_CONFIRMATION_SOURCES:
        raise_api_error(
            status_code=status.HTTP_409_CONFLICT,
            code="FINALIZE_CONFIRMATION_REQUIRED",
            message="Finalize confirmation source is invalid",
            recovery_action={
                "type": "confirm_finalize",
                "label": "重新确认终稿",
                "target": None,
            },
        )
    return normalized


def _resolve_finalize_preference(preference: str | None, current_state: dict) -> str:
    candidate = (
        normalize_finalize_preference(preference)
        or normalize_finalize_preference(current_state.get("finalize_preference"))
        or "balanced"
    )
    normalized = str(candidate)
    if normalized not in ALLOWED_FINALIZE_PREFERENCES:
        raise_api_error(
            status_code=status.HTTP_409_CONFLICT,
            code="FINALIZE_PREFERENCE_INVALID",
            message="Finalize preference is invalid",
            recovery_action={
                "type": "confirm_finalize",
                "label": "重新选择终稿偏好",
                "target": None,
            },
        )
    return normalized


def create_finalize_session_transition(
    db: Session,
    session_id: str,
    *,
    confirmation_source: str,
    preference: str | None = None,
) -> FinalizeSessionTransition:
    current_state = state_repository.get_latest_state(db, session_id) or {}
    _require_finalize_ready(current_state)
    normalized_source = _validate_confirmation_source(confirmation_source)
    resolved_preference = _resolve_finalize_preference(preference, current_state)

    readiness = evaluate_finalize_readiness(current_state)
    finalized_sections = build_finalized_sections(current_state, resolved_preference)
    next_state_version = _resolve_next_state_version(db, session_id, current_state)

    next_state = deepcopy(current_state)
    next_state["workflow_stage"] = "completed"
    next_state["finalization_ready"] = bool(readiness.get("ready_for_confirmation"))
    next_state["finalize_confirmation_source"] = normalized_source
    next_state["finalize_preference"] = resolved_preference
    next_state["prd_snapshot"] = {"sections": finalized_sections}
    next_state["prd_draft"] = {
        "version": next_state_version,
        "status": "finalized",
        "sections": finalized_sections,
    }
    next_state["delivery_milestone"] = {
        **build_finalize_delivery_milestone(
            {
                **next_state,
                "prd_draft": {
                    "version": next_state_version,
                    "status": "finalized",
                    "sections": finalized_sections,
                },
            }
        ),
    }

    try:
        state_version = state_repository.create_state_version(
            db=db,
            session_id=session_id,
            version=next_state_version,
            state_json=next_state,
        )
        prd_repository.create_prd_snapshot(
            db=db,
            session_id=session_id,
            version=next_state_version,
            sections=finalized_sections,
        )
    except Exception:
        db.rollback()
        raise

    return FinalizeSessionTransition(
        state=next_state,
        state_version_id=state_version.id,
        prd_snapshot_version=next_state_version,
    )


def finalize_session(
    db: Session,
    session_id: str,
    user_id: str,
    *,
    confirmation_source: str,
    preference: str | None = None,
):
    create_finalize_session_transition(
        db=db,
        session_id=session_id,
        confirmation_source=confirmation_source,
        preference=preference,
    )
    db.commit()
    return session_service.get_session_snapshot(db, session_id, user_id)
