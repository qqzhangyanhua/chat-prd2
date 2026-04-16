from __future__ import annotations

import logging
from dataclasses import asdict
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.agent.runtime import run_agent
from app.core.api_error import raise_api_error
from app.db.models import LLMModelConfig, ProjectSession
from app.repositories import assistant_reply_groups as assistant_reply_groups_repository
from app.repositories import assistant_reply_versions as assistant_reply_versions_repository
from app.repositories import messages as messages_repository
from app.repositories import model_configs as model_configs_repository
from app.repositories import state as state_repository
from app.services.message_models import (
    LocalReplyStream,
    PreparedMessageStream,
    PreparedRegenerateStream,
)
from app.services.message_state import build_diagnostics_payload, build_guidance_payload
from app.services.model_gateway import ModelGatewayError, open_reply_stream

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = "你是用户的 AI 产品协作助手，请基于上下文给出简洁、直接的中文回复。"


def require_turn_decision(agent_result: object) -> object:
    turn_decision = getattr(agent_result, "turn_decision", None)
    if turn_decision is None:
        raise RuntimeError("Agent result must include turn_decision")
    return turn_decision


def serialize_model_option(model_config: LLMModelConfig) -> dict[str, str]:
    return {
        "id": model_config.id,
        "name": model_config.name,
        "model": model_config.model,
    }


def normalize_recommended_usage_text(value: str) -> str:
    trimmed = value.strip()
    if not trimmed:
        return ""
    if trimmed[-1] in {"。", "！", "？", ".", "!", "?"}:
        return trimmed
    return f"{trimmed}。"


def build_recommended_model_basis(model_config: LLMModelConfig) -> str:
    configured_usage = model_config.recommended_usage
    if configured_usage:
        return normalize_recommended_usage_text(configured_usage)

    model_name = model_config.model
    normalized = model_name.lower()
    if "claude" in normalized or "sonnet" in normalized:
        return "这个替代模型更适合继续长文本推理。"
    if "gpt" in normalized:
        return "这个替代模型适合继续通用对话。"
    return "这个替代模型当前可用，适合继续当前对话。"


def infer_model_scene(model_config: LLMModelConfig | None) -> str:
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


def infer_model_family(model_config: LLMModelConfig | None) -> str:
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


def scene_rank_for_target(candidate_scene: str, target_scene: str) -> int:
    rank_map = {
        "general": {"general": 0, "reasoning": 1, "fallback": 2},
        "reasoning": {"reasoning": 0, "general": 1, "fallback": 2},
        "fallback": {"fallback": 0, "general": 1, "reasoning": 2},
    }
    return rank_map.get(target_scene, rank_map["general"]).get(candidate_scene, 3)


def sort_available_models(
    enabled_models: list[LLMModelConfig],
    *,
    requested_model: LLMModelConfig | None = None,
) -> list[LLMModelConfig]:
    target_scene = infer_model_scene(requested_model)
    target_family = infer_model_family(requested_model)

    def sort_key(model_config: LLMModelConfig) -> tuple[int, int, str, str]:
        candidate_scene = infer_model_scene(model_config)
        candidate_family = infer_model_family(model_config)
        scene_rank = scene_rank_for_target(candidate_scene, target_scene)
        family_rank = 0 if target_family != "any" and candidate_family == target_family else 1
        return (
            scene_rank,
            family_rank,
            model_config.name.lower(),
            model_config.id,
        )

    return sorted(enabled_models, key=sort_key)


def resolve_recommended_model_scene(model_config: LLMModelConfig) -> str:
    configured_scene = getattr(model_config, "recommended_scene", None)
    if configured_scene in {"general", "reasoning", "fallback"}:
        return configured_scene
    return infer_model_scene(model_config)


