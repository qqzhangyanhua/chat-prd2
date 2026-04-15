from __future__ import annotations

import logging
from collections.abc import Generator
from dataclasses import asdict
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.agent.runtime import run_agent
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
from app.schemas.message import AssistantErrorEventData
from app.schemas.message import AssistantVersionStartedEventData
from app.schemas.message import MessageAcceptedEventData
from app.schemas.message import ReplyGroupCreatedEventData
from app.services import finalize_session as finalize_session_service
from app.services.message_models import (
    LocalReplyStream,
    MessageResult,
    MessageStreamEvent,
    PreparedMessageStream,
    PreparedRegenerateStream,
)
from app.services.message_persistence import (
    persist_assistant_reply_and_version as _persist_assistant_reply_and_version_impl,
    persist_regenerated_reply_version as _persist_regenerated_reply_version_impl,
)
from app.services.message_preparation import (
    build_conversation_history as _build_conversation_history_impl,
    build_gateway_messages as _build_gateway_messages_impl,
    build_gateway_messages_for_regenerate as _build_gateway_messages_for_regenerate_impl,
    build_model_meta as _build_model_meta_impl,
    get_enabled_model_config as _get_enabled_model_config_impl,
    get_user_and_mirror_assistant_message as _get_user_and_mirror_assistant_message_impl,
    prepare_message_stream as _prepare_message_stream_impl,
    prepare_regenerate_stream as _prepare_regenerate_stream_impl,
    raise_model_gateway_unavailable as _raise_model_gateway_unavailable_impl,
    raise_regeneration_conflict as _raise_regeneration_conflict_impl,
    require_turn_decision as _require_turn_decision_impl,
)
from app.services.message_state import (
    apply_prd_patch,
    apply_state_patch,
    build_collaboration_mode_label as _build_collaboration_mode_label,
    infer_model_scene as _infer_model_scene,
    merge_state_patch_with_decision as _merge_state_patch_with_decision,
)
from app.services.model_gateway import ModelGatewayError, generate_reply
from app.services.model_gateway import open_reply_stream
from app.services.prd_runtime import build_prd_updated_event_data as _build_prd_updated_event_data
from app.services.prd_runtime import preview_prd_meta as _preview_prd_meta
from app.services.prd_runtime import preview_prd_sections as _preview_prd_sections


logger = logging.getLogger(__name__)

SYSTEM_PROMPT = "你是用户的 AI 产品协作助手，请基于上下文给出简洁、直接的中文回复。"


def _is_finalize_action(action: dict) -> bool:
    return action.get("action") == "finalize"


def _extract_prd_snapshot_version(snapshot: object, default: int) -> int:
    if isinstance(snapshot, dict):
        prd_snapshot = snapshot.get("prd_snapshot")
        if isinstance(prd_snapshot, dict) and isinstance(prd_snapshot.get("version"), int):
            return prd_snapshot["version"]
        return default
    prd_snapshot = getattr(snapshot, "prd_snapshot", None)
    version = getattr(prd_snapshot, "version", None)
    if isinstance(version, int):
        return version
    return default


def _build_finalized_prd_updated_payload(snapshot: object) -> dict:
    if isinstance(snapshot, dict):
        prd_snapshot = snapshot.get("prd_snapshot")
        sections = prd_snapshot.get("sections") if isinstance(prd_snapshot, dict) else {}
        return {"sections": sections if isinstance(sections, dict) else {}, "meta": {"status": "finalized"}}
    prd_snapshot = getattr(snapshot, "prd_snapshot", None)
    sections = getattr(prd_snapshot, "sections", None)
    if not isinstance(sections, dict):
        sections = {}
    return {"sections": sections, "meta": {"status": "finalized"}}


