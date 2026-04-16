from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.schemas.message import AgentTurnDecisionResponse
from app.schemas.message import AssistantReplyGroupResponse
from app.schemas.message import ConversationMessageResponse
from app.schemas.replay import ReplayTimelineItemResponse

GUIDANCE_EVENT = "guidance"
DIAGNOSTICS_EVENT = "diagnostics"
PRD_DELTA_EVENT = "prd_delta"
FINALIZE_EVENT = "finalize"
EXPORT_EVENT = "export"

_REPLAY_EXPORT_FILE_NAME = "ai-cofounder-prd.md"


def _iso_or_none(value: object) -> str | None:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, str) and value.strip():
        return value
    return None


def _normalize_sections_changed(decision: AgentTurnDecisionResponse) -> list[str]:
    seen: set[str] = set()
    collected: list[str] = []
    for section in decision.decision_sections:
        meta = section.meta if isinstance(section.meta, dict) else {}
        draft_updates = meta.get("draft_updates")
        if isinstance(draft_updates, dict):
            keys = draft_updates.get("section_keys")
            if isinstance(keys, list):
                for item in keys:
                    if isinstance(item, str) and item not in seen:
                        seen.add(item)
                        collected.append(item)
    prd_patch = decision.prd_patch_json or {}
    if isinstance(prd_patch, dict):
        for key in prd_patch.keys():
            if key not in seen:
                seen.add(key)
                collected.append(key)
    return sorted(collected)


def _build_guidance_summary(decision: AgentTurnDecisionResponse) -> str:
    for section in decision.decision_sections:
        if section.key == "judgement" and section.content.strip():
            return section.content.strip()
    return decision.decision_summary.strip() or "继续推进当前会话。"


def _extract_conversation_strategy(decision: AgentTurnDecisionResponse) -> str | None:
    for section in decision.decision_sections:
        meta = section.meta if isinstance(section.meta, dict) else {}
        value = meta.get("conversation_strategy")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _build_diagnostics_summary(decision: AgentTurnDecisionResponse) -> str | None:
    for section in decision.decision_sections:
        meta = section.meta if isinstance(section.meta, dict) else {}
        diagnostics = meta.get("diagnostics")
        if not isinstance(diagnostics, list) or not diagnostics:
            continue
        titles = [
            item.get("title", "").strip()
            for item in diagnostics
            if isinstance(item, dict) and isinstance(item.get("title"), str) and item.get("title", "").strip()
        ]
        if titles:
            return "；".join(titles[:3])
    return None


def _build_prd_delta_summary(decision: AgentTurnDecisionResponse, sections_changed: list[str]) -> str | None:
    prd_patch = decision.prd_patch_json or {}
    if not isinstance(prd_patch, dict) or not prd_patch:
        return None
    fragments: list[str] = []
    for key in sections_changed:
        value = prd_patch.get(key)
        if not isinstance(value, dict):
            continue
        content = value.get("content")
        if isinstance(content, str) and content.strip():
            fragments.append(f"{key}: {content.strip()}")
    if not fragments:
        return None
    return "；".join(fragments[:3])


def _has_finalized_delivery(state: dict[str, Any]) -> bool:
    milestone = state.get("delivery_milestone")
    if isinstance(milestone, dict) and milestone.get("status") == "finalized":
        return True
    return state.get("workflow_stage") == "completed"


def _build_finalize_delivery_milestone(state: dict[str, Any]) -> dict[str, Any]:
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


def build_session_replay_timeline(
    *,
    state: dict[str, Any],
    messages: list[ConversationMessageResponse],
    assistant_reply_groups: list[AssistantReplyGroupResponse],
    turn_decisions: list[AgentTurnDecisionResponse],
) -> list[ReplayTimelineItemResponse]:
    timeline: list[ReplayTimelineItemResponse] = []

    for index, decision in enumerate(turn_decisions):
        event_at = _iso_or_none(decision.created_at)
        sections_changed = _normalize_sections_changed(decision)
        guidance_summary = _build_guidance_summary(decision)
        timeline.append(
            ReplayTimelineItemResponse(
                id=f"{decision.id}:guidance",
                type=GUIDANCE_EVENT,
                title="Guidance Decision",
                summary=guidance_summary,
                event_at=event_at,
                metadata={
                    "turn_decision_id": decision.id,
                    "phase": decision.phase,
                    "conversation_strategy": _extract_conversation_strategy(decision),
                    "user_message_id": decision.user_message_id,
                    "reply_group_count": len(assistant_reply_groups),
                    "message_count": len(messages),
                    "order": index * 10,
                },
            )
        )

        diagnostics_summary = _build_diagnostics_summary(decision)
        if diagnostics_summary:
            timeline.append(
                ReplayTimelineItemResponse(
                    id=f"{decision.id}:diagnostics",
                    type=DIAGNOSTICS_EVENT,
                    title="Diagnostics",
                    summary=diagnostics_summary,
                    event_at=event_at,
                    metadata={
                        "turn_decision_id": decision.id,
                        "phase": decision.phase,
                        "user_message_id": decision.user_message_id,
                        "order": index * 10 + 1,
                    },
                )
            )

        prd_delta_summary = _build_prd_delta_summary(decision, sections_changed)
        if prd_delta_summary:
            timeline.append(
                ReplayTimelineItemResponse(
                    id=f"{decision.id}:prd_delta",
                    type=PRD_DELTA_EVENT,
                    title="PRD Change",
                    summary=prd_delta_summary,
                    event_at=event_at,
                    sections_changed=sections_changed,
                    metadata={
                        "turn_decision_id": decision.id,
                        "phase": decision.phase,
                        "user_message_id": decision.user_message_id,
                        "order": index * 10 + 2,
                    },
                )
            )

    if _has_finalized_delivery(state):
        finalize_metadata = _build_finalize_delivery_milestone(state)
        timeline.append(
            ReplayTimelineItemResponse(
                id="delivery:finalize",
                type=FINALIZE_EVENT,
                title="Finalize Milestone",
                summary="会话已进入终稿交付状态。",
                event_at=None,
                metadata=finalize_metadata,
            )
        )
        timeline.append(
            ReplayTimelineItemResponse(
                id="delivery:export",
                type=EXPORT_EVENT,
                title="Export Milestone",
                summary="终稿已具备导出为结构化 PRD 文本的条件。",
                event_at=None,
                metadata={
                    "file_name": _REPLAY_EXPORT_FILE_NAME,
                    "finalize_preference": finalize_metadata.get("finalize_preference"),
                    "status": finalize_metadata.get("status"),
                },
            )
        )

    return timeline
