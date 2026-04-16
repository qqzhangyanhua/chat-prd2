from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.agent.types import (
    GUIDANCE_SUGGESTION_COUNT,
    AgentResult,
    NextAction,
    PmMentorOutput,
    Suggestion,
    TurnDecision,
)
from app.services.model_gateway import ModelGatewayError, call_pm_mentor_llm

logger = logging.getLogger(__name__)

MAX_HISTORY_TURNS = 10
_FREEFORM_AFFORDANCE = {
    "label": "都不对，我补充",
    "value": "freeform",
    "kind": "freeform",
}

ALLOWED_NEXT_FOCUS = {"target_user", "problem", "solution", "mvp_scope", "done"}
ALLOWED_NEXT_MOVES = {
    "probe_for_specificity",
    "assume_and_advance",
    "challenge_and_reframe",
    "summarize_and_confirm",
    "force_rank_or_choose",
}
ALLOWED_STATUS = {"missing", "draft", "confirmed"}
ALLOWED_SUGGESTION_TYPES = {"direction", "tradeoff", "recommendation", "warning"}
ALLOWED_PRD_SECTION_KEYS = {
    "target_user",
    "problem",
    "solution",
    "mvp_scope",
    "constraints",
    "success_metrics",
    "out_of_scope",
    "open_questions",
}
SECTION_TITLES = {
    "target_user": "目标用户",
    "problem": "核心问题",
    "solution": "解决方案",
    "mvp_scope": "MVP 范围",
    "constraints": "约束条件",
    "success_metrics": "成功指标",
    "out_of_scope": "不做清单",
    "open_questions": "待确认问题",
}

PM_MENTOR_SYSTEM_PROMPT = """你是一位经验丰富的 AI 产品联合创始人（PM 导师风格）。
你的职责是帮助用户把一个模糊的想法，逐步打磨成一份清晰可执行的 PRD。

【你的工作方式】
每轮对话，你必须做四件事：
1. Observation  — 指出用户本轮输入中最关键的信息或隐含假设
2. Challenge    — 挑战一个具体的假设或盲点（不能泛泛追问）
3. Suggestion   — 给出一个具体的 PM 视角建议或框架
4. Question     — 只问一个最关键的问题，推动对话向前

【建议选项规则】
- 每轮都必须返回正好 4 个 suggestions，供用户直接选择继续
- 每个 suggestion 必须包含：type, label, content, rationale, priority
- content 必须是用户可以直接发送的完整句子
- recommendation 必须对应 suggestions 中的一项
- 如果当前信息还少，suggestions 应围绕“用户 / 问题 / 方案切入口 / 自由补充”组织
- 如果当前信息已经较多，suggestions 应围绕“确认 / 补充 / 对比 / 继续下一步”组织
- reply 里不要只留下一个裸问题，要自然告诉用户“你可以直接选一个方向继续”

【PRD 更新规则】
- 信息具体（有场景、有角色、有边界）→ 写入对应 section，status: "draft"
- 用户明确确认 → status: "confirmed"
- 信息模糊、矛盾或不完整 → status: "missing"，content 写明缺什么
- 本轮没有新信息 → prd_updates 返回空对象 {}

【禁止行为】
- question 里不能同时问多个问题
- observation 不能重复上轮已知信息
- challenge 必须指向具体假设，不能泛泛质疑
- 信息不足时不能强行推进到下一个 section
- 不允许省略 suggestions 或 recommendation，且 suggestions 数量必须正好等于 4

【输出格式】
严格返回 JSON，包含以下字段：
observation, challenge, suggestion, question, reply, prd_updates, confidence, next_focus, next_move, suggestions, recommendation"""

PM_MENTOR_REPAIR_SYSTEM_PROMPT = """你正在修复上一轮 PM 导师输出中的 suggestions 字段。

【你的唯一任务】
- 只重写 suggestions 和 recommendation
- 必须返回正好 4 个 suggestions
- 不要改写 reply、observation、challenge、suggestion、question、prd_updates、confidence、next_focus、next_move

【强约束】
- 每个 suggestion 必须包含：type, label, content, rationale, priority
- content 必须是用户可以直接发送的完整中文句子
- recommendation 必须对应这 4 个 suggestions 之一
- 如果信息不足，优先围绕“目标用户 / 核心问题 / 方案切入口 / 自由补充”给出 4 个方向

【输出格式】
严格返回 JSON，只包含以下字段：
suggestions, recommendation"""


def _build_conversation_history(conversation_history: list[dict[str, str]] | None) -> list[dict[str, str]]:
    if not conversation_history:
        return []
    filtered = [m for m in conversation_history if m.get("role") in {"user", "assistant"}]
    return filtered[-(MAX_HISTORY_TURNS * 2):]


def _build_current_prd(state: dict[str, Any]) -> dict[str, Any]:
    prd_snapshot = state.get("prd_snapshot") or {}
    sections = prd_snapshot.get("sections") or {}
    missing = [
        key for key, value in sections.items()
        if isinstance(value, dict) and value.get("status") == "missing"
    ]
    return {"sections": sections, "missing": missing}


def _build_user_prompt(
    state: dict[str, Any],
    user_input: str,
    conversation_history: list[dict[str, str]] | None = None,
) -> str:
    history = _build_conversation_history(conversation_history)
    current_prd = _build_current_prd(state)
    turn_count = int(state.get("iteration") or 0)
    return json.dumps(
        {
            "current_prd": current_prd,
            "conversation_history": history,
            "turn_count": turn_count,
            "user_input": user_input,
            "assistant_goals": {
                "always_offer_guided_options": True,
                "suggestion_count": str(GUIDANCE_SUGGESTION_COUNT),
                "each_option_should_be_sendable": True,
            },
        },
        ensure_ascii=False,
    )


