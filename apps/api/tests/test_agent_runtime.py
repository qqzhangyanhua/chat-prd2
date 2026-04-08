from typing import get_args
import pytest

from app.agent.prompts import PROBE_PROBLEM_REPLY, PROBE_SOLUTION_REPLY, SUMMARIZE_UNDERSTANDING_REPLY
from app.agent.reply_composer import (
    ASSUMPTION_PREFIX,
    CONFIRM_ITEMS_PREFIX,
    JUDGEMENT_PREFIX,
    NEXT_STEP_PREFIX,
    SUGGEST_PREFIX_RECOMMEND,
)
from app.agent.extractor import StructuredExtractionResult
from app.agent.runtime import decide_next_action, run_agent
from app.agent.types import ActionTarget
from app.agent.understanding import UnderstandingResult


def _phase1_state(**overrides):
    base = {
        "idea": "做一个 AI Co-founder",
        "target_user": None,
        "problem": None,
        "solution": None,
        "mvp_scope": [],
        "iteration": 0,
        "stage_hint": "问题探索",
        "current_phase": "idea_clarification",
        "phase_goal": None,
        "working_hypotheses": [],
        "evidence": [],
        "decision_readiness": None,
        "pm_risk_flags": [],
        "recommended_directions": [],
        "pending_confirmations": [],
        "rejected_options": [],
        "next_best_questions": [],
    }
    base.update(overrides)
    return base


def _assert_reply_prefixes(reply: str, next_step_fragment: str) -> None:
    assert JUDGEMENT_PREFIX in reply
    assert ASSUMPTION_PREFIX in reply
    assert SUGGEST_PREFIX_RECOMMEND in reply
    assert CONFIRM_ITEMS_PREFIX in reply
    assert NEXT_STEP_PREFIX in reply
    assert next_step_fragment in reply


def test_action_target_only_exposes_currently_supported_target():
    required_targets = {"target_user", "problem", "solution", "mvp_scope"}

    assert required_targets.issubset(set(get_args(ActionTarget)))


def test_decide_next_action_prefers_probe_when_target_user_missing():
    state = _phase1_state()
    action = decide_next_action(state, "我想做一个帮助创业者梳理想法的产品")
    assert action.action == "probe_deeper"
    assert action.target == "target_user"


def test_decide_next_action_summarizes_when_target_user_exists():
    state = _phase1_state(target_user="独立创业者")

    action = decide_next_action(state, "我想先收敛需求")

    assert action.action == "probe_deeper"
    assert action.target == "problem"


def test_run_agent_returns_probe_reply_and_empty_patches_when_target_user_missing():
    state = _phase1_state()

    result = run_agent(state, "我想做一个帮助创业者梳理想法的产品")

    assert result.reply != PROBE_PROBLEM_REPLY
    _assert_reply_prefixes(result.reply, "如果当前问题判断不对你直接指出")
    assert result.action.action == "probe_deeper"
    assert result.action.target == "problem"
    assert result.state_patch == {
        "target_user": "我想做一个帮助创业者梳理想法的产品",
        "iteration": 1,
        "stage_hint": "问题定义",
    }
    assert result.prd_patch == {
        "target_user": {
            "title": "目标用户",
            "content": "我想做一个帮助创业者梳理想法的产品",
            "status": "confirmed",
        },
    }
    assert result.decision_log == [
        {
            "section": "target_user",
            "value": "我想做一个帮助创业者梳理想法的产品",
        }
    ]
    assert result.turn_decision is not None
    assert result.turn_decision.next_move == "challenge_and_reframe"
    assert result.turn_decision.phase == "idea_clarification"
    assert result.turn_decision.state_patch == result.state_patch
    assert result.turn_decision.prd_patch == result.prd_patch
    assert result.turn_decision.suggestions
    assert result.turn_decision.recommendation is not None
    assert any(
        suggestion.label in result.reply for suggestion in result.turn_decision.suggestions
    )


