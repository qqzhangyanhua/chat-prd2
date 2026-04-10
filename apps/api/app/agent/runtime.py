from __future__ import annotations

from typing import Any

from app.agent.types import AgentResult, NextAction, TurnDecision


def _build_completed_result(state: dict[str, Any]) -> AgentResult:
    turn_decision = TurnDecision(
        phase="completed",
        phase_goal=None,
        understanding={
            "summary": "PRD 已完成，可以导出或继续修改。",
            "candidate_updates": {},
            "ambiguous_points": [],
        },
        assumptions=[],
        gaps=[],
        challenges=[],
        pm_risk_flags=[],
        next_move="summarize_and_confirm",
        suggestions=[],
        recommendation=None,
        reply_brief={"focus": "completed", "must_include": []},
        state_patch={},
        prd_patch={},
        needs_confirmation=[],
        confidence="high",
        strategy_reason=None,
        next_best_questions=[],
        conversation_strategy="confirm",
    )
    return AgentResult(
        reply="PRD 已完成。你可以导出 PRD，或者继续告诉我需要修改的地方。",
        action=NextAction(action="summarize_understanding", target=None, reason="PRD 已完成"),
        reply_mode="local",
        state_patch={},
        prd_patch={},
        decision_log=[],
        understanding=None,
        turn_decision=turn_decision,
    )


def _build_fallback_result(state: dict[str, Any], user_input: str) -> AgentResult:
    turn_decision = TurnDecision(
        phase="error",
        phase_goal=None,
        understanding={
            "summary": "模型配置不可用，使用降级回复。",
            "candidate_updates": {},
            "ambiguous_points": [],
        },
        assumptions=[],
        gaps=[],
        challenges=[],
        pm_risk_flags=[],
        next_move="probe_for_specificity",
        suggestions=[],
        recommendation=None,
        reply_brief={"focus": "fallback", "must_include": []},
        state_patch={},
        prd_patch={},
        needs_confirmation=[],
        confidence="low",
        strategy_reason=None,
        next_best_questions=[],
        conversation_strategy="clarify",
    )
    return AgentResult(
        reply="我现在暂时无法访问模型，请稍后重试或检查模型配置。",
        action=NextAction(action="probe_deeper", target=None, reason="模型不可用"),
        reply_mode="local",
        state_patch={},
        prd_patch={},
        decision_log=[],
        understanding=None,
        turn_decision=turn_decision,
    )


def decide_next_action(state: dict[str, Any], user_input: str) -> NextAction:
    """Deprecated stub kept for import compatibility. Will be removed in Task 7."""
    return NextAction(action="probe_deeper", target=None, reason="deprecated")


def run_agent(
    state: dict[str, Any],
    user_input: str,
    model_result: Any = None,
    *,
    model_config: Any = None,
    conversation_history: list[dict[str, str]] | None = None,
) -> AgentResult:
    """Agent 主入口（瘦编排层）。

    处理三个边界条件，其余全部交给 PM Mentor LLM：
    1. workflow_stage == "completed" → 返回完成回复
    2. model_config is None → 降级本地回复
    3. 其余 → run_pm_mentor
    """
    if state.get("workflow_stage") == "completed":
        return _build_completed_result(state)

    if model_config is None:
        return _build_fallback_result(state, user_input)

    from app.agent.pm_mentor import run_pm_mentor
    return run_pm_mentor(
        state,
        user_input,
        model_config,
        conversation_history=conversation_history,
    )
