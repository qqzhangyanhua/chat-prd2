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


CONFIRM_CONTINUE_COMMAND = "确认，继续下一步"

CONFIRM_FOCUS_COMMANDS = {
    CONFIRM_CONTINUE_COMMAND: {
        "phase_goal": "明确首轮验证优先级",
        "stage_hint": "推进验证优先级",
        "strategy_reason": "当前共识已锁定，下一步进入首轮验证优先级收敛。",
        "recommendation": {
            "label": "先锁定首轮验证项",
            "content": "先在频率、付费意愿、转化阻力里选一个最优先验证项",
            "rationale": "先锁定验证目标，后续访谈和方案取舍才不会发散",
            "type": "recommendation",
            "priority": 1,
        },
        "suggestions": [
            {
                "type": "recommendation",
                "label": "先锁定首轮验证项",
                "content": "先在频率、付费意愿、转化阻力里选一个最优先验证项",
                "rationale": "先锁定验证目标，后续访谈和方案取舍才不会发散",
                "priority": 1,
            },
            {
                "type": "direction",
                "label": "优先验证频率",
                "content": "先判断这个问题是否足够高频",
                "rationale": "频率不成立，后续价值和付费判断都会失真",
                "priority": 2,
            },
            {
                "type": "tradeoff",
                "label": "再决定验证付费还是转化阻力",
                "content": "在频率成立后，再判断用户是否愿意付费或卡在哪一步",
                "rationale": "先后顺序更稳定，验证成本更低",
                "priority": 3,
            },
        ],
        "next_best_questions": [
            "为了继续推进，请直接回答你现在最想先验证的是频率、付费意愿，还是转化阻力？"
        ],
        "reply_lines": [
            "下一步我会把讨论推进到“首轮验证优先级”，先判断你现在最该优先验证哪一项。",
            "如果你还没明确顺序，我更建议先看“频率”是否成立，因为它最先决定这个问题值不值得继续深挖。",
            "请你直接告诉我当前最想先验证的是频率、付费意愿，还是转化阻力。",
        ],
    },
    "确认，先看频率": {
        "phase_goal": "明确问题发生频率是否足够高",
        "stage_hint": "推进频率验证",
        "strategy_reason": "当前共识已锁定，下一步进入频率验证。",
        "recommendation": {
            "label": "先验证问题频率",
            "content": "先判断这个问题是否高频到值得优先解决",
            "rationale": "低频问题通常不值得优先投入 MVP",
            "type": "recommendation",
            "priority": 1,
        },
        "suggestions": [
            {
                "type": "recommendation",
                "label": "先验证问题频率",
                "content": "先判断这个问题是否高频到值得优先解决",
                "rationale": "低频问题通常不值得优先投入 MVP",
                "priority": 1,
            },
            {
                "type": "direction",
                "label": "补一条最近发生的真实案例",
                "content": "先说明最近一次发生在什么场景、谁触发、结果如何",
                "rationale": "真实案例比抽象判断更能校准频率",
                "priority": 2,
            },
            {
                "type": "tradeoff",
                "label": "区分偶发痛点和高频痛点",
                "content": "先分清这是偶发抱怨还是反复发生的问题",
                "rationale": "频率会直接影响产品优先级",
                "priority": 3,
            },
        ],
        "next_best_questions": [
            "为了继续推进，请直接补一句这个问题平均多久发生一次，最好带上最近一次真实场景。"
        ],
        "reply_lines": [
            "下一步我会先把讨论推进到“频率验证”，先判断这个问题是不是高频到值得优先做。",
            "如果频率站不住，后面再谈付费和转化都会偏早。",
            "请你直接告诉我这个问题平均多久发生一次，最好顺手带上最近一次真实场景。",
        ],
    },
    "确认，先看付费意愿": {
        "phase_goal": "明确付费意愿是否成立",
        "stage_hint": "推进付费意愿验证",
        "strategy_reason": "当前共识已锁定，下一步进入付费意愿验证。",
        "recommendation": {
            "label": "先验证付费意愿",
            "content": "先判断用户有没有为这类结果付费的真实动机",
            "rationale": "没有付费意愿，再顺畅的方案也很难成立为业务",
            "type": "recommendation",
            "priority": 1,
        },
        "suggestions": [
            {
                "type": "recommendation",
                "label": "先验证付费意愿",
                "content": "先判断用户有没有为这类结果付费的真实动机",
                "rationale": "没有付费意愿，再顺畅的方案也很难成立为业务",
                "priority": 1,
            },
            {
                "type": "direction",
                "label": "先找现有替代方案价格锚点",
                "content": "先看用户现在是否已经在为其他替代方案买单",
                "rationale": "已有支付行为比口头意愿更可靠",
                "priority": 2,
            },
            {
                "type": "tradeoff",
                "label": "区分愿意花钱和愿意花时间",
                "content": "先判断用户到底更愿意付钱还是自己折腾",
                "rationale": "这会直接决定后续商业模式方向",
                "priority": 3,
            },
        ],
        "next_best_questions": [
            "为了继续推进，请直接回答这类用户现在有没有为替代方案付费，或者愿不愿意为更好结果付费。"
        ],
        "reply_lines": [
            "下一步我会先把讨论推进到“付费意愿验证”，先判断这是不是一个用户愿意掏钱解决的问题。",
            "如果用户只觉得麻烦但不愿付费，产品价值和商业化路径都要重算。",
            "请你直接告诉我这类用户现在有没有为替代方案付费，或者愿不愿意为更好结果付费。",
        ],
    },
    "确认，先看转化阻力": {
        "phase_goal": "明确转化阻力集中在哪一环",
        "stage_hint": "推进转化阻力验证",
        "strategy_reason": "当前共识已锁定，下一步进入转化阻力验证。",
        "recommendation": {
            "label": "先验证转化阻力",
            "content": "先判断用户会卡在理解、接入还是结果稳定性",
            "rationale": "不先识别转化阻力，MVP 很容易做成却没人持续使用",
            "type": "recommendation",
            "priority": 1,
        },
        "suggestions": [
            {
                "type": "recommendation",
                "label": "先验证转化阻力",
                "content": "先判断用户会卡在理解、接入还是结果稳定性",
                "rationale": "不先识别转化阻力，MVP 很容易做成却没人持续使用",
                "priority": 1,
            },
            {
                "type": "direction",
                "label": "先找最容易流失的一步",
                "content": "先指出用户最可能在哪一步退出",
                "rationale": "最薄弱的一环通常决定整体转化",
                "priority": 2,
            },
            {
                "type": "tradeoff",
                "label": "区分理解成本和接入成本",
                "content": "先判断是看不懂，还是用起来太麻烦",
                "rationale": "不同阻力决定完全不同的产品打法",
                "priority": 3,
            },
        ],
        "next_best_questions": [
            "为了继续推进，请直接回答用户现在最容易卡在哪一步，是理解成本、接入成本，还是结果不够稳定。"
        ],
        "reply_lines": [
            "下一步我会先把讨论推进到“转化阻力验证”，先判断用户最可能卡在哪一步。",
            "如果不先识别阻力点，后面功能越堆越多，反而更难形成转化闭环。",
            "请你直接告诉我用户现在最容易卡在哪一步，是理解成本、接入成本，还是结果不够稳定。",
        ],
    },
}

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

