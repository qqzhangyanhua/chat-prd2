from __future__ import annotations

import logging
from collections.abc import Generator
from dataclasses import asdict, dataclass
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.agent.runtime import run_agent
from app.agent.extractor import first_missing_section, normalize_model_extraction_result
from app.core.api_error import raise_api_error
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
from app.schemas.message import ReplyGroupCreatedEventData
from app.services.model_gateway import ModelGatewayError, generate_reply
from app.services.model_gateway import generate_structured_extraction
from app.services.model_gateway import open_reply_stream
from app.services.prd_runtime import build_prd_updated_event_data as _build_prd_updated_event_data
from app.services.prd_runtime import preview_prd_meta as _preview_prd_meta
from app.services.prd_runtime import preview_prd_sections as _preview_prd_sections


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


class LocalReplyStream:
    def __init__(self, reply: str) -> None:
        self._reply = reply

    def __iter__(self):
        yield self._reply

    def close(self):
        return None


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


_PERSISTED_WORKFLOW_STATE_FIELDS: tuple[str, ...] = (
    "workflow_stage",
    "idea_parse_result",
    "prd_draft",
    "critic_result",
    "refine_history",
    "finalization_ready",
)


def _coerce_mapping(value: object) -> dict:
    if isinstance(value, dict):
        return value
    return {}


def _extract_workflow_state_from_turn_decision(turn_decision: object) -> dict:
    """
    兼容真实 turn_decision 载荷：
    1) 部分字段可能在 turn_decision 顶层
    2) 更多字段可能仅存在于 turn_decision.state_patch
    """
    decision_state_patch = _coerce_mapping(getattr(turn_decision, "state_patch", None))
    extracted: dict = {}
    for key in _PERSISTED_WORKFLOW_STATE_FIELDS:
        value = getattr(turn_decision, key, None)
        if value is not None:
            extracted[key] = value
            continue
        if key in decision_state_patch:
            extracted[key] = decision_state_patch[key]
    return extracted


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


def _build_collaboration_mode_label(scene: str) -> str:
    labels = {
        "reasoning": "深度推演模式",
        "general": "通用协作模式",
        "fallback": "稳态兜底模式",
    }
    return labels.get(scene, "通用协作模式")


def _merge_state_patch_with_decision(
    state_patch: dict,
    turn_decision: object,
    *,
    model_config: LLMModelConfig | None = None,
    current_state: dict | None = None,
) -> dict:
    decision_patch = _build_decision_state_patch(turn_decision)
    workflow_patch = _extract_workflow_state_from_turn_decision(turn_decision)
    scene = _infer_model_scene(model_config)
    if model_config is None and current_state is not None:
        existing_scene = current_state.get("current_model_scene")
        if isinstance(existing_scene, str) and existing_scene in {"general", "reasoning", "fallback"}:
            scene = existing_scene

    decision_patch["current_model_scene"] = scene
    decision_patch["collaboration_mode_label"] = _build_collaboration_mode_label(scene)
    # 旧字段保持原合并语义：agent_result.state_patch 仍可覆盖 decision_patch。
    merged = {**decision_patch, **(state_patch or {})}
    # 新增闭环字段优先以 turn_decision / turn_decision.state_patch 为准，
    # 同时兼容 agent_result.state_patch 缺失这些字段的真实路径。
    final_patch = {**merged, **workflow_patch}
    # 确保持久化后的 state 一定包含这些字段，但不覆盖已有 state 的值。
    if current_state is not None:
        for key in _PERSISTED_WORKFLOW_STATE_FIELDS:
            if key in final_patch:
                continue
            if key in current_state:
                continue
            final_patch[key] = None
    return final_patch


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


def _serialize_model_option(model_config: LLMModelConfig) -> dict[str, str]:
    return {
        "id": model_config.id,
        "name": model_config.name,
        "model": model_config.model,
    }


def _normalize_recommended_usage_text(value: str) -> str:
    trimmed = value.strip()
    if not trimmed:
        return ""
    if trimmed[-1] in {"。", "！", "？", ".", "!", "?"}:
        return trimmed
    return f"{trimmed}。"


def _build_recommended_model_basis(model_config: LLMModelConfig) -> str:
    configured_usage = model_config.recommended_usage
    if configured_usage:
        return _normalize_recommended_usage_text(configured_usage)

    model_name = model_config.model
    normalized = model_name.lower()
    if "claude" in normalized or "sonnet" in normalized:
        return "这个替代模型更适合继续长文本推理。"
    if "gpt" in normalized:
        return "这个替代模型适合继续通用对话。"
    return "这个替代模型当前可用，适合继续当前对话。"


