from __future__ import annotations

from copy import deepcopy

from app.agent.decision_engine import build_turn_decision
from app.agent.extractor import (
    StructuredExtractionResult,
    build_rule_extraction_result,
    choose_extraction_result,
    first_missing_section,
)
from app.agent.reply_composer import compose_reply
from app.agent.suggestion_planner import build_suggestions
from app.agent.types import AgentResult, NextAction
from app.agent.understanding import understand_user_input


def _apply_agent_patch(state: dict, state_patch: dict, prd_patch: dict) -> dict:
    next_state = deepcopy(state)
    next_state.update(state_patch)
    snapshot = next_state.setdefault("prd_snapshot", {})
    sections = snapshot.setdefault("sections", {})
    sections.update(prd_patch)
    return next_state


def decide_next_action(state: dict, _user_input: str) -> NextAction:
    missing_section = first_missing_section(state)
    if missing_section == "target_user":
        return NextAction(
            action="probe_deeper",
            target="target_user",
            reason="当前还不清楚目标用户是谁，需要继续追问",
        )
    if missing_section == "problem":
        return NextAction(
            action="probe_deeper",
            target="problem",
            reason="目标用户已经明确，下一步需要确认最值得优先解决的核心问题",
        )
    if missing_section == "solution":
        return NextAction(
            action="probe_deeper",
            target="solution",
            reason="核心问题已经明确，下一步需要压缩出最可行的解决方案方向",
        )
    if missing_section == "mvp_scope":
        return NextAction(
            action="probe_deeper",
            target="mvp_scope",
            reason="方案方向已经出现，下一步需要把首版 MVP 范围压缩到最小闭环",
        )

    return NextAction(
        action="summarize_understanding",
        target=None,
        reason="核心 PRD 骨架已经齐备，可以先总结当前理解并推动下一步决策",
    )


def run_agent(
    state: dict,
    user_input: str,
    model_result: StructuredExtractionResult | None = None,
) -> AgentResult:
    understanding = understand_user_input(state, user_input)

    rule_result = build_rule_extraction_result(state, user_input)
    extraction_result = choose_extraction_result(rule_result, model_result)

    state_patch = extraction_result.state_patch
    prd_patch = extraction_result.prd_patch
    decision_log = extraction_result.decision_log

    if not extraction_result.should_update and first_missing_section(state) is None:
        state_patch = {
            "iteration": int(state.get("iteration") or 0) + 1,
            "stage_hint": "总结共识",
        }

    next_state = _apply_agent_patch(state, state_patch, prd_patch) if state_patch or prd_patch else state
    action = decide_next_action(next_state, user_input)
    # Phase 1 仍保留旧 action 字段兼容链路，reply 改由 turn_decision 编排生成
    turn_decision = build_turn_decision(next_state, understanding, state_patch, prd_patch)
    suggestions, recommendation = build_suggestions(turn_decision)
    turn_decision.suggestions = suggestions
    turn_decision.recommendation = recommendation
    reply = compose_reply(turn_decision)
    return AgentResult(
        reply=reply,
        action=action,
        state_patch=state_patch,
        prd_patch=prd_patch,
        decision_log=decision_log,
        understanding=understanding,
        turn_decision=turn_decision,
    )
