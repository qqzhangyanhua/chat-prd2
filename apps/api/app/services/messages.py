from __future__ import annotations

from dataclasses import asdict, dataclass

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.agent.runtime import run_agent
from app.db.models import LLMModelConfig
from app.db.models import ProjectSession
from app.repositories import messages as messages_repository
from app.repositories import model_configs as model_configs_repository
from app.repositories import prd as prd_repository
from app.repositories import state as state_repository
from app.services.model_gateway import ModelGatewayError, generate_reply


SYSTEM_PROMPT = "你是用户的 AI 产品协作助手，请基于上下文给出简洁、直接的中文回复。"


@dataclass(frozen=True, slots=True)
class MessageResult:
    user_message_id: str
    assistant_message_id: str
    action: dict
    reply: str


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
        agent_result = run_agent(state, content)
        reply = generate_reply(
            base_url=model_config.base_url,
            api_key=model_config.api_key,
            model=model_config.model,
            messages=_build_gateway_messages(db, session_id),
        )

        new_state = apply_state_patch(state, agent_result.state_patch)
        new_state = apply_prd_patch(new_state, agent_result.prd_patch)

        latest_version = state_repository.get_latest_state_version(db, session_id)
        next_version = (latest_version.version + 1) if latest_version else 1

        state_repository.create_state_version(db, session_id, next_version, new_state)
        prd_repository.create_prd_snapshot(
            db, session_id, next_version,
            new_state.get("prd_snapshot", {}).get("sections", {}),
        )

        assistant_message = messages_repository.create_message(
            db=db,
            session_id=session_id,
            role="assistant",
            content=reply,
            meta={**model_meta, "action": asdict(agent_result.action)},
        )
        messages_repository.touch_session_activity(db, session)
        db.commit()
    except ModelGatewayError as exc:
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
        assistant_message_id=assistant_message.id,
        action=asdict(agent_result.action),
        reply=reply,
    )
