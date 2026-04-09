from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict

from app.agent.decision_engine import build_turn_decision, review_prd_draft_critical_gaps
from app.agent.extractor import (
    StructuredExtractionResult,
    build_rule_extraction_result,
    choose_extraction_result,
    first_missing_section,
    merge_refine_input_into_prd_draft,
    normalize_text,
    is_missing,
    should_capture,
)
from app.agent.reply_composer import compose_reply
from app.agent.suggestion_planner import build_suggestions
from app.agent.types import AgentResult, CriticResult, NextAction, PrdDraftResult, Suggestion, TurnDecision
from app.agent.understanding import parse_idea_input, understand_user_input
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

FINALIZE_CONFIRM_PHRASES = (
    "确认设计",
    "确认无误",
    "开始整理",
    "输出最终版",
    "生成最终版",
)

BUSINESS_PREFERENCE_PHRASES = (
    "业务版",
    "偏业务",
    "业务描述",
)

TECHNICAL_PREFERENCE_PHRASES = (
    "技术版",
    "偏技术",
    "技术细节",
    "技术实现",
)



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


def _normalize_section(title: str, content: str | None, status: str = "confirmed") -> dict[str, str]:
    normalized_content = normalize_text(content or "")
    normalized_status = status if status in {"missing", "draft", "inferred", "confirmed"} else "confirmed"
    return {
        "title": title,
        "content": normalized_content,
        "status": normalized_status if normalized_content else "missing",
    }


def _normalize_prd_draft_sections(prd_draft: dict) -> dict[str, dict[str, str]]:
    raw_sections = deepcopy((prd_draft or {}).get("sections") or {})

    def _read_content(key: str) -> str:
        value = raw_sections.get(key)
        if isinstance(value, dict):
            return normalize_text(str(value.get("content") or ""))
        return ""

    summary_content = _read_content("summary")
    if not summary_content:
        summary_content = _read_content("one_liner") or _read_content("positioning")

    return {
        "summary": _normalize_section("一句话概述", summary_content, "draft"),
        "target_user": _normalize_section("目标用户", _read_content("target_user"), "confirmed"),
        "problem": _normalize_section("核心问题", _read_content("problem"), "confirmed"),
        "solution": _normalize_section("解决方案", _read_content("solution"), "confirmed"),
        "mvp_scope": _normalize_section("MVP 范围", _read_content("mvp_scope"), "confirmed"),
        "constraints": _normalize_section("约束条件", _read_content("constraints"), "draft"),
        "success_metrics": _normalize_section("成功指标", _read_content("success_metrics"), "draft"),
        "out_of_scope": _normalize_section("不做清单", _read_content("out_of_scope"), "draft"),
        "open_questions": _normalize_section("待确认问题", _read_content("open_questions"), "draft"),
    }


def _is_finalize_confirm_input(user_input: str) -> bool:
    normalized = normalize_text(user_input)
    if not normalized:
        return False
    return any(phrase in normalized for phrase in FINALIZE_CONFIRM_PHRASES) or "确认" in normalized


def _resolve_finalize_preference(user_input: str) -> str:
    normalized = normalize_text(user_input)
    if any(phrase in normalized for phrase in TECHNICAL_PREFERENCE_PHRASES):
        return "technical"
    if any(phrase in normalized for phrase in BUSINESS_PREFERENCE_PHRASES):
        return "business"
    return "balanced"