def _build_repair_prompt(
    state: dict[str, Any],
    user_input: str,
    mentor_output: PmMentorOutput,
    conversation_history: list[dict[str, str]] | None = None,
) -> str:
    history = _build_conversation_history(conversation_history)
    current_prd = _build_current_prd(state)
    return json.dumps(
        {
            "task": "repair_suggestions_only",
            "current_prd": current_prd,
            "conversation_history": history,
            "user_input": user_input,
            "locked_fields": {
                "observation": mentor_output.observation,
                "challenge": mentor_output.challenge,
                "suggestion": mentor_output.suggestion,
                "question": mentor_output.question,
                "reply": mentor_output.reply,
                "prd_updates": mentor_output.prd_updates,
                "confidence": mentor_output.confidence,
                "next_focus": mentor_output.next_focus,
                "next_move": mentor_output.next_move,
            },
            "invalid_output": {
                "suggestion_count": mentor_output.raw_suggestion_count or len(mentor_output.suggestions),
                "suggestions": [
                    {
                        "type": item.type,
                        "label": item.label,
                        "content": item.content,
                        "rationale": item.rationale,
                        "priority": item.priority,
                    }
                    for item in mentor_output.suggestions
                ],
                "recommendation": mentor_output.recommendation,
            },
        },
        ensure_ascii=False,
    )


