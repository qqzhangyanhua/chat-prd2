from __future__ import annotations

from app.agent.types import Suggestion, TurnDecision

JUDGEMENT_PREFIX = "我现在的判断是"
ASSUMPTION_PREFIX = "关键假设是"
SUGGEST_PREFIX = "我建议"
SUGGEST_PREFIX_RECOMMEND = "我更建议"
CONFIRM_ITEMS_PREFIX = "当前待确认的是"
NEXT_STEP_PREFIX = "下一步动作是"

NEXT_MOVE_JUDGEMENT = {
    "probe_for_specificity": "目前关键信息还不够具体，需要先把描述说清楚",
    "assume_and_advance": "你已经给出方向信号，可以基于假设先推进",
    "challenge_and_reframe": "需要先回到问题本身，再谈方案细节",
    "summarize_and_confirm": "核心信息基本齐全，可以先确认当前共识",
    "force_rank_or_choose": "需要你在几个方向里做取舍或排序",
}


def compose_reply(decision: TurnDecision) -> str:
    return "。".join(
        f"{section['title']}{section['content']}" for section in build_reply_sections(decision)
    )


def build_reply_sections(decision: TurnDecision | object) -> list[dict[str, str]]:
    suggestion_title = _suggest_prefix(decision)
    return [
        {"key": "judgement", "title": JUDGEMENT_PREFIX, "content": _build_judgement(decision)},
        {"key": "assumption", "title": ASSUMPTION_PREFIX, "content": _build_assumption(decision)},
        {"key": "suggestion", "title": suggestion_title, "content": _build_suggestion(decision)},
        {
            "key": "confirmation",
            "title": CONFIRM_ITEMS_PREFIX,
            "content": _build_confirmation_items(decision),
        },
        {"key": "next_step", "title": NEXT_STEP_PREFIX, "content": _build_next_step(decision)},
    ]


def _build_judgement(decision: TurnDecision | object) -> str:
    next_move = getattr(decision, "next_move", None)
    phase_goal = getattr(decision, "phase_goal", None)
    base = NEXT_MOVE_JUDGEMENT.get(next_move, "需要先把关键信息收敛清楚")
    if phase_goal:
        return f"{base}，目标是{phase_goal}"
    return base


def _build_assumption(decision: TurnDecision | object) -> str:
    labels = _extract_assumption_labels(decision)
    if not labels:
        return "当前不额外补假设，先按现有信息推进"

    limited = labels[:2]
    joined = "、".join(f"“{label}”" for label in limited)
    suffix = "这个假设" if len(limited) == 1 else "这些假设"
    return f"先按{joined}{suffix}推进"


def _extract_assumption_labels(decision: TurnDecision | object) -> list[str]:
    labels: list[str] = []
    for item in getattr(decision, "assumptions", []) or []:
        label = item.get("label") if isinstance(item, dict) else None
        if isinstance(label, str) and label.strip():
            labels.append(label.strip())
    return labels


def _suggest_prefix(decision: TurnDecision | object) -> str:
    if getattr(decision, "recommendation", None):
        return SUGGEST_PREFIX_RECOMMEND
    return SUGGEST_PREFIX


def _build_suggestion(decision: TurnDecision | object) -> str:
    suggestions = getattr(decision, "suggestions", []) or []
    recommendation = getattr(decision, "recommendation", None) or {}
    rec_label = recommendation.get("label") or (
        _suggestion_label(suggestions[0]) if suggestions else "先收敛关键信息"
    )
    rec_content = recommendation.get("content")
    other_labels = _collect_other_labels(rec_label, suggestions)
    message = f"先按“{rec_label}”推进"
    if rec_content:
        message = f"{message}，具体做法是{rec_content}"
    if other_labels:
        message = f"{message}，备选方向还有{other_labels}"
    return message


def _suggestion_label(item: Suggestion | dict) -> str:
    if isinstance(item, dict):
        return str(item.get("label", "")).strip()
    return item.label


def _collect_other_labels(rec_label: str, suggestions: list[Suggestion | dict]) -> str:
    labels = [_suggestion_label(item) for item in suggestions if _suggestion_label(item) != rec_label]
    if not labels:
        return ""
    limited = labels[:2]
    decorated = [f"“{label}”" for label in limited]
    return "、".join(decorated)


def _build_confirmation_items(decision: TurnDecision | object) -> str:
    confirmations = getattr(decision, "needs_confirmation", []) or []
    if confirmations:
        return _join_items(confirmations)
    return "没有新增确认项，我先继续推进"


def _join_items(items: list[str]) -> str:
    return "、".join(items)


def _primary_confirmation(decision: TurnDecision | object) -> str | None:
    confirmations = getattr(decision, "needs_confirmation", []) or []
    if not confirmations:
        return None
    return confirmations[0]


def _primary_gap(decision: TurnDecision | object) -> str | None:
    gaps = getattr(decision, "gaps", []) or []
    if not gaps:
        return None
    focus = gaps[0].strip()
    if focus.startswith("缺少"):
        return focus[2:]
    return focus


def _primary_recommendation_label(decision: TurnDecision | object) -> str | None:
    recommendation = getattr(decision, "recommendation", None) or {}
    label = recommendation.get("label")
    if isinstance(label, str) and label.strip():
        return label.strip()
    suggestions = getattr(decision, "suggestions", []) or []
    if suggestions:
        return _suggestion_label(suggestions[0])
    return None


def _primary_next_best_question(decision: TurnDecision | object) -> str | None:
    questions = getattr(decision, "next_best_questions", []) or []
    if not questions:
        return None
    question = questions[0]
    if isinstance(question, str) and question.strip():
        return question.strip()
    return None


def _build_next_step(decision: TurnDecision | object) -> str:
    primary_confirmation = _primary_confirmation(decision)
    primary_gap = _primary_gap(decision)
    recommendation_label = _primary_recommendation_label(decision)
    next_best_question = _primary_next_best_question(decision)
    next_move = getattr(decision, "next_move", None)
    phase_goal = getattr(decision, "phase_goal", None) or "当前目标"

    if next_move == "force_rank_or_choose":
        if primary_confirmation:
            message = f"请你直接在上面方向里做取舍，顺手确认{primary_confirmation}，我就按你的选择继续展开"
        else:
            message = "请你直接在上面方向里做取舍，我就按你的选择继续展开"
        return _append_next_best_question(message, next_best_question)

    if next_move == "summarize_and_confirm":
        if primary_confirmation:
            message = f"请你先确认{primary_confirmation}，确认后我就继续细化下一步"
        else:
            message = "请你先确认当前共识，确认后我就继续细化下一步"
        return _append_next_best_question(message, next_best_question)

    if next_move == "assume_and_advance":
        if recommendation_label:
            message = f"如果你认可这个推进点，我就先按“{recommendation_label}”继续展开"
        else:
            message = "如果你认可这个推进点，我就先按当前建议继续展开"
        return _append_next_best_question(message, next_best_question)

    if next_move == "probe_for_specificity":
        if primary_gap:
            message = f"请你先把{primary_gap}补具体，我再继续收敛"
        else:
            message = f"请你先把和“{phase_goal}”相关的关键信息补具体，我再继续收敛"
        return _append_next_best_question(message, next_best_question)

    message = "如果当前问题判断不对你直接指出，我会先重构问题定义再推进方案"
    return _append_next_best_question(message, next_best_question)


def _append_next_best_question(message: str, next_best_question: str | None) -> str:
    if not next_best_question:
        return message
    return f"{message}，我下一轮最建议你直接回答：{next_best_question}"
