from unittest.mock import MagicMock, patch

from app.agent.runtime import run_agent
from app.agent.types import AgentResult, NextAction, TurnDecision


def test_run_agent_completed_stage_returns_local_reply():
    state = {"workflow_stage": "completed"}
    result = run_agent(state, "继续")
    assert result.reply_mode == "local"
    assert result.turn_decision is not None
    assert result.turn_decision.phase == "completed"


def test_run_agent_reopens_completed_workflow_for_followup_edit():
    state = {
        "workflow_stage": "completed",
        "iteration": 8,
        "prd_snapshot": {
            "sections": {
                "problem": {
                    "title": "核心问题",
                    "content": "旧问题",
                    "status": "confirmed",
                }
            }
        },
    }
    mock_config = MagicMock()
    mock_result = AgentResult(
        reply="收到，我们继续修改目标用户。",
        action=NextAction(action="probe_deeper", target=None, reason="继续修改"),
        reply_mode="local",
        turn_decision=TurnDecision(
            phase="target_user",
            phase_goal="重新澄清目标用户",
            understanding={"summary": "用户想修改目标用户", "candidate_updates": {}, "ambiguous_points": []},
            assumptions=[],
            gaps=[],
            challenges=[],
            pm_risk_flags=[],
            next_move="probe_for_specificity",
            suggestions=[],
            recommendation=None,
            reply_brief={},
            state_patch={"workflow_stage": "refine_loop"},
            prd_patch={},
            needs_confirmation=[],
            confidence="medium",
            conversation_strategy="clarify",
        ),
    )

    with patch("app.agent.pm_mentor.run_pm_mentor", return_value=mock_result) as mock_pm:
        result = run_agent(state, "我想改一下目标用户", model_config=mock_config)

    mock_pm.assert_called_once()
    assert result.reply == "收到，我们继续修改目标用户。"


def test_run_agent_reopens_completed_workflow_before_delegating_to_pm_mentor():
    state = {
        "workflow_stage": "completed",
        "finalization_ready": True,
        "pending_confirmations": ["请确认是否进入终稿"],
        "critic_result": {"overall_verdict": "pass", "question_queue": []},
        "prd_snapshot": {
            "sections": {
                "problem": {"title": "核心问题", "content": "旧问题", "status": "confirmed"},
                "solution": {"title": "解决方案", "content": "旧方案", "status": "confirmed"},
            }
        },
    }
    mock_config = MagicMock()
    captured = {}
    mock_result = AgentResult(
        reply="收到，进入修改模式。",
        action=NextAction(action="probe_deeper", target=None, reason="继续修改"),
        reply_mode="local",
        turn_decision=TurnDecision(
            phase="problem",
            phase_goal="重开澄清",
            understanding={"summary": "用户继续编辑", "candidate_updates": {}, "ambiguous_points": []},
            assumptions=[],
            gaps=[],
            challenges=[],
            pm_risk_flags=[],
            next_move="probe_for_specificity",
            suggestions=[],
            recommendation=None,
            reply_brief={},
            state_patch={"workflow_stage": "refine_loop"},
            prd_patch={},
            needs_confirmation=[],
            confidence="medium",
            conversation_strategy="clarify",
        ),
    )

    def _fake_run_pm_mentor(state_arg, user_input, model_config, *, conversation_history=None):
        captured["state"] = state_arg
        captured["user_input"] = user_input
        return mock_result

    with patch("app.agent.pm_mentor.run_pm_mentor", side_effect=_fake_run_pm_mentor):
        result = run_agent(state, "我想把核心问题改成自动化效率问题", model_config=mock_config)

    assert captured["state"]["workflow_stage"] == "refine_loop"
    assert captured["state"]["finalization_ready"] is False
    assert captured["state"]["pending_confirmations"] == []
    assert captured["state"]["critic_result"] is None
    assert result.reply == "收到，进入修改模式。"