def _validate_prd_updates(raw_updates: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(raw_updates, dict):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for key, val in raw_updates.items():
        if key not in ALLOWED_PRD_SECTION_KEYS:
            continue
        if not isinstance(val, dict):
            continue
        status = val.get("status")
        if status not in ALLOWED_STATUS:
            val = {**val, "status": "draft"}
        result[key] = val
    return result


def _infer_conversation_strategy(
    confidence: str,
    next_focus: str,
    state: dict[str, Any],
) -> str:
    if next_focus == "done":
        return "confirm"
    sections = state.get("prd_snapshot", {}).get("sections", {})
    missing_count = sum(
        1 for v in sections.values()
        if isinstance(v, dict) and v.get("status") == "missing"
    )
    if confidence == "high" and missing_count <= 1:
        return "converge"
    return "clarify"


def _is_sendable_sentence(content: str) -> bool:
    normalized = content.strip()
    if not normalized:
        return False
    if not normalized.endswith(("。", "！", "？")):
        return False
    if not re.match(r"^(我|先|请|麻烦|可以|直接|你先)", normalized):
        return False
    return bool(re.search(r"(想|要|请|帮|补充|明确|比较|说明|列|确认|继续|直接)", normalized))


def _coerce_sendable_content(content: str, label: str) -> str:
    normalized = content.strip()
    if _is_sendable_sentence(normalized):
        return normalized

    cleaned = normalized.rstrip("。！？；;，,：:")
    if cleaned:
        return f"我想先从{cleaned}这个方向继续，请你帮我把这一块问清楚。"
    return f"我想先从{label.strip()}这个方向继续，请你帮我把这一块问清楚。"


def _normalize_suggestions(raw_suggestions: Any) -> list[Suggestion]:
    if not isinstance(raw_suggestions, list):
        return []

    normalized: list[Suggestion] = []
    for raw_item in raw_suggestions:
        if not isinstance(raw_item, dict):
            continue

        label = raw_item.get("label")
        content = raw_item.get("content")
        rationale = raw_item.get("rationale")
        priority = raw_item.get("priority")
        suggestion_type = raw_item.get("type")

        if not isinstance(label, str) or not label.strip():
            continue
        if not isinstance(content, str) or not content.strip():
            continue
        if not isinstance(rationale, str) or not rationale.strip():
            continue

        if suggestion_type not in ALLOWED_SUGGESTION_TYPES:
            continue

        normalized.append(
            Suggestion(
                type=suggestion_type,
                label=label.strip(),
                content=_coerce_sendable_content(content, label),
                rationale=rationale.strip(),
                priority=priority if isinstance(priority, int) and priority > 0 else len(normalized) + 1,
            )
        )

    deduped: list[Suggestion] = []
    seen: set[tuple[str, str]] = set()
    for item in sorted(normalized, key=lambda candidate: candidate.priority):
        key = (item.label, item.content)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
        if len(deduped) >= GUIDANCE_SUGGESTION_COUNT:
            break
    return deduped


def _has_mandatory_suggestions(suggestions: list[Suggestion]) -> bool:
    if len(suggestions) != GUIDANCE_SUGGESTION_COUNT:
        return False
    return all(_is_sendable_sentence(item.content) for item in suggestions)


def _has_valid_raw_suggestion_contract(mentor_output: PmMentorOutput) -> bool:
    return mentor_output.raw_suggestion_count == GUIDANCE_SUGGESTION_COUNT and _has_mandatory_suggestions(
        mentor_output.suggestions
    )


def _merge_with_programmatic_fallback(
    existing: list[Suggestion],
    *,
    user_input: str,
    next_focus: str,
) -> list[Suggestion]:
    merged: list[Suggestion] = []
    seen: set[tuple[str, str]] = set()

    for item in existing:
        key = (item.label, item.content)
        if key in seen:
            continue
        seen.add(key)
        merged.append(
            Suggestion(
                type=item.type,
                label=item.label,
                content=_coerce_sendable_content(item.content, item.label),
                rationale=item.rationale,
                priority=len(merged) + 1,
            )
        )
        if len(merged) >= GUIDANCE_SUGGESTION_COUNT:
            return merged

    for fallback in _build_fallback_suggestions(user_input, next_focus):
        key = (fallback.label, fallback.content)
        if key in seen:
            continue
        seen.add(key)
        merged.append(
            Suggestion(
                type=fallback.type,
                label=fallback.label,
                content=fallback.content,
                rationale=fallback.rationale,
                priority=len(merged) + 1,
            )
        )
        if len(merged) >= GUIDANCE_SUGGESTION_COUNT:
            break
    return merged


def _normalize_recommendation(raw_recommendation: Any, suggestions: list[Suggestion]) -> dict[str, Any] | None:
    if isinstance(raw_recommendation, dict):
        label = raw_recommendation.get("label")
        if isinstance(label, str) and label.strip():
            normalized_label = label.strip()
            matched = next((item for item in suggestions if item.label == normalized_label), None)
            if matched is not None:
                return {"label": matched.label, "content": matched.content}

    if suggestions:
        first = suggestions[0]
        return {"label": first.label, "content": first.content}
    return None


def _get_raw_suggestion_count(raw_suggestions: Any) -> int:
    if not isinstance(raw_suggestions, list):
        return 0
    return len(raw_suggestions)


def _infer_subject_hint(user_input: str) -> str:
    normalized = user_input.strip()
    lowered = normalized.lower()
    if "todolist" in lowered or "todo list" in lowered:
        return "这个 todolist"
    if "待办" in normalized:
        return "这个待办产品"
    if "任务管理" in normalized:
        return "这个任务管理工具"
    if "prd" in lowered:
        return "这个产品想法"
    return "这个产品"


def _build_fallback_suggestions(user_input: str, next_focus: str) -> list[Suggestion]:
    subject = _infer_subject_hint(user_input)
    options_by_focus: dict[str, list[tuple[str, str, str]]] = {
        "target_user": [
            ("先缩小用户", f"我想先明确，{subject}第一版最想服务谁。", "先锁定用户，后续痛点和功能才更容易收敛。"),
            ("先讲典型场景", "我先描述一个最典型的使用场景，你帮我反推目标用户。", "有场景时，更容易判断谁会真正愿意用。"),
            ("先让我选方向", "你先给我几个可能的目标用户方向，我来选一个。", "如果还没想透，先做方向对比比硬想更省力。"),
            ("我直接补充", "我直接补充我现在观察到的用户特点。", "保留自由表达出口，避免选项限制你的真实想法。"),
        ],
        "problem": [
            ("先讲高频麻烦", f"我想先讲清楚，{subject}里最高频出现的那个麻烦是什么。", "先锁定高频问题，后面才容易判断值不值得做。"),
            ("先讲最痛一刻", "我想先描述用户最崩溃的一次具体场景，你帮我抽出核心问题。", "具体场景比抽象描述更容易暴露真实痛点。"),
            ("先讲替代方案", "我想先说说，用户现在是怎么勉强解决这个问题的。", "先看现有替代方案，才能判断问题是否真的足够痛。"),
            ("我直接补充", f"我直接补充我现在对{subject}核心问题的判断。", "保留自由输入，方便直接讲你已经观察到的问题。"),
        ],
        "solution": [
            ("先讲方案主线", f"我想先说明，{subject}第一版最核心的解决方式是什么。", "先讲主线方案，能避免功能堆砌。"),
            ("先讲差异化", f"我想先比较，{subject}和现有做法最大的不同是什么。", "差异化清楚了，方案价值才站得住。"),
            ("先讲关键流程", "我想先描述用户完成一次任务的关键流程。", "关键流程能帮助快速判断方案是否顺。"),
            ("我直接补充", f"我直接补充我对{subject}方案的想法。", "保留自由输入，便于直接表达你的方案直觉。"),
        ],
        "mvp_scope": [
            ("先定必须有", f"我想先列出，{subject}第一版必须有的 3 个能力。", "先定必须项，能避免首版范围失控。"),
            ("先定不要做", f"我想先说清楚，{subject}第一版坚决不做什么。", "先划边界，能更快形成可交付 MVP。"),
            ("先定完成标准", f"我想先定义，怎样算{subject}第一版已经可用了。", "先有完成标准，后面的取舍会更稳。"),
            ("我直接补充", f"我直接补充我对{subject}范围的判断。", "保留自由输入，方便你直接讲边界。"),
        ],
        "done": [
            ("先确认共识", "我先确认一下你现在的理解是否准确。", "先确认共识，能减少后面返工。"),
            ("先补遗漏", "我想先补上还有疑问或没写清楚的地方。", "在定稿前补漏，比事后返修成本更低。"),
            ("继续下一步", "我想在这份 PRD 基础上继续拆 MVP 或技术方案。", "当主线清楚后，可以自然进入下一步。"),
            ("我直接补充", "我直接补充我还想调整的地方。", "保留自由输入，避免遗漏你的真实需求。"),
        ],
    }
    raw_options = options_by_focus.get(next_focus) or [
        ("先聊目标用户", f"我想先明确，{subject}主要给谁用。", "先锁定用户，后面的需求判断才不会发散。"),
        ("先聊核心问题", f"我想先讲清楚，{subject}到底想解决什么具体麻烦。", "问题越具体，PRD 越容易落地。"),
        ("先聊核心功能", f"我想先列一下，我脑子里已经想到的{subject}核心功能。", "把核心能力说出来，有助于快速判断主线。"),
        ("我直接补充", f"我不想选项，我直接补充我现在对{subject}的想法。", "保留自由表达出口，避免选项限制你的思路。"),
    ]
    return [
        Suggestion(
            type="direction",
            label=label,
            content=content,
            rationale=rationale,
            priority=index + 1,
        )
        for index, (label, content, rationale) in enumerate(raw_options[:GUIDANCE_SUGGESTION_COUNT])
    ]


def _resolve_existing_guidance_focus(state: dict[str, Any]) -> str | None:
    for candidate in (
        state.get("current_phase"),
        state.get("stage_hint"),
    ):
        if candidate in ALLOWED_NEXT_FOCUS:
            return candidate
    return None


def _infer_phase_subfocus(focus: str) -> str | None:
    phase_subfocus_map = {
        "target_user": "target_user.segment",
        "problem": "problem.frequency",
        "solution": "solution.core_loop",
        "mvp_scope": "mvp_scope.must_have",
    }
    return phase_subfocus_map.get(focus)


def _focus_dimension_from_focus(focus: str | None) -> str:
    focus_map = {
        "target_user": "target_user",
        "problem": "problem",
        "solution": "solution",
        "mvp_scope": "boundary",
        "done": "validation",
        "greeting": "target_user",
        "completed": "validation",
        "finalize": "validation",
        "error": "constraint",
    }
    return focus_map.get(focus or "", "problem")


def _build_option_card_id(focus_dimension: str, index: int, label: str) -> str:
    compact = re.sub(r"\s+", "-", label.strip().lower())
    compact = re.sub(r"[^a-z0-9\u4e00-\u9fff-]+", "", compact).strip("-")
    suffix = compact or f"option-{index + 1}"
    return f"{focus_dimension}-{index + 1}-{suffix}"


def _build_option_cards(
    suggestions: list[Suggestion],
    *,
    focus_dimension: str,
) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    for index, item in enumerate(suggestions[:GUIDANCE_SUGGESTION_COUNT]):
        cards.append(
            {
                "id": _build_option_card_id(focus_dimension, index, item.label),
                "label": item.label,
                "title": item.label,
                "content": item.content,
                "description": item.rationale,
                "type": item.type,
                "priority": item.priority,
            }
        )
    return cards


def _available_mode_switches(guidance_mode: str, response_mode: str) -> list[dict[str, str]]:
    switches: list[dict[str, str]] = []
    if response_mode != "options_first":
        switches.append({"mode": "options_first", "label": "改成先给选项"})
    if guidance_mode != "confirm":
        switches.append({"mode": "confirm", "label": "直接进入确认"})
    switches.append({"mode": "freeform", "label": "直接自由补充"})
    return switches


def _is_high_uncertainty_input(user_input: str) -> bool:
    normalized = user_input.strip().lower()
    if not normalized:
        return False
    markers = (
        "不确定",
        "不知道",
        "没想好",
        "不清楚",
        "哪个",
        "怎么选",
        "先解决",
        "先做哪个",
        "值得先",
        "方向",
    )
    return any(marker in normalized for marker in markers)


def _resolve_guidance_contract(
    *,
    focus: str | None,
    conversation_strategy: str,
    strategy_reason: str | None,
    suggestions: list[Suggestion],
    user_input: str | None = None,
    force_options_first: bool = False,
    force_trigger: str | None = None,
    force_reason: str | None = None,
) -> dict[str, Any]:
    focus_dimension = _focus_dimension_from_focus(focus)
    guidance_mode = {
        "greet": "explore",
        "clarify": "explore",
        "choose": "compare",
        "converge": "narrow",
        "confirm": "confirm",
    }.get(conversation_strategy, "explore")
    guidance_step = {
        "greet": "choose",
        "clarify": "answer",
        "choose": "compare",
        "converge": "answer",
        "confirm": "confirm",
    }.get(conversation_strategy, "answer")
    response_mode = "confirm_reply" if conversation_strategy == "confirm" else "direct_answer"
    transition_trigger = force_trigger
    transition_reason = force_reason or strategy_reason or "继续沿当前维度把信息压实。"

    high_uncertainty = force_options_first or (
        user_input is not None and len(suggestions) >= 2 and _is_high_uncertainty_input(user_input)
    )
    if high_uncertainty:
        response_mode = "options_first"
        guidance_mode = "explore"
        guidance_step = "choose"
        transition_trigger = transition_trigger or "high_uncertainty"
        transition_reason = force_reason or strategy_reason or "当前信息还不够确定，先给你几个方向做选择更有效。"

    option_cards = _build_option_cards(suggestions, focus_dimension=focus_dimension) if response_mode == "options_first" else []
    freeform_affordance = dict(_FREEFORM_AFFORDANCE) if response_mode == "options_first" else None
    return {
        "response_mode": response_mode,
        "guidance_mode": guidance_mode,
        "guidance_step": guidance_step,
        "focus_dimension": focus_dimension,
        "transition_reason": transition_reason,
        "transition_trigger": transition_trigger,
        "option_cards": option_cards,
        "freeform_affordance": freeform_affordance,
        "can_switch_mode": True,
        "available_mode_switches": _available_mode_switches(guidance_mode, response_mode),
    }


def _generic_suggestion_conflicts(focus: str) -> set[str]:
    conflict_labels_by_focus = {
        "target_user": {"先聊核心问题", "先聊核心功能"},
        "problem": {"先聊目标用户", "先聊核心功能"},
        "solution": {"先聊目标用户", "先聊核心问题"},
        "mvp_scope": {"先聊目标用户", "先聊核心问题"},
    }
    return conflict_labels_by_focus.get(focus, set())


def _should_replace_with_phase_specific_suggestions(
    suggestions: list[Suggestion],
    *,
    focus: str,
) -> bool:
    generic_labels = {"先聊目标用户", "先聊核心问题", "先聊核心功能", "我直接补充"}
    labels = {item.label for item in suggestions}
    conflict_labels = _generic_suggestion_conflicts(focus)
    if not conflict_labels:
        return False
    return bool(labels & generic_labels) and bool(labels & conflict_labels)


def _phase_specific_bucket(content: str, focus: str) -> str:
    normalized = content.strip()
    if focus == "solution":
        if "差异" in normalized or "不同" in normalized:
            return "differentiation"
        if "流程" in normalized or "路径" in normalized or "一步" in normalized:
            return "flow"
        if "直接补充" in normalized:
            return "freeform"
        return "mainline"
    if focus == "mvp_scope":
        if "不做" in normalized or "不要做" in normalized or "边界" in normalized:
            return "boundary"
        if "完成标准" in normalized or "可用" in normalized:
            return "success_bar"
        if "直接补充" in normalized:
            return "freeform"
        return "must_have"
    return "generic"


def _has_phase_specific_diversity(
    suggestions: list[Suggestion],
    *,
    focus: str,
) -> bool:
    if focus not in {"solution", "mvp_scope"}:
        return True
    buckets = {_phase_specific_bucket(item.content, focus) for item in suggestions}
    return len(buckets) >= 3


def _should_force_phase_specific_fallback(
    suggestions: list[Suggestion],
    *,
    focus: str | None,
) -> bool:
    if focus is None:
        return False
    if _should_replace_with_phase_specific_suggestions(suggestions, focus=focus):
        return True
    return not _has_phase_specific_diversity(suggestions, focus=focus)


def _call_pm_mentor_once(
    model_config: Any,
    *,
    system_prompt: str,
    user_prompt: str,
) -> dict[str, Any]:
    return call_pm_mentor_llm(
        base_url=model_config.base_url,
        api_key=model_config.api_key,
        model=model_config.model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
    )


def _is_low_information_input(user_input: str) -> bool:
    """检测用户输入是否信息量很低。"""
    normalized = user_input.strip().lower()
    if not normalized:
        return True
    if len(normalized) <= 8:
        return normalized in {"想法", "产品", "项目", "不知道", "没想好", "不清楚", "随便聊聊"}
    markers = (
        "不知道怎么说",
        "没想清楚",
        "还没想好",
        "不太清楚",
        "有个想法",
        "模糊方向",
        "想做个产品",
        "想创业",
    )
    return any(marker in normalized for marker in markers)


def _has_concrete_idea_but_incomplete(user_input: str, state: dict[str, Any]) -> bool:
    """检测用户是否已有具体想法但细节不完整。"""
    normalized = user_input.strip().lower()
    concrete_markers = (
        "我想", "我要", "我打算", "我计划", "我的想法是",
        "我想做", "我想开发", "我想创建", "我想建立",
    )
    has_concrete = any(marker in normalized for marker in concrete_markers)
    if not has_concrete:
        return False

    sections = state.get("prd_snapshot", {}).get("sections", {})
    confirmed_count = sum(
        1 for v in sections.values()
        if isinstance(v, dict) and v.get("status") == "confirmed"
    )
    missing_count = sum(
        1 for v in sections.values()
        if isinstance(v, dict) and v.get("status") == "missing"
    )
    return confirmed_count >= 1 and missing_count >= 1


def _has_contradictory_info(user_input: str, state: dict[str, Any]) -> bool:
    """检测用户是否提出了矛盾信息。"""
    normalized = user_input.strip().lower()
    contradiction_markers = (
        "但是", "不过", "其实", "等等", "我改主意了",
        "我想改", "我觉得不对", "我重新想想", "我改变主意",
        "矛盾", "冲突", "不一致",
    )
    has_contradiction_signal = any(marker in normalized for marker in contradiction_markers)
    if not has_contradiction_signal:
        return False

    sections = state.get("prd_snapshot", {}).get("sections", {})
    draft_count = sum(
        1 for v in sections.values()
        if isinstance(v, dict) and v.get("status") == "draft"
    )
    return draft_count >= 2


def _wants_quick_confirmation(user_input: str) -> bool:
    """检测用户是否想要快速确认。"""
    normalized = user_input.strip().lower()
    confirmation_markers = (
        "确认", "就这样", "就这个", "没问题", "可以了",
        "差不多了", "差不多就这样", "就这样吧", "我觉得可以",
        "我同意", "我赞成", "我认可", "我确认",
    )
    return any(marker in normalized for marker in confirmation_markers)


def _wants_deep_dive(user_input: str, next_focus: str) -> bool:
    """检测用户是否想要深度讨论某个维度。"""
    normalized = user_input.strip().lower()
    deep_dive_markers = (
        "详细", "深入", "展开", "具体", "细节",
        "再说说", "多说点", "讲讲", "说说",
        "怎么", "如何", "为什么", "什么意思",
    )
    has_deep_dive_signal = any(marker in normalized for marker in deep_dive_markers)
    return has_deep_dive_signal and next_focus in ALLOWED_NEXT_FOCUS


def _is_jumping_around(user_input: str, state: dict[str, Any]) -> bool:
    """检测用户是否在跳跃式思维（跳过当前阶段）。"""
    normalized = user_input.strip().lower()
    jump_markers = (
        "方案", "解决方案", "怎么做", "怎么实现",
        "技术", "技术栈", "开发", "实现",
        "价格", "收费", "商业模式", "盈利",
    )
    has_jump_signal = any(marker in normalized for marker in jump_markers)
    if not has_jump_signal:
        return False

    sections = state.get("prd_snapshot", {}).get("sections", {})
    missing_count = sum(
        1 for v in sections.values()
        if isinstance(v, dict) and v.get("status") == "missing"
    )
    return missing_count >= 2


def _normalize_text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _get_section_text(state: dict[str, Any], key: str) -> str:
    sections = state.get("prd_snapshot", {}).get("sections", {})
    section = sections.get(key)
    if not isinstance(section, dict):
        return ""
    return _normalize_text(section.get("content"))


def _make_diagnostic_id(diagnostic_type: str, impact_scope: list[str], title: str) -> str:
    scope = "-".join(sorted(impact_scope))
    compact = re.sub(r"\s+", "-", title.strip().lower())
    compact = re.sub(r"[^a-z0-9\u4e00-\u9fff-]+", "", compact).strip("-")
    return f"{diagnostic_type}-{scope or 'general'}-{compact or 'item'}"


def _build_diagnostic_item(
    *,
    diagnostic_type: str,
    bucket: str,
    title: str,
    detail: str,
    impact_scope: list[str],
    prompt: str,
    label: str,
    confidence: str = "medium",
    status: str = "open",
) -> dict[str, Any]:
    return {
        "id": _make_diagnostic_id(diagnostic_type, impact_scope, title),
        "type": diagnostic_type,
        "bucket": bucket,
        "status": status,
        "title": title,
        "detail": detail,
        "impact_scope": impact_scope,
        "suggested_next_step": {
            "action_kind": "ask_user",
            "label": label,
            "prompt": prompt,
        },
        "confidence": confidence,
    }


def _collect_contradiction_diagnostics(user_input: str, state: dict[str, Any]) -> list[dict[str, Any]]:
    normalized = user_input.strip().lower()
    exploratory_markers = ("也可能", "还没想清楚", "不太确定", "可能是", "先探索")
    if any(marker in normalized for marker in exploratory_markers):
        return []
    diagnostics: list[dict[str, Any]] = []
    contradiction_specs = [
        ("target_user", ("面向小团队", "小团队负责人", "团队负责人", "不是独立开发者", "改成团队")),
        ("problem", ("其实不是", "不是任务跟进", "改成", "重新定义问题")),
        ("solution", ("不是这个方案", "改方案", "重新做法", "换个解决方式")),
        ("mvp_scope", ("不做这个", "先不做", "范围改成", "mvp 改成")),
    ]
    for scope, markers in contradiction_specs:
        existing = _get_section_text(state, scope)
        if not existing:
            continue
        if any(marker in normalized for marker in markers):
            diagnostics.append(
                _build_diagnostic_item(
                    diagnostic_type="contradiction",
                    bucket="to_validate",
                    title=f"{scope} 主线冲突",
                    detail=f"当前输入看起来在改写已存在的 {scope} 判断：{existing}",
                    impact_scope=[scope],
                    prompt=f"如果现在只能保留一个 {scope} 主线，你想改成什么？",
                    label=f"先确认 {scope}",
                    confidence="high",
                )
            )
    return diagnostics


def _collect_gap_diagnostics(state: dict[str, Any]) -> list[dict[str, Any]]:
    gap_specs = [
        ("target_user", "目标用户缺失", "还没有说清楚第一版最想服务谁。", "如果只能先服务一类人，第一版最该服务谁？"),
        ("problem", "核心问题缺失", "还没有说清楚用户最痛的那个问题。", "如果只能先解决一个问题，最高频最痛的是哪个？"),
        ("solution", "方案主线缺失", "还没有说清楚第一版如何解决这个问题。", "如果只保留一个核心动作，第一版到底怎么解决这个问题？"),
        ("mvp_scope", "验证标准缺失", "还没有明确第一版做到什么程度才算可验证。", "做到什么结果时，你会认为第一版已经值得继续做？"),
    ]
    diagnostics: list[dict[str, Any]] = []
    for scope, title, detail, prompt in gap_specs:
        existing = _get_section_text(state, scope)
        if existing:
            continue
        bucket = "unknown" if scope != "mvp_scope" else "to_validate"
        diagnostics.append(
            _build_diagnostic_item(
                diagnostic_type="gap",
                bucket=bucket,
                title=title,
                detail=detail,
                impact_scope=[scope],
                prompt=prompt,
                label=f"先补 {scope}",
            )
        )
    return diagnostics


def _collect_assumption_diagnostics(user_input: str) -> list[dict[str, Any]]:
    normalized = user_input.strip().lower()
    diagnostics: list[dict[str, Any]] = []
    if "默认" in normalized or "先做 web" in normalized or "web 端" in normalized:
        diagnostics.append(
            _build_diagnostic_item(
                diagnostic_type="assumption",
                bucket="risk",
                title="默认先做 Web 端",
                detail="当前推进默认第一版只做 Web 端，但用户还没有明确确认。",
                impact_scope=["solution", "mvp_scope"],
                prompt="你是不是已经明确决定第一版只做 Web 端？",
                label="确认首发载体",
            )
        )
    if "独立开发者" in normalized and ("默认" in normalized or "先面向" in normalized):
        diagnostics.append(
            _build_diagnostic_item(
                diagnostic_type="assumption",
                bucket="risk",
                title="默认先服务独立开发者",
                detail="当前推进把独立开发者当成默认主线，但用户还没有正式确认。",
                impact_scope=["target_user"],
                prompt="你现在是不是已经决定第一版先服务独立开发者？",
                label="确认目标用户主线",
            )
        )
    return diagnostics


def _collect_diagnostic_items(
    *,
    state: dict[str, Any],
    user_input: str,
) -> list[dict[str, Any]]:
    collected = (
        _collect_contradiction_diagnostics(user_input, state)
        + _collect_gap_diagnostics(state)
        + _collect_assumption_diagnostics(user_input)
    )
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in collected:
        item_id = item["id"]
        if item_id in seen:
            continue
        seen.add(item_id)
        deduped.append(item)
    return deduped


def _summarize_diagnostics(diagnostics: list[dict[str, Any]]) -> dict[str, int]:
    summary = {
        "open_count": 0,
        "unknown_count": 0,
        "risk_count": 0,
        "to_validate_count": 0,
    }
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


def _normalize_text_id(value: str) -> str:
    compact = re.sub(r"\s+", "-", value.strip().lower())
    compact = re.sub(r"[^a-z0-9\u4e00-\u9fff-]+", "", compact)
    return compact.strip("-") or "item"


def _map_status_to_assertion_state(status: str, *, content: str) -> str:
    if status == "confirmed":
        return "confirmed"
    if status == "missing" and content.strip():
        return "to_validate"
    return "inferred"


def _derive_section_completeness(entries: list[dict[str, Any]]) -> str:
    if not entries:
        return "missing"
    if all(entry.get("assertion_state") == "confirmed" for entry in entries):
        return "complete"
    return "partial"


def _build_structured_prd_state(
    *,
    prd_updates: dict[str, dict[str, Any]],
    user_input: str,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, list[str]]]:
    sections: dict[str, dict[str, Any]] = {}
    evidence_registry: list[dict[str, Any]] = []
    section_keys: list[str] = []
    entry_ids: list[str] = []
    evidence_ids: list[str] = []

    for section_key, payload in prd_updates.items():
        if section_key not in ALLOWED_PRD_SECTION_KEYS:
            continue
        if not isinstance(payload, dict):
            continue
        content = str(payload.get("content") or "").strip()
        if not content:
            continue
        status = str(payload.get("status") or "draft")
        assertion_state = _map_status_to_assertion_state(status, content=content)
        entry_id = f"entry-{section_key}-{_normalize_text_id(content)}"
        evidence_kind = "user_message" if assertion_state == "confirmed" else "system_inference"
        evidence_id = f"evidence-{section_key}-{evidence_kind}-{_normalize_text_id(content)}"
        evidence_registry.append(
            {
                "id": evidence_id,
                "kind": evidence_kind,
                "excerpt": user_input.strip() if assertion_state == "confirmed" else content,
                "section_keys": [section_key],
            }
        )
        entry = {
            "id": entry_id,
            "text": content,
            "assertion_state": assertion_state,
            "evidence_ref_ids": [evidence_id],
            "derived_from_diagnostics": [],
        }
        sections[section_key] = {
            "title": SECTION_TITLES.get(section_key, section_key),
            "entries": [entry],
            "completeness": _derive_section_completeness([entry]),
            "summary": content,
        }
        section_keys.append(section_key)
        entry_ids.append(entry_id)
        evidence_ids.append(evidence_id)

    return (
        {
            "version": 1,
            "status": "drafting",
            "sections": sections,
            "summary": {
                "section_keys": section_keys,
                "entry_ids": entry_ids,
                "evidence_ids": evidence_ids,
            },
        },
        evidence_registry,
        {
            "section_keys": section_keys,
            "entry_ids": entry_ids,
            "evidence_ids": evidence_ids,
        },
    )