VALIDATION_FOLLOWUP_FLOWS = {
    ("frequency", 1): {
        "phase_goal": "确认高频问题是否造成真实损失",
        "stage_hint": "频率影响确认",
        "strategy_reason": "频率信号已记录，下一步确认它是否真的造成损失。",
        "summary_prefix": "用户补充了问题发生频率的描述。",
        "evidence_prefix": "频率线索",
        "recommendation": {
            "label": "先确认高频是否真的带来损失",
            "content": "把频率和真实损失连起来，再决定是否值得优先做",
            "rationale": "高频但无损失的问题，优先级仍可能不成立",
            "type": "recommendation",
            "priority": 1,
        },
        "suggestions": [
            {
                "type": "recommendation",
                "label": "先确认高频是否真的带来损失",
                "content": "把频率和真实损失连起来，再决定是否值得优先做",
                "rationale": "高频但无损失的问题，优先级仍可能不成立",
                "priority": 1,
            },
            {
                "type": "direction",
                "label": "补真实损失",
                "content": "说明会多花多少时间、错过什么机会、造成什么错误",
                "rationale": "损失越具体，优先级越容易判断",
                "priority": 2,
            },
            {
                "type": "tradeoff",
                "label": "区分高频噪音和高频痛点",
                "content": "判断这是单纯烦，还是会持续拖慢关键动作",
                "rationale": "不是所有高频问题都值得优先解决",
                "priority": 3,
            },
        ],
        "next_best_questions": [
            "为了继续推进，请直接回答如果这件事持续发生，实际会多花什么时间、错过什么机会，或者带来什么损失。"
        ],
        "reply_lines": [
            "我先按你的描述把当前判断收成“这是一个高频信号候选”，先不急着直接认定它值得优先做。",
            "下一步我会继续追问这个频率到底有没有真实后果，因为没有损失的高频问题不一定值得做成产品。",
            "请你直接告诉我，如果这件事持续发生，实际会多花什么时间、错过什么机会，或者带来什么损失。",
        ],
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
    state_patch = {
        "conversation_strategy": "converge",
        "validation_focus": validation_focus,
        "validation_step": validation_step + 1,
        "iteration": int(state.get("iteration") or 0) + 1,
        "stage_hint": flow["stage_hint"],
        "evidence": evidence,
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
        next_move="assume_and_advance",
        suggestions=[Suggestion(**item) for item in flow["suggestions"]],
        recommendation=dict(flow["recommendation"]),
        reply_brief={"focus": "assume_and_advance", "must_include": []},
        state_patch=state_patch,
        prd_patch={},
        needs_confirmation=[],
        confidence="medium",
        strategy_reason=flow["strategy_reason"],
        next_best_questions=next_best_questions,
        conversation_strategy="converge",
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