def test_run_agent_finalize_stage_with_confirmation_returns_finalize_action():
    state = {
        "workflow_stage": "finalize",
        "finalization_ready": True,
    }

    result = run_agent(state, "确认无误，输出最终版，偏技术", model_config=MagicMock())

    assert result.reply_mode == "local"
    assert result.action.action == "finalize"
    assert result.action.reason == "用户确认进入终稿"
    assert result.state_patch["workflow_stage"] == "finalize"
    assert result.state_patch["finalization_ready"] is True
    assert result.state_patch["finalize_preference"] == "technical"
    assert result.state_patch["finalize_confirmation_source"] == "message"
    assert result.turn_decision is not None
    assert result.turn_decision.phase == "finalize"


def test_run_agent_routes_pm_mentor_result_to_finalize_via_readiness():
    mock_config = MagicMock()
    mock_result = AgentResult(
        reply="信息已经完整。",
        action=NextAction(action="probe_deeper", target=None, reason="继续确认"),
        reply_mode="local",
        state_patch={"stage_hint": "done"},
        prd_patch={
            "target_user": {"title": "目标用户", "content": "独立开发者", "status": "confirmed"},
            "problem": {"title": "核心问题", "content": "任务分散", "status": "confirmed"},
            "solution": {"title": "解决方案", "content": "统一任务面板", "status": "confirmed"},
            "mvp_scope": {"title": "MVP 范围", "content": "任务录入+提醒", "status": "confirmed"},
            "constraints": {"title": "约束条件", "content": "首版仅 Web", "status": "confirmed"},
            "success_metrics": {"title": "成功指标", "content": "7 日留存 > 20%", "status": "confirmed"},
        },
        turn_decision=TurnDecision(
            phase="done",
            phase_goal="确认是否收口",
            understanding={"summary": "信息趋于完整", "candidate_updates": {}, "ambiguous_points": []},
            assumptions=[],
            gaps=[],
            challenges=[],
            pm_risk_flags=[],
            next_move="summarize_and_confirm",
            suggestions=[],
            recommendation=None,
            reply_brief={},
            state_patch={"stage_hint": "done"},
            prd_patch={},
            needs_confirmation=[],
            confidence="high",
            conversation_strategy="confirm",
        ),
    )

    with patch("app.agent.pm_mentor.run_pm_mentor", return_value=mock_result):
        result = run_agent(
            {"prd_snapshot": {"sections": {}}},
            "我们先收口一下",
            model_config=mock_config,
        )

    assert result.state_patch["workflow_stage"] == "finalize"
    assert result.state_patch["finalization_ready"] is True
    assert result.turn_decision is not None
    assert result.turn_decision.state_patch["workflow_stage"] == "finalize"
    assert result.turn_decision.state_patch["finalization_ready"] is True


def test_run_agent_reopen_completed_turn_stays_in_refine_loop_even_if_readiness_ready():
    state = {
        "workflow_stage": "completed",
        "finalization_ready": True,
        "prd_snapshot": {
            "sections": {
                "target_user": {"title": "目标用户", "content": "独立开发者", "status": "confirmed"},
                "problem": {"title": "核心问题", "content": "任务分散", "status": "confirmed"},
                "solution": {"title": "解决方案", "content": "统一任务面板", "status": "confirmed"},
                "mvp_scope": {"title": "MVP 范围", "content": "任务录入+提醒", "status": "confirmed"},
                "constraints": {"title": "约束条件", "content": "首版仅 Web", "status": "confirmed"},
                "success_metrics": {"title": "成功指标", "content": "7 日留存 > 20%", "status": "confirmed"},
            }
        },
    }
    mock_config = MagicMock()
    mock_result = AgentResult(
        reply="收到，我们继续细化问题描述。",
        action=NextAction(action="probe_deeper", target=None, reason="继续修改"),
        reply_mode="local",
        state_patch={"stage_hint": "problem"},
        prd_patch={},
        turn_decision=TurnDecision(
            phase="problem",
            phase_goal="更新核心问题",
            understanding={"summary": "用户希望改动问题描述", "candidate_updates": {}, "ambiguous_points": []},
            assumptions=[],
            gaps=[],
            challenges=[],
            pm_risk_flags=[],
            next_move="probe_for_specificity",
            suggestions=[],
            recommendation=None,
            reply_brief={},
            state_patch={"stage_hint": "problem"},
            prd_patch={},
            needs_confirmation=[],
            confidence="medium",
            conversation_strategy="clarify",
        ),
    )

    with patch("app.agent.pm_mentor.run_pm_mentor", return_value=mock_result):
        result = run_agent(state, "我想改一下核心问题的描述", model_config=mock_config)

    assert result.state_patch["workflow_stage"] == "refine_loop"
    assert result.state_patch["finalization_ready"] is True
    assert result.turn_decision is not None
    assert result.turn_decision.state_patch["workflow_stage"] == "refine_loop"