def _build_finalized_sections(prd_draft: dict, preference: str) -> dict[str, dict[str, str]]:
    sections = _normalize_prd_draft_sections(prd_draft)

    summary = sections["summary"]["content"]
    target_user = sections["target_user"]["content"]
    problem = sections["problem"]["content"]
    solution = sections["solution"]["content"]
    mvp_scope = sections["mvp_scope"]["content"]
    constraints = sections["constraints"]["content"]
    success_metrics = sections["success_metrics"]["content"]
    out_of_scope = sections["out_of_scope"]["content"]
    open_questions = sections["open_questions"]["content"]

    if preference == "technical" and constraints:
        solution = f"{solution}\n\n技术约束：{constraints}".strip()
    elif preference == "business" and out_of_scope:
        mvp_scope = f"{mvp_scope}\n\n本阶段明确不做：{out_of_scope}".strip()

    return {
        "summary": _normalize_section("一句话概述", summary, "confirmed" if summary else "missing"),
        "target_user": _normalize_section("目标用户", target_user, "confirmed" if target_user else "missing"),
        "problem": _normalize_section("核心问题", problem, "confirmed" if problem else "missing"),
        "solution": _normalize_section("解决方案", solution, "confirmed" if solution else "missing"),
        "mvp_scope": _normalize_section("MVP 范围", mvp_scope, "confirmed" if mvp_scope else "missing"),
        "constraints": _normalize_section("约束条件", constraints, "confirmed" if constraints else "missing"),
        "success_metrics": _normalize_section("成功指标", success_metrics, "confirmed" if success_metrics else "missing"),
        "out_of_scope": _normalize_section("不做清单", out_of_scope, "confirmed" if out_of_scope else "missing"),
        "open_questions": _normalize_section("待确认问题", open_questions, "draft" if open_questions else "missing"),
    }


