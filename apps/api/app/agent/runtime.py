from __future__ import annotations

from copy import deepcopy

from app.agent.decision_engine import build_turn_decision
from app.agent.extractor import (
    StructuredExtractionResult,
    build_rule_extraction_result,
    choose_extraction_result,
    first_missing_section,
    normalize_text,
    should_capture,
)
from app.agent.reply_composer import compose_reply
from app.agent.suggestion_planner import build_suggestions
from app.agent.types import AgentResult, NextAction, Suggestion, TurnDecision
from app.agent.understanding import understand_user_input
from app.agent.types import UnderstandingResult
from app.agent.validation_flows import (
    CONFIRM_FOCUS_COMMANDS,
    VAGUE_VALIDATION_PHRASES,
    VALIDATION_FOLLOWUP_FLOWS,
    VALIDATION_SWITCH_COMMANDS,
    VALIDATION_VAGUE_REPLY_HINTS,
)

CORRECTION_COMMANDS = {
    "不对，先改目标用户": {
        "target": "target_user",
        "stage_hint": "重新校准目标用户",
        "state_patch": {
            "conversation_strategy": "clarify",
            "target_user": None,
            "problem": None,
            "solution": None,
            "mvp_scope": [],
            "pending_confirmations": [],
        },
        "prd_patch": {
            "target_user": {
                "title": "目标用户",
                "content": "已回滚，等待重新确认目标用户。",
                "status": "missing",
            },
            "problem": {
                "title": "核心问题",
                "content": "已回滚，等待目标用户重新明确后再重建问题判断。",
                "status": "missing",
            },
            "solution": {
                "title": "解决方案",
                "content": "已回滚，等待目标用户与问题重新确认后再收敛方案。",
                "status": "missing",
            },
            "mvp_scope": {
                "title": "MVP 范围",
                "content": "已回滚，等待上游共识重新确认后再压缩 MVP。",
                "status": "missing",
            },
        },
        "reply": "我先回滚当前关于目标用户及其后续共识，避免错误前提继续传导。请你重新告诉我最想服务的第一类用户是谁，尽量具体到角色、场景和触发时机。我会先重建目标用户判断，再据此重排核心问题、方案方向和 MVP。",
        "reason": "我先撤回当前目标用户及其后续判断，重新确认目标用户后再继续推进。",
        "understanding_summary": "用户否定了当前目标用户判断，要求回到目标用户重新校准。",
    },
    "不对，先改核心问题": {
        "target": "problem",
        "stage_hint": "重新校准核心问题",
        "state_patch": {
            "conversation_strategy": "clarify",
            "problem": None,
            "solution": None,
            "mvp_scope": [],
            "pending_confirmations": [],
        },
        "prd_patch": {
            "problem": {
                "title": "核心问题",
                "content": "已回滚，等待重新确认核心问题。",
                "status": "missing",
            },
            "solution": {
                "title": "解决方案",
                "content": "已回滚，等待核心问题重新明确后再收敛方案。",
                "status": "missing",
            },
            "mvp_scope": {
                "title": "MVP 范围",
                "content": "已回滚，等待问题与方案重新确认后再压缩 MVP。",
                "status": "missing",
            },
        },
        "reply": "我先回滚当前关于核心问题及其后续方案共识，避免在错误问题定义上继续推进。请你重新描述当前最值得优先解决的核心问题，尽量讲清触发场景、已有替代方案和真实损失。我会先重建问题判断，再据此重排方案方向和 MVP。",
        "reason": "我先撤回当前核心问题及其后续判断，重新确认问题后再继续推进。",
        "understanding_summary": "用户否定了当前核心问题判断，要求回到问题定义重新校准。",
    },
}



def _apply_agent_patch(state: dict, state_patch: dict, prd_patch: dict) -> dict:
    next_state = deepcopy(state)
    next_state.update(state_patch)
    snapshot = next_state.setdefault("prd_snapshot", {})
    sections = snapshot.setdefault("sections", {})
    sections.update(prd_patch)
    return next_state