def test_run_agent_returns_summary_reply_when_target_user_exists():
    state = _phase1_state(
        target_user="独立创业者",
        iteration=0,
        stage_hint="问题探索",
    )

    result = run_agent(state, "他们现在最大的痛点是不知道先验证哪个需求")

    assert result.reply != PROBE_SOLUTION_REPLY
    _assert_reply_prefixes(result.reply, "如果你认可这个推进点")
    assert result.action.action == "probe_deeper"
    assert result.action.target == "solution"
    assert result.state_patch == {
        "problem": "他们现在最大的痛点是不知道先验证哪个需求",
        "iteration": 1,
        "stage_hint": "方案收敛",
    }
    assert result.prd_patch == {
        "problem": {
            "title": "核心问题",
            "content": "他们现在最大的痛点是不知道先验证哪个需求",
            "status": "confirmed",
        },
    }
    assert result.turn_decision is not None
    assert result.turn_decision.suggestions
    assert result.turn_decision.recommendation is not None
    assert result.turn_decision.next_best_questions
    assert result.turn_decision.next_best_questions[0] in result.reply
    assert any(
        suggestion.label in result.reply for suggestion in result.turn_decision.suggestions
    )


def test_run_agent_summarizes_after_core_prd_sections_are_complete():
    state = _phase1_state(
        target_user="独立创业者",
        problem="不知道先验证哪个需求",
        solution="通过连续追问沉淀结构化 PRD",
        mvp_scope=["创建会话、持续追问、导出 PRD"],
        iteration=3,
        stage_hint="MVP 收敛",
    )

    result = run_agent(state, "继续")

    assert result.reply != SUMMARIZE_UNDERSTANDING_REPLY
    _assert_reply_prefixes(result.reply, "请你先确认")
    assert result.action.action == "summarize_understanding"
    assert result.action.target is None
    assert result.state_patch == {
        "iteration": 4,
        "stage_hint": "总结共识",
    }
    assert result.prd_patch == {}
    assert result.turn_decision is not None
    assert result.turn_decision.next_move == "summarize_and_confirm"
    assert result.turn_decision.next_best_questions == ["请确认当前理解是否准确"]
    assert "我下一轮最建议你直接回答" in result.reply
    assert result.turn_decision.state_patch == result.state_patch
    assert result.turn_decision.prd_patch == result.prd_patch


def test_run_agent_enters_target_user_correction_mode_on_negative_confirm_reply():
    state = _phase1_state(
        conversation_strategy="confirm",
        target_user="独立创业者",
        problem="不知道先验证哪个需求",
        solution="通过连续追问沉淀结构化 PRD",
        mvp_scope=["创建会话、持续追问、导出 PRD"],
        pending_confirmations=["目标用户是否准确"],
    )

    result = run_agent(state, "不对，先改目标用户")

    assert result.action.action == "probe_deeper"
    assert result.action.target == "target_user"
    assert result.state_patch["target_user"] is None
    assert result.state_patch["problem"] is None
    assert result.state_patch["solution"] is None
    assert result.state_patch["mvp_scope"] == []
    assert result.state_patch["pending_confirmations"] == []
    assert "我先回滚当前关于目标用户及其后续共识" in result.reply
    assert "请你重新告诉我最想服务的第一类用户是谁" in result.reply
    assert "我会先重建目标用户判断" in result.reply
    assert result.turn_decision is not None
    assert result.turn_decision.conversation_strategy == "clarify"


def test_run_agent_enters_local_confirm_continue_mode_after_positive_confirm_reply():
    state = _phase1_state(
        conversation_strategy="confirm",
        target_user="独立创业者",
        problem="不知道先验证哪个需求",
        solution="通过连续追问沉淀结构化 PRD",
        mvp_scope=["创建会话、持续追问、导出 PRD"],
        pending_confirmations=["目标用户是否准确", "核心问题是否准确"],
    )

    result = run_agent(state, "确认，继续下一步")

    assert result.reply_mode == "local"
    assert result.action.action == "summarize_understanding"
    assert result.action.target is None
    assert result.state_patch["conversation_strategy"] == "converge"
    assert result.state_patch["pending_confirmations"] == []
    assert result.state_patch["stage_hint"] == "推进验证优先级"
    assert "我先锁定当前关于目标用户、核心问题、解决方案、MVP 范围的共识" in result.reply
    assert "下一步我会把讨论推进到“首轮验证优先级”" in result.reply
    assert "请你直接告诉我当前最想先验证的是频率、付费意愿，还是转化阻力" in result.reply
    assert result.turn_decision is not None
    assert result.turn_decision.conversation_strategy == "converge"
    assert result.turn_decision.next_move == "assume_and_advance"
    assert result.turn_decision.phase_goal == "明确首轮验证优先级"
    assert result.turn_decision.next_best_questions == [
        "为了继续推进，请直接回答你现在最想先验证的是频率、付费意愿，还是转化阻力？"
    ]


