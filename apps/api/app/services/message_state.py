from __future__ import annotations

from dataclasses import asdict

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


def _coerce_mapping(value: object) -> dict:
    if isinstance(value, dict):
        return value
    return {}


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


def build_decision_state_patch(turn_decision: object) -> dict:
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
    if current_state is not None:
        for key in _PERSISTED_WORKFLOW_STATE_FIELDS:
            if key in final_patch:
                continue
            if key in current_state:
                continue
            final_patch[key] = None
    return final_patch