def parse_pm_mentor_output(raw: dict[str, Any]) -> PmMentorOutput:
    observation = raw.get("observation") or ""
    challenge = raw.get("challenge") or ""
    suggestion = raw.get("suggestion") or ""
    question = raw.get("question") or ""

    raw_next_focus = raw.get("next_focus") or "problem"
    next_focus = raw_next_focus if raw_next_focus in ALLOWED_NEXT_FOCUS else "problem"

    confidence_raw = raw.get("confidence") or "medium"
    confidence = confidence_raw if confidence_raw in {"high", "medium", "low"} else "medium"
    next_move_raw = raw.get("next_move")
    next_move = next_move_raw if next_move_raw in ALLOWED_NEXT_MOVES else None

    prd_updates = _validate_prd_updates(raw.get("prd_updates"))
    raw_suggestions = raw.get("suggestions")
    raw_suggestion_count = _get_raw_suggestion_count(raw_suggestions)
    suggestions = _normalize_suggestions(raw_suggestions)
    recommendation = _normalize_recommendation(raw.get("recommendation"), suggestions)

    reply = raw.get("reply") or ""
    if not reply.strip():
        parts = [p for p in [observation, challenge, suggestion, question] if p.strip()]
        reply = "\n\n".join(parts) or "我需要更多信息才能继续推进。"

    return PmMentorOutput(
        observation=observation,
        challenge=challenge,
        suggestion=suggestion,
        question=question,
        reply=reply,
        prd_updates=prd_updates,
        confidence=confidence,
        next_focus=next_focus,
        raw_suggestion_count=raw_suggestion_count,
        suggestions=suggestions,
        recommendation=recommendation,
        next_move=next_move,
    )


