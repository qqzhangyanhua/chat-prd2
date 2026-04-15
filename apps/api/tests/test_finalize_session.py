from unittest.mock import MagicMock, patch

from app.agent.runtime import run_agent
from app.agent.types import AgentResult, NextAction, TurnDecision


def _mock_completed_result(reply: str = "好的，已进入 completed。") -> AgentResult:
    return AgentResult(
        reply=reply,
        action=NextAction(action="summarize_understanding", target=None, reason="完成"),
        reply_mode="local",
        turn_decision=TurnDecision(
            phase="done",
            phase_goal="完成并归档",
            understanding={"summary": "用户确认完成", "candidate_updates": {}, "ambiguous_points": []},
            assumptions=[],
            gaps=[],
            challenges=[],
            pm_risk_flags=[],
            next_move="summarize_and_confirm",
            suggestions=[],
            recommendation=None,
            reply_brief={},
            state_patch={"workflow_stage": "completed"},
            prd_patch={},
            needs_confirmation=[],
            confidence="high",
            conversation_strategy="confirm",
        ),
    )


def _mock_refine_result(reply: str = "我们继续补齐细节。") -> AgentResult:
    return AgentResult(
        reply=reply,
        action=NextAction(action="probe_deeper", target=None, reason="继续澄清"),
        reply_mode="local",
        turn_decision=TurnDecision(
            phase="refine_loop",
            phase_goal="补齐缺口",
            understanding={"summary": "继续澄清中", "candidate_updates": {}, "ambiguous_points": []},
            assumptions=[],
            gaps=["仍需确认关键信息"],
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


def test_run_agent_blocks_finalize_when_not_ready_even_if_user_confirms():
    state = {
        "workflow_stage": "finalize",
        "finalization_ready": False,
        "prd_snapshot": {
            "sections": {
                "target_user": {"title": "目标用户", "content": "独立开发者", "status": "confirmed"},
                "problem": {"title": "核心问题", "content": "需求确认成本高", "status": "confirmed"},
                "solution": {"title": "解决方案", "content": "AI 协作问答流", "status": "confirmed"},
                "mvp_scope": {"title": "MVP 范围", "content": "只做 Web 端", "status": "confirmed"},
                "constraints": {"title": "约束条件", "content": "", "status": "missing"},
                "success_metrics": {"title": "成功指标", "content": "", "status": "missing"},
            }
        },
    }

    with patch("app.agent.pm_mentor.run_pm_mentor", return_value=_mock_completed_result()):
        result = run_agent(state, "我确认，直接出最终版", model_config=MagicMock())

    assert result.turn_decision is not None
    assert result.turn_decision.state_patch.get("workflow_stage") != "completed"
    assert result.turn_decision.phase != "done"


def test_run_agent_allows_finalize_to_completed_when_ready_and_confirmation_source_present():
    state = {
        "workflow_stage": "finalize",
        "finalization_ready": True,
        "confirmation_source": "explicit_user_confirm",
        "prd_snapshot": {
            "sections": {
                "target_user": {"title": "目标用户", "content": "独立开发者", "status": "confirmed"},
                "problem": {"title": "核心问题", "content": "需求确认成本高", "status": "confirmed"},
                "solution": {"title": "解决方案", "content": "AI 协作问答流", "status": "confirmed"},
                "mvp_scope": {"title": "MVP 范围", "content": "只做 Web 端", "status": "confirmed"},
                "constraints": {"title": "约束条件", "content": "首版不做私有化", "status": "confirmed"},
                "success_metrics": {"title": "成功指标", "content": "7 天留存 >= 20%", "status": "confirmed"},
            }
        },
    }

    # 契约：ready 且有明确确认来源时，runtime 应允许 finalize 并强制进入 completed。
    with patch("app.agent.pm_mentor.run_pm_mentor", return_value=_mock_refine_result()):
        result = run_agent(state, "我确认，按这个版本收敛为终稿", model_config=MagicMock())

    assert result.turn_decision is not None
    assert result.turn_decision.state_patch.get("workflow_stage") == "completed"
    assert result.turn_decision.phase == "done"


def test_run_agent_blocks_finalize_without_explicit_confirmation_even_if_ready():
    state = {
        "workflow_stage": "finalize",
        "finalization_ready": True,
        "prd_snapshot": {
            "sections": {
                "target_user": {"title": "目标用户", "content": "独立开发者", "status": "confirmed"},
                "problem": {"title": "核心问题", "content": "需求确认成本高", "status": "confirmed"},
                "solution": {"title": "解决方案", "content": "AI 协作问答流", "status": "confirmed"},
                "mvp_scope": {"title": "MVP 范围", "content": "只做 Web 端", "status": "confirmed"},
                "constraints": {"title": "约束条件", "content": "首版不做私有化", "status": "confirmed"},
                "success_metrics": {"title": "成功指标", "content": "7 天留存 >= 20%", "status": "confirmed"},
            }
        },
    }

    with patch("app.agent.pm_mentor.run_pm_mentor", return_value=_mock_completed_result()):
        result = run_agent(state, "继续补充一个渠道假设", model_config=MagicMock())

    assert result.turn_decision is not None
    assert result.turn_decision.state_patch.get("workflow_stage") != "completed"
    assert result.turn_decision.phase != "done"