def build_select_available_model_details(
    db: Session,
    *,
    requested_model_config_id: str,
    requested_model: LLMModelConfig | None = None,
) -> dict[str, object]:
    enabled_models = model_configs_repository.list_enabled_model_configs(db)
    ranked_models = sort_available_models(enabled_models, requested_model=requested_model)
    available_model_configs = [serialize_model_option(item) for item in ranked_models]
    details: dict[str, object] = {
        "available_model_configs": available_model_configs,
        "requested_model_config_id": requested_model_config_id,
    }

    if requested_model is not None:
        details["requested_model_name"] = requested_model.name

    recommended_model_entity = ranked_models[0] if ranked_models else None
    recommended_model = (
        serialize_model_option(recommended_model_entity)
        if recommended_model_entity is not None
        else None
    )
    if recommended_model is not None:
        details["recommended_model_config_id"] = recommended_model["id"]
        details["recommended_model_scene"] = resolve_recommended_model_scene(recommended_model_entity)
        details["recommended_model_name"] = recommended_model["name"]
        details["recommended_model_reason"] = (
            "原先选择的模型已停用，建议先切换到这个可用模型继续对话。"
            if requested_model is not None
            else "原先选择的模型已不存在，建议先切换到这个可用模型继续对话。"
        ) + build_recommended_model_basis(recommended_model_entity)

    return details


def get_enabled_model_config(db: Session, model_config_id: str) -> LLMModelConfig:
    model_config = model_configs_repository.get_model_config_by_id(db, model_config_id)
    if model_config is None:
        raise_api_error(
            status_code=status.HTTP_404_NOT_FOUND,
            code="MODEL_CONFIG_NOT_FOUND",
            message="Model config not found",
            recovery_action={"type": "select_available_model", "label": "选择可用模型", "target": None},
            details=build_select_available_model_details(db, requested_model_config_id=model_config_id),
        )
    if not model_config.enabled:
        raise_api_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="MODEL_CONFIG_DISABLED",
            message="Model config is disabled",
            recovery_action={"type": "select_available_model", "label": "选择可用模型", "target": None},
            details=build_select_available_model_details(
                db,
                requested_model_config_id=model_config.id,
                requested_model=model_config,
            ),
        )
    return model_config


def raise_model_gateway_unavailable(error: ModelGatewayError) -> None:
    raise_api_error(
        status_code=status.HTTP_502_BAD_GATEWAY,
        code="MODEL_GATEWAY_UNAVAILABLE",
        message=str(error),
        recovery_action={"type": "retry", "label": "稍后重试", "target": None},
    )


def raise_regeneration_conflict(code: str, message: str) -> None:
    raise_api_error(
        status_code=status.HTTP_409_CONFLICT,
        code=code,
        message=message,
        recovery_action={"type": "reload_session", "label": "重新加载会话", "target": None},
    )


def build_model_meta(model_config: LLMModelConfig) -> dict[str, str]:
    return {
        "model_config_id": model_config.id,
        "model_name": model_config.model,
        "display_name": model_config.name,
        "base_url": model_config.base_url,
    }


def build_gateway_messages(db: Session, session_id: str) -> list[dict[str, str]]:
    history = messages_repository.get_messages_for_session(db, session_id)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for item in history:
        if item.role not in {"user", "assistant"}:
            continue
        messages.append({"role": item.role, "content": item.content})
    return messages


def build_conversation_history(
    db: Session,
    session_id: str,
    *,
    up_to_message_id: str | None = None,
) -> list[dict[str, str]]:
    """Return user/assistant messages for conversation history passed to run_agent."""
    history = messages_repository.get_messages_for_session(db, session_id)
    result: list[dict[str, str]] = []
    for item in history:
        if item.role not in {"user", "assistant"}:
            continue
        result.append({"role": item.role, "content": item.content})
        if up_to_message_id is not None and item.id == up_to_message_id and item.role == "user":
            break
    return result


