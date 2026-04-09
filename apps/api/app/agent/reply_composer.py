from __future__ import annotations

from app.agent.types import TurnDecision

DRAFT_SUMMARY_PREFIX = "草稿摘要："
CRITIC_VERDICT_PREFIX = "Critic 结论："
NEXT_QUESTION_PREFIX = "唯一下一问："

_VALID_VERDICTS = {"pass", "revise", "block"}

_STATUS_LABELS = {
    "draft_hypothesis": "假设草案阶段",
    "draft_refined": "细化草稿阶段",
    "ready_for_finalize": "准备确认阶段",
}
_PHASE_LABELS = {
    "initial_draft": "初稿阶段",
    "refine_loop": "补齐关键信息阶段",
    "finalize": "最终整理阶段",
}
_FINALIZE_CONFIRM_PROMPT = "如果当前摘要没有偏差，请直接回复“确认设计”"
_FALLBACK_NO_QUESTION = "目前没有特别要问的问题，你可以直接指出摘要偏差"


def compose_reply(decision: TurnDecision) -> str:
    sections = build_reply_sections(decision)
    return "\n\n".join(f"{section['title']}{section['content']}" for section in sections)


def build_reply_sections(decision: TurnDecision | object) -> list[dict[str, str]]:
    return [
        {
            "key": "judgement",
            "title": DRAFT_SUMMARY_PREFIX,
            "content": _build_draft_summary(decision),
        },
        {
            "key": "critic_verdict",
            "title": CRITIC_VERDICT_PREFIX,
            "content": _build_critic_verdict(decision),
        },
        {
            "key": "next_step",
            "title": NEXT_QUESTION_PREFIX,
            "content": _build_next_question(decision),
        },
    ]


def _build_draft_summary(decision: TurnDecision | object) -> str:
    prd_draft = _resolve_prd_draft(decision)

    fragments: list[str] = []
    version = prd_draft.get("version")
    status = prd_draft.get("status")
    if version is not None:
        fragments.append(f"PRD v{version}")
    if isinstance(status, str):
        fragments.append(_status_label(status))

    if fragments:
        stage = f"当前草稿处于{'，'.join(fragments)}"
    else:
        stage = _build_phase_summary(decision)

    details: list[str] = []
    assumptions = _clean_list(prd_draft.get("assumptions"))
    if assumptions:
        details.append(f"关键假设包括{_format_items(assumptions)}")

    missing_information = _collect_missing_information(decision, prd_draft)
    if missing_information:
        details.append(f"缺失信息包括{_format_items(missing_information)}")

    summary = stage
    for idx, detail in enumerate(details):
        delimiter = "，" if idx == 0 else "；"
        summary = f"{summary}{delimiter}{detail}"
    return summary


def _build_critic_verdict(decision: TurnDecision | object) -> str:
    critic_result = _resolve_critic_result(decision)
    verdict = _determine_overall_verdict(decision, critic_result)
    major_gaps = _collect_major_gaps(decision, critic_result)
    if verdict == "pass" and not major_gaps:
        gap_description = "关键缺口已补齐"
    elif major_gaps:
        gap_description = f"主要缺口包括{_format_items(major_gaps)}"
    else:
        gap_description = "目前尚未明确具体缺口"

    return f"当前 Critic 判断是 {verdict}，{gap_description}"


def _build_next_question(decision: TurnDecision | object) -> str:
    critic_result = _resolve_critic_result(decision)
    question_queue = critic_result.get("question_queue")
    question = _strict_queue_head(question_queue)
    if question is None and "question_queue" not in critic_result:
        question = _strict_queue_head(getattr(decision, "next_best_questions", None))

    verdict = _determine_overall_verdict(decision, critic_result)
    if not question:
        if verdict == "pass":
            return _FINALIZE_CONFIRM_PROMPT
        return _FALLBACK_NO_QUESTION
    return question


def _build_phase_summary(decision: TurnDecision | object) -> str:
    phase = getattr(decision, "phase", None)
    phase_goal = getattr(decision, "phase_goal", None)
    label = _phase_label(phase)
    if label:
        base = f"当前对话已进入{label}"
        if phase_goal:
            return f"{base}，目标是{phase_goal}"
        return base
    if phase_goal:
        return f"当前对话目标是{phase_goal}"
    return "当前对话正在推进中"


def _collect_major_gaps(decision: TurnDecision | object, critic_gaps: list[str] | None) -> list[str]:
    if "major_gaps" in critic_gaps:
        return _clean_list(critic_gaps.get("major_gaps"))
    return _clean_list(getattr(decision, "gaps", None))


def _collect_missing_information(decision: TurnDecision | object, prd_draft: dict[str, object]) -> list[str]:
    if "missing_information" in prd_draft:
        return _clean_list(prd_draft.get("missing_information"))
    return _clean_list(getattr(decision, "gaps", None))


def _clean_list(items: list[str] | None) -> list[str]:
    if not items:
        return []
    cleaned: list[str] = []
    for item in items:
        if isinstance(item, str):
            stripped = item.strip()
            if stripped:
                cleaned.append(stripped)
    return cleaned


def _format_items(items: list[str], limit: int = 2) -> str:
    limited = items[:limit]
    return "、".join(f"“{item}”" for item in limited)


def _status_label(status: str) -> str:
    return _STATUS_LABELS.get(status, "草稿阶段")


def _phase_label(phase: str | None) -> str:
    if not phase:
        return ""
    return _PHASE_LABELS.get(phase, "")


def _resolve_prd_draft(decision: TurnDecision | object) -> dict[str, object]:
    prd_draft = getattr(decision, "prd_draft", None)
    if isinstance(prd_draft, dict):
        return prd_draft

    state_patch = getattr(decision, "state_patch", None)
    if isinstance(state_patch, dict):
        state_patch_prd_draft = state_patch.get("prd_draft")
        if isinstance(state_patch_prd_draft, dict):
            return state_patch_prd_draft
    return {}


def _resolve_critic_result(decision: TurnDecision | object) -> dict[str, object]:
    critic_result = getattr(decision, "critic_result", None)
    if isinstance(critic_result, dict):
        return critic_result

    state_patch = getattr(decision, "state_patch", None)
    if isinstance(state_patch, dict):
        state_patch_critic_result = state_patch.get("critic_result")
        if isinstance(state_patch_critic_result, dict):
            return state_patch_critic_result
    return {}


def _determine_overall_verdict(decision: TurnDecision | object, critic_result: dict[str, object]) -> str:
    raw_verdict = str(critic_result.get("overall_verdict") or "").strip().lower()
    if raw_verdict in _VALID_VERDICTS:
        return raw_verdict
    if not critic_result and _should_auto_finalize(decision):
        return "pass"
    return "revise"


def _should_auto_finalize(decision: TurnDecision | object) -> bool:
    phase = getattr(decision, "phase", None)
    if phase != "finalize":
        return False
    if _clean_list(getattr(decision, "gaps", None)):
        return False
    if _clean_list(getattr(decision, "next_best_questions", None)):
        return False
    return True


def _strict_queue_head(items: list[str] | None) -> str | None:
    if not isinstance(items, list) or not items:
        return None
    first = items[0]
    if not isinstance(first, str):
        return None
    stripped = first.strip()
    if not stripped:
        return None
    return stripped
