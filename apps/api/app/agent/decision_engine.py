from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from typing import Literal

from app.agent.extractor import first_missing_section, is_missing
from app.agent.types import ConversationStrategy, CriticResult, NextMove, TurnDecision, UnderstandingResult

MISSING_SECTION_GAPS = {
    "target_user": "缺少明确的目标用户",
    "problem": "缺少清晰的核心问题",
    "solution": "缺少可行的解决方案方向",
    "mvp_scope": "缺少最小可行范围（MVP）",
}

PHASE_GOALS = {
    "target_user": "收敛目标用户",
    "problem": "明确核心问题",
    "solution": "收敛方案方向",
    "mvp_scope": "压缩 MVP 范围",
    "complete": "总结共识并确认下一步",
}

NON_DIRECTIONAL_STATE_PATCH_KEYS = {"iteration", "stage_hint", "conversation_strategy"}

_CRITICAL_PRODUCT_SPEC_KEYWORDS: tuple[str, ...] = ("核心文件格式", "预览深度", "权限边界")

_CRITICAL_QUESTIONS_BY_KEYWORD: dict[str, str] = {
    "核心文件格式": "首版必须支持哪些核心文件格式？请按优先级列出 3-5 个（例如 DWG/DXF/PDF/IFC/STEP/GLTF）。",
    "预览深度": "预览交互深度要到什么程度：仅旋转缩放，还是测量、标注、剖切、构件选择？首版必须有哪 1-2 项？",
    "权限边界": "权限边界怎么定：哪些人可以查看/编辑/分享？是否需要外链分享、到期、下载限制？",
}


def review_prd_draft_critical_gaps(prd_draft: dict) -> dict:
    """最小 Critic 规则：基于 prd_draft.missing_information 识别关键产品方案缺口。

    规则：当“核心文件格式 / 预览深度 / 权限边界”这类关键项缺少 >= 2 项时，直接 block。
    """

    missing_information = list((prd_draft or {}).get("missing_information") or [])
    matched_keywords: list[str] = []
    for keyword in _CRITICAL_PRODUCT_SPEC_KEYWORDS:
        if any(keyword in str(item) for item in missing_information):
            matched_keywords.append(keyword)

    question_queue = [_CRITICAL_QUESTIONS_BY_KEYWORD[k] for k in matched_keywords]
    major_gaps = [item for item in missing_information if any(k in str(item) for k in matched_keywords)]

    blocking_questions: list[str] = []
    Verdict = Literal["pass", "revise", "block"]
    overall_verdict: Verdict
    if not missing_information:
        overall_verdict = "pass"
    elif len(matched_keywords) >= 2:
        overall_verdict = "block"
        blocking_questions = list(question_queue)
    else:
        # missing_information 非空时，无论是否命中关键关键词，均至少需要 revise，不直接放行。
        overall_verdict = "revise"

    critic = CriticResult(
        overall_verdict=overall_verdict,
        major_gaps=major_gaps,
        question_queue=question_queue,
        blocking_questions=blocking_questions,
        recommended_next_focus=matched_keywords[0] if matched_keywords else None,
    )
    return asdict(critic)


def _merge_state(state: dict, state_patch: dict) -> dict:
    merged = deepcopy(state)
    merged.update(state_patch)
    return merged


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered


def _build_gaps(state: dict, understanding: UnderstandingResult) -> list[str]:
    gaps: list[str] = []
    for key in ("target_user", "problem", "solution", "mvp_scope"):
        if is_missing(state.get(key)):
            gaps.append(MISSING_SECTION_GAPS[key])
    gaps.extend(understanding.ambiguous_points)
    return gaps


def _build_assumptions(understanding: UnderstandingResult) -> list[dict[str, str]]:
    return [{"label": item, "source": "user_input"} for item in understanding.assumption_candidates]


def _build_challenges(understanding: UnderstandingResult) -> list[str]:
    challenges: list[str] = []
    if "user_too_broad" in understanding.risk_hints:
        challenges.append("目标用户范围过泛，需优先收敛")
    if "problem_too_vague" in understanding.risk_hints:
        challenges.append("问题描述过于模糊，需要具体化")
    if "solution_before_problem" in understanding.risk_hints:
        challenges.append("方案先于问题，需要先明确问题")
    return challenges


def _select_next_move(
    understanding: UnderstandingResult,
    conversation_strategy: ConversationStrategy,
) -> NextMove:
    if "solution_before_problem" in understanding.risk_hints:
        return "challenge_and_reframe"
    if "user_too_broad" in understanding.risk_hints:
        return "force_rank_or_choose"
    if "problem_too_vague" in understanding.risk_hints:
        return "probe_for_specificity"
    if conversation_strategy == "confirm":
        return "summarize_and_confirm"
    if conversation_strategy == "choose":
        return "force_rank_or_choose"
    if conversation_strategy == "converge":
        return "assume_and_advance"
    return "probe_for_specificity"


def _select_confidence(next_move: NextMove) -> str:
    if next_move in {"force_rank_or_choose", "challenge_and_reframe"}:
        return "low"
    if next_move == "summarize_and_confirm":
        return "high"
    return "medium"


def _resolve_phase(state: dict) -> str:
    phase = state.get("current_phase")
    if isinstance(phase, str) and phase.strip():
        return phase
    missing = first_missing_section(state)
    if missing is None:
        return "alignment_review"
    return f"{missing}_clarification"


def _resolve_phase_goal(state: dict) -> str | None:
    phase_goal = state.get("phase_goal")
    if isinstance(phase_goal, str) and phase_goal.strip():
        return phase_goal
    missing = first_missing_section(state)
    if missing is None:
        return PHASE_GOALS["complete"]
    return PHASE_GOALS[missing]


