from __future__ import annotations

from types import SimpleNamespace

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session


def _normalize_suggestion_options(raw_options: object) -> list[dict]:
    if not isinstance(raw_options, list):
        return []

    normalized: list[dict] = []
    for item in raw_options:
        if not isinstance(item, dict):
            continue
        label = item.get("label")
        content = item.get("content")
        rationale = item.get("rationale")
        priority = item.get("priority")
        suggestion_type = item.get("type")
        if not isinstance(label, str) or not label.strip():
            continue
        if not isinstance(content, str) or not content.strip():
            continue
        if not isinstance(rationale, str) or not rationale.strip():
            continue
        normalized.append(
            {
                "label": label.strip(),
                "content": content.strip(),
                "rationale": rationale.strip(),
                "priority": priority if isinstance(priority, int) and priority > 0 else len(normalized) + 1,
                "type": suggestion_type if isinstance(suggestion_type, str) else "direction",
            }
        )
    return sorted(normalized, key=lambda item: item["priority"])


def build_reply_sections(decision: object) -> list[dict]:
    phase_goal = getattr(decision, "phase_goal", None) or "继续推进当前 PRD"
    strategy_reason = getattr(decision, "strategy_reason", None) or "继续澄清当前关键信息。"
    next_best_questions = getattr(decision, "next_best_questions", None) or []
    next_question = next_best_questions[0] if next_best_questions else "为了继续推进，请先补一个最具体的真实场景。"
    return [
        {
            "key": "judgement",
            "title": "当前判断：",
            "content": str(strategy_reason),
        },
        {
            "key": "critic_verdict",
            "title": "当前目标：",
            "content": str(phase_goal),
        },
        {
            "key": "next_step",
            "title": "唯一下一问：",
            "content": str(next_question),
        },
    ]
from app.core.api_error import raise_api_error
from app.db.models import AgentTurnDecision, AssistantReplyGroup
from app.repositories import assistant_reply_versions as assistant_reply_versions_repository
from app.repositories import messages as messages_repository
from app.repositories import prd as prd_repository
from app.repositories import sessions as sessions_repository
from app.repositories import state as state_repository
from app.schemas.message import AssistantReplyGroupResponse
from app.schemas.message import AssistantReplyVersionResponse
from app.schemas.message import AgentTurnDecisionResponse
from app.schemas.message import AgentTurnDecisionSectionResponse
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


SCHEMA_OUTDATED_DETAIL = "数据库结构版本过旧，请先执行 alembic upgrade head"


def _raise_if_schema_outdated(error: Exception) -> None:
    normalized_message = str(error).lower()
    schema_markers = (
        "agent_turn_decisions",
        "assistant_reply_groups",
        "assistant_reply_versions",
        "undefinedtable",
        "no such table",
    )
    if any(marker in normalized_message for marker in schema_markers):
        try:
            raise_api_error(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                code="SCHEMA_OUTDATED",
                message=SCHEMA_OUTDATED_DETAIL,
                recovery_action={
                    "type": "run_migration",
                    "label": "执行数据库迁移",
                    "target": "cd apps/api && alembic upgrade head",
                },
            )
        except Exception as api_error:
            raise api_error from error


def _raise_session_not_found() -> None:
    raise_api_error(
        status_code=status.HTTP_404_NOT_FOUND,
        code="SESSION_NOT_FOUND",
        message="Session not found",
        recovery_action={
            "type": "open_workspace_home",
            "label": "返回工作台首页",
            "target": "/workspace",
        },
    )


def _raise_session_snapshot_missing() -> None:
    raise_api_error(
        status_code=status.HTTP_404_NOT_FOUND,
        code="SESSION_SNAPSHOT_MISSING",
        message="Session snapshot not found",
        recovery_action={
            "type": "open_workspace_home",
            "label": "返回工作台首页",
            "target": "/workspace",
        },
    )


def _list_assistant_reply_groups(db: Session, session_id: str) -> list[AssistantReplyGroupResponse]:
    try:
        groups = list(
            db.execute(
                select(AssistantReplyGroup)
                .where(AssistantReplyGroup.session_id == session_id)
                .order_by(AssistantReplyGroup.created_at.asc()),
            ).scalars().all(),
        )
    except (OperationalError, ProgrammingError) as error:
        _raise_if_schema_outdated(error)
        raise
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