def _run_finalize_flow(state: dict, user_input: str) -> AgentResult:
    prd_draft = state.get("prd_draft") if isinstance(state.get("prd_draft"), dict) else {}
    critic_result = state.get("critic_result") if isinstance(state.get("critic_result"), dict) else {}
    overall_verdict = critic_result.get("overall_verdict")

    if overall_verdict != "pass":
        reply = "当前还有关键缺口没有补齐，先不要整理最终版 PRD。请先按 Critic 问题队列把剩余信息补齐。"
        state_patch = {
            "workflow_stage": "refine_loop",
            "finalization_ready": False,
        }
        understanding = UnderstandingResult(
            summary="用户尝试进入 finalize，但 Critic 尚未通过。",
            candidate_updates={},
            assumption_candidates=[],
            ambiguous_points=[],
            risk_hints=[],
        )
        turn_decision = TurnDecision(
            phase="refine_loop",
            phase_goal="Critic 未通过，继续补齐关键缺口",
            understanding={
                "summary": understanding.summary,
                "candidate_updates": {},
                "ambiguous_points": [],
            },
            assumptions=[],
            gaps=list(critic_result.get("major_gaps") or []),
            challenges=[],
            pm_risk_flags=[],
            next_move="probe_for_specificity",
            suggestions=[],
            recommendation=None,
            reply_brief={"focus": "probe_for_specificity", "must_include": []},
            state_patch=state_patch,
            prd_patch={},
            needs_confirmation=[],
            confidence="medium",
            strategy_reason="finalize 需要建立在 Critic pass 之上，当前仍需继续 refine。",
            next_best_questions=list(critic_result.get("question_queue") or [])[:1],
            conversation_strategy="clarify",
        )
        return AgentResult(
            reply=reply,
            action=NextAction(
                action="probe_deeper",
                target=None,
                reason="Critic 未通过，不能 finalize。",
            ),
            reply_mode="local",
            state_patch=state_patch,
            prd_patch={},
            decision_log=[],
            understanding=understanding,
            turn_decision=turn_decision,
        )

    if not _is_finalize_confirm_input(user_input):
        reply = "如果当前摘要没有偏差，请直接回复“确认设计”，或者告诉我最终版更偏业务描述还是技术细节。"
        state_patch = {
            "workflow_stage": "finalize",
            "finalization_ready": True,
        }
        understanding = UnderstandingResult(
            summary="用户已进入 finalize 阶段，但本轮还未明确确认生成最终版。",
            candidate_updates={},
            assumption_candidates=[],
            ambiguous_points=[],
            risk_hints=[],
        )
        turn_decision = TurnDecision(
            phase="finalize",
            phase_goal="确认最终版 PRD 的整理偏好",
            understanding={
                "summary": understanding.summary,
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
            reply_brief={"focus": "summarize_and_confirm", "must_include": []},
            state_patch=state_patch,
            prd_patch={},
            needs_confirmation=["请确认是否现在整理最终版 PRD"],
            confidence="high",
            strategy_reason="Critic 已通过，但 finalize 仍需用户确认输出偏好。",
            next_best_questions=[],
            conversation_strategy="confirm",
        )
        return AgentResult(
            reply=reply,
            action=NextAction(
                action="summarize_understanding",
                target=None,
                reason="等待用户确认最终版整理偏好。",
            ),
            reply_mode="local",
            state_patch=state_patch,
            prd_patch={},
            decision_log=[],
            understanding=understanding,
            turn_decision=turn_decision,
        )

    preference = _resolve_finalize_preference(user_input)
    finalized_sections = _build_finalized_sections(prd_draft, preference)
    next_prd_draft = {
        **deepcopy(prd_draft),
        "status": "finalized",
        "sections": finalized_sections,
        "finalize_preferences": preference,
    }

    state_patch = {
        "workflow_stage": "completed",
        "finalization_ready": True,
        "prd_draft": next_prd_draft,
    }
    understanding = UnderstandingResult(
        summary="Critic 已通过，系统已整理并生成最终版 PRD。",
        candidate_updates={},
        assumption_candidates=[],
        ambiguous_points=[],
        risk_hints=[],
    )
    turn_decision = TurnDecision(
        phase="finalize",
        phase_goal="整理最终版 PRD 并完成当前闭环",
        understanding={
            "summary": understanding.summary,
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
        reply_brief={"focus": "summarize_and_confirm", "must_include": []},
        state_patch=state_patch,
        prd_patch=finalized_sections,
        needs_confirmation=[],
        confidence="high",
        strategy_reason="Critic 已通过，本轮把草稿整理成最终版 PRD。",
        next_best_questions=[],
        conversation_strategy="confirm",
    )
    return AgentResult(
        reply="我已经基于当前确认过的信息整理出最终版 PRD。后续如果你要继续修改，我会在这版终稿基础上增量更新。",
        action=NextAction(
            action="summarize_understanding",
            target=None,
            reason="已生成最终版 PRD。",
        ),
        reply_mode="local",
        state_patch=state_patch,
        prd_patch=finalized_sections,
        decision_log=[],
        understanding=understanding,
        turn_decision=turn_decision,
    )


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


def _build_initial_prd_draft(state: dict, idea_result) -> dict:
    # 初次 PRD 草案只承诺最小闭环：版本、状态、sections 骨架、假设与缺口。
    snapshot_sections = ((state.get("prd_snapshot") or {}).get("sections") or {})
    sections = deepcopy(snapshot_sections)
    if not sections:
        one_liner = idea_result.product_type or "未能解析产品类型"
        sections = {
            "one_liner": {
                "title": "一句话概述",
                "content": one_liner,
                "status": "draft",
            }
        }

    missing_information = list(idea_result.open_questions or [])
    if not missing_information:
        missing_information = ["目标用户与核心场景尚未明确"]

    draft = PrdDraftResult(
        version=1,
        status="draft_hypothesis",
        sections=sections,
        assumptions=list(idea_result.implicit_assumptions or []),
        missing_information=missing_information,
        critic_ready=True,
    )
    return asdict(draft)


def _review_prd_draft(prd_draft: dict, idea_result) -> dict:
    # 最小规则 critic：发现关键缺口并生成问题队列，驱动 refine_loop。
    major_gaps: list[str] = []
    question_queue: list[str] = []

    product_type = idea_result.product_type
    if not product_type:
        major_gaps.append("未能从输入中解析出明确的产品类型或交付形态")
        question_queue.append("你希望这个产品的核心交付物是什么：网页端预览、桌面端插件，还是嵌入式组件？")

    domain_signals = set(idea_result.domain_signals or [])
    is_3d_drawing = bool(domain_signals.intersection({"3D", "3D预览"})) and ("图纸" in domain_signals)
    if is_3d_drawing:
        major_gaps.extend(
            [
                "尚未明确需要支持的图纸/模型格式与导入方式",
                "尚未明确权限与角色模型（谁能看、谁能改、谁能分享）",
                "尚未明确预览深度与交互能力边界（测量/标注/剖切/爆炸等）",
            ]
        )
        question_queue.extend(
            [
                "首版必须支持哪些文件格式？例如 DWG/DXF/PDF/IFC/STEP/GLTF 等，优先级如何？",
                "权限怎么设计：访客、成员、管理员？是否需要外链分享与到期控制？",
                "预览的交互深度要到什么程度：仅旋转缩放，还是测量、标注、剖切、构件选择？",
                "性能与体验目标是什么：单文件最大尺寸、并发预览人数、首屏加载时间目标？",
            ]
        )
    else:
        major_gaps.extend(
            [
                "尚未明确目标用户与使用场景",
                "尚未明确核心价值主张（相比现有替代方案好在哪里）",
                "尚未明确首版能力边界与不做清单",
            ]
        )
        question_queue.extend(
            [
                "你最想服务的第一类用户是谁？他们在什么场景下会用它？",
                "这个产品首版要解决的一个核心场景是什么？请描述一次从触发到完成闭环的流程。",
                "首版你愿意明确不做什么？列 3 条不做清单，帮助我们压缩范围。",
            ]
        )

    verdict = "revise" if product_type else "block"
    critic = CriticResult(
        overall_verdict=verdict,
        major_gaps=major_gaps,
        question_queue=question_queue,
    )
    return asdict(critic)


def _run_initial_draft_flow(state: dict, user_input: str) -> AgentResult:
    idea_result = parse_idea_input(user_input)
    prd_draft = _build_initial_prd_draft(state, idea_result)
    critic_result = _review_prd_draft(prd_draft, idea_result)

    next_question = (critic_result.get("question_queue") or ["为了继续推进，请先补充你希望首版支持的文件格式与权限模型。"])[0]
    reply = (
        "我先把你的想法解析成一个 PRD v1 草案假设，并做了第一轮 Critic 审阅。"
        "接下来我会按问题队列逐条补齐关键缺口，进入 refine_loop。"
        f"\n\n{next_question}"
    )

    state_patch = {
        "workflow_stage": "refine_loop",
        "idea_parse_result": asdict(idea_result),
        "prd_draft": prd_draft,
        "critic_result": critic_result,
    }
    turn_decision = TurnDecision(
        phase="initial_draft",
        phase_goal="生成 PRD v1 草案并进入 refine_loop 补齐关键缺口",
        understanding={
            "summary": idea_result.idea_summary,
            "candidate_updates": {},
            "ambiguous_points": list(idea_result.open_questions or []),
        },
        assumptions=[{"content": item} for item in (idea_result.implicit_assumptions or [])],
        gaps=list(critic_result.get("major_gaps") or []),
        challenges=[],
        pm_risk_flags=[],
        next_move="probe_for_specificity",
        suggestions=[],
        recommendation=None,
        reply_brief={"focus": "probe_for_specificity", "must_include": []},
        state_patch=state_patch,
        prd_patch={},
        needs_confirmation=[],
        confidence="medium",
        strategy_reason="首次输入先做最小闭环：idea_parser -> PRD v1 -> Critic -> refine_loop。",
        conversation_strategy="clarify",
        next_best_questions=list(critic_result.get("question_queue") or []),
    )

    return AgentResult(
        reply=reply,
        action=NextAction(
            action="summarize_understanding",
            target=None,
            reason="首次输入已生成 PRD v1 + Critic，进入 refine_loop 继续补齐关键缺口。",
        ),
        reply_mode="local",
        state_patch=state_patch,
        prd_patch={},
        decision_log=[],
        understanding=UnderstandingResult(
            summary=idea_result.idea_summary,
            candidate_updates={},
            assumption_candidates=list(idea_result.implicit_assumptions or []),
            ambiguous_points=list(idea_result.open_questions or []),
            risk_hints=[],
        ),
        turn_decision=turn_decision,
    )


def _run_refine_loop_flow(state: dict, user_input: str) -> AgentResult:
    prd_draft = state.get("prd_draft") or {}
    critic_result = review_prd_draft_critical_gaps(prd_draft if isinstance(prd_draft, dict) else {})

    question_queue = list(critic_result.get("question_queue") or [])
    overall_verdict = critic_result.get("overall_verdict")
    finalization_ready = overall_verdict == "pass"

    if overall_verdict == "pass":
        prefix = "当前关键信息已基本齐备，Critic 已通过，可以准备进入 finalize。"
        next_question = "如果你确认无误，我可以开始整理最终版 PRD。你希望最终版更偏业务描述还是更偏技术实现细节？"
    else:
        next_question = (
            question_queue[0]
            if question_queue
            else "为了继续推进，请先补充：首版核心文件格式、预览深度，以及权限边界分别是什么？"
        )
        if overall_verdict == "block":
            prefix = "当前产品方案存在关键缺口，先卡口补齐后再继续推进。"
        else:
            prefix = "我已刷新当前 PRD 草案的 Critic 审阅结果，我们继续按问题队列补齐关键缺口。"

    state_patch = {
        "critic_result": critic_result,
        "finalization_ready": finalization_ready,
    }
    if finalization_ready:
        state_patch["workflow_stage"] = "finalize"

    understanding = UnderstandingResult(
        summary="refine_loop 推进词触发 Critic 刷新；若已通过则准备进入 finalize。",
        candidate_updates={},
        assumption_candidates=[],
        ambiguous_points=[],
        risk_hints=[],
    )
    turn_decision = TurnDecision(
        phase="finalize" if finalization_ready else "refine_loop",
        phase_goal="Critic 已通过，准备进入 finalize 整理最终版 PRD" if finalization_ready else "按单问题队列补齐关键缺口，推动进入 finalize",
        understanding={
            "summary": understanding.summary,
            "candidate_updates": {},
            "ambiguous_points": [],
        },
        assumptions=[],
        gaps=list(critic_result.get("major_gaps") or []),
        challenges=[],
        pm_risk_flags=[],
        next_move="probe_for_specificity",
        suggestions=[],
        recommendation=None,
        reply_brief={"focus": "probe_for_specificity", "must_include": []},
        state_patch=state_patch,
        prd_patch={},
        needs_confirmation=[],
        confidence="medium",
        strategy_reason="refine_loop 阶段对推进词走 Critic 刷新；通过后明确迁移到 finalize。",
        next_best_questions=question_queue[:1] if not finalization_ready else [],
        conversation_strategy="clarify",
    )

    return AgentResult(
        reply=f"{prefix}\n\n{next_question}",
        action=NextAction(
            action="summarize_understanding",
            target=None,
            reason="refine_loop 阶段优先刷新 Critic，并按单问题队列推进补齐缺口。",
        ),
        reply_mode="local",
        state_patch=state_patch,
        prd_patch={},
        decision_log=[],
        understanding=understanding,
        turn_decision=turn_decision,
    )


def _should_enter_initial_draft_flow(state: dict) -> bool:
    workflow_stage = state.get("workflow_stage")
    if workflow_stage != "idea_parser":
        return False

    if state.get("prd_draft") or state.get("critic_result"):
        return False

    if any(not is_missing(state.get(key)) for key in ("target_user", "problem", "solution", "mvp_scope")):
        return False

    if state.get("pending_confirmations") or state.get("validation_focus") or state.get("phase_goal"):
        return False

    if state.get("conversation_strategy") in {"confirm", "converge", "choose"}:
        return False

    if int(state.get("iteration") or 0) > 0:
        return False

    return True


def run_agent(
    state: dict,
    user_input: str,
    model_result: StructuredExtractionResult | None = None,
) -> AgentResult:
    if _should_enter_initial_draft_flow(state):
        # 首次消息优先走 PRD v1 + Critic 的最小闭环编排，绕过旧的四字段填槽收敛路径。
        return _run_initial_draft_flow(state, user_input)

    if state.get("workflow_stage") == "refine_loop":
        # refine_loop 下：
        # 1) 推进词：刷新 Critic 并继续单问题队列；
        # 2) 实质输入：走最小写回桥接 -> 更新 prd_draft -> 重跑 Critic，避免落回旧四字段路径吞错语义。
        if not should_capture(user_input):
            return _run_refine_loop_flow(state, user_input)

        prd_draft = state.get("prd_draft") if isinstance(state.get("prd_draft"), dict) else {}
        critic_result_before = state.get("critic_result") if isinstance(state.get("critic_result"), dict) else {}
        next_prd_draft, signals = merge_refine_input_into_prd_draft(
            prd_draft or {},
            critic_result_before,
            user_input,
        )
        critic_result = review_prd_draft_critical_gaps(next_prd_draft)
        finalization_ready = critic_result.get("overall_verdict") == "pass"

        question_queue = list(critic_result.get("question_queue") or [])
        if finalization_ready:
            next_question = "如果你确认无误，我可以开始整理最终版 PRD。你希望最终版更偏业务描述还是更偏技术实现细节？"
        else:
            next_question = (
                question_queue[0]
                if question_queue
                else "我已记录你的补充。为了继续推进，请补充剩余关键缺口（文件格式/预览深度/权限边界）中你还没明确的部分。"
            )

        state_patch = {
            "prd_draft": next_prd_draft,
            "critic_result": critic_result,
            "finalization_ready": finalization_ready,
        }
        if finalization_ready:
            state_patch["workflow_stage"] = "finalize"
        understanding = UnderstandingResult(
            summary="refine_loop 收到实质补充信息，已写回 PRD 草案并重跑 Critic。",
            candidate_updates={
                "file_format": bool(signals.get("file_format")),
                "preview_depth": bool(signals.get("preview_depth")),
                "permission_boundary": bool(signals.get("permission_boundary")),
            },
            assumption_candidates=[],
            ambiguous_points=[],
            risk_hints=[],
        )
        turn_decision = TurnDecision(
            phase="finalize" if finalization_ready else "refine_loop",
            phase_goal="Critic 已通过，准备进入 finalize 整理最终版 PRD"
            if finalization_ready
            else "把补充写回 PRD 草案并持续补齐关键缺口",
            understanding={
                "summary": understanding.summary,
                "candidate_updates": dict(understanding.candidate_updates),
                "ambiguous_points": [],
            },
            assumptions=[],
            gaps=list(critic_result.get("major_gaps") or []),
            challenges=[],
            pm_risk_flags=[],
            next_move="probe_for_specificity",
            suggestions=[],
            recommendation=None,
            reply_brief={"focus": "probe_for_specificity", "must_include": []},
            state_patch=state_patch,
            prd_patch={},
            needs_confirmation=[],
            confidence="medium",
            strategy_reason="refine_loop 实质输入走最小写回桥接，不落回旧四字段填槽。",
            next_best_questions=question_queue[:1] if not finalization_ready else [],
            conversation_strategy="clarify",
        )
        prd_patch = dict(next_prd_draft.get("sections") or {})

        prefix = (
            "当前关键信息已基本齐备，Critic 已通过，可以整理最终版 PRD。"
            if finalization_ready
            else "已记录并写回你的补充，我们继续补齐剩余关键缺口。"
        )
        return AgentResult(
            reply=f"{prefix}\n\n{next_question}",
            action=NextAction(
                action="summarize_understanding",
                target=None,
                reason="refine_loop 实质输入已写回 prd_draft 并重跑 Critic。",
            ),
            reply_mode="local",
            state_patch=state_patch,
            prd_patch=prd_patch,
            decision_log=[],
            understanding=understanding,
            turn_decision=turn_decision,
        )

    if state.get("workflow_stage") == "finalize":
        return _run_finalize_flow(state, user_input)

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
