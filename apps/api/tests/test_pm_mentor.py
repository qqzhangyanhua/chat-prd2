import json
import pytest
from unittest.mock import MagicMock, patch


def test_parse_pm_mentor_output_full():
    from app.agent.pm_mentor import parse_pm_mentor_output
    raw = {
        "observation": "用户想做B2B SaaS",
        "challenge": "决策者还是执行者？",
        "suggestion": "先定义购买决策链",
        "question": "谁最终付费：HR总监还是员工？",
        "reply": "完整回复文本",
        "prd_updates": {"target_user": {"content": "HR总监", "status": "draft"}},
        "confidence": "medium",
        "next_focus": "target_user",
    }
    result = parse_pm_mentor_output(raw)
    assert result.observation == "用户想做B2B SaaS"
    assert result.prd_updates["target_user"]["status"] == "draft"
    assert result.confidence == "medium"
    assert result.reply == "完整回复文本"


def test_parse_pm_mentor_output_missing_reply_uses_fallback():
    from app.agent.pm_mentor import parse_pm_mentor_output
    raw = {
        "observation": "obs",
        "challenge": "ch",
        "suggestion": "sg",
        "question": "q?",
        "prd_updates": {},
        "confidence": "low",
        "next_focus": "problem",
        # "reply" is intentionally missing
    }
    result = parse_pm_mentor_output(raw)
    assert "obs" in result.reply
    assert "q?" in result.reply


def test_parse_pm_mentor_output_invalid_confidence_defaults_to_medium():
    from app.agent.pm_mentor import parse_pm_mentor_output
    raw = {
        "observation": "x", "challenge": "y", "suggestion": "z",
        "question": "q?", "reply": "r",
        "prd_updates": {}, "confidence": "unknown_value", "next_focus": "problem",
    }
    result = parse_pm_mentor_output(raw)
    assert result.confidence == "medium"


def test_build_user_prompt_includes_prd_sections():
    from app.agent.pm_mentor import _build_user_prompt
    state = {
        "prd_snapshot": {
            "sections": {"target_user": {"content": "HR总监", "status": "draft"}}
        },
        "iteration": 3,
    }
    prompt = _build_user_prompt(state, "我想加一个功能")
    data = json.loads(prompt)
    assert data["turn_count"] == 3
    assert "target_user" in data["current_prd"]["sections"]
    assert data["user_input"] == "我想加一个功能"


def test_build_user_prompt_missing_prd_snapshot():
    from app.agent.pm_mentor import _build_user_prompt
    state = {}
    prompt = _build_user_prompt(state, "测试")
    data = json.loads(prompt)
    assert data["current_prd"]["sections"] == {}
    assert data["turn_count"] == 0


def test_run_pm_mentor_calls_llm_and_returns_agent_result():
    from app.agent.pm_mentor import run_pm_mentor
    from app.agent.types import AgentResult

    fake_llm_output = {
        "observation": "用户想做任务管理工具",
        "challenge": "目标用户是个人还是团队？",
        "suggestion": "先锁定个人用户再扩展",
        "question": "你最想先服务的是个人用户还是小团队？",
        "reply": "你的想法很有意思。目标用户是个人还是团队？",
        "prd_updates": {"target_user": {"content": "待确认", "status": "missing"}},
        "confidence": "medium",
        "next_focus": "target_user",
    }

    mock_config = MagicMock()
    mock_config.base_url = "http://fake"
    mock_config.api_key = "key"
    mock_config.model = "gpt-4"

    with patch("app.agent.pm_mentor.call_pm_mentor_llm", return_value=fake_llm_output):
        result = run_pm_mentor({}, "我想做个任务管理工具", mock_config)

    assert isinstance(result, AgentResult)
    assert result.reply_mode == "local"
    assert result.reply  # non-empty
    assert result.turn_decision is not None
    assert result.state_patch.get("iteration") == 1


def test_run_pm_mentor_llm_failure_returns_fallback():
    from app.agent.pm_mentor import run_pm_mentor
    from app.services.model_gateway import ModelGatewayError

    mock_config = MagicMock()
    mock_config.base_url = "http://fake"
    mock_config.api_key = "key"
    mock_config.model = "gpt-4"

    with patch("app.agent.pm_mentor.call_pm_mentor_llm", side_effect=ModelGatewayError("timeout")):
        result = run_pm_mentor({}, "测试", mock_config)

    assert result.reply_mode == "local"
    assert result.reply  # fallback reply is non-empty
    assert result.turn_decision is not None
