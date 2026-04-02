from typing import get_args

from app.agent.prompts import PROBE_TARGET_USER_REPLY, SUMMARIZE_UNDERSTANDING_REPLY
from app.agent.runtime import decide_next_action, run_agent
from app.agent.types import ActionTarget


def test_action_target_only_exposes_currently_supported_target():
    assert get_args(ActionTarget) == ("target_user",)


def test_decide_next_action_prefers_probe_when_target_user_missing():
    state = {
        "idea": "做一个 AI Co-founder",
        "target_user": None,
        "problem": None,
        "solution": None,
    }
    action = decide_next_action(state, "我想做一个帮助创业者梳理想法的产品")
    assert action.action == "probe_deeper"
    assert action.target == "target_user"


def test_decide_next_action_summarizes_when_target_user_exists():
    state = {
        "idea": "做一个 AI Co-founder",
        "target_user": "独立创业者",
        "problem": None,
        "solution": None,
    }

    action = decide_next_action(state, "我想先收敛需求")

    assert action.action == "summarize_understanding"
    assert action.target is None


def test_run_agent_returns_probe_reply_and_empty_patches_when_target_user_missing():
    state = {
        "idea": "做一个 AI Co-founder",
        "target_user": None,
        "problem": None,
        "solution": None,
    }

    result = run_agent(state, "我想做一个帮助创业者梳理想法的产品")

    assert result.reply == PROBE_TARGET_USER_REPLY
    assert result.action.action == "probe_deeper"
    assert result.action.target == "target_user"
    assert result.state_patch == {}
    assert result.prd_patch == {}
    assert result.decision_log == []


def test_run_agent_returns_summary_reply_when_target_user_exists():
    state = {
        "idea": "做一个 AI Co-founder",
        "target_user": "独立创业者",
        "problem": None,
        "solution": None,
    }

    result = run_agent(state, "继续")

    assert result.reply == SUMMARIZE_UNDERSTANDING_REPLY
    assert result.action.action == "summarize_understanding"
    assert result.action.target is None
