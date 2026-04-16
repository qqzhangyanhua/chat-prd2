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
    status: str
    ready_for_confirmation: bool
    missing_sections: list[str]
    gap_prompts: list[str]
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
    if isinstance(section, dict) and "entries" in section:
        completeness = section.get("completeness")
        if completeness == "missing":
            return False
        entries = section.get("entries")
        if not isinstance(entries, list):
            return False
        return any(_is_structured_entry_complete(item) for item in entries)
    if isinstance(section, dict):
        status = section.get("status")
        if isinstance(status, str) and status.strip().lower() == "missing":
            return False
        if "content" in section:
            return not _is_empty_value(section.get("content"))
        return not _is_empty_value(section)
    return not _is_empty_value(section)


def _is_structured_entry_complete(entry: object) -> bool:
    if not isinstance(entry, Mapping):
        return False
    text = entry.get("text")
    return isinstance(text, str) and text.strip() != ""


def _section_has_to_validate(section: object) -> bool:
    if not isinstance(section, Mapping) or "entries" not in section:
        return False
    entries = section.get("entries")
    if not isinstance(entries, list):
        return False
    return any(
        isinstance(item, Mapping)
        and item.get("assertion_state") == "to_validate"
        and _is_structured_entry_complete(item)
        for item in entries
    )


def _build_gap_prompts(missing: list[str], to_validate_sections: list[str], diagnostic_risk_count: int) -> list[str]:
    prompts = [f"请补充「{field}」内容" for field in missing]
    prompts.extend(f"「{field}」已有内容，但仍存在待验证项，请先补齐验证信息。" for field in to_validate_sections)
    if diagnostic_risk_count > 0:
        prompts.append(f"当前仍有 {diagnostic_risk_count} 个开放风险待处理，请先完成关键确认。")
    return prompts


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


def _build_critic_result(
    *,
    ready: bool,
    missing: list[str],
    status: str,
    ready_for_confirmation: bool,
    gap_prompts: list[str],
) -> CriticResult:
    return CriticResult(
        overall_verdict="pass" if ready else "revise",
        major_gaps=list(missing) if missing else list(gap_prompts),
        question_queue=list(gap_prompts),
        ready=ready,
        missing=list(missing),
        required_sections=list(FINALIZE_REQUIRED_SECTIONS),
    )


def evaluate_finalize_readiness(state: Mapping[str, Any]) -> dict[str, Any]:
    prd_draft = state.get("prd_draft")
    sections = _extract_sections(state)
    missing = [
        field
        for field in FINALIZE_REQUIRED_SECTIONS
        if not _is_section_complete(sections.get(field))
    ]
    to_validate_sections = [
        field
        for field in FINALIZE_REQUIRED_SECTIONS
        if field not in missing and _section_has_to_validate(sections.get(field))
    ]
    diagnostic_summary = state.get("diagnostic_summary")
    diagnostic_risk_count = 0
    if isinstance(diagnostic_summary, Mapping):
        risk_count = diagnostic_summary.get("risk_count")
        to_validate_count = diagnostic_summary.get("to_validate_count")
        if isinstance(risk_count, int):
            diagnostic_risk_count += risk_count
        if isinstance(to_validate_count, int):
            diagnostic_risk_count += to_validate_count

    draft_status = prd_draft.get("status") if isinstance(prd_draft, Mapping) else None
    ready_for_confirmation = len(missing) == 0 and not to_validate_sections and diagnostic_risk_count == 0 and draft_status != "finalized"
    if draft_status == "finalized":
        status = "finalized"
        ready = True
    elif missing:
        status = "drafting"
        ready = False
    elif to_validate_sections or diagnostic_risk_count > 0:
        status = "needs_input"
        ready = False
    else:
        status = "ready_for_confirmation"
        ready = True

    gap_prompts = _build_gap_prompts(missing, to_validate_sections, diagnostic_risk_count)
    critic_result = asdict(
        _build_critic_result(
            ready=ready,
            missing=missing,
            status=status,
            ready_for_confirmation=ready_for_confirmation,
            gap_prompts=gap_prompts,
        )
    )
    critic_result["status"] = status
    critic_result["ready_for_confirmation"] = ready_for_confirmation
    critic_result["missing_sections"] = list(missing)
    critic_result["gap_prompts"] = list(gap_prompts)
    return asdict(
        FinalizeReadinessResult(
            ready=ready,
            missing=missing,
            status=status,
            ready_for_confirmation=ready_for_confirmation,
            missing_sections=list(missing),
            gap_prompts=list(gap_prompts),
            critic_result=critic_result,
        )
    )