def _infer_model_scene(model_config: LLMModelConfig | None) -> str:
    if model_config is None:
        return "general"

    configured_scene = getattr(model_config, "recommended_scene", None)
    if configured_scene in {"general", "reasoning", "fallback"}:
        return configured_scene

    haystack = " ".join(
        part.lower()
        for part in (
            model_config.recommended_usage or "",
            model_config.name or "",
            model_config.model or "",
        )
        if part
    )
    if any(keyword in haystack for keyword in ("长文本", "推理", "reason", "claude", "sonnet")):
        return "reasoning"
    if any(keyword in haystack for keyword in ("通用", "对话", "chat", "gpt")):
        return "general"
    return "fallback"


def _infer_model_family(model_config: LLMModelConfig | None) -> str:
    if model_config is None:
        return "any"

    haystack = " ".join(
        part.lower()
        for part in (model_config.name or "", model_config.model or "")
        if part
    )
    if "claude" in haystack or "sonnet" in haystack:
        return "claude"
    if "gpt" in haystack or "openai" in haystack:
        return "gpt"
    return "other"


def _scene_rank_for_target(candidate_scene: str, target_scene: str) -> int:
    rank_map = {
        "general": {
            "general": 0,
            "reasoning": 1,
            "fallback": 2,
        },
        "reasoning": {
            "reasoning": 0,
            "general": 1,
            "fallback": 2,
        },
        "fallback": {
            "fallback": 0,
            "general": 1,
            "reasoning": 2,
        },
    }
    return rank_map.get(target_scene, rank_map["general"]).get(candidate_scene, 3)


def _sort_available_models(
    enabled_models: list[LLMModelConfig],
    *,
    requested_model: LLMModelConfig | None = None,
) -> list[LLMModelConfig]:
    target_scene = _infer_model_scene(requested_model)
    target_family = _infer_model_family(requested_model)

    def sort_key(model_config: LLMModelConfig) -> tuple[int, int, str, str]:
        candidate_scene = _infer_model_scene(model_config)
        candidate_family = _infer_model_family(model_config)
        scene_rank = _scene_rank_for_target(candidate_scene, target_scene)
        family_rank = 0 if target_family != "any" and candidate_family == target_family else 1
        return (
            scene_rank,
            family_rank,
            model_config.name.lower(),
            model_config.id,
        )

    return sorted(enabled_models, key=sort_key)


def _resolve_recommended_model_scene(model_config: LLMModelConfig) -> str:
    configured_scene = getattr(model_config, "recommended_scene", None)
    if configured_scene in {"general", "reasoning", "fallback"}:
        return configured_scene
    return _infer_model_scene(model_config)


def _build_select_available_model_details(
    db: Session,
    *,
    requested_model_config_id: str,
    requested_model: LLMModelConfig | None = None,
) -> dict[str, object]:
    enabled_models = model_configs_repository.list_enabled_model_configs(db)
    ranked_models = _sort_available_models(enabled_models, requested_model=requested_model)
    available_model_configs = [_serialize_model_option(item) for item in ranked_models]
    details: dict[str, object] = {
        "available_model_configs": available_model_configs,
        "requested_model_config_id": requested_model_config_id,
    }

    if requested_model is not None:
        details["requested_model_name"] = requested_model.name

    recommended_model_entity = ranked_models[0] if ranked_models else None
    recommended_model = (
        _serialize_model_option(recommended_model_entity)
        if recommended_model_entity is not None
        else None
    )
    if recommended_model is not None:
        details["recommended_model_config_id"] = recommended_model["id"]
        details["recommended_model_scene"] = _resolve_recommended_model_scene(recommended_model_entity)
        details["recommended_model_name"] = recommended_model["name"]
        details["recommended_model_reason"] = (
            "原先选择的模型已停用，建议先切换到这个可用模型继续对话。"
            if requested_model is not None
            else "原先选择的模型已不存在，建议先切换到这个可用模型继续对话。"
        ) + _build_recommended_model_basis(recommended_model_entity)

    return details


def _get_enabled_model_config(db: Session, model_config_id: str) -> LLMModelConfig:
    model_config = model_configs_repository.get_model_config_by_id(db, model_config_id)
    if model_config is None:
        raise_api_error(
            status_code=status.HTTP_404_NOT_FOUND,
            code="MODEL_CONFIG_NOT_FOUND",
            message="Model config not found",
            recovery_action={
                "type": "select_available_model",
                "label": "选择可用模型",
                "target": None,
            },
            details=_build_select_available_model_details(
                db,
                requested_model_config_id=model_config_id,
            ),
        )
    if not model_config.enabled:
        raise_api_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="MODEL_CONFIG_DISABLED",
            message="Model config is disabled",
            recovery_action={
                "type": "select_available_model",
                "label": "选择可用模型",
                "target": None,
            },
            details=_build_select_available_model_details(
                db,
                requested_model_config_id=model_config.id,
                requested_model=model_config,
            ),
        )
    return model_config