def _list_turn_decisions(db: Session, session_id: str) -> list[AgentTurnDecisionResponse]:
    try:
        decisions = list(
            db.execute(
                select(AgentTurnDecision)
                .where(AgentTurnDecision.session_id == session_id)
                .order_by(AgentTurnDecision.created_at.asc()),
            ).scalars().all(),
        )
    except (OperationalError, ProgrammingError) as error:
        _raise_if_schema_outdated(error)
        raise
    return [
        AgentTurnDecisionResponse.model_validate(item).model_copy(
            update={
                "decision_summary": _build_turn_decision_summary(item),
                "decision_sections": _build_turn_decision_sections(item),
            },
        )
        for item in decisions
    ]


def _build_turn_decision_sections(
    decision: AgentTurnDecision,
) -> list[AgentTurnDecisionSectionResponse]:
    conversation_strategy = _infer_conversation_strategy(decision)
    strategy_reason = _infer_strategy_reason(decision, conversation_strategy)
    next_best_questions = _infer_next_best_questions(decision, conversation_strategy)
    confirm_quick_replies = _infer_confirm_quick_replies(decision, conversation_strategy)
    suggestion_options = _normalize_suggestion_options(decision.suggestions_json or [])
    snapshot = SimpleNamespace(
        phase=decision.phase,
        phase_goal=decision.phase_goal,
        assumptions=decision.assumptions_json or [],
        next_move=decision.next_move,
        suggestions=decision.suggestions_json or [],
        recommendation=decision.recommendation_json,
        needs_confirmation=decision.needs_confirmation_json or [],
        conversation_strategy=conversation_strategy,
        strategy_reason=strategy_reason,
        next_best_questions=next_best_questions,
        gaps=[],
    )
    sections: list[AgentTurnDecisionSectionResponse] = []
    for section in build_reply_sections(snapshot):
        meta: dict = {}
        if section["key"] == "judgement":
            meta = {
                "conversation_strategy": conversation_strategy,
                "strategy_label": _conversation_strategy_label(conversation_strategy),
                "strategy_reason": strategy_reason,
            }
        elif section["key"] == "next_step":
            meta = {
                "next_best_questions": next_best_questions,
                "confirm_quick_replies": confirm_quick_replies,
                "suggestion_options": suggestion_options,
            }
        sections.append(
            AgentTurnDecisionSectionResponse.model_validate({**section, "meta": meta})
        )
    return sections


def _infer_conversation_strategy(decision: AgentTurnDecision) -> str:
    if decision.next_move == "force_rank_or_choose":
        return "choose"
    if decision.next_move == "assume_and_advance":
        return "converge"
    if decision.next_move == "summarize_and_confirm":
        return "confirm"
    strategy_from_state = (decision.state_patch_json or {}).get("conversation_strategy")
    if strategy_from_state in {"greet", "clarify", "choose", "converge", "confirm"}:
        return strategy_from_state
    return "clarify"


def _conversation_strategy_label(strategy: str) -> str:
    labels = {
        "greet": "欢迎引导",
        "clarify": "继续澄清",
        "choose": "推动取舍",
        "converge": "收敛推进",
        "confirm": "确认共识",
    }
    return labels.get(strategy, "继续推进")


def _infer_next_best_questions(decision: AgentTurnDecision, strategy: str) -> list[str]:
    explicit_questions = (decision.state_patch_json or {}).get("next_best_questions")
    if isinstance(explicit_questions, list):
        cleaned = [item.strip() for item in explicit_questions if isinstance(item, str) and item.strip()]
        if cleaned:
            return cleaned
    confirmations = decision.needs_confirmation_json or []
    if strategy == "confirm":
        return confirmations or ["请确认当前理解是否准确"]
    if strategy == "choose":
        return ["如果只能先选一个主线，你更愿意先收敛用户还是问题？"]
    if strategy == "converge":
        return ["基于当前信息，你最想先验证哪一项：频率、付费意愿，还是转化阻力？"]
    if decision.next_move == "challenge_and_reframe":
        return ["如果我对问题的判断不对，你最想先纠正用户、问题，还是方案？"]
    return ["为了继续推进，你先补一个最具体的真实场景。"]


def _infer_confirm_quick_replies(decision: AgentTurnDecision, strategy: str) -> list[str]:
    if strategy != "confirm":
        return []

    confirmations = decision.needs_confirmation_json or []
    items = [
        "确认，继续下一步",
        "确认，先看频率",
        "确认，先看付费意愿",
        "确认，先看转化阻力",
    ]
    if any("目标用户" in item for item in confirmations):
        items.append("不对，先改目标用户")
    if any("问题" in item or "痛点" in item for item in confirmations):
        items.append("不对，先改核心问题")

    if len(items) == 4:
        items.extend(["不对，先改目标用户", "不对，先改核心问题"])

    deduped: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


