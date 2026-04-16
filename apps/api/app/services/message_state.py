from __future__ import annotations

from dataclasses import asdict

from app.agent.readiness import evaluate_finalize_readiness
from app.db.models import LLMModelConfig


_PERSISTED_WORKFLOW_STATE_FIELDS: tuple[str, ...] = (
    "workflow_stage",
    "idea_parse_result",
    "prd_draft",
    "critic_result",
    "refine_history",
    "finalization_ready",
)


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


def _dedupe_str_list(items: list[str]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered


def normalize_guidance_suggestions(raw_suggestions: object) -> list[dict]:
    if not isinstance(raw_suggestions, list):
        return []

    normalized: list[dict] = []
    for item in raw_suggestions:
        if hasattr(item, "__dataclass_fields__"):
            item = asdict(item)
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


def _coerce_mapping(value: object) -> dict:
    if isinstance(value, dict):
        return value
    return {}


def _normalize_question_list(items: object) -> list[str]:
    if not isinstance(items, list):
        return []
    return [item.strip() for item in items if isinstance(item, str) and item.strip()]


def _resolve_guidance_suggestions(decision: object) -> list[dict]:
    suggestions = normalize_guidance_suggestions(getattr(decision, "suggestions", None))
    if suggestions:
        return suggestions
    return normalize_guidance_suggestions(getattr(decision, "suggestions_json", None))


def _resolve_guidance_recommendation(decision: object) -> object:
    recommendation = getattr(decision, "recommendation", None)
    if recommendation is not None:
        return recommendation
    return getattr(decision, "recommendation_json", None)


def _resolve_decision_state_patch(decision: object) -> dict[str, object]:
    state_patch = getattr(decision, "state_patch_json", None)
    if isinstance(state_patch, dict):
        return state_patch
    state_patch = getattr(decision, "state_patch", None)
    if isinstance(state_patch, dict):
        return state_patch
    return {}


def _resolve_guidance_field(decision: object, key: str, default: object = None) -> object:
    direct = getattr(decision, key, None)
    if direct is not None:
        return direct
    return _resolve_decision_state_patch(decision).get(key, default)


def _resolve_guidance_option_cards(decision: object) -> list[dict]:
    option_cards = _resolve_guidance_field(decision, "option_cards", [])
    if not isinstance(option_cards, list):
        return []
    normalized: list[dict] = []
    for item in option_cards:
        if not isinstance(item, dict):
            continue
        card_id = item.get("id")
        label = item.get("label") or item.get("title")
        content = item.get("content")
        if not isinstance(card_id, str) or not card_id.strip():
            continue
        if not isinstance(label, str) or not label.strip():
            continue
        if not isinstance(content, str) or not content.strip():
            continue
        normalized.append(
            {
                "id": card_id.strip(),
                "label": label.strip(),
                "title": (item.get("title") or label).strip() if isinstance(item.get("title") or label, str) else label.strip(),
                "content": content.strip(),
                "description": item.get("description", ""),
                "type": item.get("type", "direction"),
                "priority": item.get("priority", len(normalized) + 1),
            }
        )
    return normalized


def _resolve_guidance_mapping(value: object) -> dict[str, object] | None:
    if not isinstance(value, dict):
        return None
    return value


def _empty_diagnostic_summary() -> dict[str, int]:
    return {
        "open_count": 0,
        "unknown_count": 0,
        "risk_count": 0,
        "to_validate_count": 0,
    }


def _normalize_draft_entry(raw_item: object) -> dict[str, object] | None:
    if not isinstance(raw_item, dict):
        return None
    entry_id = raw_item.get("id")
    text = raw_item.get("text")
    assertion_state = raw_item.get("assertion_state")
    evidence_ref_ids = raw_item.get("evidence_ref_ids")
    if not isinstance(entry_id, str) or not entry_id.strip():
        return None
    if not isinstance(text, str) or not text.strip():
        return None
    if assertion_state not in {"confirmed", "inferred", "to_validate"}:
        return None
    if not isinstance(evidence_ref_ids, list):
        return None
    normalized_refs = [item.strip() for item in evidence_ref_ids if isinstance(item, str) and item.strip()]
    return {
        "id": entry_id.strip(),
        "text": text.strip(),
        "assertion_state": assertion_state,
        "evidence_ref_ids": normalized_refs,
        "derived_from_diagnostics": [
            item.strip()
            for item in raw_item.get("derived_from_diagnostics", [])
            if isinstance(item, str) and item.strip()
        ],
    }


def _normalize_draft_section(raw_item: object) -> dict[str, object] | None:
    if not isinstance(raw_item, dict):
        return None
    title = raw_item.get("title")
    entries = raw_item.get("entries")
    completeness = raw_item.get("completeness")
    if not isinstance(title, str) or not title.strip():
        return None
    if completeness not in {"complete", "partial", "missing"}:
        return None
    if not isinstance(entries, list):
        return None
    normalized_entries = [entry for raw_entry in entries if (entry := _normalize_draft_entry(raw_entry)) is not None]
    return {
        "title": title.strip(),
        "entries": normalized_entries,
        "completeness": completeness,
        "summary": raw_item.get("summary") if isinstance(raw_item.get("summary"), str) else None,
    }


def normalize_prd_draft(raw_draft: object) -> dict[str, object] | None:
    if not isinstance(raw_draft, dict):
        return None
    sections = raw_draft.get("sections")
    if not isinstance(sections, dict):
        return None
    normalized_sections: dict[str, dict[str, object]] = {}
    for key, raw_section in sections.items():
        if not isinstance(key, str) or not key.strip():
            continue
        section = _normalize_draft_section(raw_section)
        if section is None:
            continue
        normalized_sections[key.strip()] = section
    return {
        "version": raw_draft.get("version") if isinstance(raw_draft.get("version"), int) else 1,
        "status": raw_draft.get("status") if isinstance(raw_draft.get("status"), str) else "drafting",
        "sections": normalized_sections,
        "summary": raw_draft.get("summary") if isinstance(raw_draft.get("summary"), dict) else {},
    }


def normalize_evidence_registry(raw_items: object) -> list[dict[str, object]]:
    if not isinstance(raw_items, list):
        return []
    normalized: list[dict[str, object]] = []
    seen: set[str] = set()
    for raw_item in raw_items:
        if not isinstance(raw_item, dict):
            continue
        item_id = raw_item.get("id")
        kind = raw_item.get("kind")
        excerpt = raw_item.get("excerpt")
        section_keys = raw_item.get("section_keys")
        if not isinstance(item_id, str) or not item_id.strip():
            continue
        if kind not in {"user_message", "assistant_decision", "system_inference", "diagnostic"}:
            continue
        if not isinstance(excerpt, str) or not excerpt.strip():
            continue
        if not isinstance(section_keys, list):
            continue
        normalized_keys = [item.strip() for item in section_keys if isinstance(item, str) and item.strip()]
        if item_id in seen:
            continue
        seen.add(item_id)
        normalized.append(
            {
                "id": item_id.strip(),
                "kind": kind,
                "excerpt": excerpt.strip(),
                "section_keys": normalized_keys,
                "message_id": raw_item.get("message_id") if isinstance(raw_item.get("message_id"), str) else None,
                "turn_decision_id": raw_item.get("turn_decision_id") if isinstance(raw_item.get("turn_decision_id"), str) else None,
                "created_at": raw_item.get("created_at") if isinstance(raw_item.get("created_at"), str) else None,
            }
        )
    return normalized


def _normalize_diagnostic_item(raw_item: object) -> dict[str, object] | None:
    if not isinstance(raw_item, dict):
        return None
    item = dict(raw_item)
    item_id = item.get("id")
    item_type = item.get("type")
    bucket = item.get("bucket")
    status = item.get("status")
    title = item.get("title")
    detail = item.get("detail")
    impact_scope = item.get("impact_scope")
    next_step = item.get("suggested_next_step")
    confidence = item.get("confidence")
    if not isinstance(item_id, str) or not item_id.strip():
        return None
    if item_type not in {"contradiction", "gap", "assumption"}:
        return None
    if bucket not in {"unknown", "risk", "to_validate"}:
        return None
    if status not in {"open", "resolved", "superseded"}:
        return None
    if not isinstance(title, str) or not title.strip():
        return None
    if not isinstance(detail, str) or not detail.strip():
        return None
    if not isinstance(impact_scope, list):
        return None
    normalized_scope = [part.strip() for part in impact_scope if isinstance(part, str) and part.strip()]
    if not normalized_scope:
        return None
    next_step_mapping = _resolve_guidance_mapping(next_step)
    if next_step_mapping is None:
        return None
    action_kind = next_step_mapping.get("action_kind")
    label = next_step_mapping.get("label")
    prompt = next_step_mapping.get("prompt")
    if not isinstance(action_kind, str) or not action_kind.strip():
        return None
    if not isinstance(label, str) or not label.strip():
        return None
    if not isinstance(prompt, str) or not prompt.strip():
        return None
    normalized_confidence = confidence if confidence in {"high", "medium", "low"} else "medium"
    return {
        "id": item_id.strip(),
        "type": item_type,
        "bucket": bucket,
        "status": status,
        "title": title.strip(),
        "detail": detail.strip(),
        "impact_scope": normalized_scope,
        "suggested_next_step": {
            "action_kind": action_kind.strip(),
            "label": label.strip(),
            "prompt": prompt.strip(),
        },
        "confidence": normalized_confidence,
    }


def normalize_diagnostics(raw_items: object) -> list[dict[str, object]]:
    if not isinstance(raw_items, list):
        return []
    normalized: list[dict[str, object]] = []
    seen: set[str] = set()
    for raw_item in raw_items:
        item = _normalize_diagnostic_item(raw_item)
        if item is None:
            continue
        item_id = str(item["id"])
        if item_id in seen:
            continue
        seen.add(item_id)
        normalized.append(item)
    return normalized


def summarize_diagnostics(diagnostics: list[dict[str, object]]) -> dict[str, int]:
    summary = _empty_diagnostic_summary()
    for item in diagnostics:
        if item.get("status") != "open":
            continue
        summary["open_count"] += 1
        bucket = item.get("bucket")
        if bucket == "unknown":
            summary["unknown_count"] += 1
        elif bucket == "risk":
            summary["risk_count"] += 1
        elif bucket == "to_validate":
            summary["to_validate_count"] += 1
    return summary


def build_open_diagnostics_ledger(
    state_diagnostics: object,
    latest_diagnostics: object,
) -> list[dict[str, object]]:
    ledger_by_id: dict[str, dict[str, object]] = {}
    for item in normalize_diagnostics(state_diagnostics):
        ledger_by_id[str(item["id"])] = item
    for item in normalize_diagnostics(latest_diagnostics):
        ledger_by_id[str(item["id"])] = item
    return [item for item in ledger_by_id.values() if item.get("status") == "open"]


def build_guidance_payload(
    decision: object,
    *,
    session_id: str | None = None,
    user_message_id: str | None = None,
    conversation_strategy: str | None = None,
    next_best_questions: list[str] | None = None,
    confirm_quick_replies: list[str] | None = None,
) -> dict[str, object]:
    normalized_next_questions = _normalize_question_list(
        next_best_questions
        if next_best_questions is not None
        else getattr(decision, "next_best_questions", None)
    )
    payload = {
        "phase": getattr(decision, "phase", "idea_clarification"),
        "conversation_strategy": conversation_strategy or getattr(decision, "conversation_strategy", "clarify"),
        "next_move": getattr(decision, "next_move", "probe_for_specificity"),
        "suggestions": _resolve_guidance_suggestions(decision),
        "recommendation": _resolve_guidance_recommendation(decision),
        "next_best_questions": normalized_next_questions,
        "response_mode": _resolve_guidance_field(decision, "response_mode", "direct_answer"),
        "guidance_mode": _resolve_guidance_field(decision, "guidance_mode", "explore"),
        "guidance_step": _resolve_guidance_field(decision, "guidance_step", "answer"),
        "focus_dimension": _resolve_guidance_field(decision, "focus_dimension", None),
        "transition_reason": _resolve_guidance_field(decision, "transition_reason", None),
        "transition_trigger": _resolve_guidance_field(decision, "transition_trigger", None),
        "option_cards": _resolve_guidance_option_cards(decision),
        "freeform_affordance": _resolve_guidance_mapping(_resolve_guidance_field(decision, "freeform_affordance", None)),
        "available_mode_switches": list(_resolve_guidance_field(decision, "available_mode_switches", []) or []),
    }
    if confirm_quick_replies is not None:
        payload["confirm_quick_replies"] = confirm_quick_replies
    if session_id is not None:
        payload["session_id"] = session_id
    if user_message_id is not None:
        payload["user_message_id"] = user_message_id
    return payload


def build_diagnostics_payload(
    decision: object,
    *,
    ledger_diagnostics: object | None = None,
) -> dict[str, object]:
    diagnostics = normalize_diagnostics(getattr(decision, "diagnostics", None))
    if not diagnostics:
        diagnostics = normalize_diagnostics(_resolve_decision_state_patch(decision).get("diagnostics"))
    ledger = build_open_diagnostics_ledger(ledger_diagnostics, diagnostics)
    summary = getattr(decision, "diagnostic_summary", None)
    if not isinstance(summary, dict):
        summary = _resolve_decision_state_patch(decision).get("diagnostic_summary")
    normalized_summary = summary if isinstance(summary, dict) else summarize_diagnostics(diagnostics)
    if set(normalized_summary.keys()) != {"open_count", "unknown_count", "risk_count", "to_validate_count"}:
        normalized_summary = summarize_diagnostics(diagnostics)
    return {
        "diagnostics": diagnostics,
        "diagnostic_summary": normalized_summary,
        "ledger_summary": summarize_diagnostics(ledger),
    }


def extract_workflow_state_from_turn_decision(turn_decision: object) -> dict:
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


def merge_readiness_state_patch(
    state_patch: dict,
    *,
    current_state: dict | None = None,
) -> dict:
    patch = dict(state_patch or {})

    prd_draft = patch.get("prd_draft")
    if not isinstance(prd_draft, dict) and current_state is not None:
        current_draft = current_state.get("prd_draft")
        if isinstance(current_draft, dict):
            prd_draft = current_draft
    if not isinstance(prd_draft, dict):
        return patch

    readiness_state: dict = {"prd_draft": prd_draft}
    if current_state is not None and isinstance(current_state.get("prd_snapshot"), dict):
        readiness_state["prd_snapshot"] = current_state.get("prd_snapshot")
    readiness = evaluate_finalize_readiness(readiness_state)

    patch.setdefault("finalization_ready", bool(readiness.get("ready_for_confirmation", readiness["ready"])))
    patch.setdefault("critic_result", readiness["critic_result"])

    if "workflow_stage" not in patch:
        current_stage = current_state.get("workflow_stage") if current_state is not None else None
        if current_stage != "completed":
            patch["workflow_stage"] = "finalize" if patch["finalization_ready"] else "refine_loop"

    return patch


def build_decision_state_patch(turn_decision: object) -> dict:
    decision_state_patch = _resolve_decision_state_patch(turn_decision)
    suggestions = getattr(turn_decision, "suggestions", []) or []
    recommendation = getattr(turn_decision, "recommendation", None)
    recommended_directions = [asdict(item) for item in suggestions]
    if recommendation and not any(
        item.get("label") == recommendation.get("label")
        for item in recommended_directions
    ):
        recommended_directions.insert(0, recommendation)

    diagnostics = normalize_diagnostics(getattr(turn_decision, "diagnostics", None))
    diagnostic_summary = getattr(turn_decision, "diagnostic_summary", None)
    if not isinstance(diagnostic_summary, dict):
        diagnostic_summary = summarize_diagnostics(diagnostics)
    prd_draft = normalize_prd_draft(decision_state_patch.get("prd_draft"))
    evidence = normalize_evidence_registry(decision_state_patch.get("evidence"))
    assumptions = getattr(turn_decision, "assumptions", []) or []
    assumption_items = [item for item in diagnostics if item.get("type") == "assumption"]
    if assumption_items:
        assumptions = [
            {
                "id": item["id"],
                "title": item["title"],
            }
            for item in assumption_items
        ]
    pm_risk_flags = _dedupe_str_list(
        [
            str(item["title"])
            for item in diagnostics
            if item.get("bucket") == "risk" and isinstance(item.get("title"), str)
        ]
        or list(getattr(turn_decision, "pm_risk_flags", []) or [])
    )
    open_questions = _dedupe_str_list(
        [
            str(item["suggested_next_step"]["prompt"])
            for item in diagnostics
            if isinstance(item.get("suggested_next_step"), dict)
            and isinstance(item["suggested_next_step"].get("prompt"), str)
        ]
    )
    patch = {
        "current_phase": getattr(turn_decision, "phase", "idea_clarification"),
        "current_phase_subfocus": getattr(turn_decision, "phase_subfocus", None),
        "conversation_strategy": getattr(turn_decision, "conversation_strategy", "clarify"),
        "strategy_reason": getattr(turn_decision, "strategy_reason", None),
        "phase_goal": getattr(turn_decision, "phase_goal", None),
        "working_hypotheses": assumptions,
        "pm_risk_flags": pm_risk_flags,
        "recommended_directions": recommended_directions,
        "pending_confirmations": list(getattr(turn_decision, "needs_confirmation", []) or []),
        "next_best_questions": list(getattr(turn_decision, "next_best_questions", []) or []),
        "open_questions": open_questions,
        "diagnostics": diagnostics,
        "diagnostic_summary": diagnostic_summary,
        "response_mode": getattr(turn_decision, "response_mode", "direct_answer"),
        "guidance_mode": getattr(turn_decision, "guidance_mode", "explore"),
        "guidance_step": getattr(turn_decision, "guidance_step", "answer"),
        "focus_dimension": getattr(turn_decision, "focus_dimension", None),
        "transition_reason": getattr(turn_decision, "transition_reason", None),
        "transition_trigger": getattr(turn_decision, "transition_trigger", None),
        "option_cards": _resolve_guidance_option_cards(turn_decision),
        "freeform_affordance": _resolve_guidance_mapping(getattr(turn_decision, "freeform_affordance", None)),
        "available_mode_switches": list(getattr(turn_decision, "available_mode_switches", []) or []),
    }
    if prd_draft is not None:
        patch["prd_draft"] = prd_draft
    if evidence:
        patch["evidence"] = evidence
    return patch


def build_collaboration_mode_label(scene: str) -> str:
    labels = {
        "reasoning": "深度推演模式",
        "general": "通用协作模式",
        "fallback": "稳态兜底模式",
    }
    return labels.get(scene, "通用协作模式")


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


def merge_state_patch_with_decision(
    state_patch: dict,
    turn_decision: object,
    *,
    model_config: LLMModelConfig | None = None,
    current_state: dict | None = None,
) -> dict:
    decision_patch = build_decision_state_patch(turn_decision)
    current_diagnostics = current_state.get("diagnostics") if current_state is not None else None
    decision_patch["diagnostics"] = build_open_diagnostics_ledger(
        current_diagnostics,
        decision_patch.get("diagnostics"),
    )
    decision_patch["diagnostic_summary"] = summarize_diagnostics(decision_patch["diagnostics"])
    workflow_patch = extract_workflow_state_from_turn_decision(turn_decision)
    scene = infer_model_scene(model_config)
    if model_config is None and current_state is not None:
        existing_scene = current_state.get("current_model_scene")
        if isinstance(existing_scene, str) and existing_scene in {"general", "reasoning", "fallback"}:
            scene = existing_scene

    decision_patch["current_model_scene"] = scene
    decision_patch["collaboration_mode_label"] = build_collaboration_mode_label(scene)
    merged = {**decision_patch, **(state_patch or {})}
    final_patch = {**merged, **workflow_patch}
    final_patch = merge_readiness_state_patch(final_patch, current_state=current_state)
    if current_state is not None:
        for key in _PERSISTED_WORKFLOW_STATE_FIELDS:
            if key in final_patch:
                continue
            if key in current_state:
                continue
            final_patch[key] = None
    return final_patch