def _build_assistant_error_event(
    *,
    session_id: str,
    user_message_id: str,
    reply_group_id: str | None,
    assistant_version_id: str | None,
    version_no: int | None,
    model_config_id: str,
    message: str,
    is_regeneration: bool,
) -> MessageStreamEvent:
    return MessageStreamEvent(
        type="assistant.error",
        data=AssistantErrorEventData(
            session_id=session_id,
            user_message_id=user_message_id,
            reply_group_id=reply_group_id,
            assistant_version_id=assistant_version_id,
            version_no=version_no,
            model_config_id=model_config_id,
            code="MODEL_STREAM_FAILED",
            message=message,
            recovery_action={
                "type": "retry",
                "label": "稍后重试",
                "target": None,
            },
            is_regeneration=is_regeneration,
            is_latest=False,
        ).model_dump(),
    )

def _require_turn_decision(agent_result: object) -> object:
    return _require_turn_decision_impl(agent_result)


def _get_enabled_model_config(db: Session, model_config_id: str) -> LLMModelConfig:
    return _get_enabled_model_config_impl(db, model_config_id)


def _raise_model_gateway_unavailable(error: ModelGatewayError) -> None:
    _raise_model_gateway_unavailable_impl(error)


def _raise_regeneration_conflict(code: str, message: str) -> None:
    _raise_regeneration_conflict_impl(code, message)


def _build_model_meta(model_config: LLMModelConfig) -> dict[str, str]:
    return _build_model_meta_impl(model_config)


def _build_conversation_history(
    db: Session,
    session_id: str,
    *,
    up_to_message_id: str | None = None,
) -> list[dict[str, str]]:
    return _build_conversation_history_impl(
        db,
        session_id,
        up_to_message_id=up_to_message_id,
    )


def _build_gateway_messages(db: Session, session_id: str) -> list[dict[str, str]]:
    return _build_gateway_messages_impl(db, session_id)


def _build_gateway_messages_for_regenerate(
    db: Session,
    session_id: str,
    user_message_id: str,
) -> list[dict[str, str]]:
    return _build_gateway_messages_for_regenerate_impl(db, session_id, user_message_id)


def _get_user_and_mirror_assistant_message(
    db: Session,
    session_id: str,
    user_message_id: str,
) -> tuple[object, object]:
    return _get_user_and_mirror_assistant_message_impl(db, session_id, user_message_id)


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
) -> tuple[str, str, int, str, int, str | None]:
    return _persist_assistant_reply_and_version_impl(
        db=db,
        session_id=session_id,
        session=session,
        user_message_id=user_message_id,
        reply_group_id=reply_group_id,
        assistant_version_id=assistant_version_id,
        version_no=version_no,
        reply=reply,
        model_meta=model_meta,
        action=action,
        turn_decision=turn_decision,
        state=state,
        state_patch=state_patch,
        prd_patch=prd_patch,
        model_config=model_config,
    )


def _prepare_message_stream(
    db: Session,
    session_id: str,
    session: ProjectSession,
    content: str,
    model_config_id: str,
) -> PreparedMessageStream:
    return _prepare_message_stream_impl(
        db=db,
        session_id=session_id,
        session=session,
        content=content,
        model_config_id=model_config_id,
        require_turn_decision_fn=_require_turn_decision,
        run_agent_fn=run_agent,
        open_reply_stream_fn=open_reply_stream,
        raise_model_gateway_unavailable_fn=_raise_model_gateway_unavailable,
    )


