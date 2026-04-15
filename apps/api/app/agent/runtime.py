from __future__ import annotations

from typing import Any

from app.agent.types import AgentResult, NextAction, Suggestion, TurnDecision


_COMPLETED_REOPEN_KEYWORDS = (
    "改",
    "修改",
    "调整",
    "重写",
    "重做",
    "优化",
    "补充",
    "修正",
    "修复",
    "更新",
    "完善",
    "细化",
    "重构",
    "删掉",
    "去掉",
    "替换",
    "变成",
)

_COMPLETED_NON_REOPEN_PHRASES = (
    "好的",
    "收到",
    "明白",
    "继续",
    "导出吧",
    "下载吧",
    "导出",
    "下载",
)


def _is_greeting_input(state: dict[str, Any], user_input: str) -> bool:
    """检测是否为问候类输入。
    
    问候条件：
    1. 会话初期（iteration <= 2）
    2. 输入长度 <= 20 字符
    3. 匹配问候模式
    4. 不包含产品关键词
    """
    iteration = state.get("iteration", 0)
    input_stripped = user_input.strip()
    input_length = len(input_stripped)
    input_lower = input_stripped.lower()
    
    # 条件1: 会话初期
    if iteration > 2:
        return False
    
    # 条件2: 输入长度限制
    if input_length > 20:
        return False
    
    # 条件3: 匹配问候模式
    greeting_patterns = [
        "你好", "您好", "hi", "hello", "在吗", "在不在",
        "你是谁", "你是什么", "介绍一下", "干什么的"
    ]
    
    is_greeting = any(pattern in input_lower for pattern in greeting_patterns)
    if not is_greeting:
        return False
    
    # 条件4: 不包含产品关键词
    product_keywords = ["功能", "需求", "产品", "用户", "场景", "问题", "方案"]
    contains_product = any(keyword in input_stripped for keyword in product_keywords)
    if contains_product:
        return False
    
    return True


def _build_greeting_result(state: dict[str, Any]) -> AgentResult:
    """构建友好的问候响应。"""
    suggestions = [
        Suggestion(
            type="direction",
            label="讨论产品想法",
            content="我有一个产品想法，想和你一起梳理成清晰的 PRD。",
            rationale="适合已经有方向、想快速进入产品讨论的情况。",
            priority=1,
        ),
        Suggestion(
            type="direction",
            label="了解协作方式",
            content="我想先了解你能怎么帮我推进产品想法。",
            rationale="适合还没准备好展开细节、先确认协作方式的情况。",
            priority=2,
        ),
        Suggestion(
            type="direction",
            label="从模糊方向开始",
            content="我现在只有一个模糊方向，还不知道怎么描述，想让你带着我一步步梳理。",
            rationale="适合想法很早期、不知道该从哪里开始的情况。",
            priority=3,
        ),
        Suggestion(
            type="direction",
            label="我直接补充现状",
            content="我直接补充我现在脑子里已有的产品想法，你帮我一起收敛。",
            rationale="适合不想套模板、想直接把当前想法倒出来的情况。",
            priority=4,
        ),
    ]
    reply = (
        "你好！我是 AI 产品联合创始人，专注于帮助你把模糊想法一步步整理成清晰的 PRD。\n\n"
        "如果你现在还说不清，也没关系。你可以直接点下面一个最接近你的选项，"
        "或者自己补充一句你现在在想什么。"
    )

    turn_decision = TurnDecision(
        phase="greeting",
        phase_goal=None,
        understanding={
            "summary": "用户发送问候，提供友好引导。",
            "candidate_updates": {},
            "ambiguous_points": [],
        },
        assumptions=[],
        gaps=[],
        challenges=[],
        pm_risk_flags=[],
        next_move="probe_for_specificity",
        suggestions=suggestions,
        recommendation={
            "label": suggestions[0].label,
            "content": suggestions[0].content,
        },
        reply_brief={"focus": "greeting", "must_include": []},
        state_patch={},
        prd_patch={},
        needs_confirmation=[],
        confidence="high",
        strategy_reason="先用可选方向承接用户，再进入正式问题澄清。",
        next_best_questions=[item.content for item in suggestions],
        conversation_strategy="greet",
    )

    current_iteration = state.get("iteration", 0)
    state_patch = {
        "iteration": current_iteration + 1,
        "conversation_strategy": "greet",
        "strategy_reason": "先用可选方向承接用户，再进入正式问题澄清。",
        "next_best_questions": [item.content for item in suggestions],
    }

    return AgentResult(
        reply=reply,
        action=NextAction(action="probe_deeper", target=None, reason="问候用户并提供可选引导"),
        reply_mode="local",
        state_patch=state_patch,
        prd_patch={},
        decision_log=[],
        understanding=None,
        turn_decision=turn_decision,
    )