def _confirmed_sections(state: dict) -> list[str]:
    items: list[str] = []
    if state.get("target_user"):
        items.append("目标用户")
    if state.get("problem"):
        items.append("核心问题")
    if state.get("solution"):
        items.append("解决方案")
    if state.get("mvp_scope"):
        items.append("MVP 范围")
    return items


def _build_validation_switch_result(state: dict, user_input: str) -> AgentResult | None:
    command = VALIDATION_SWITCH_COMMANDS.get(user_input.strip())
    if command is None:
        return None
    if state.get("conversation_strategy") != "converge":
        return None
    if state.get("validation_focus") != command["from_focus"]:
        return None

    target_flow = CONFIRM_FOCUS_COMMANDS[command["target_command"]]
    validation_focus = "frequency" if command["target_command"] == "确认，先看频率" else "conversion_resistance"
    state_patch = {
        "conversation_strategy": "converge",
        "validation_focus": validation_focus,
        "validation_step": 1,
        "iteration": int(state.get("iteration") or 0) + 1,
        "stage_hint": target_flow["stage_hint"],
        "pending_confirmations": [],
    }
    understanding = UnderstandingResult(
        summary="用户要求暂停当前验证主线，切换到另一条验证焦点。",
        candidate_updates={},
        assumption_candidates=[],
        ambiguous_points=[],
        risk_hints=[],
    )
    turn_decision = TurnDecision(
        phase="alignment_review",
        phase_goal=target_flow["phase_goal"],
        understanding={
            "summary": understanding.summary,
            "candidate_updates": {},
            "ambiguous_points": [],
        },
        assumptions=list(state.get("working_hypotheses") or []),
        gaps=[],
        challenges=[],
        pm_risk_flags=list(state.get("pm_risk_flags") or []),
        next_move="assume_and_advance",
        suggestions=[Suggestion(**item) for item in target_flow["suggestions"]],
        recommendation=dict(target_flow["recommendation"]),
        reply_brief={"focus": "assume_and_advance", "must_include": []},
        state_patch=state_patch,
        prd_patch={},
        needs_confirmation=[],
        confidence="medium",
        strategy_reason=f"当前主线已切到{target_flow['phase_goal']}。",
        next_best_questions=list(target_flow["next_best_questions"]),
        conversation_strategy="converge",
    )

    return AgentResult(
        reply=command["reply"],
        action=NextAction(
            action="summarize_understanding",
            target=None,
            reason=f"切换验证焦点到{target_flow['phase_goal']}。",
        ),
        reply_mode="local",
        state_patch=state_patch,
        prd_patch={},
        decision_log=[],
        understanding=understanding,
        turn_decision=turn_decision,
    )


def _is_vague_validation_reply(user_input: str) -> bool:
    normalized = normalize_text(user_input)
    if not normalized:
        return True
    return any(phrase in normalized for phrase in VAGUE_VALIDATION_PHRASES)


def _build_vague_validation_result(state: dict, user_input: str) -> AgentResult | None:
    if state.get("conversation_strategy") != "converge":
        return None
    if not _is_vague_validation_reply(user_input):
        return None

    validation_focus = state.get("validation_focus")
    validation_step = int(state.get("validation_step") or 0)
    hint = VALIDATION_VAGUE_REPLY_HINTS.get((validation_focus, validation_step))
    if hint is None:
        return None

    state_patch = {
        "conversation_strategy": "converge",
        "validation_focus": validation_focus,
        "validation_step": validation_step,
        "iteration": int(state.get("iteration") or 0) + 1,
        "stage_hint": hint["stage_hint"],
    }
    understanding = UnderstandingResult(
        summary="用户这轮回答过于模糊，当前不足以推进验证判断。",
        candidate_updates={},
        assumption_candidates=[],
        ambiguous_points=["用户这轮只给了模糊回答，缺少可执行细节。"],
        risk_hints=[],
    )
    turn_decision = TurnDecision(
        phase="alignment_review",
        phase_goal=hint["phase_goal"],
        understanding={
            "summary": understanding.summary,
            "candidate_updates": {},
            "ambiguous_points": understanding.ambiguous_points,
        },
        assumptions=list(state.get("working_hypotheses") or []),
        gaps=["缺少可判断的频率尺度"],
        challenges=[],
        pm_risk_flags=list(state.get("pm_risk_flags") or []),
        next_move="probe_for_specificity",
        suggestions=[Suggestion(**item) for item in hint["suggestions"]],
        recommendation=dict(hint["recommendation"]),
        reply_brief={"focus": "probe_for_specificity", "must_include": []},
        state_patch=state_patch,
        prd_patch={},
        needs_confirmation=[],
        confidence="medium",
        strategy_reason=hint["strategy_reason"],
        next_best_questions=list(hint["next_best_questions"]),
        conversation_strategy="converge",
    )
    reply = "".join(hint["reply_lines"]) + hint["next_best_questions"][0]

    return AgentResult(
        reply=reply,
        action=NextAction(
            action="probe_deeper",
            target=None,
            reason=hint["strategy_reason"],
        ),
        reply_mode="local",
        state_patch=state_patch,
        prd_patch={},
        decision_log=[],
        understanding=understanding,
        turn_decision=turn_decision,
    )


