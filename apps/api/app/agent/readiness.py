from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping


CORE_REQUIRED_SECTIONS: tuple[str, ...] = (
    "target_user",
    "problem",
    "solution",
    "mvp_scope",
)

FINALIZE_REQUIRED_SECTIONS: tuple[str, ...] = (
    *CORE_REQUIRED_SECTIONS,
    "constraints",
    "success_metrics",
)


@dataclass(frozen=True)
class CriticResult:
    overall_verdict: str
    major_gaps: list[str]
    question_queue: list[str]
    ready: bool
    missing: list[str]
    required_sections: list[str]


@dataclass(frozen=True)
class FinalizeReadinessResult:
    ready: bool
    missing: list[str]
    critic_result: dict[str, Any]


def _is_empty_value(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, list):
        return all(_is_empty_value(item) for item in value)
    if isinstance(value, dict):
        return all(_is_empty_value(item) for item in value.values())
    return False


def _is_section_complete(section: object) -> bool:
    if isinstance(section, dict):
        status = section.get("status")
        if isinstance(status, str) and status.strip().lower() == "missing":
            return False
        if "content" in section:
            return not _is_empty_value(section.get("content"))
        return not _is_empty_value(section)
    return not _is_empty_value(section)


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


def _build_critic_result(*, ready: bool, missing: list[str]) -> CriticResult:
    return CriticResult(
        overall_verdict="pass" if ready else "revise",
        major_gaps=list(missing),
        question_queue=[f"请补充「{field}」内容" for field in missing],
        ready=ready,
        missing=list(missing),
        required_sections=list(FINALIZE_REQUIRED_SECTIONS),
    )


def evaluate_finalize_readiness(state: Mapping[str, Any]) -> dict[str, Any]:
    sections = _extract_sections(state)
    missing = [
        field
        for field in FINALIZE_REQUIRED_SECTIONS
        if not _is_section_complete(sections.get(field))
    ]
    ready = len(missing) == 0
    critic_result = asdict(_build_critic_result(ready=ready, missing=missing))
    return asdict(
        FinalizeReadinessResult(
            ready=ready,
            missing=missing,
            critic_result=critic_result,
        )
    )
