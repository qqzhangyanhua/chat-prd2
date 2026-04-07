from __future__ import annotations

import logging
from collections.abc import Generator
from dataclasses import asdict, dataclass
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.agent.runtime import run_agent
from app.agent.extractor import first_missing_section, normalize_model_extraction_result
from app.db.models import AssistantReplyGroup
from app.db.models import AssistantReplyVersion
from app.db.models import LLMModelConfig
from app.db.models import ProjectSession
from app.repositories import agent_turn_decisions as agent_turn_decisions_repository
from app.repositories import assistant_reply_groups as assistant_reply_groups_repository
from app.repositories import assistant_reply_versions as assistant_reply_versions_repository
from app.repositories import messages as messages_repository
from app.repositories import model_configs as model_configs_repository
from app.repositories import prd as prd_repository
from app.repositories import state as state_repository
from app.schemas.message import AssistantDeltaEventData
from app.schemas.message import AssistantDoneEventData
from app.schemas.message import AssistantVersionStartedEventData
from app.schemas.message import MessageAcceptedEventData
from app.schemas.message import PrdUpdatedEventData
from app.schemas.message import ReplyGroupCreatedEventData
from app.services.model_gateway import ModelGatewayError, generate_reply
from app.services.model_gateway import generate_structured_extraction
from app.services.model_gateway import open_reply_stream


logger = logging.getLogger(__name__)

SYSTEM_PROMPT = "你是用户的 AI 产品协作助手，请基于上下文给出简洁、直接的中文回复。"


@dataclass(frozen=True, slots=True)
class MessageResult:
    user_message_id: str
    assistant_message_id: str
    action: dict
    reply: str


@dataclass(frozen=True, slots=True)
class MessageStreamEvent:
    type: str
    data: dict


@dataclass(frozen=True, slots=True)
class PreparedMessageStream:
    user_message_id: str
    reply_group_id: str
    assistant_version_id: str
    next_version_no: int
    action: dict
    turn_decision: object
    state: dict
    state_patch: dict
    prd_patch: dict
    model_meta: dict[str, str]
    reply_stream: object


@dataclass(frozen=True, slots=True)
class PreparedRegenerateStream(PreparedMessageStream):
    assistant_message_id: str


def apply_state_patch(current_state: dict, patch: dict) -> dict:
    if not patch:
        return current_state
    return {**current_state, **patch}


def apply_prd_patch(current_state: dict, patch: dict) -> dict:
    if not patch:
        return current_state
    sections = current_state.get("prd_snapshot", {}).get("sections", {})
    current_state["prd_snapshot"]["sections"] = {**sections, **patch}
    return current_state


def _preview_prd_sections(state: dict, patch: dict) -> dict:
    sections = state.get("prd_snapshot", {}).get("sections", {})
    if not patch:
        return sections
    return {**sections, **patch}


def _require_turn_decision(agent_result: object) -> object:
    turn_decision = getattr(agent_result, "turn_decision", None)
    if turn_decision is None:
        raise RuntimeError("Agent result must include turn_decision")
    return turn_decision