@pytest.mark.parametrize(
    ("user_input", "reply_fragment", "question"),
    [
        (
            "确认，先看频率",
            "我会先把讨论推进到“频率验证”",
            "为了继续推进，请直接补一句这个问题平均多久发生一次，最好带上最近一次真实场景。",
        ),
        (
            "确认，先看付费意愿",
            "我会先把讨论推进到“付费意愿验证”",
            "为了继续推进，请直接回答这类用户现在有没有为替代方案付费，或者愿不愿意为更好结果付费。",
        ),
        (
            "确认，先看转化阻力",
            "我会先把讨论推进到“转化阻力验证”",
            "为了继续推进，请直接回答用户现在最容易卡在哪一步，是理解成本、接入成本，还是结果不够稳定。",
        ),
    ],
)
def test_run_agent_supports_specific_local_confirm_commands(user_input, reply_fragment, question):
    state = _phase1_state(
        conversation_strategy="confirm",
        target_user="独立创业者",
        problem="不知道先验证哪个需求",
        solution="通过连续追问沉淀结构化 PRD",
        mvp_scope=["创建会话、持续追问、导出 PRD"],
        pending_confirmations=["目标用户是否准确"],
    )

    result = run_agent(state, user_input)

    assert result.reply_mode == "local"
    assert result.state_patch["conversation_strategy"] == "converge"
    assert result.state_patch["pending_confirmations"] == []
    assert reply_fragment in result.reply
    assert result.turn_decision is not None
    assert result.turn_decision.phase_goal is not None
    assert result.turn_decision.next_best_questions == [question]


def test_run_agent_keeps_frequency_validation_in_local_stable_flow_after_focus_selected():
    state = _phase1_state(
        conversation_strategy="converge",
        target_user="独立创业者",
        problem="不知道先验证哪个需求",
        solution="通过连续追问沉淀结构化 PRD",
        mvp_scope=["创建会话、持续追问、导出 PRD"],
        phase_goal="明确问题发生频率是否足够高",
        stage_hint="推进频率验证",
        validation_focus="frequency",
        validation_step=1,
    )

    result = run_agent(state, "最近几乎每天都会发生，尤其在准备新需求评审时")

    assert result.reply_mode == "local"
    assert result.state_patch["validation_focus"] == "frequency"
    assert result.state_patch["validation_step"] == 2
    assert result.state_patch["conversation_strategy"] == "converge"
    assert "我先按你的描述把当前判断收成“这是一个高频信号候选”" in result.reply
    assert "下一步我会继续追问这个频率到底有没有真实后果" in result.reply
    assert result.turn_decision is not None
    assert result.turn_decision.phase_goal == "确认高频问题是否造成真实损失"
    assert result.turn_decision.next_best_questions == [
        "为了继续推进，请直接回答如果这件事持续发生，实际会多花什么时间、错过什么机会，或者带来什么损失。"
    ]