def _build_completed_result(state: dict[str, Any]) -> AgentResult:
    sections = state.get("prd_snapshot", {}).get("sections", {})
    confirmed = [
        v.get("title", k)
        for k, v in sections.items()
        if isinstance(v, dict) and v.get("status") == "confirmed"
    ]
    section_summary = "、".join(confirmed) if confirmed else "各核心模块"
    reply = (
        f"PRD 已整理完成！我们共同确认了：{section_summary}。\n\n"
        "你现在可以：\n"
        "- 点击右上角「导出 PRD」下载 Markdown 文档\n"
        "- 继续告诉我需要调整的地方，我会帮你修改\n"
        "- 或者基于这份 PRD，我们可以进一步拆解技术方案"
    )
    suggestions = [
        Suggestion(
            type="direction",
            label="导出 PRD",
            content="我想先导出这份 PRD，看看完整文档版本。",
            rationale="适合先沉淀当前成果，再决定是否继续修改。",
            priority=1,
        ),
        Suggestion(
            type="direction",
            label="继续修改内容",
            content="我想继续修改这份 PRD，有几个地方还需要调整。",
            rationale="适合已经发现问题，准备继续 refinement 的情况。",
            priority=2,
        ),
        Suggestion(
            type="direction",
            label="补齐遗漏",
            content="我想先检查一下，这份 PRD 里还有没有遗漏或说得不够清楚的地方。",
            rationale="适合在导出前做一次补漏，减少返工。",
            priority=3,
        ),
        Suggestion(
            type="direction",
            label="进入下一步",
            content="我想基于这份 PRD，继续拆解 MVP 或技术方案。",
            rationale="适合主线已经清楚，准备进入后续规划的情况。",
            priority=4,
        ),
    ]
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
        suggestions=suggestions,
        recommendation={"label": suggestions[0].label, "content": suggestions[0].content},
        reply_brief={"focus": "completed", "must_include": []},
        state_patch={},
        prd_patch={},
        needs_confirmation=[],
        confidence="high",
        strategy_reason=None,
        next_best_questions=[item.content for item in suggestions],
        conversation_strategy="confirm",
    )
    return AgentResult(
        reply=reply,
        action=NextAction(action="summarize_understanding", target=None, reason="PRD 已完成"),
        reply_mode="local",
        state_patch={},
        prd_patch={},
        decision_log=[],
        understanding=None,
        turn_decision=turn_decision,
    )


def _should_reopen_completed_workflow(user_input: str) -> bool:
    normalized = user_input.strip().lower()
    if not normalized:
        return False

    if normalized in _COMPLETED_NON_REOPEN_PHRASES:
        return False

    if any(keyword in normalized for keyword in _COMPLETED_REOPEN_KEYWORDS):
        return True

    # 长一些的产品跟进通常意味着继续 refinement，而不是停留在完成态摘要。
    return len(normalized) >= 12


def _build_fallback_result(state: dict[str, Any], user_input: str) -> AgentResult:
    suggestions = [
        Suggestion(
            type="direction",
            label="重试刚才的话题",
            content="我想继续刚才的话题，你先按现有信息帮我往下推进。",
            rationale="适合模型暂时不可用后，先保留对话连续性。",
            priority=1,
        ),
        Suggestion(
            type="direction",
            label="先讲目标用户",
            content="我想先明确，这个产品第一版最想服务谁。",
            rationale="先锁定目标用户，后续讨论更容易收敛。",
            priority=2,
        ),
        Suggestion(
            type="direction",
            label="先讲核心问题",
            content="我想先讲清楚，这个产品到底想解决什么具体麻烦。",
            rationale="先把问题说透，再谈方案会更稳。",
            priority=3,
        ),
        Suggestion(
            type="direction",
            label="我直接补充",
            content="我直接补充我现在对这个产品的想法，你帮我整理。",
            rationale="保留自由输入，避免固定选项挡住真实想法。",
            priority=4,
        ),
    ]
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
        suggestions=suggestions,
        recommendation={"label": suggestions[0].label, "content": suggestions[0].content},
        reply_brief={"focus": "fallback", "must_include": []},
        state_patch={},
        prd_patch={},
        needs_confirmation=[],
        confidence="low",
        strategy_reason=None,
        next_best_questions=[item.content for item in suggestions],
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
    *,
    model_config: Any = None,
    conversation_history: list[dict[str, str]] | None = None,
) -> AgentResult:
    """Agent 主入口（瘦编排层）。

    处理四个边界条件，其余全部交给 PM Mentor LLM：
    1. workflow_stage == "completed" → 返回完成回复
    2. model_config is None → 降级本地回复
    3. 问候类输入（会话初期） → 返回友好引导
    4. 其余 → run_pm_mentor
    """
    if state.get("workflow_stage") == "completed":
        if not _should_reopen_completed_workflow(user_input):
            return _build_completed_result(state)

    if model_config is None:
        return _build_fallback_result(state, user_input)

    # 问候语识别与拦截
    if _is_greeting_input(state, user_input):
        return _build_greeting_result(state)

    from app.agent.pm_mentor import run_pm_mentor
    return run_pm_mentor(
        state,
        user_input,
        model_config,
        conversation_history=conversation_history,
    )