def _dedupe_str_list(items: list[str]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered


def _build_decision_state_patch(turn_decision: object) -> dict:
    suggestions = getattr(turn_decision, "suggestions", []) or []
    recommendation = getattr(turn_decision, "recommendation", None)
    recommended_directions = [asdict(item) for item in suggestions]
    if recommendation and not any(
        item.get("label") == recommendation.get("label")
        for item in recommended_directions
    ):
        recommended_directions.insert(0, recommendation)

    assumptions = getattr(turn_decision, "assumptions", []) or []
    return {
        "current_phase": getattr(turn_decision, "phase", "idea_clarification"),
        "conversation_strategy": getattr(turn_decision, "conversation_strategy", "clarify"),
        "strategy_reason": getattr(turn_decision, "strategy_reason", None),
        "phase_goal": getattr(turn_decision, "phase_goal", None),
        "working_hypotheses": assumptions,
        "pm_risk_flags": _dedupe_str_list(list(getattr(turn_decision, "pm_risk_flags", []) or [])),
        "recommended_directions": recommended_directions,
        "pending_confirmations": list(getattr(turn_decision, "needs_confirmation", []) or []),
        "next_best_questions": list(getattr(turn_decision, "next_best_questions", []) or []),
    }


def _merge_state_patch_with_decision(state_patch: dict, turn_decision: object) -> dict:
    decision_patch = _build_decision_state_patch(turn_decision)
    return {**decision_patch, **state_patch}


def _resolve_model_extraction_result(
    state: dict,
    user_input: str,
    model_config: LLMModelConfig,
) -> object | None:
    target_section = first_missing_section(state)
    if target_section is None:
        return None

    try:
        payload = generate_structured_extraction(
            base_url=model_config.base_url,
            api_key=model_config.api_key,
            model=model_config.model,
            state=state,
            target_section=target_section,
            user_input=user_input,
        )
    except ModelGatewayError as exc:
        logger.warning(
            "结构化提取失败，回退规则结果: model_config_id=%s model=%s base_url=%s detail=%s",
            model_config.id,
            model_config.model,
            model_config.base_url,
            exc,
        )
        return None

    return normalize_model_extraction_result(payload)


def _get_enabled_model_config(db: Session, model_config_id: str) -> LLMModelConfig:
    model_config = model_configs_repository.get_model_config_by_id(db, model_config_id)
    if model_config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model config not found")
    if not model_config.enabled:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Model config is disabled")
    return model_config


def _build_model_meta(model_config: LLMModelConfig) -> dict[str, str]:
    return {
        "model_config_id": model_config.id,
        "model_name": model_config.model,
        "display_name": model_config.name,
        "base_url": model_config.base_url,
    }


def _build_gateway_messages(db: Session, session_id: str) -> list[dict[str, str]]:
    history = messages_repository.get_messages_for_session(db, session_id)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for item in history:
        if item.role not in {"user", "assistant"}:
            continue
        messages.append({"role": item.role, "content": item.content})
    return messages


def _build_gateway_messages_for_regenerate(
    db: Session,
    session_id: str,
    user_message_id: str,
) -> list[dict[str, str]]:
    history = messages_repository.get_messages_for_session(db, session_id)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for item in history:
        if item.role not in {"user", "assistant"}:
            continue
        messages.append({"role": item.role, "content": item.content})
        if item.id == user_message_id and item.role == "user":
            break
    return messages


def _get_user_and_mirror_assistant_message(
    db: Session,
    session_id: str,
    user_message_id: str,
) -> tuple[object, object]:
    history = messages_repository.get_messages_for_session(db, session_id)
    user_message = None
    mirror_assistant = None
    user_seen = False
    for item in history:
        if not user_seen and item.id == user_message_id and item.role == "user":
            user_message = item
            user_seen = True
            continue
        if user_seen:
            if item.role == "assistant":
                mirror_assistant = item
                break
            if item.role == "user":
                break
    if user_message is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User message not found")
    if mirror_assistant is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Assistant mirror message not found")
    return user_message, mirror_assistant


def _persist_assistant_reply_and_version(
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
) -> tuple[str, str, int, str, int]:
    merged_state_patch = _merge_state_patch_with_decision(state_patch, turn_decision)
    new_state = apply_state_patch(state, merged_state_patch)
    new_state = apply_prd_patch(new_state, prd_patch)

    latest_state_version = state_repository.get_latest_state_version(db, session_id)
    next_state_version = (latest_state_version.version + 1) if latest_state_version else 1

    state_version = state_repository.create_state_version(db, session_id, next_state_version, new_state)
    prd_repository.create_prd_snapshot(
        db, session_id, next_state_version,
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
    )


def _prepare_message_stream(
    db: Session,
    session_id: str,
    session: ProjectSession,
    content: str,
    model_config_id: str,
) -> PreparedMessageStream:
    model_config = _get_enabled_model_config(db, model_config_id)
    model_meta = _build_model_meta(model_config)

    try:
        user_message = messages_repository.create_message(
            db=db,
            session_id=session_id,
            role="user",
            content=content,
            meta=model_meta,
        )
        messages_repository.touch_session_activity(db, session)

        state = state_repository.get_latest_state(db, session_id)
        model_extraction_result = _resolve_model_extraction_result(state, content, model_config)
        agent_result = run_agent(state, content, model_result=model_extraction_result)
        turn_decision = _require_turn_decision(agent_result)
        reply_stream = open_reply_stream(
            base_url=model_config.base_url,
            api_key=model_config.api_key,
            model=model_config.model,
            messages=_build_gateway_messages(db, session_id),
        )
        db.commit()
    except ModelGatewayError as exc:
        logger.warning(
            "消息发送调用模型失败: session_id=%s model_config_id=%s model=%s base_url=%s detail=%s",
            session_id,
            model_config.id,
            model_config.model,
            model_config.base_url,
            exc,
        )
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    except Exception:
        db.rollback()
        raise

    return PreparedMessageStream(
        user_message_id=user_message.id,
        reply_group_id=str(uuid4()),
        assistant_version_id=str(uuid4()),
        next_version_no=1,
        action=asdict(agent_result.action),
        turn_decision=turn_decision,
        state=state,
        state_patch=agent_result.state_patch,
        prd_patch=agent_result.prd_patch,
        model_meta=model_meta,
        reply_stream=reply_stream,
    )


def _prepare_regenerate_stream(
    db: Session,
    session_id: str,
    user_message_id: str,
    model_config_id: str,
) -> PreparedRegenerateStream:
    model_config = _get_enabled_model_config(db, model_config_id)
    model_meta = _build_model_meta(model_config)
    user_message, assistant_message = _get_user_and_mirror_assistant_message(
        db=db,
        session_id=session_id,
        user_message_id=user_message_id,
    )
    reply_group = assistant_reply_groups_repository.get_reply_group_by_user_message(
        db=db,
        user_message_id=user_message_id,
    )
    if reply_group is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Reply group not found")
    latest_version = assistant_reply_versions_repository.get_latest_version_for_group(
        db=db,
        reply_group_id=reply_group.id,
    )
    if latest_version is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Reply version history not found")
    next_version_no = latest_version.version_no + 1

    try:
        state = state_repository.get_latest_state(db, session_id)
        agent_result = run_agent(state, "继续")
        turn_decision = _require_turn_decision(agent_result)
        reply_stream = open_reply_stream(
            base_url=model_config.base_url,
            api_key=model_config.api_key,
            model=model_config.model,
            messages=_build_gateway_messages_for_regenerate(db, session_id, user_message_id),
        )
    except ModelGatewayError as exc:
        logger.warning(
            "消息重生成调用模型失败: session_id=%s user_message_id=%s model_config_id=%s model=%s base_url=%s detail=%s",
            session_id,
            user_message_id,
            model_config.id,
            model_config.model,
            model_config.base_url,
            exc,
        )
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    except Exception:
        db.rollback()
        raise

    return PreparedRegenerateStream(
        user_message_id=user_message.id,
        reply_group_id=reply_group.id,
        assistant_version_id=str(uuid4()),
        next_version_no=next_version_no,
        action=asdict(agent_result.action),
        turn_decision=turn_decision,
        state=state,
        state_patch=agent_result.state_patch,
        prd_patch=agent_result.prd_patch,
        model_meta=model_meta,
        reply_stream=reply_stream,
        assistant_message_id=assistant_message.id,
    )


def handle_user_message(
    db: Session,
    session_id: str,
    session: ProjectSession,
    content: str,
    model_config_id: str,
) -> MessageResult:
    model_config = _get_enabled_model_config(db, model_config_id)
    model_meta = _build_model_meta(model_config)

    try:
        user_message = messages_repository.create_message(
            db=db,
            session_id=session_id,
            role="user",
            content=content,
            meta=model_meta,
        )
        messages_repository.touch_session_activity(db, session)

        state = state_repository.get_latest_state(db, session_id)
        model_extraction_result = _resolve_model_extraction_result(state, content, model_config)
        agent_result = run_agent(state, content, model_result=model_extraction_result)
        turn_decision = _require_turn_decision(agent_result)
        reply = generate_reply(
            base_url=model_config.base_url,
            api_key=model_config.api_key,
            model=model_config.model,
            messages=_build_gateway_messages(db, session_id),
        )

        assistant_message_id, _, _, _, _ = _persist_assistant_reply_and_version(
            db=db,
            session_id=session_id,
            session=session,
            user_message_id=user_message.id,
            reply_group_id=str(uuid4()),
            assistant_version_id=str(uuid4()),
            version_no=1,
            reply=reply,
            model_meta=model_meta,
            action=asdict(agent_result.action),
            turn_decision=turn_decision,
            state=state,
            state_patch=agent_result.state_patch,
            prd_patch=agent_result.prd_patch,
        )
    except ModelGatewayError as exc:
        logger.warning(
            "消息发送调用模型失败: session_id=%s model_config_id=%s model=%s base_url=%s detail=%s",
            session_id,
            model_config.id,
            model_config.model,
            model_config.base_url,
            exc,
        )
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    except Exception:
        db.rollback()
        raise

    return MessageResult(
        user_message_id=user_message.id,
        assistant_message_id=assistant_message_id,
        action=asdict(agent_result.action),
        reply=reply,
    )


def stream_user_message_events(
    db: Session,
    session_id: str,
    session: ProjectSession,
    content: str,
    model_config_id: str,
) -> Generator[MessageStreamEvent, None, None]:
    prepared = _prepare_message_stream(
        db=db,
        session_id=session_id,
        session=session,
        content=content,
        model_config_id=model_config_id,
    )

    def event_generator() -> Generator[MessageStreamEvent, None, None]:
        yield MessageStreamEvent(
            type="message.accepted",
            data=MessageAcceptedEventData(
                message_id=prepared.user_message_id,
                session_id=session_id,
            ).model_dump(),
        )
        yield MessageStreamEvent(
            type="reply_group.created",
            data=ReplyGroupCreatedEventData(
                reply_group_id=prepared.reply_group_id,
                user_message_id=prepared.user_message_id,
                session_id=session_id,
                is_regeneration=False,
                is_latest=False,
            ).model_dump(),
        )
        yield MessageStreamEvent(
            type="action.decided",
            data=prepared.action,
        )
        yield MessageStreamEvent(
            type="assistant.version.started",
            data=AssistantVersionStartedEventData(
                session_id=session_id,
                user_message_id=prepared.user_message_id,
                reply_group_id=prepared.reply_group_id,
                assistant_version_id=prepared.assistant_version_id,
                version_no=prepared.next_version_no,
                assistant_message_id=None,
                model_config_id=prepared.model_meta["model_config_id"],
                is_regeneration=False,
                is_latest=False,
            ).model_dump(),
        )

        reply_parts: list[str] = []
        try:
            for delta in prepared.reply_stream:
                reply_parts.append(delta)
                yield MessageStreamEvent(
                    type="assistant.delta",
                    data=AssistantDeltaEventData(
                        session_id=session_id,
                        user_message_id=prepared.user_message_id,
                        reply_group_id=prepared.reply_group_id,
                        assistant_version_id=prepared.assistant_version_id,
                        version_no=prepared.next_version_no,
                        assistant_message_id=None,
                        model_config_id=prepared.model_meta["model_config_id"],
                        delta=delta,
                        is_regeneration=False,
                        is_latest=False,
                    ).model_dump(),
                )
        except ModelGatewayError as exc:
            logger.warning(
                "消息流式生成中断: session_id=%s model_config_id=%s base_url=%s detail=%s",
                session_id,
                prepared.model_meta["model_config_id"],
                prepared.model_meta["base_url"],
                exc,
            )
            return
        finally:
            close = getattr(prepared.reply_stream, "close", None)
            if callable(close):
                close()

        try:
            assistant_message_id, reply_group_id, version_no, version_id, prd_snapshot_version = _persist_assistant_reply_and_version(
                db=db,
                session_id=session_id,
                session=session,
                user_message_id=prepared.user_message_id,
                reply_group_id=prepared.reply_group_id,
                assistant_version_id=prepared.assistant_version_id,
                version_no=prepared.next_version_no,
                reply="".join(reply_parts),
                model_meta=prepared.model_meta,
                action=prepared.action,
                turn_decision=prepared.turn_decision,
                state=prepared.state,
                state_patch=prepared.state_patch,
                prd_patch=prepared.prd_patch,
            )
        except Exception:
            db.rollback()
            raise

        yield MessageStreamEvent(
            type="prd.updated",
            data=PrdUpdatedEventData(
                sections=_preview_prd_sections(prepared.state, prepared.prd_patch),
            ).model_dump(),
        )
        yield MessageStreamEvent(
            type="assistant.done",
            data=AssistantDoneEventData(
                session_id=session_id,
                user_message_id=prepared.user_message_id,
                reply_group_id=reply_group_id,
                assistant_version_id=version_id,
                version_id=version_id,
                version_no=version_no,
                assistant_message_id=assistant_message_id,
                model_config_id=prepared.model_meta["model_config_id"],
                prd_snapshot_version=prd_snapshot_version,
                is_regeneration=False,
                is_latest=True,
            ).model_dump() | {"message_id": assistant_message_id},
        )

    return event_generator()


def _persist_regenerated_reply_version(
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
    state: dict,
    state_patch: dict,
    prd_patch: dict,
) -> tuple[str, int, int]:
    latest_state_version = state_repository.get_latest_state_version(db, session_id)
    if latest_state_version is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="State snapshot not found")
    latest_prd_snapshot = prd_repository.get_latest_prd_snapshot(db, session_id)
    if latest_prd_snapshot is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="PRD snapshot not found")

    reply_group = assistant_reply_groups_repository.get_reply_group_by_user_message(db=db, user_message_id=user_message_id)
    if reply_group is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Reply group not found")
    if reply_group.id != reply_group_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Reply group mismatch")
    latest_version = assistant_reply_versions_repository.get_latest_version_for_group(
        db=db,
        reply_group_id=reply_group.id,
    )
    if latest_version is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Reply version history not found")
    if latest_version.version_no + 1 != version_no:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Reply version sequence mismatch")
    created_version = AssistantReplyVersion(
        id=assistant_version_id,
        reply_group_id=reply_group.id,
        session_id=session_id,
        user_message_id=user_message_id,
        version_no=version_no,
        content=reply,
        action_snapshot=action,
        model_meta=model_meta,
        state_version_id=latest_state_version.id,
        prd_snapshot_version=latest_prd_snapshot.version,
    )
    db.add(created_version)
    db.flush()
    reply_group.latest_version_id = assistant_version_id
    db.add(reply_group)
    _, assistant_message = _get_user_and_mirror_assistant_message(
        db=db,
        session_id=session_id,
        user_message_id=user_message_id,
    )
    assistant_message.content = reply
    assistant_message.meta = {**model_meta, "action": action}
    db.add(assistant_message)
    messages_repository.touch_session_activity(db, session)
    db.commit()
    return assistant_version_id, version_no, latest_prd_snapshot.version


