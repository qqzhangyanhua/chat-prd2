from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


ExtractionConfidence = Literal["high", "medium", "low"]
ExtractionSource = Literal["rule", "model"]

GENERIC_CONTINUATIONS = {
    "继续",
    "继续吧",
    "继续推进",
    "继续下去",
    "好的",
    "好",
    "嗯",
    "ok",
    "okay",
}

UNCERTAIN_REPLY_PHRASES = (
    "还没想好",
    "还没有想好",
    "不确定",
    "不清楚",
    "待定",
    "之后再说",
    "再想想",
    "没想好",
)

SECTION_TITLES = {
    "target_user": "目标用户",
    "problem": "核心问题",
    "solution": "解决方案",
    "mvp_scope": "MVP 范围",
}

NEXT_STAGE_HINTS = {
    "target_user": "问题定义",
    "problem": "方案收敛",
    "solution": "MVP 收敛",
    "mvp_scope": "总结共识",
}


@dataclass
class StructuredExtractionResult:
    should_update: bool
    state_patch: dict = field(default_factory=dict)
    prd_patch: dict = field(default_factory=dict)
    confidence: ExtractionConfidence = "low"
    reasoning_summary: str = ""
    decision_log: list[dict[str, str]] = field(default_factory=list)
    source: ExtractionSource = "rule"


def normalize_text(user_input: str) -> str:
    return " ".join(user_input.split()).strip()


def is_missing(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, list):
        return len(value) == 0
    return False


def first_missing_section(state: dict) -> str | None:
    for key in ("target_user", "problem", "solution", "mvp_scope"):
        if is_missing(state.get(key)):
            return key
    return None


def should_capture(user_input: str) -> bool:
    normalized = normalize_text(user_input)
    return bool(normalized) and normalized.lower() not in GENERIC_CONTINUATIONS


def build_rule_extraction_result(state: dict, user_input: str) -> StructuredExtractionResult:
    current_missing_section = first_missing_section(state)
    if current_missing_section is None or not should_capture(user_input):
        return StructuredExtractionResult(
            should_update=False,
            confidence="low",
            reasoning_summary="规则提取未识别到可更新字段",
            source="rule",
        )

    normalized = normalize_text(user_input)
    next_iteration = int(state.get("iteration") or 0) + 1
    state_patch: dict[str, object] = {
        "iteration": next_iteration,
        "stage_hint": NEXT_STAGE_HINTS[current_missing_section],
    }
    if current_missing_section == "mvp_scope":
        state_patch["mvp_scope"] = [normalized]
    else:
        state_patch[current_missing_section] = normalized

    return StructuredExtractionResult(
        should_update=True,
        state_patch=state_patch,
        prd_patch={
            current_missing_section: {
                "title": SECTION_TITLES[current_missing_section],
                "content": normalized,
                "status": "confirmed",
            }
        },
        confidence="medium",
        reasoning_summary=f"规则提取将输入归入 {current_missing_section}",
        decision_log=[{"section": current_missing_section, "value": normalized}],
        source="rule",
    )


def choose_extraction_result(
    rule_result: StructuredExtractionResult,
    model_result: StructuredExtractionResult | None,
) -> StructuredExtractionResult:
    if (
        model_result is not None
        and model_result.should_update
        and model_result.confidence in {"high", "medium"}
    ):
        return model_result
    return rule_result


def _contains_uncertain_reply(text: str) -> bool:
    return any(phrase in text for phrase in UNCERTAIN_REPLY_PHRASES)


def _normalize_prd_section(section: str, value: Any) -> dict[str, str] | None:
    if not isinstance(value, dict):
        return None
    content = normalize_text(str(value.get("content", "")))
    if not content:
        return None
    title = normalize_text(str(value.get("title", ""))) or SECTION_TITLES[section]
    status = value.get("status")
    normalized_status = status if status in {"confirmed", "inferred"} else "confirmed"
    return {
        "title": title,
        "content": content,
        "status": normalized_status,
    }


def normalize_model_extraction_result(payload: dict[str, Any] | None) -> StructuredExtractionResult | None:
    if not isinstance(payload, dict) or not payload.get("should_update"):
        return None

    confidence_raw = payload.get("confidence")
    confidence: ExtractionConfidence = (
        confidence_raw if confidence_raw in {"high", "medium", "low"} else "low"
    )

    raw_state_patch = payload.get("state_patch")
    raw_prd_patch = payload.get("prd_patch")
    if not isinstance(raw_state_patch, dict):
        raw_state_patch = {}
    if not isinstance(raw_prd_patch, dict):
        raw_prd_patch = {}

    state_patch: dict[str, Any] = {}
    for key in ("target_user", "problem", "solution"):
        value = raw_state_patch.get(key)
        if isinstance(value, str) and normalize_text(value):
            state_patch[key] = normalize_text(value)

    mvp_scope = raw_state_patch.get("mvp_scope")
    if isinstance(mvp_scope, list):
        normalized_scope = [
            normalize_text(str(item))
            for item in mvp_scope
            if normalize_text(str(item))
        ]
        if normalized_scope:
            state_patch["mvp_scope"] = normalized_scope

    if isinstance(raw_state_patch.get("iteration"), int):
        state_patch["iteration"] = raw_state_patch["iteration"]
    if isinstance(raw_state_patch.get("stage_hint"), str) and normalize_text(raw_state_patch["stage_hint"]):
        state_patch["stage_hint"] = normalize_text(raw_state_patch["stage_hint"])

    prd_patch: dict[str, dict[str, str]] = {}
    for section in ("target_user", "problem", "solution", "mvp_scope"):
        normalized_section = _normalize_prd_section(section, raw_prd_patch.get(section))
        if normalized_section is not None:
            prd_patch[section] = normalized_section

    if not state_patch and not prd_patch:
        return None

    decision_log = [
        {"section": section, "value": details["content"]}
        for section, details in prd_patch.items()
    ]

    return StructuredExtractionResult(
        should_update=True,
        state_patch=state_patch,
        prd_patch=prd_patch,
        confidence=confidence,
        reasoning_summary=normalize_text(str(payload.get("reasoning_summary", ""))),
        decision_log=decision_log,
        source="model",
    )
