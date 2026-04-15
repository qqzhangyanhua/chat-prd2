from __future__ import annotations

import logging
from copy import deepcopy
from typing import Any

from sqlalchemy.orm import Session

from app.agent.readiness import evaluate_finalize_readiness
from app.repositories import prd as prd_repository
from app.repositories import state as state_repository


logger = logging.getLogger(__name__)

LEGACY_BACKFILL_VERSION = "closure_v1"
EXPLICIT_CLOSURE_FIELDS = (
    "workflow_stage",
    "prd_draft",
    "critic_result",
    "finalization_ready",
)


def needs_legacy_backfill(state: dict[str, Any] | None) -> bool:
    if not isinstance(state, dict):
        return False
    return any(field not in state for field in EXPLICIT_CLOSURE_FIELDS)


def _extract_legacy_sections(
    current_state: dict[str, Any],
    latest_prd_snapshot: object | None,
) -> dict[str, dict[str, Any]]:
    prd_draft = current_state.get("prd_draft")
    if isinstance(prd_draft, dict) and isinstance(prd_draft.get("sections"), dict):
        return deepcopy(prd_draft["sections"])

    current_snapshot = current_state.get("prd_snapshot")
    if isinstance(current_snapshot, dict) and isinstance(current_snapshot.get("sections"), dict):
        snapshot_sections = current_snapshot.get("sections")
        if snapshot_sections:
            return deepcopy(snapshot_sections)

    snapshot_sections = getattr(latest_prd_snapshot, "sections", None)
    if isinstance(snapshot_sections, dict):
        return deepcopy(snapshot_sections)
    return {}


def backfill_legacy_session_state(
    db: Session,
    session_id: str,
    current_state: dict[str, Any],
    latest_prd_snapshot: object | None,
) -> bool:
    if not needs_legacy_backfill(current_state):
        return False

    try:
        latest_state_version = state_repository.get_latest_state_version(db, session_id)
        if latest_state_version is None:
            return False

        next_version = int(latest_state_version.version) + 1
        sections = _extract_legacy_sections(current_state, latest_prd_snapshot)
        readiness = evaluate_finalize_readiness(
            {
                "prd_draft": {
                    "sections": sections,
                },
            }
        )
        next_stage = "finalize" if readiness["ready"] else "refine_loop"

        next_state = deepcopy(current_state)
        next_state["workflow_stage"] = next_stage
        next_state["finalization_ready"] = bool(readiness["ready"])
        next_state["critic_result"] = readiness["critic_result"]
        next_state["prd_snapshot"] = {"sections": deepcopy(sections)}
        next_state["prd_draft"] = {
            "version": next_version,
            "status": "draft_refined",
            "sections": deepcopy(sections),
        }
        next_state["legacy_backfill_version"] = LEGACY_BACKFILL_VERSION

        if next_state["workflow_stage"] == "completed":
            raise AssertionError("legacy backfill must never mark session completed")

        state_repository.create_state_version(
            db=db,
            session_id=session_id,
            version=next_version,
            state_json=next_state,
        )
        prd_repository.create_prd_snapshot(
            db=db,
            session_id=session_id,
            version=next_version,
            sections=deepcopy(sections),
        )
        return True
    except Exception:
        db.rollback()
        logger.exception("legacy session backfill failed", extra={"session_id": session_id})
        return False
