from __future__ import annotations

from dataclasses import asdict
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.types import TurnDecision
from app.db.models import AgentTurnDecision, ConversationMessage


def _build_turn_decision_state_patch(turn_decision: TurnDecision) -> dict:
    state_patch = dict(turn_decision.state_patch or {})
    state_patch.setdefault("current_phase_subfocus", turn_decision.phase_subfocus)
    state_patch.setdefault("conversation_strategy", turn_decision.conversation_strategy)
    state_patch.setdefault("strategy_reason", turn_decision.strategy_reason)
    state_patch.setdefault("next_best_questions", list(turn_decision.next_best_questions or []))
    state_patch.setdefault("response_mode", turn_decision.response_mode)
    state_patch.setdefault("guidance_mode", turn_decision.guidance_mode)
    state_patch.setdefault("guidance_step", turn_decision.guidance_step)
    state_patch.setdefault("focus_dimension", turn_decision.focus_dimension)
    state_patch.setdefault("transition_reason", turn_decision.transition_reason)
    state_patch.setdefault("transition_trigger", turn_decision.transition_trigger)
    state_patch.setdefault("option_cards", list(turn_decision.option_cards or []))
    state_patch.setdefault("freeform_affordance", turn_decision.freeform_affordance)
    state_patch.setdefault("available_mode_switches", list(turn_decision.available_mode_switches or []))
    state_patch.setdefault("diagnostics", list(turn_decision.diagnostics or []))
    state_patch.setdefault("diagnostic_summary", dict(turn_decision.diagnostic_summary or {}))
    return state_patch


def _apply_turn_decision_fields(entity: AgentTurnDecision, turn_decision: TurnDecision) -> AgentTurnDecision:
    entity.phase = turn_decision.phase
    entity.phase_goal = turn_decision.phase_goal
    entity.understanding_summary = str(turn_decision.understanding.get("summary") or "")
    entity.assumptions_json = turn_decision.assumptions
    entity.risk_flags_json = turn_decision.pm_risk_flags
    entity.next_move = turn_decision.next_move
    entity.suggestions_json = [asdict(suggestion) for suggestion in turn_decision.suggestions]
    entity.recommendation_json = turn_decision.recommendation
    entity.needs_confirmation_json = turn_decision.needs_confirmation
    entity.confidence = turn_decision.confidence
    entity.state_patch_json = _build_turn_decision_state_patch(turn_decision)
    entity.prd_patch_json = turn_decision.prd_patch
    return entity


def create_turn_decision(
    db: Session,
    session_id: str,
    user_message_id: str,
    turn_decision: TurnDecision,
) -> AgentTurnDecision:
    user_message = db.execute(
        select(ConversationMessage).where(ConversationMessage.id == user_message_id)
    ).scalar_one_or_none()
    if user_message is None:
        raise ValueError("User message does not exist")
    if user_message.session_id != session_id:
        raise ValueError("User message does not belong to session")
    if user_message.role != "user":
        raise ValueError("User message must have user role")

    decision = AgentTurnDecision(
        id=str(uuid4()),
        session_id=session_id,
        user_message_id=user_message_id,
        phase=turn_decision.phase,
        phase_goal=turn_decision.phase_goal,
        understanding_summary=str(turn_decision.understanding.get("summary") or ""),
        assumptions_json=turn_decision.assumptions,
        risk_flags_json=turn_decision.pm_risk_flags,
        next_move=turn_decision.next_move,
        suggestions_json=[asdict(suggestion) for suggestion in turn_decision.suggestions],
        recommendation_json=turn_decision.recommendation,
        needs_confirmation_json=turn_decision.needs_confirmation,
        confidence=turn_decision.confidence,
        state_patch_json=_build_turn_decision_state_patch(turn_decision),
        prd_patch_json=turn_decision.prd_patch,
    )
    db.add(decision)
    db.flush()
    return decision


def upsert_turn_decision(
    db: Session,
    session_id: str,
    user_message_id: str,
    turn_decision: TurnDecision,
) -> AgentTurnDecision:
    existing = get_latest_for_user_message(db, user_message_id)
    if existing is not None:
        if existing.session_id != session_id:
            raise ValueError("User message decision does not belong to session")
        _apply_turn_decision_fields(existing, turn_decision)
        db.add(existing)
        db.flush()
        return existing
    return create_turn_decision(
        db=db,
        session_id=session_id,
        user_message_id=user_message_id,
        turn_decision=turn_decision,
    )


def get_latest_for_user_message(db: Session, user_message_id: str) -> AgentTurnDecision | None:
    statement = (
        select(AgentTurnDecision)
        .where(AgentTurnDecision.user_message_id == user_message_id)
        .order_by(AgentTurnDecision.created_at.desc())
        .limit(1)
    )
    return db.execute(statement).scalar_one_or_none()
