from unittest.mock import MagicMock, patch

from app.agent.runtime import run_agent
from app.agent.types import AgentResult, NextAction, TurnDecision


def test_run_agent_completed_stage_returns_local_reply():
    state = {"workflow_stage": "completed"}
    result = run_agent(state, "继续")
    assert result.reply_mode == "local"
    assert result.turn_decision is not None
    assert result.turn_decision.phase == "completed"


def test_run_agent_no_model_config_returns_fallback():
    state = {}
    result = run_agent(state, "我想做一个应用", model_config=None)
    assert result.reply_mode == "local"
    assert result.turn_decision is not None
    assert result.reply  # non-empty fallback message


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
        result = run_agent({}, "hello", model_config=mock_config)
        mock_pm.assert_called_once()

    assert result.reply == "mentor reply"