def _prepare_regenerate_stream(
    db: Session,
    session_id: str,
    user_message_id: str,
    model_config_id: str,
) -> PreparedRegenerateStream:
    return _prepare_regenerate_stream_impl(
        db=db,
        session_id=session_id,
        user_message_id=user_message_id,
        model_config_id=model_config_id,
        require_turn_decision_fn=_require_turn_decision,
        run_agent_fn=run_agent,
        open_reply_stream_fn=open_reply_stream,
        raise_model_gateway_unavailable_fn=_raise_model_gateway_unavailable,
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
        conversation_history = _build_conversation_history(db, session_id)
        if conversation_history and conversation_history[-1] == {"role": "user", "content": content}:
            conversation_history = conversation_history[:-1]
        agent_result = run_agent(
            state,
            content,
            model_config=model_config,
            conversation_history=conversation_history,
        )
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

        action_payload = asdict(agent_result.action)
        assistant_message_id, _, _, _, _, _ = _persist_assistant_reply_and_version(
            db=db,
            session_id=session_id,
            session=session,
            user_message_id=user_message.id,
            reply_group_id=str(uuid4()),
            assistant_version_id=str(uuid4()),
            version_no=1,
            reply=reply,
            model_meta=model_meta,
            action=action_payload,
            turn_decision=turn_decision,
            state=state,
            state_patch=agent_result.state_patch,
            prd_patch=agent_result.prd_patch,
            model_config=model_config,
        )
        if _is_finalize_action(action_payload):
            finalize_session_service.finalize_session(
                db=db,
                session_id=session_id,
                user_id=session.user_id,
                confirmation_source="message",
                preference=agent_result.state_patch.get("finalize_preference"),
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
        action=action_payload,
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
        error_event: MessageStreamEvent | None = None
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
            error_event = _build_assistant_error_event(
                session_id=session_id,
                user_message_id=prepared.user_message_id,
                reply_group_id=prepared.reply_group_id,
                assistant_version_id=prepared.assistant_version_id,
                version_no=prepared.next_version_no,
                model_config_id=prepared.model_meta["model_config_id"],
                message=str(exc),
                is_regeneration=False,
            )
        finally:
            close = getattr(prepared.reply_stream, "close", None)
            if callable(close):
                close()

        if error_event is not None:
            yield error_event
            return

        try:
            assistant_message_id, reply_group_id, version_no, version_id, prd_snapshot_version, created_at = _persist_assistant_reply_and_version(
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

        finalized_snapshot = None
        if _is_finalize_action(prepared.action):
            finalized_snapshot = finalize_session_service.finalize_session(
                db=db,
                session_id=session_id,
                user_id=session.user_id,
                confirmation_source="message",
                preference=prepared.state_patch.get("finalize_preference"),
            )
            prd_snapshot_version = _extract_prd_snapshot_version(
                finalized_snapshot,
                prd_snapshot_version,
            )

        if finalized_snapshot is None:
            prd_updated_payload = _build_prd_updated_event_data(
                prepared.state,
                prepared.state_patch,
                prepared.prd_patch,
            )
        else:
            prd_updated_payload = _build_finalized_prd_updated_payload(finalized_snapshot)
        yield MessageStreamEvent(
            type="prd.updated",
            data=prd_updated_payload,
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
                created_at=created_at,
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
) -> tuple[str, int, int, str | None]:
    return _persist_regenerated_reply_version_impl(
        db=db,
        session_id=session_id,
        session=session,
        user_message_id=user_message_id,
        reply_group_id=reply_group_id,
        assistant_version_id=assistant_version_id,
        version_no=version_no,
        reply=reply,
        model_meta=model_meta,
        action=action,
        turn_decision=turn_decision,
        state=state,
        state_patch=state_patch,
        prd_patch=prd_patch,
    )


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
        error_event: MessageStreamEvent | None = None
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
            error_event = _build_assistant_error_event(
                session_id=session_id,
                user_message_id=prepared.user_message_id,
                reply_group_id=prepared.reply_group_id,
                assistant_version_id=prepared.assistant_version_id,
                version_no=prepared.next_version_no,
                model_config_id=prepared.model_meta["model_config_id"],
                message=str(exc),
                is_regeneration=True,
            )
        finally:
            close = getattr(prepared.reply_stream, "close", None)
            if callable(close):
                close()

        if error_event is not None:
            yield error_event
            return

        try:
            version_id, version_no, prd_snapshot_version, created_at = _persist_regenerated_reply_version(
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
                created_at=created_at,
                is_regeneration=True,
                is_latest=True,
            ).model_dump(),
        )

    return event_generator()