def _resolve_needs_confirmation(state: dict, next_move: NextMove) -> list[str]:
    confirmations = list(state.get("pending_confirmations") or [])
    if confirmations:
        return confirmations
    if next_move == "summarize_and_confirm":
        return ["请确认当前理解是否准确"]
    return []


def _resolve_conversation_strategy(
    state: dict,
    understanding: UnderstandingResult,
    gaps: list[str],
    has_direction_signal: bool,
) -> ConversationStrategy:
    current_strategy = state.get("conversation_strategy")

    if "user_too_broad" in understanding.risk_hints:
        return "choose"

    if current_strategy == "choose":
        if has_direction_signal:
            return "converge"
        return "choose"

    if any(hint in understanding.risk_hints for hint in ("problem_too_vague", "solution_before_problem")):
        return "clarify"

    if current_strategy == "confirm" and not has_direction_signal:
        return "confirm"

    if not gaps:
        return "confirm"

    if current_strategy == "converge":
        return "converge"

    if has_direction_signal:
        return "converge"

    return "clarify"


def _build_next_best_questions(
    conversation_strategy: ConversationStrategy,
    gaps: list[str],
    needs_confirmation: list[str],
) -> list[str]:
    if conversation_strategy == "confirm":
        return list(needs_confirmation) or ["请确认当前理解是否准确"]

    if conversation_strategy == "choose":
        return ["如果只能先选一个主线，你更愿意先收敛用户还是问题？"]

    if conversation_strategy == "converge":
        return ["基于当前信息，你最想先验证哪一项：频率、付费意愿，还是转化阻力？"]

    if gaps:
        focus = gaps[0]
        if focus.startswith("缺少"):
            focus = focus[2:]
        return [f"为了继续推进，请先把{focus}补具体。"]

    return ["为了继续推进，请先补充一个最具体的真实场景。"]


def _has_direction_signal(
    state_patch: dict,
    understanding: UnderstandingResult,
    prd_patch: dict,
) -> bool:
    meaningful_state_keys = {
        key
        for key, value in state_patch.items()
        if key not in NON_DIRECTIONAL_STATE_PATCH_KEYS and not is_missing(value)
    }
    meaningful_prd_patch = any(
        isinstance(value, dict)
        and value.get("status") != "missing"
        and not is_missing(value.get("content"))
        for value in prd_patch.values()
    )
    return bool(meaningful_state_keys or understanding.candidate_updates or meaningful_prd_patch)


def _build_strategy_reason(
    previous_strategy: str | None,
    conversation_strategy: ConversationStrategy,
    understanding: UnderstandingResult,
    has_direction_signal: bool,
) -> str:
    if conversation_strategy == "choose":
        return "目标用户仍然过泛，当前先推动你做主线取舍。"

    if conversation_strategy == "clarify":
        if "solution_before_problem" in understanding.risk_hints:
            return "方案先于问题，当前需要回到 clarify 重构问题定义。"
        if "problem_too_vague" in understanding.risk_hints:
            return "当前问题描述仍然过于模糊，需要继续 clarify。"
        return "当前关键信息仍不够具体，需要继续 clarify。"

    if conversation_strategy == "converge":
        if previous_strategy == "choose":
            return "用户已经给出明确取舍信号，策略从 choose 进入 converge。"
        if has_direction_signal:
            return "已有方向信号，但仍有关键缺口，当前继续 converge。"
        return "当前已进入收敛阶段，先继续 converge。"

    if previous_strategy == "confirm" and not has_direction_signal:
        return "这轮没有新增风险，当前继续停留在 confirm 锁定共识。"
    return "核心信息已基本齐备，当前进入 confirm 锁定共识。"


def build_turn_decision(
    state: dict,
    understanding: UnderstandingResult,
    state_patch: dict,
    prd_patch: dict,
) -> TurnDecision:
    merged_state = _merge_state(state, state_patch)
    previous_strategy = state.get("conversation_strategy")
    gaps = _build_gaps(merged_state, understanding)
    has_direction_signal = _has_direction_signal(state_patch, understanding, prd_patch)
    conversation_strategy = _resolve_conversation_strategy(
        merged_state,
        understanding,
        gaps,
        has_direction_signal,
    )
    next_move = _select_next_move(understanding, conversation_strategy)
    confidence = _select_confidence(next_move)
    needs_confirmation = _resolve_needs_confirmation(merged_state, next_move)
    pm_risk_flags = _dedupe(
        list(merged_state.get("pm_risk_flags") or []) + list(understanding.risk_hints)
    )
    next_best_questions = _build_next_best_questions(
        conversation_strategy,
        gaps,
        needs_confirmation,
    )
    strategy_reason = _build_strategy_reason(
        previous_strategy,
        conversation_strategy,
        understanding,
        has_direction_signal,
    )

    return TurnDecision(
        phase=_resolve_phase(merged_state),
        phase_goal=_resolve_phase_goal(merged_state),
        understanding={
            "summary": understanding.summary,
            "candidate_updates": understanding.candidate_updates,
            "ambiguous_points": understanding.ambiguous_points,
        },
        assumptions=_build_assumptions(understanding),
        gaps=gaps,
        challenges=_build_challenges(understanding),
        pm_risk_flags=pm_risk_flags,
        next_move=next_move,
        suggestions=[],
        recommendation=None,
        reply_brief={"focus": next_move, "must_include": []},
        state_patch=state_patch,
        prd_patch=prd_patch,
        needs_confirmation=needs_confirmation,
        confidence=confidence,
        strategy_reason=strategy_reason,
        next_best_questions=next_best_questions,
        conversation_strategy=conversation_strategy,
    )
