from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.agent.readiness import evaluate_finalize_readiness
from app.schemas.review import PrdReviewResponse


REQUIRED_REVIEW_DIMENSIONS: tuple[str, ...] = (
    "goal_clarity",
    "scope_boundary",
    "success_metrics",
    "risk_exposure",
    "validation_completeness",
)

_DIMENSION_SECTION_KEYS: dict[str, tuple[str, ...]] = {
    "goal_clarity": ("target_user", "problem", "solution"),
    "scope_boundary": ("mvp_scope", "constraints"),
    "success_metrics": ("success_metrics",),
}


def _extract_sections(state: Mapping[str, Any]) -> dict[str, Any]:
    prd_draft = state.get("prd_draft")
    if isinstance(prd_draft, Mapping):
        sections = prd_draft.get("sections")
        if isinstance(sections, Mapping):
            return dict(sections)

    prd_snapshot = state.get("prd_snapshot")
    if isinstance(prd_snapshot, Mapping):
        sections = prd_snapshot.get("sections")
        if isinstance(sections, Mapping):
            return dict(sections)
    return {}


def _has_text_content(section: object) -> bool:
    if not isinstance(section, Mapping):
        return False

    entries = section.get("entries")
    if isinstance(entries, list):
        return any(
            isinstance(item, Mapping)
            and isinstance(item.get("text"), str)
            and item.get("text").strip()
            for item in entries
        )

    content = section.get("content")
    return isinstance(content, str) and bool(content.strip())


def _has_to_validate_entries(section: object) -> bool:
    if not isinstance(section, Mapping):
        return False
    entries = section.get("entries")
    if not isinstance(entries, list):
        return False
    return any(
        isinstance(item, Mapping)
        and item.get("assertion_state") == "to_validate"
        and isinstance(item.get("text"), str)
        and item.get("text").strip()
        for item in entries
    )


def _collect_open_diagnostics(state: Mapping[str, Any]) -> list[dict[str, str]]:
    diagnostics = state.get("diagnostics")
    if not isinstance(diagnostics, list):
        return []

    normalized: list[dict[str, str]] = []
    for item in diagnostics:
        if not isinstance(item, Mapping) or item.get("status") != "open":
            continue
        bucket = item.get("bucket")
        title = item.get("title")
        if not isinstance(bucket, str) or not isinstance(title, str) or not title.strip():
            continue
        normalized.append({"bucket": bucket, "title": title.strip()})
    return normalized


def _build_scalar_check(
    *,
    dimension: str,
    sections: Mapping[str, Any],
    missing_sections: set[str],
) -> dict[str, object]:
    required_keys = _DIMENSION_SECTION_KEYS[dimension]
    missing = [key for key in required_keys if key in missing_sections or not _has_text_content(sections.get(key))]
    if missing:
        return {
            "verdict": "missing",
            "summary": f"{dimension} 缺少必要信息。",
            "evidence": list(missing),
        }
    if dimension == "success_metrics" and any(_has_to_validate_entries(sections.get(key)) for key in required_keys):
        return {
            "verdict": "needs_input",
            "summary": "success_metrics 已有草稿，但指标仍停留在待验证状态。",
            "evidence": list(required_keys),
        }
    return {
        "verdict": "pass",
        "summary": f"{dimension} 已具备当前复核所需信息。",
        "evidence": list(required_keys),
    }


def _build_risk_exposure_check(
    *,
    sections: Mapping[str, Any],
    open_diagnostics: list[dict[str, str]],
) -> dict[str, object]:
    risk_section = sections.get("risks_to_validate")
    risk_titles = [
        item["title"]
        for item in open_diagnostics
        if item["bucket"] in {"risk", "to_validate"}
    ]
    has_open_risk = bool(risk_titles) or _has_to_validate_entries(risk_section)
    if has_open_risk:
        return {
            "verdict": "needs_input",
            "summary": "仍有开放风险或待验证项未消化。",
            "evidence": list(dict.fromkeys(risk_titles or ["to_validate"])),
        }
    if _has_text_content(risk_section):
        return {
            "verdict": "pass",
            "summary": "已明确记录当前风险与待验证信息。",
            "evidence": ["risks_to_validate"],
        }
    return {
        "verdict": "pass",
        "summary": "当前没有开放风险阻塞质量复核。",
        "evidence": [],
    }


def _build_validation_completeness_check(
    *,
    sections: Mapping[str, Any],
    open_diagnostics: list[dict[str, str]],
) -> dict[str, object]:
    open_questions = sections.get("open_questions")
    validation_titles = [
        item["title"]
        for item in open_diagnostics
        if item["bucket"] in {"to_validate", "unknown"}
    ]
    has_open_validation = bool(validation_titles) or _has_to_validate_entries(sections.get("success_metrics"))
    if has_open_validation:
        return {
            "verdict": "needs_input",
            "summary": "仍有待验证项或未决问题需要补齐。",
            "evidence": list(dict.fromkeys(validation_titles or ["to_validate"])),
        }
    if _has_text_content(open_questions):
        return {
            "verdict": "pass",
            "summary": "待确认问题已被显式记录，便于后续验证。",
            "evidence": ["open_questions"],
        }
    return {
        "verdict": "pass",
        "summary": "当前没有额外待验证缺口阻塞复核。",
        "evidence": [],
    }


def _derive_top_level_verdict(readiness: Mapping[str, Any]) -> str:
    status = readiness.get("status")
    if status == "finalized" or readiness.get("ready") is True:
        return "pass"
    if status == "needs_input":
        return "needs_input"
    return "revise"


def build_prd_review(state: Mapping[str, Any]) -> dict[str, object]:
    sections = _extract_sections(state)
    readiness = evaluate_finalize_readiness(state)
    open_diagnostics = _collect_open_diagnostics(state)
    missing_sections = {
        item
        for item in readiness.get("missing_sections", [])
        if isinstance(item, str) and item.strip()
    }

    checks = {
        "goal_clarity": _build_scalar_check(
            dimension="goal_clarity",
            sections=sections,
            missing_sections=missing_sections,
        ),
        "scope_boundary": _build_scalar_check(
            dimension="scope_boundary",
            sections=sections,
            missing_sections=missing_sections,
        ),
        "success_metrics": _build_scalar_check(
            dimension="success_metrics",
            sections=sections,
            missing_sections=missing_sections,
        ),
        "risk_exposure": _build_risk_exposure_check(
            sections=sections,
            open_diagnostics=open_diagnostics,
        ),
        "validation_completeness": _build_validation_completeness_check(
            sections=sections,
            open_diagnostics=open_diagnostics,
        ),
    }

    verdict = _derive_top_level_verdict(readiness)
    gaps = [
        item
        for item in readiness.get("gap_prompts", [])
        if isinstance(item, str) and item.strip()
    ]
    summary = {
        "pass": "当前 PRD 关键信息已齐备，可进入确认或交付环节。",
        "needs_input": "当前 PRD 结构已成型，但仍有待验证项或开放风险需要补齐。",
        "revise": "当前 PRD 仍缺少关键章节，尚不能作为稳定交付基线。",
    }[verdict]

    return PrdReviewResponse(
        verdict=verdict,
        status=str(readiness.get("status", "drafting")),
        summary=summary,
        checks=checks,
        gaps=gaps,
        missing_sections=sorted(missing_sections),
        ready_for_confirmation=bool(readiness.get("ready_for_confirmation")),
    ).model_dump()