def run_pm_mentor(
    state: dict[str, Any],
    user_input: str,
    model_config: Any,
    *,
    conversation_history: list[dict[str, str]] | None = None,
) -> AgentResult:
    """调用 LLM PM Mentor，返回 AgentResult（reply_mode="local"）。"""
    user_prompt = _build_user_prompt(state, user_input, conversation_history)

    raw: dict[str, Any] = {}
    try:
        raw = _call_pm_mentor_once(
            model_config,
            system_prompt=PM_MENTOR_SYSTEM_PROMPT,
            user_prompt=user_prompt,
        )
    except ModelGatewayError:
        logger.warning("PM Mentor LLM 调用失败，使用降级回复")

    mentor_output = parse_pm_mentor_output(raw)
    raw_contract_invalid = not _has_valid_raw_suggestion_contract(mentor_output)
    if raw_contract_invalid:
        repair_prompt = _build_repair_prompt(state, user_input, mentor_output, conversation_history)
        repair_raw: dict[str, Any] = {}
        try:
            repair_raw = _call_pm_mentor_once(
                model_config,
                system_prompt=PM_MENTOR_REPAIR_SYSTEM_PROMPT,
                user_prompt=repair_prompt,
            )
        except ModelGatewayError:
            logger.warning("PM Mentor suggestions 补救生成失败，转入程序化兜底")

        repaired_suggestions = _normalize_suggestions(repair_raw.get("suggestions"))
        repaired_count = _get_raw_suggestion_count(repair_raw.get("suggestions"))
        if repaired_count == GUIDANCE_SUGGESTION_COUNT and _has_mandatory_suggestions(repaired_suggestions):
            mentor_output.suggestions = repaired_suggestions
            mentor_output.recommendation = _normalize_recommendation(
                repair_raw.get("recommendation"),
                repaired_suggestions,
            )
            mentor_output.raw_suggestion_count = repaired_count

    prd_patch = mentor_output.prd_updates
    suggestions = mentor_output.suggestions
    if raw_contract_invalid:
        suggestions = _merge_with_programmatic_fallback(
            suggestions,
            user_input=user_input,
            next_focus=mentor_output.next_focus,
        )
    existing_focus = _resolve_existing_guidance_focus(state)
    if _should_force_phase_specific_fallback(suggestions, focus=existing_focus):
        suggestions = _build_fallback_suggestions(
            user_input,
            existing_focus,
        )
    guidance_focus = existing_focus or mentor_output.next_focus
    recommendation = _normalize_recommendation(mentor_output.recommendation, suggestions)
    next_best_questions = [item.content for item in suggestions]
    phase_subfocus = _infer_phase_subfocus(guidance_focus)

    conversation_strategy = _infer_conversation_strategy(
        mentor_output.confidence, mentor_output.next_focus, state
    )
    next_move = mentor_output.next_move or {
        "confirm": "summarize_and_confirm",
        "converge": "assume_and_advance",
    }.get(conversation_strategy, "probe_for_specificity")

    state_patch: dict[str, Any] = {
        "iteration": int(state.get("iteration") or 0) + 1,
        "stage_hint": mentor_output.next_focus,
        "current_phase_subfocus": phase_subfocus,
        "conversation_strategy": conversation_strategy,
        "next_best_questions": next_best_questions,
    }
    structured_prd_draft, evidence_registry, draft_summary = _build_structured_prd_state(
        prd_updates=prd_patch,
        user_input=user_input,
    )
    guidance_contract = _resolve_guidance_contract(
        focus=guidance_focus,
        conversation_strategy=conversation_strategy,
        strategy_reason=mentor_output.suggestion or None,
        suggestions=suggestions,
        user_input=user_input,
        force_options_first=raw_contract_invalid,
        force_trigger="high_uncertainty" if raw_contract_invalid else None,
        force_reason=(
            "当前还缺少足够明确的方向判断，先给你几个可反应选项，再继续收敛。"
            if raw_contract_invalid else None
        ),
    )
    diagnostics = _collect_diagnostic_items(state=state, user_input=user_input)
    diagnostic_summary = _summarize_diagnostics(diagnostics)
    assumption_items = [item for item in diagnostics if item["type"] == "assumption"]
    gap_items = [item for item in diagnostics if item["type"] == "gap"]
    contradiction_items = [item for item in diagnostics if item["type"] == "contradiction"]
    state_patch.update(guidance_contract)
    state_patch["diagnostics"] = diagnostics
    state_patch["diagnostic_summary"] = diagnostic_summary
    state_patch["prd_draft"] = structured_prd_draft
    state_patch["evidence"] = evidence_registry
    state_patch["open_questions"] = [
        item["suggested_next_step"]["prompt"]
        for item in diagnostics
        if isinstance(item.get("suggested_next_step"), dict)
    ]

    turn_decision = TurnDecision(
        phase=mentor_output.next_focus,
        phase_goal=mentor_output.question or None,
        understanding={
            "summary": mentor_output.observation,
            "candidate_updates": prd_patch,
            "ambiguous_points": [],
        },
        assumptions=[
            {"id": item["id"], "title": item["title"]}
            for item in assumption_items
        ],
        gaps=[str(item["title"]) for item in gap_items],
        challenges=(
            [mentor_output.challenge] if mentor_output.challenge else []
        ) + [str(item["title"]) for item in contradiction_items[:1]],
        pm_risk_flags=[str(item["title"]) for item in diagnostics if item.get("bucket") == "risk"],
        next_move=next_move,
        suggestions=suggestions,
        recommendation=recommendation,
        reply_brief={"focus": mentor_output.next_focus, "must_include": []},
        state_patch=state_patch,
        prd_patch=prd_patch,
        needs_confirmation=[],
        confidence=mentor_output.confidence,
        strategy_reason=mentor_output.suggestion or None,
        next_best_questions=next_best_questions,
        conversation_strategy=conversation_strategy,
        phase_subfocus=phase_subfocus,
        response_mode=guidance_contract["response_mode"],
        guidance_mode=guidance_contract["guidance_mode"],
        guidance_step=guidance_contract["guidance_step"],
        focus_dimension=guidance_contract["focus_dimension"],
        transition_reason=guidance_contract["transition_reason"],
        transition_trigger=guidance_contract["transition_trigger"],
        option_cards=guidance_contract["option_cards"],
        freeform_affordance=guidance_contract["freeform_affordance"],
        can_switch_mode=guidance_contract["can_switch_mode"],
        available_mode_switches=guidance_contract["available_mode_switches"],
        diagnostics=diagnostics,
        diagnostic_summary=diagnostic_summary,
        draft_summary=draft_summary,
    )

    return AgentResult(
        reply=mentor_output.reply,
        action=NextAction(
            action="probe_deeper",
            target=None,
            reason=mentor_output.question or "继续推进 PRD 补充",
            observation=mentor_output.observation,
            challenge=mentor_output.challenge,
            suggestion=mentor_output.suggestion,
            question=mentor_output.question,
        ),
        reply_mode="local",
        state_patch=state_patch,
        prd_patch=prd_patch,
        decision_log=[],
        understanding=None,
        turn_decision=turn_decision,
    )