def _infer_strategy_reason(decision: AgentTurnDecision, strategy: str) -> str:
    state_patch = decision.state_patch_json or {}
    explicit_reason = state_patch.get("strategy_reason")
    if isinstance(explicit_reason, str) and explicit_reason.strip():
        return explicit_reason.strip()
    risk_flags = decision.risk_flags_json or []
    if strategy == "greet":
        return "先用可选方向承接用户，再逐步进入正式梳理。"
    if strategy == "choose":
        return "目标用户仍然过泛，当前先推动你做主线取舍。"
    if strategy == "converge":
        return "已有方向信号，但仍有关键缺口，当前继续 converge。"
    if strategy == "confirm":
        if decision.needs_confirmation_json:
            return "核心信息已基本齐备，当前进入 confirm 锁定共识。"
        return "这轮没有新增风险，当前继续停留在 confirm 锁定共识。"
    if "solution_before_problem" in risk_flags:
        return "方案先于问题，当前需要回到 clarify 重构问题定义。"
    if "problem_too_vague" in risk_flags:
        return "当前问题描述仍然过于模糊，需要继续 clarify。"
    return "当前关键信息仍不够具体，需要继续 clarify。"


def _build_turn_decision_summary(decision: AgentTurnDecision) -> str:
    return "；".join(
        f"{section.title}{section.content}" for section in _build_turn_decision_sections(decision)
    )


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
        "current_phase": "idea_clarification",
        "conversation_strategy": "clarify",
        "current_model_scene": "general",
        "collaboration_mode_label": "通用协作模式",
        "strategy_reason": None,
        "phase_goal": None,
        "working_hypotheses": [],
        "evidence": [],
        "decision_readiness": None,
        "pm_risk_flags": [],
        "recommended_directions": [],
        "pending_confirmations": [],
        "rejected_options": [],
        "next_best_questions": [],
        "workflow_stage": "idea_parser",
        "idea_parse_result": None,
        "prd_draft": None,
        "critic_result": None,
        "refine_history": [],
        "finalization_ready": False,
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
        turn_decisions=[],
    )


def get_session_snapshot(db: Session, session_id: str, user_id: str) -> SessionCreateResponse:
    session = sessions_repository.get_session_for_user(db, session_id, user_id)
    if session is None:
        _raise_session_not_found()

    state_version = state_repository.get_latest_state_version(db, session_id)
    prd_snapshot = prd_repository.get_latest_prd_snapshot(db, session_id)

    if state_version is None or prd_snapshot is None:
        _raise_session_snapshot_missing()

    session = sessions_repository.touch_session(db, session)
    db.commit()
    db.refresh(session)

    raw_messages = messages_repository.get_messages_for_session(db, session_id)
    assistant_reply_groups = _list_assistant_reply_groups(db, session_id)
    messages = _build_timeline_messages(raw_messages, assistant_reply_groups)
    turn_decisions = _list_turn_decisions(db, session_id)

    return SessionCreateResponse(
        session=SessionResponse.model_validate(session),
        state=StateSnapshot.model_validate(state_version.state_json),
        prd_snapshot=PrdSnapshotResponse.model_validate(prd_snapshot),
        messages=messages,
        assistant_reply_groups=assistant_reply_groups,
        turn_decisions=turn_decisions,
    )


def list_sessions(db: Session, user_id: str) -> SessionListResponse:
    sessions = sessions_repository.list_sessions_for_user(db, user_id)
    return SessionListResponse(
        sessions=[SessionResponse.model_validate(item) for item in sessions]
    )


def update_session(
    db: Session,
    session_id: str,
    user_id: str,
    payload: SessionUpdateRequest,
) -> SessionCreateResponse:
    session = sessions_repository.get_session_for_user(db, session_id, user_id)
    if session is None:
        _raise_session_not_found()

    updated = sessions_repository.update_session_title(db, session, payload.title)
    db.commit()
    db.refresh(updated)
    return get_session_snapshot(db, session_id, user_id)


def delete_session(db: Session, session_id: str, user_id: str) -> None:
    session = sessions_repository.get_session_for_user(db, session_id, user_id)
    if session is None:
        _raise_session_not_found()

    db.delete(session)
    db.commit()


def export_session_markdown(db: Session, session_id: str, user_id: str) -> str:
    session = sessions_repository.get_session_for_user(db, session_id, user_id)
    if session is None:
        _raise_session_not_found()

    latest_prd = prd_repository.get_latest_prd_snapshot(db, session_id)
    if latest_prd is None:
        return "# PRD\n\n暂无内容。"

    lines = ["# PRD", ""]
    for key, section in latest_prd.sections.items():
        if not isinstance(section, dict):
            continue
        title = section.get("title") or key
        content = section.get("content") or ""
        lines.extend([f"## {title}", str(content), ""])
    return "\n".join(lines).strip() + "\n"
