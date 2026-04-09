from typing import get_args
import pytest

from app.agent.prompts import PROBE_PROBLEM_REPLY, PROBE_SOLUTION_REPLY, SUMMARIZE_UNDERSTANDING_REPLY
from app.agent.reply_composer import (
    CRITIC_VERDICT_PREFIX,
    DRAFT_SUMMARY_PREFIX,
    NEXT_QUESTION_PREFIX,
)
from app.agent.extractor import StructuredExtractionResult
from app.agent.runtime import decide_next_action, run_agent
from app.agent.types import ActionTarget
from app.agent.understanding import UnderstandingResult


def _phase1_state(**overrides):
    base = {
        "idea": "做一个 AI Co-founder",
        "workflow_stage": "prd_draft",
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


def _assert_reply_prefixes(reply: str, next_step_fragment: str | None = None) -> None:
    assert DRAFT_SUMMARY_PREFIX in reply
    assert CRITIC_VERDICT_PREFIX in reply
    assert NEXT_QUESTION_PREFIX in reply
    if next_step_fragment is not None:
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
    _assert_reply_prefixes(result.reply, "为了继续推进，请先把清晰的核心问题补具体。")
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


def test_run_agent_returns_summary_reply_when_target_user_exists():
    state = _phase1_state(
        target_user="独立创业者",
        iteration=0,
        stage_hint="问题探索",
    )

    result = run_agent(state, "他们现在最大的痛点是不知道先验证哪个需求")

    assert result.reply != PROBE_SOLUTION_REPLY
    _assert_reply_prefixes(result.reply, "基于当前信息，你最想先验证哪一项：频率、付费意愿，还是转化阻力？")
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
    _assert_reply_prefixes(result.reply, "请确认当前理解是否准确")
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
    assert NEXT_QUESTION_PREFIX in result.reply
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


def test_run_agent_closes_frequency_validation_with_local_verdict_and_confirm_gate():
    state = _phase1_state(
        conversation_strategy="converge",
        target_user="独立创业者",
        problem="不知道先验证哪个需求",
        solution="通过连续追问沉淀结构化 PRD",
        mvp_scope=["创建会话、持续追问、导出 PRD"],
        phase_goal="确认高频问题是否造成真实损失",
        stage_hint="频率影响确认",
        validation_focus="frequency",
        validation_step=2,
        evidence=["频率线索：最近几乎每天都会发生"],
    )

    result = run_agent(state, "如果一直这样，团队每周都会多花半天时间，而且经常错过最佳验证窗口")

    assert result.reply_mode == "local"
    assert result.state_patch["validation_focus"] == "frequency"
    assert result.state_patch["validation_step"] == 3
    assert result.state_patch["conversation_strategy"] == "confirm"
    assert result.state_patch["pending_confirmations"] == ["是否把这个问题定义为当前最值得优先验证的问题"]
    assert "基于你刚才补的频率和损失，我现在倾向判断这是一个值得优先推进的问题" in result.reply
    assert "如果你确认，我下一步就直接开始压缩最小验证方案" in result.reply
    assert result.turn_decision is not None
    assert result.turn_decision.conversation_strategy == "confirm"
    assert result.turn_decision.phase_goal == "确认是否把该问题作为当前优先验证对象"
    assert result.turn_decision.next_move == "summarize_and_confirm"
    assert result.turn_decision.needs_confirmation == ["是否把这个问题定义为当前最值得优先验证的问题"]


def test_run_agent_closes_conversion_resistance_validation_with_local_verdict_and_confirm_gate():
    state = _phase1_state(
        conversation_strategy="converge",
        target_user="独立创业者",
        problem="不知道先验证哪个需求",
        solution="通过连续追问沉淀结构化 PRD",
        mvp_scope=["创建会话、持续追问、导出 PRD"],
        phase_goal="确认首要阻力是否直接打断转化",
        stage_hint="转化阻力影响确认",
        validation_focus="conversion_resistance",
        validation_step=2,
        evidence=["转化阻力线索：大多数人会卡在第一次接入"],
    )

    result = run_agent(state, "一旦卡住，大多数人就会先放弃，等以后再说，少数人会直接去找人工替代")

    assert result.reply_mode == "local"
    assert result.state_patch["validation_focus"] == "conversion_resistance"
    assert result.state_patch["validation_step"] == 3
    assert result.state_patch["conversation_strategy"] == "confirm"
    assert result.state_patch["pending_confirmations"] == ["是否把这个阻力定义为当前最值得优先验证的问题"]
    assert "基于你刚才补的阻力和流失结果，我现在倾向判断这是一个值得优先处理的转化阻力" in result.reply
    assert "如果你确认，我下一步就直接开始压缩最小验证方案" in result.reply
    assert result.turn_decision is not None
    assert result.turn_decision.conversation_strategy == "confirm"
    assert result.turn_decision.phase_goal == "确认是否把该阻力作为当前优先验证对象"
    assert result.turn_decision.next_move == "summarize_and_confirm"
    assert result.turn_decision.needs_confirmation == ["是否把这个阻力定义为当前最值得优先验证的问题"]


def test_run_agent_keeps_frequency_validation_step_when_reply_is_too_vague():
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

    result = run_agent(state, "差不多吧")

    assert result.reply_mode == "local"
    assert result.state_patch["validation_focus"] == "frequency"
    assert result.state_patch["validation_step"] == 1
    assert result.state_patch["conversation_strategy"] == "converge"
    assert "这轮回答还不足以支持我判断频率" in result.reply
    assert "请你不要再用“差不多”这种概括说法" in result.reply
    assert result.turn_decision is not None
    assert result.turn_decision.phase_goal == "明确问题发生频率是否足够高"
    assert result.turn_decision.next_best_questions == [
        "为了继续推进，请直接回答这个问题是每天、每周，还是偶发出现，并补一个最近一次真实场景。"
    ]


def test_run_agent_keeps_conversion_resistance_validation_step_when_reply_is_too_vague():
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

    result = run_agent(state, "还行吧")

    assert result.reply_mode == "local"
    assert result.state_patch["validation_focus"] == "conversion_resistance"
    assert result.state_patch["validation_step"] == 1
    assert result.state_patch["conversation_strategy"] == "converge"
    assert "这轮回答还不足以支持我判断转化阻力" in result.reply
    assert "请你不要再用“还行”这种概括说法" in result.reply
    assert result.turn_decision is not None
    assert result.turn_decision.phase_goal == "明确转化阻力集中在哪一环"
    assert result.turn_decision.next_best_questions == [
        "为了继续推进，请直接回答用户最容易卡在哪一步，并补一句卡住后通常是放弃、延后，还是转去其他替代方案。"
    ]


def test_run_agent_can_switch_from_frequency_to_conversion_resistance_locally():
    state = _phase1_state(
        conversation_strategy="converge",
        target_user="独立创业者",
        problem="不知道先验证哪个需求",
        solution="通过连续追问沉淀结构化 PRD",
        mvp_scope=["创建会话、持续追问、导出 PRD"],
        phase_goal="明确问题发生频率是否足够高",
        stage_hint="推进频率验证",
        validation_focus="frequency",
        validation_step=2,
        evidence=["频率线索：最近几乎每天都会发生"],
    )

    result = run_agent(state, "先别看频率，改看转化阻力")

    assert result.reply_mode == "local"
    assert result.state_patch["validation_focus"] == "conversion_resistance"
    assert result.state_patch["validation_step"] == 1
    assert result.state_patch["conversation_strategy"] == "converge"
    assert result.state_patch["stage_hint"] == "推进转化阻力验证"
    assert "我先停止继续看频率，切到“转化阻力验证”" in result.reply
    assert "请你直接告诉我用户现在最容易卡在哪一步" in result.reply
    assert result.turn_decision is not None
    assert result.turn_decision.phase_goal == "明确转化阻力集中在哪一环"
    assert result.turn_decision.next_best_questions == [
        "为了继续推进，请直接回答用户现在最容易卡在哪一步，是理解成本、接入成本，还是结果不够稳定。"
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


def test_run_agent_auto_generates_initial_prd_v1_and_critic_on_first_idea_input():
    state = {
        "idea": "我想做一个在线3D图纸预览平台",
        "workflow_stage": "idea_parser",
        "prd_snapshot": {"sections": {}},
    }

    result = run_agent(state, "我想做一个在线3D图纸预览平台")

    assert result.state_patch["workflow_stage"] == "refine_loop"
    assert result.state_patch["idea_parse_result"]["product_type"] == "在线3D图纸预览平台"
    assert result.state_patch["prd_draft"]["version"] == 1
    assert result.state_patch["prd_draft"]["status"] == "draft_hypothesis"
    assert result.state_patch["critic_result"]["overall_verdict"] in {"revise", "block"}
    assert result.state_patch["critic_result"]["question_queue"]
    assert result.turn_decision is not None
    assert result.turn_decision.next_best_questions


def test_run_agent_blocks_refine_loop_when_missing_critical_product_spec_items():
    state = {
        "workflow_stage": "refine_loop",
        "prd_draft": {
            "version": 1,
            "status": "draft_hypothesis",
            "sections": {},
            "assumptions": [],
            "missing_information": [
                "未明确核心文件格式",
                "未明确预览深度",
                "未明确权限边界",
            ],
            "critic_ready": True,
        },
    }

    result = run_agent(state, "继续")

    assert result.state_patch["critic_result"]["overall_verdict"] == "block"
    assert result.state_patch["finalization_ready"] is False


def test_run_agent_refine_loop_passes_when_missing_information_is_empty():
    state = {
        "workflow_stage": "refine_loop",
        "prd_draft": {
            "version": 1,
            "status": "draft_hypothesis",
            "sections": {},
            "assumptions": [],
            "missing_information": [],
            "critic_ready": True,
        },
    }

    result = run_agent(state, "继续")

    assert result.state_patch["critic_result"]["overall_verdict"] == "pass"
    assert result.state_patch["finalization_ready"] is True
    assert result.state_patch["workflow_stage"] == "finalize"


def test_run_agent_refine_loop_does_not_swallow_substantive_input():
    state = {
        "workflow_stage": "refine_loop",
        "prd_draft": {
            "version": 1,
            "status": "draft_hypothesis",
            "sections": {},
            "assumptions": [],
            "missing_information": [
                "未明确核心文件格式",
                "未明确预览深度",
            ],
            "critic_ready": True,
        },
    }

    result = run_agent(state, "首版先支持 DWG 和 IFC")

    assert result.reply_mode == "local"
    assert result.state_patch["prd_draft"]["version"] == 2
    assert result.state_patch["prd_draft"]["status"] == "draft_refined"
    assert "未明确核心文件格式" not in result.state_patch["prd_draft"]["missing_information"]
    assert "未明确预览深度" in result.state_patch["prd_draft"]["missing_information"]
    assert result.state_patch["critic_result"]["overall_verdict"] == "revise"
    assert result.state_patch["finalization_ready"] is False
    assert "refine_notes" in result.state_patch["prd_draft"]["sections"]


def test_run_agent_refine_loop_substantive_input_can_finish_last_gap_and_enter_finalize():
    state = {
        "workflow_stage": "refine_loop",
        "prd_draft": {
            "version": 1,
            "status": "draft_hypothesis",
            "sections": {},
            "assumptions": [],
            "missing_information": [
                "未明确核心文件格式",
            ],
            "critic_ready": True,
        },
    }

    result = run_agent(state, "首版先支持 DWG 和 IFC")

    assert result.state_patch["critic_result"]["overall_verdict"] == "pass"
    assert result.state_patch["finalization_ready"] is True
    assert result.state_patch["workflow_stage"] == "finalize"
    assert result.state_patch["prd_draft"]["version"] == 2
    assert result.state_patch["prd_draft"]["missing_information"] == []


def test_run_agent_refine_loop_does_not_clear_gap_for_non_answer_input():
    state = {
        "workflow_stage": "refine_loop",
        "prd_draft": {
            "version": 1,
            "status": "draft_hypothesis",
            "sections": {},
            "assumptions": [],
            "missing_information": [
                "尚未明确需要支持的图纸/模型格式与导入方式",
            ],
            "critic_ready": True,
        },
        "critic_result": {
            "overall_verdict": "block",
            "question_queue": ["首版必须支持哪些文件格式？"],
        },
    }

    result = run_agent(state, "还没想好")

    assert result.state_patch["prd_draft"]["version"] == 2
    assert result.state_patch["prd_draft"]["missing_information"] == [
        "尚未明确需要支持的图纸/模型格式与导入方式",
    ]
    assert result.state_patch["critic_result"]["overall_verdict"] == "revise"
    assert result.state_patch["finalization_ready"] is False
    assert result.state_patch.get("workflow_stage") != "finalize"


def test_run_agent_refine_loop_can_resolve_real_initial_draft_question_style_gap():
    state = {
        "workflow_stage": "refine_loop",
        "prd_draft": {
            "version": 1,
            "status": "draft_hypothesis",
            "sections": {},
            "assumptions": [],
            "missing_information": [
                "需要支持哪些图纸格式？",
                "如何规划不同角色的权限访问？",
            ],
            "critic_ready": True,
        },
        "critic_result": {
            "overall_verdict": "block",
            "question_queue": ["首版必须支持哪些文件格式？例如 DWG/DXF/PDF/IFC/STEP/GLTF 等，优先级如何？"],
        },
    }

    result = run_agent(state, "第一版先支持 STEP 和 OBJ")

    assert result.state_patch["prd_draft"]["version"] == 2
    assert "需要支持哪些图纸格式？" not in result.state_patch["prd_draft"]["missing_information"]
    assert "如何规划不同角色的权限访问？" in result.state_patch["prd_draft"]["missing_information"]
    assert result.state_patch["critic_result"]["overall_verdict"] == "revise"
    assert result.state_patch["finalization_ready"] is False


def test_run_agent_refine_loop_does_not_clear_permission_gap_for_uncertain_answer():
    state = {
        "workflow_stage": "refine_loop",
        "prd_draft": {
            "version": 1,
            "status": "draft_hypothesis",
            "sections": {},
            "assumptions": [],
            "missing_information": [
                "如何规划不同角色的权限访问？",
            ],
            "critic_ready": True,
        },
        "critic_result": {
            "overall_verdict": "block",
            "question_queue": ["权限怎么设计：访客、成员、管理员？是否需要外链分享与到期控制？"],
        },
    }

    result = run_agent(state, "权限这块我还没想好")

    assert result.state_patch["prd_draft"]["version"] == 2
    assert result.state_patch["prd_draft"]["missing_information"] == [
        "如何规划不同角色的权限访问？",
    ]
    assert result.state_patch["critic_result"]["overall_verdict"] == "revise"
    assert result.state_patch["finalization_ready"] is False
    assert result.state_patch["finalization_ready"] is False


def test_run_agent_finalize_flow_marks_completed_and_finalized():
    state = {
        "workflow_stage": "finalize",
        "prd_draft": {
            "version": 2,
            "status": "draft_refined",
            "sections": {
                "summary": {"title": "一句话概述", "content": "AI PRD 助手", "status": "confirmed"},
                "target_user": {"title": "目标用户", "content": "独立开发者", "status": "confirmed"},
                "problem": {"title": "核心问题", "content": "需求分散且难以收敛", "status": "confirmed"},
                "solution": {"title": "解决方案", "content": "通过对话持续沉淀 PRD", "status": "confirmed"},
                "mvp_scope": {"title": "MVP 范围", "content": "创建会话、持续追问、导出 PRD", "status": "confirmed"},
            },
            "assumptions": [],
            "missing_information": [],
            "critic_ready": True,
        },
        "critic_result": {
            "overall_verdict": "pass",
            "question_queue": [],
            "major_gaps": [],
        },
        "finalization_ready": True,
    }

    result = run_agent(state, "确认设计，按业务版输出")

    assert result.reply_mode == "local"
    assert result.state_patch["workflow_stage"] == "completed"
    assert result.state_patch["finalization_ready"] is True
    assert result.state_patch["prd_draft"]["status"] == "finalized"
    assert result.state_patch["prd_draft"]["finalize_preferences"] == "business"
    assert result.prd_patch["target_user"]["content"] == "独立开发者"
    assert result.prd_patch["solution"]["content"]


def test_run_agent_finalize_flow_rejects_when_critic_not_pass():
    state = {
        "workflow_stage": "finalize",
        "prd_draft": {
            "version": 2,
            "status": "draft_refined",
            "sections": {
                "summary": {"title": "一句话概述", "content": "AI PRD 助手", "status": "confirmed"},
            },
            "assumptions": [],
            "missing_information": ["还缺少成功指标"],
            "critic_ready": True,
        },
        "critic_result": {
            "overall_verdict": "revise",
            "question_queue": ["这个产品成功的判断标准是什么？"],
            "major_gaps": ["还缺少成功指标"],
        },
        "finalization_ready": False,
    }

    result = run_agent(state, "确认设计")

    assert result.reply_mode == "local"
    assert result.state_patch.get("workflow_stage") != "completed"
    assert result.prd_patch == {}
    assert "缺口" in result.reply or "先补齐" in result.reply


def test_run_agent_refine_loop_writes_answer_into_formal_sections():
    state = {
        "workflow_stage": "refine_loop",
        "prd_draft": {
            "version": 1,
            "status": "draft_hypothesis",
            "sections": {},
            "assumptions": [],
            "missing_information": ["未明确核心文件格式"],
            "critic_ready": True,
        },
        "critic_result": {
            "overall_verdict": "block",
            "question_queue": ["首版必须支持哪些文件格式？"],
        },
    }

    result = run_agent(state, "第一版支持 STEP 和 OBJ")

    assert result.reply_mode == "local"
    assert result.state_patch["prd_draft"]["version"] == 2
    assert "未明确核心文件格式" not in result.state_patch["prd_draft"]["missing_information"]

    sections = result.state_patch["prd_draft"]["sections"]
    assert "refine_notes" in sections
    assert any(
        "STEP" in str(section.get("content", "")) or "OBJ" in str(section.get("content", ""))
        for key, section in sections.items()
        if key != "refine_notes" and isinstance(section, dict)
    )


def test_run_agent_finalize_flow_supports_technical_preference():
    state = {
        "workflow_stage": "finalize",
        "prd_draft": {
            "version": 2,
            "status": "draft_refined",
            "sections": {
                "summary": {"title": "一句话概述", "content": "在线 3D 图纸预览平台", "status": "confirmed"},
                "solution": {"title": "解决方案", "content": "提供在线预览能力", "status": "confirmed"},
                "constraints": {"title": "约束条件", "content": "首版优先支持浏览器端", "status": "confirmed"},
            },
            "assumptions": [],
            "missing_information": [],
            "critic_ready": True,
        },
        "critic_result": {
            "overall_verdict": "pass",
            "question_queue": [],
            "major_gaps": [],
        },
        "finalization_ready": True,
    }

    result = run_agent(state, "确认设计，按技术细节版输出")

    assert result.state_patch["prd_draft"]["status"] == "finalized"
    assert result.state_patch["prd_draft"]["finalize_preferences"] == "technical"
