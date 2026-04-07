from typing import get_args

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