def test_run_agent_finalize_confirmation_still_returns_finalize_action_without_model_config():
    state = {
        "workflow_stage": "finalize",
        "finalization_ready": True,
    }

    result = run_agent(state, "确认设计，输出最终版", model_config=None)

    assert result.reply_mode == "local"
    assert result.action.action == "finalize"
    assert result.turn_decision is not None
    assert result.turn_decision.phase == "finalize"


def test_run_agent_no_model_config_returns_fallback():
    state = {}
    result = run_agent(state, "我想做一个应用", model_config=None)
    assert result.reply_mode == "local"
    assert result.turn_decision is not None
    assert result.reply  # non-empty fallback message


def test_run_agent_greeting_returns_structured_suggestions():
    state = {"iteration": 0}
    result = run_agent(state, "你好", model_config=MagicMock())

    assert result.reply_mode == "local"
    assert result.turn_decision is not None
    assert result.turn_decision.phase == "greeting"
    assert len(result.turn_decision.suggestions) == 4
    assert result.turn_decision.conversation_strategy == "greet"
    assert result.turn_decision.recommendation is not None
    assert result.turn_decision.next_best_questions == [
        item.content for item in result.turn_decision.suggestions
    ]


def test_run_agent_completed_stage_returns_four_suggestions():
    state = {
        "workflow_stage": "completed",
        "prd_snapshot": {
            "sections": {
                "problem": {"title": "核心问题", "status": "confirmed"},
                "solution": {"title": "解决方案", "status": "confirmed"},
            }
        },
    }

    result = run_agent(state, "继续", model_config=MagicMock())

    assert result.turn_decision is not None
    assert result.turn_decision.phase == "completed"
    assert len(result.turn_decision.suggestions) == 4
    assert result.turn_decision.recommendation is not None
    assert result.turn_decision.next_best_questions == [
        item.content for item in result.turn_decision.suggestions
    ]


def test_run_agent_fallback_returns_four_suggestions():
    result = run_agent({}, "我想做一个应用", model_config=None)

    assert result.turn_decision is not None
    assert len(result.turn_decision.suggestions) == 4
    assert result.turn_decision.recommendation is not None
    assert result.turn_decision.next_best_questions == [
        item.content for item in result.turn_decision.suggestions
    ]


def test_run_agent_delegates_to_pm_mentor_when_model_config_given():
    mock_config = MagicMock()
    mock_td = TurnDecision(
        phase="problem", phase_goal="q?",
        understanding={"summary": "x", "candidate_updates": {}, "ambiguous_points": []},
        assumptions=[], gaps=[], challenges=[], pm_risk_flags=[],
        next_move="probe_for_specificity", suggestions=[], recommendation=None,
        reply_brief={}, state_patch={}, prd_patch={}, needs_confirmation=[],
        confidence="medium", conversation_strategy="clarify",
    )
    mock_result = AgentResult(
        reply="mentor reply",
        action=NextAction(action="probe_deeper", target=None, reason="test"),
        reply_mode="local",
        turn_decision=mock_td,
    )

    with patch("app.agent.pm_mentor.run_pm_mentor", return_value=mock_result) as mock_pm:
        result = run_agent({}, "我想做一个任务管理工具", model_config=mock_config)
        mock_pm.assert_called_once()

    assert result.reply == "mentor reply"