def _raise_model_gateway_unavailable(error: ModelGatewayError) -> None:
    raise_api_error(
        status_code=status.HTTP_502_BAD_GATEWAY,
        code="MODEL_GATEWAY_UNAVAILABLE",
        message=str(error),
        recovery_action={
            "type": "retry",
            "label": "稍后重试",
            "target": None,
        },
    )


def _raise_regeneration_conflict(code: str, message: str) -> None:
    raise_api_error(
        status_code=status.HTTP_409_CONFLICT,
        code=code,
        message=message,
        recovery_action={
            "type": "reload_session",
            "label": "重新加载会话",
            "target": None,
        },
    )


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
    model_config: LLMModelConfig | None = None,
) -> tuple[str, str, int, str, int]:
    merged_state_patch = _merge_state_patch_with_decision(
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
        if agent_result.reply_mode == "local":
            reply_stream = LocalReplyStream(agent_result.reply)
        else:
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
        try:
            _raise_model_gateway_unavailable(exc)
        except Exception as api_error:
            raise api_error from exc
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
        _raise_regeneration_conflict("REPLY_GROUP_NOT_FOUND", "Reply group not found")
    latest_version = assistant_reply_versions_repository.get_latest_version_for_group(
        db=db,
        reply_group_id=reply_group.id,
    )
    if latest_version is None:
        _raise_regeneration_conflict(
            "REPLY_VERSION_HISTORY_MISSING",
            "Reply version history not found",
        )
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
        try:
            _raise_model_gateway_unavailable(exc)
        except Exception as api_error:
            raise api_error from exc
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
        if agent_result.reply_mode == "local":
            reply = agent_result.reply
        else:
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
            model_config=model_config,
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
        try:
            _raise_model_gateway_unavailable(exc)
        except Exception as api_error:
            raise api_error from exc
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
                model_config=model_configs_repository.get_model_config_by_id(
                    db,
                    prepared.model_meta["model_config_id"],
                ),
            )
        except Exception:
            db.rollback()
            raise

        yield MessageStreamEvent(
            type="prd.updated",
            data=_build_prd_updated_event_data(
                prepared.state,
                prepared.state_patch,
                prepared.prd_patch,
            ),
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
    turn_decision: object,
    state: dict,
    state_patch: dict,
    prd_patch: dict,
) -> tuple[str, int, int]:
    base_state_version = state_repository.get_latest_state_version(db, session_id)
    if base_state_version is None:
        _raise_regeneration_conflict("STATE_SNAPSHOT_MISSING", "State snapshot not found")
    latest_prd_snapshot = prd_repository.get_latest_prd_snapshot(db, session_id)
    if latest_prd_snapshot is None:
        _raise_regeneration_conflict("PRD_SNAPSHOT_MISSING", "PRD snapshot not found")

    reply_group = assistant_reply_groups_repository.get_reply_group_by_user_message(db=db, user_message_id=user_message_id)
    if reply_group is None:
        _raise_regeneration_conflict("REPLY_GROUP_NOT_FOUND", "Reply group not found")
    if reply_group.id != reply_group_id:
        _raise_regeneration_conflict("REPLY_GROUP_MISMATCH", "Reply group mismatch")
    latest_version = assistant_reply_versions_repository.get_latest_version_for_group(
        db=db,
        reply_group_id=reply_group.id,
    )
    if latest_version is None:
        _raise_regeneration_conflict(
            "REPLY_VERSION_HISTORY_MISSING",
            "Reply version history not found",
        )
    if latest_version.version_no + 1 != version_no:
        _raise_regeneration_conflict(
            "REPLY_VERSION_SEQUENCE_MISMATCH",
            "Reply version sequence mismatch",
        )
    merged_state_patch = _merge_state_patch_with_decision(
        state_patch,
        turn_decision,
        current_state=state,
    )
    new_state = apply_state_patch(state, merged_state_patch)
    new_state = apply_prd_patch(new_state, prd_patch)
    next_state_version = base_state_version.version + 1
    state_version = state_repository.create_state_version(
        db,
        session_id,
        next_state_version,
        new_state,
    )
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
    return assistant_version_id, version_no, next_state_version


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
            data=_build_prd_updated_event_data(
                prepared.state,
                prepared.state_patch,
                prepared.prd_patch,
            ),
        )
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