def _build_validation_followup_result(state: dict, user_input: str) -> AgentResult | None:
    if state.get("conversation_strategy") != "converge":
        return None

    validation_focus = state.get("validation_focus")
    validation_step = int(state.get("validation_step") or 0)
    flow = VALIDATION_FOLLOWUP_FLOWS.get((validation_focus, validation_step))
    if flow is None or not should_capture(user_input):
        return None

    normalized_input = normalize_text(user_input)
    evidence = list(state.get("evidence") or [])
    evidence.append(f"{flow['evidence_prefix']}：{normalized_input}")
    next_best_questions = list(flow["next_best_questions"])
    conversation_strategy = flow.get("conversation_strategy", "converge")
    pending_confirmations = list(flow.get("pending_confirmations", []))
    next_move = flow.get("next_move", "assume_and_advance")
    state_patch = {
        "conversation_strategy": conversation_strategy,
        "validation_focus": validation_focus,
        "validation_step": validation_step + 1,
        "iteration": int(state.get("iteration") or 0) + 1,
        "stage_hint": flow["stage_hint"],
        "evidence": evidence,
        "pending_confirmations": pending_confirmations,
    }
    understanding = UnderstandingResult(
        summary=f"{flow['summary_prefix']}{normalized_input}",
        candidate_updates={},
        assumption_candidates=[],
        ambiguous_points=[],
        risk_hints=[],
    )
    turn_decision = TurnDecision(
        phase="alignment_review",
        phase_goal=flow["phase_goal"],
        understanding={
            "summary": understanding.summary,
            "candidate_updates": {},
            "ambiguous_points": [],
        },
        assumptions=list(state.get("working_hypotheses") or []),
        gaps=[],
        challenges=[],
        pm_risk_flags=list(state.get("pm_risk_flags") or []),
        next_move=next_move,
        suggestions=[Suggestion(**item) for item in flow["suggestions"]],
        recommendation=dict(flow["recommendation"]),
        reply_brief={"focus": "assume_and_advance", "must_include": []},
        state_patch=state_patch,
        prd_patch={},
        needs_confirmation=pending_confirmations,
        confidence="medium",
        strategy_reason=flow["strategy_reason"],
        next_best_questions=next_best_questions,
        conversation_strategy=conversation_strategy,
    )
    reply = "".join(flow["reply_lines"])

    return AgentResult(
        reply=reply,
        action=NextAction(
            action="summarize_understanding",
            target=None,
            reason=flow["strategy_reason"],
        ),
        reply_mode="local",
        state_patch=state_patch,
        prd_patch={},
        decision_log=[],
        understanding=understanding,
        turn_decision=turn_decision,
    )