def stream_regenerate_message_events(
    db: Session,
    session_id: str,
    session: ProjectSession,
    user_message_id: str,
    model_config_id: str,
) -> Generator[MessageStreamEvent, None, None]:
    prepared = _prepare_regenerate_stream(
        db=db,
        session_id=session_id,
        user_message_id=user_message_id,
        model_config_id=model_config_id,
    )

    def event_generator() -> Generator[MessageStreamEvent, None, None]:
        yield MessageStreamEvent(
            type="action.decided",
            data=prepared.action,
        )
        yield MessageStreamEvent(
            type="assistant.version.started",
            data=AssistantVersionStartedEventData(
                session_id=session_id,
                user_message_id=prepared.user_message_id,
                reply_group_id=prepared.reply_group_id,
                assistant_version_id=prepared.assistant_version_id,
                version_no=prepared.next_version_no,
                assistant_message_id=prepared.assistant_message_id,
                model_config_id=prepared.model_meta["model_config_id"],
                is_regeneration=True,
                is_latest=False,
            ).model_dump(),
        )

        reply_parts: list[str] = []
        try:
            for delta in prepared.reply_stream:
                reply_parts.append(delta)
                yield MessageStreamEvent(
                    type="assistant.delta",
                    data=AssistantDeltaEventData(
                        session_id=session_id,
                        user_message_id=prepared.user_message_id,
                        reply_group_id=prepared.reply_group_id,
                        assistant_version_id=prepared.assistant_version_id,
                        version_no=prepared.next_version_no,
                        assistant_message_id=prepared.assistant_message_id,
                        model_config_id=prepared.model_meta["model_config_id"],
                        delta=delta,
                        is_regeneration=True,
                        is_latest=False,
                    ).model_dump(),
                )
        except ModelGatewayError as exc:
            logger.warning(
                "消息重生成流式中断: session_id=%s user_message_id=%s model_config_id=%s base_url=%s detail=%s",
                session_id,
                prepared.user_message_id,
                prepared.model_meta["model_config_id"],
                prepared.model_meta["base_url"],
                exc,
            )
            return
        finally:
            close = getattr(prepared.reply_stream, "close", None)
            if callable(close):
                close()

        try:
            version_id, version_no, prd_snapshot_version = _persist_regenerated_reply_version(
                db=db,
                session_id=session_id,
                session=session,
                user_message_id=prepared.user_message_id,
                reply_group_id=prepared.reply_group_id,
                assistant_version_id=prepared.assistant_version_id,
                version_no=prepared.next_version_no,
                reply="".join(reply_parts),
                model_meta=prepared.model_meta,
                action=prepared.action,
                state=prepared.state,
                state_patch=prepared.state_patch,
                prd_patch=prepared.prd_patch,
            )
        except Exception:
            db.rollback()
            raise

        yield MessageStreamEvent(
            type="assistant.done",
            data=AssistantDoneEventData(
                session_id=session_id,
                user_message_id=prepared.user_message_id,
                reply_group_id=prepared.reply_group_id,
                assistant_version_id=version_id,
                version_id=version_id,
                version_no=version_no,
                assistant_message_id=prepared.assistant_message_id,
                model_config_id=prepared.model_meta["model_config_id"],
                prd_snapshot_version=prd_snapshot_version,
                is_regeneration=True,
                is_latest=True,
            ).model_dump(),
        )

    return event_generator()