def test_run_agent_keeps_conversion_resistance_validation_in_local_stable_flow_after_focus_selected():
    state = _phase1_state(
        conversation_strategy="converge",
        target_user="独立创业者",
        problem="不知道先验证哪个需求",
        solution="通过连续追问沉淀结构化 PRD",
        mvp_scope=["创建会话、持续追问、导出 PRD"],
        phase_goal="明确转化阻力集中在哪一环",
        stage_hint="推进转化阻力验证",
        validation_focus="conversion_resistance",
        validation_step=1,
    )

    result = run_agent(state, "大多数人会卡在第一次接入，不知道要准备什么资料")

    assert result.reply_mode == "local"
    assert result.state_patch["validation_focus"] == "conversion_resistance"
    assert result.state_patch["validation_step"] == 2
    assert result.state_patch["conversation_strategy"] == "converge"
    assert "我先按你的描述把当前阻力判断收成“首要阻力候选已经出现”" in result.reply
    assert "下一步我会继续追问这个阻力到底会不会直接打断转化" in result.reply
    assert result.turn_decision is not None
    assert result.turn_decision.phase_goal == "确认首要阻力是否直接打断转化"
    assert result.turn_decision.next_best_questions == [
        "为了继续推进，请直接回答一旦卡在这里，用户最常见的结果是放弃、延后，还是转去其他替代方案。"
    ]


def test_run_agent_allows_action_and_next_move_diverge():
    state = _phase1_state()

    result = run_agent(state, "我想做一个产品来帮助创业者梳理方案")

    assert result.action.action == "probe_deeper"
    assert result.action.target == "problem"
    assert result.turn_decision is not None
    assert result.turn_decision.next_move == "challenge_and_reframe"


def test_run_agent_prefers_valid_model_extraction_over_rule_result():
    state = _phase1_state(
        iteration=0,
        stage_hint="问题探索",
    )

    model_result = StructuredExtractionResult(
        should_update=True,
        state_patch={
            "target_user": "独立开发者团队负责人",
            "iteration": 1,
            "stage_hint": "问题定义",
        },
        prd_patch={
            "target_user": {
                "title": "目标用户",
                "content": "独立开发者团队负责人",
                "status": "confirmed",
            }
        },
        confidence="high",
        reasoning_summary="模型识别到用户明确描述了目标用户",
        decision_log=[{"section": "target_user", "value": "独立开发者团队负责人"}],
        source="model",
    )

    result = run_agent(state, "我们主要服务独立开发者团队负责人", model_result=model_result)

    assert result.state_patch["target_user"] == "独立开发者团队负责人"
    assert result.prd_patch["target_user"]["content"] == "独立开发者团队负责人"
    assert result.decision_log == [{"section": "target_user", "value": "独立开发者团队负责人"}]


def test_run_agent_falls_back_to_rule_result_when_model_result_is_low_confidence():
    state = _phase1_state(iteration=0, stage_hint="问题探索")

    model_result = StructuredExtractionResult(
        should_update=True,
        state_patch={
            "target_user": "泛互联网用户",
            "iteration": 1,
            "stage_hint": "问题定义",
        },
        prd_patch={
            "target_user": {
                "title": "目标用户",
                "content": "泛互联网用户",
                "status": "confirmed",
            }
        },
        confidence="low",
        reasoning_summary="模型置信度不足",
        decision_log=[{"section": "target_user", "value": "泛互联网用户"}],
        source="model",
    )

    result = run_agent(state, "独立开发者", model_result=model_result)

    assert result.state_patch["target_user"] == "独立开发者"
    assert result.prd_patch["target_user"]["content"] == "独立开发者"
    assert result.decision_log == [{"section": "target_user", "value": "独立开发者"}]


def test_run_agent_calls_understanding_layer(monkeypatch):
    state = _phase1_state()
    called = {}

    def fake_understand(s, user_input):
        called["args"] = (s.copy(), user_input)
        return UnderstandingResult(
            summary="测试",
            candidate_updates={},
            assumption_candidates=[],
            ambiguous_points=[],
            risk_hints=[],
        )

    monkeypatch.setattr("app.agent.runtime.understand_user_input", fake_understand)

    result = run_agent(state, "测试理解层")

    assert "args" in called
    assert called["args"][1] == "测试理解层"
    assert result.understanding is not None
    assert result.understanding.summary == "测试"
    assert result.understanding.risk_hints == []


def test_run_agent_returns_understanding_result():
    state = _phase1_state()
    result = run_agent(state, "我们主要服务独立开发者团队")
    assert result.understanding is not None
    assert "用户表述了" in result.understanding.summary
    assert result.understanding.candidate_updates.get("target_user") == "我们主要服务独立开发者团队"