def _build_confirm_continue_result(state: dict, user_input: str) -> AgentResult | None:
    command = CONFIRM_FOCUS_COMMANDS.get(user_input.strip())
    if command is None:
        return None
    if state.get("conversation_strategy") != "confirm":
        return None
    if first_missing_section(state) is not None:
        return None

    locked_sections = "、".join(_confirmed_sections(state)) or "当前共识"
    next_best_questions = list(command["next_best_questions"])
    state_patch = {
        "conversation_strategy": "converge",
        "pending_confirmations": [],
        "iteration": int(state.get("iteration") or 0) + 1,
        "stage_hint": command["stage_hint"],
    }
    understanding = UnderstandingResult(
        summary="用户确认当前共识，希望直接进入下一步推进。",
        candidate_updates={},
        assumption_candidates=[],
        ambiguous_points=[],
        risk_hints=[],
    )
    turn_decision = TurnDecision(
        phase="alignment_review",
        phase_goal=command["phase_goal"],
        understanding={
            "summary": understanding.summary,
            "candidate_updates": {},
            "ambiguous_points": [],
        },
        assumptions=list(state.get("working_hypotheses") or []),
        gaps=[],
        challenges=[],
        pm_risk_flags=list(state.get("pm_risk_flags") or []),
        next_move="assume_and_advance",
        suggestions=[Suggestion(**item) for item in command["suggestions"]],
        recommendation=None,
        reply_brief={"focus": "assume_and_advance", "must_include": []},
        state_patch=state_patch,
        prd_patch={},
        needs_confirmation=[],
        confidence="medium",
        strategy_reason=command["strategy_reason"],
        next_best_questions=next_best_questions,
        conversation_strategy="converge",
    )
    turn_decision.recommendation = dict(command["recommendation"])
    reply = (
        f"我先锁定当前关于{locked_sections}的共识，后面不再在这一层来回漂移。"
        + "".join(command["reply_lines"])
    )

    return AgentResult(
        reply=reply,
        action=NextAction(
            action="summarize_understanding",
            target=None,
            reason="当前共识已确认，下一步推进首轮验证优先级。",
        ),
        reply_mode="local",
        state_patch=state_patch,
        prd_patch={},
        decision_log=[],
        understanding=understanding,
        turn_decision=turn_decision,
    )


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


def _build_correction_result(state: dict, user_input: str) -> AgentResult | None:
    command = CORRECTION_COMMANDS.get(user_input.strip())
    if command is None:
        return None

    state_patch = {
        **command["state_patch"],
        "iteration": int(state.get("iteration") or 0) + 1,
        "stage_hint": command["stage_hint"],
    }
    prd_patch = command["prd_patch"]
    understanding = UnderstandingResult(
        summary=command["understanding_summary"],
        candidate_updates={},
        assumption_candidates=[],
        ambiguous_points=[],
        risk_hints=[],
    )

    next_state = _apply_agent_patch(state, state_patch, prd_patch)
    action = NextAction(
        action="probe_deeper",
        target=command["target"],
        reason=command["reason"],
    )
    turn_decision = build_turn_decision(next_state, understanding, state_patch, prd_patch)
    suggestions, recommendation = build_suggestions(turn_decision)
    turn_decision.suggestions = suggestions
    turn_decision.recommendation = recommendation

    return AgentResult(
        reply=command["reply"],
        action=action,
        reply_mode="local",
        state_patch=state_patch,
        prd_patch=prd_patch,
        decision_log=[],
        understanding=understanding,
        turn_decision=turn_decision,
    )


def run_agent(
    state: dict,
    user_input: str,
    model_result: StructuredExtractionResult | None = None,
) -> AgentResult:
    validation_switch_result = _build_validation_switch_result(state, user_input)
    if validation_switch_result is not None:
        return validation_switch_result

    vague_validation_result = _build_vague_validation_result(state, user_input)
    if vague_validation_result is not None:
        return vague_validation_result

    validation_followup_result = _build_validation_followup_result(state, user_input)
    if validation_followup_result is not None:
        return validation_followup_result

    confirm_continue_result = _build_confirm_continue_result(state, user_input)
    if confirm_continue_result is not None:
        return confirm_continue_result

    correction_result = _build_correction_result(state, user_input)
    if correction_result is not None:
        return correction_result

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
        reply_mode="gateway",
        state_patch=state_patch,
        prd_patch=prd_patch,
        decision_log=decision_log,
        understanding=understanding,
        turn_decision=turn_decision,
    )
