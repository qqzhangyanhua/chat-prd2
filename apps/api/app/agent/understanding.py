from __future__ import annotations

from typing import Any, Dict, List

from app.agent.extractor import (
    first_missing_section,
    is_missing,
    normalize_text,
    should_capture,
)
from app.agent.types import UnderstandingResult

USER_TOO_BROAD_PHRASES = (
    "所有创业者",
    "所有用户",
    "面向所有人",
    "泛互联网用户",
)
PROBLEM_TOO_VAGUE_PHRASES = ("效率低", "不方便", "体验不好")
SOLUTION_INDICATORS = ("方案", "产品", "功能", "平台", "工具", "服务")
ASSUMPTION_PHRASES = ("我猜", "可能", "也许", "大概")
AMBIGUOUS_PHRASES = ("还不清楚", "不确定", "待明确", "不知道", "模糊")


def _build_candidate_updates(state: dict, normalized_input: str) -> Dict[str, Any]:
    # 理解层的最小候选字段映射，后续会与决策层解耦
    updates: Dict[str, Any] = {}
    missing = first_missing_section(state)
    if not missing:
        return updates

    if missing == "mvp_scope":
        updates["mvp_scope"] = [normalized_input]
    else:
        updates[missing] = normalized_input

    return updates


def _detect_assumptions(normalized_input: str) -> List[str]:
    normalized = normalized_input.lower()
    for phrase in ASSUMPTION_PHRASES:
        if phrase in normalized:
            return [normalized_input]
    return []


def _detect_ambiguous_points(normalized_input: str) -> List[str]:
    normalized = normalized_input.lower()
    points: List[str] = []
    for phrase in AMBIGUOUS_PHRASES:
        if phrase in normalized:
            points.append(f"表达尚不明确：{phrase}")
    return points


def _detect_risk_hints(state: dict, normalized_input: str) -> List[str]:
    normalized = normalized_input.lower()
    hints: List[str] = []
    if any(phrase in normalized for phrase in USER_TOO_BROAD_PHRASES):
        hints.append("user_too_broad")
    if any(phrase in normalized for phrase in PROBLEM_TOO_VAGUE_PHRASES):
        hints.append("problem_too_vague")
    if is_missing(state.get("problem")):
        if any(indicator in normalized for indicator in SOLUTION_INDICATORS):
            hints.append("solution_before_problem")
    return hints


def _build_summary(normalized_input: str) -> str:
    if not normalized_input:
        return "本轮输入未提供具体内容。"
    return f"用户表述了：{normalized_input}。"


def understand_user_input(state: dict, user_input: str) -> UnderstandingResult:
    normalized = normalize_text(user_input)
    summary = _build_summary(normalized)
    candidate_updates: Dict[str, Any] = {}
    if normalized and should_capture(user_input):
        candidate_updates = _build_candidate_updates(state, normalized)

    assumption_candidates = _detect_assumptions(normalized)
    ambiguous_points = _detect_ambiguous_points(normalized)
    risk_hints = _detect_risk_hints(state, normalized)

    return UnderstandingResult(
        summary=summary,
        candidate_updates=candidate_updates,
        assumption_candidates=assumption_candidates,
        ambiguous_points=ambiguous_points,
        risk_hints=risk_hints,
    )