def build_gateway_messages_for_regenerate(
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


def build_decision_guidance_payload(
    *,
    session_id: str,
    user_message_id: str,
    turn_decision: object,
    state: dict | None = None,
) -> dict[str, object]:
    guidance = build_guidance_payload(
        turn_decision,
        session_id=session_id,
        user_message_id=user_message_id,
        next_best_questions=list(getattr(turn_decision, "next_best_questions", []) or []),
    )
    diagnostics = build_diagnostics_payload(
        turn_decision,
        ledger_diagnostics=(state or {}).get("diagnostics") if isinstance(state, dict) else None,
    )
    return {**guidance, **diagnostics}


def get_user_and_mirror_assistant_message(
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


def prepare_message_stream(
    db: Session,
    session_id: str,
    session: ProjectSession,
    content: str,
    model_config_id: str,
    *,
    require_turn_decision_fn=require_turn_decision,
    run_agent_fn=run_agent,
    open_reply_stream_fn=open_reply_stream,
    raise_model_gateway_unavailable_fn=raise_model_gateway_unavailable,
) -> PreparedMessageStream:
    model_config = get_enabled_model_config(db, model_config_id)
    model_meta = build_model_meta(model_config)

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
        conversation_history = build_conversation_history(db, session_id, up_to_message_id=None)
        # Exclude the just-created user message from history (it is passed as user_input)
        if conversation_history and conversation_history[-1] == {"role": "user", "content": content}:
            conversation_history = conversation_history[:-1]
        agent_result = run_agent_fn(
            state, content,
            model_config=model_config,
            conversation_history=conversation_history,
        )
        turn_decision = require_turn_decision_fn(agent_result)
        if agent_result.reply_mode == "local":
            reply_stream = LocalReplyStream(agent_result.reply)
        else:
            reply_stream = open_reply_stream_fn(
                base_url=model_config.base_url,
                api_key=model_config.api_key,
                model=model_config.model,
                messages=build_gateway_messages(db, session_id),
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
            raise_model_gateway_unavailable_fn(exc)
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
        guidance=build_decision_guidance_payload(
            session_id=session_id,
            user_message_id=user_message.id,
            turn_decision=turn_decision,
            state=state,
        ),
        turn_decision=turn_decision,
        state=state,
        state_patch=agent_result.state_patch,
        prd_patch=agent_result.prd_patch,
        model_meta=model_meta,
        reply_stream=reply_stream,
    )


def prepare_regenerate_stream(
    db: Session,
    session_id: str,
    user_message_id: str,
    model_config_id: str,
    *,
    require_turn_decision_fn=require_turn_decision,
    run_agent_fn=run_agent,
    open_reply_stream_fn=open_reply_stream,
    raise_model_gateway_unavailable_fn=raise_model_gateway_unavailable,
) -> PreparedRegenerateStream:
    model_config = get_enabled_model_config(db, model_config_id)
    model_meta = build_model_meta(model_config)
    user_message, assistant_message = get_user_and_mirror_assistant_message(
        db=db,
        session_id=session_id,
        user_message_id=user_message_id,
    )
    reply_group = assistant_reply_groups_repository.get_reply_group_by_user_message(
        db=db,
        user_message_id=user_message_id,
    )
    if reply_group is None:
        raise_regeneration_conflict("REPLY_GROUP_NOT_FOUND", "Reply group not found")
    latest_version = assistant_reply_versions_repository.get_latest_version_for_group(
        db=db,
        reply_group_id=reply_group.id,
    )
    if latest_version is None:
        raise_regeneration_conflict("REPLY_VERSION_HISTORY_MISSING", "Reply version history not found")
    next_version_no = latest_version.version_no + 1

    try:
        state = state_repository.get_latest_state(db, session_id)
        conversation_history = build_conversation_history(
            db, session_id, up_to_message_id=user_message_id
        )
        if conversation_history and conversation_history[-1] == {"role": "user", "content": user_message.content}:
            conversation_history = conversation_history[:-1]
        agent_result = run_agent_fn(
            state, user_message.content,
            model_config=model_config,
            conversation_history=conversation_history,
        )
        turn_decision = require_turn_decision_fn(agent_result)
        if agent_result.reply_mode == "local":
            reply_stream = LocalReplyStream(agent_result.reply)
        else:
            reply_stream = open_reply_stream_fn(
                base_url=model_config.base_url,
                api_key=model_config.api_key,
                model=model_config.model,
                messages=build_gateway_messages_for_regenerate(db, session_id, user_message_id),
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
            raise_model_gateway_unavailable_fn(exc)
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
        guidance=build_decision_guidance_payload(
            session_id=session_id,
            user_message_id=user_message.id,
            turn_decision=turn_decision,
            state=state,
        ),
        turn_decision=turn_decision,
        state=state,
        state_patch=agent_result.state_patch,
        prd_patch=agent_result.prd_patch,
        model_meta=model_meta,
        reply_stream=reply_stream,
        assistant_message_id=assistant_message.id,
    )
