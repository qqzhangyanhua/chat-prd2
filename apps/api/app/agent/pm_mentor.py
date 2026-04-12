from __future__ import annotations

import json
import logging
from typing import Any

from app.agent.types import AgentResult, NextAction, PmMentorOutput, TurnDecision
from app.services.model_gateway import ModelGatewayError, call_pm_mentor_llm

logger = logging.getLogger(__name__)

MAX_HISTORY_TURNS = 10

ALLOWED_NEXT_FOCUS = {"target_user", "problem", "solution", "mvp_scope", "done"}
ALLOWED_STATUS = {"missing", "draft", "confirmed"}
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

PM_MENTOR_SYSTEM_PROMPT = """你是一位经验丰富的 AI 产品联合创始人（PM 导师风格）。
你的职责是帮助用户把一个模糊的想法，逐步打磨成一份清晰可执行的 PRD。

【你的工作方式】
每轮对话，你必须做四件事：
1. Observation  — 指出用户本轮输入中最关键的信息或隐含假设
2. Challenge    — 挑战一个具体的假设或盲点（不能泛泛追问）
3. Suggestion   — 给出一个具体的 PM 视角建议或框架
4. Question     — 只问一个最关键的问题，推动对话向前

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

【输出格式】
严格返回 JSON，包含以下字段：
observation, challenge, suggestion, question, reply, prd_updates, confidence, next_focus"""


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


def parse_pm_mentor_output(raw: dict[str, Any]) -> PmMentorOutput:
    observation = raw.get("observation") or ""
    challenge = raw.get("challenge") or ""
    suggestion = raw.get("suggestion") or ""
    question = raw.get("question") or ""

    raw_next_focus = raw.get("next_focus") or "problem"
    next_focus = raw_next_focus if raw_next_focus in ALLOWED_NEXT_FOCUS else "problem"

    confidence_raw = raw.get("confidence") or "medium"
    confidence = confidence_raw if confidence_raw in {"high", "medium", "low"} else "medium"

    prd_updates = _validate_prd_updates(raw.get("prd_updates"))

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
        raw = call_pm_mentor_llm(
            base_url=model_config.base_url,
            api_key=model_config.api_key,
            model=model_config.model,
            system_prompt=PM_MENTOR_SYSTEM_PROMPT,
            user_prompt=user_prompt,
        )
    except ModelGatewayError:
        logger.warning("PM Mentor LLM 调用失败，使用降级回复")

    mentor_output = parse_pm_mentor_output(raw)

    prd_patch = mentor_output.prd_updates

    conversation_strategy = _infer_conversation_strategy(
        mentor_output.confidence, mentor_output.next_focus, state
    )
    next_move = {
        "confirm": "summarize_and_confirm",
        "converge": "assume_and_advance",
    }.get(conversation_strategy, "probe_for_specificity")

    state_patch: dict[str, Any] = {
        "iteration": int(state.get("iteration") or 0) + 1,
        "stage_hint": mentor_output.next_focus,
        "conversation_strategy": conversation_strategy,
    }
    if mentor_output.next_focus == "done":
        state_patch["workflow_stage"] = "completed"

    turn_decision = TurnDecision(
        phase=mentor_output.next_focus,
        phase_goal=mentor_output.question or None,
        understanding={
            "summary": mentor_output.observation,
            "candidate_updates": prd_patch,
            "ambiguous_points": [],
        },
        assumptions=[],
        gaps=[],
        challenges=[mentor_output.challenge] if mentor_output.challenge else [],
        pm_risk_flags=[],
        next_move=next_move,
        suggestions=[],
        recommendation=None,
        reply_brief={"focus": mentor_output.next_focus, "must_include": []},
        state_patch=state_patch,
        prd_patch=prd_patch,
        needs_confirmation=[],
        confidence=mentor_output.confidence,
        strategy_reason=mentor_output.suggestion or None,
        next_best_questions=[mentor_output.question] if mentor_output.question else [],
        conversation_strategy=conversation_strategy,
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
