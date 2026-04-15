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
