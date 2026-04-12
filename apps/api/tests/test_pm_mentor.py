import json
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


def test_parse_pm_mentor_output_parses_structured_suggestions():
    from app.agent.pm_mentor import parse_pm_mentor_output

    raw = {
        "observation": "用户只给了模糊方向",
        "challenge": "现在还没有具体用户和场景",
        "suggestion": "先选一个更容易展开的切入口",
        "question": "你更想先从用户、问题还是场景开始？",
        "reply": "我先给你几个更容易展开的切入口。",
        "prd_updates": {},
        "confidence": "medium",
        "next_focus": "problem",
        "next_move": "force_rank_or_choose",
        "recommendation": {"label": "我知道用户是谁"},
        "suggestions": [
            {
                "type": "direction",
                "label": "我知道用户是谁",
                "content": "我已经大概知道想服务谁了，但还没想透他们最痛的问题。",
                "rationale": "先从用户入手更容易收敛。",
                "priority": 2,
            },
            {
                "type": "direction",
                "label": "我知道问题很痛",
                "content": "我已经感觉到这个问题很痛了，但目标用户还比较泛。",
                "rationale": "先从痛点入手更容易举例。",
                "priority": 1,
            },
        ],
    }
    result = parse_pm_mentor_output(raw)
    assert result.next_move == "force_rank_or_choose"
    assert [item.label for item in result.suggestions] == ["我知道问题很痛", "我知道用户是谁"]
    assert result.recommendation == {
        "label": "我知道用户是谁",
        "content": "我已经大概知道想服务谁了，但还没想透他们最痛的问题。",
    }


def test_parse_pm_mentor_output_ignores_invalid_suggestions():
    from app.agent.pm_mentor import parse_pm_mentor_output

    raw = {
        "observation": "obs",
        "challenge": "ch",
        "suggestion": "sg",
        "question": "q?",
        "reply": "reply",
        "prd_updates": {},
        "confidence": "medium",
        "next_focus": "problem",
        "suggestions": [
            {"label": "缺 type", "content": "x", "rationale": "y", "priority": 1},
            "bad",
        ],
    }
    result = parse_pm_mentor_output(raw)
    assert result.suggestions == []
    assert result.recommendation is None


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
    }
    result = parse_pm_mentor_output(raw)
    assert "obs" in result.reply
    assert "q?" in result.reply


def test_parse_pm_mentor_output_invalid_confidence_defaults_to_medium():
    from app.agent.pm_mentor import parse_pm_mentor_output

    raw = {
        "observation": "x",
        "challenge": "y",
        "suggestion": "z",
        "question": "q?",
        "reply": "r",
        "prd_updates": {},
        "confidence": "unknown_value",
        "next_focus": "problem",
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


def test_run_pm_mentor_uses_default_suggestions_for_low_information_input():
    from app.agent.pm_mentor import run_pm_mentor
    from app.agent.types import AgentResult

    fake_llm_output = {
        "observation": "用户只有模糊方向",
        "challenge": "现在还没有具体用户和场景",
        "suggestion": "先给用户几个容易回答的切入口",
        "question": "",
        "reply": "我先给你几个更容易展开的方向。",
        "prd_updates": {},
        "confidence": "medium",
        "next_focus": "problem",
    }

    mock_config = MagicMock()
    mock_config.base_url = "http://fake"
    mock_config.api_key = "key"
    mock_config.model = "gpt-4"

    with patch("app.agent.pm_mentor.call_pm_mentor_llm", return_value=fake_llm_output):
        result = run_pm_mentor({}, "我有个想法，但不知道怎么说", mock_config)

    assert isinstance(result, AgentResult)
    assert result.turn_decision is not None
    assert len(result.turn_decision.suggestions) == 3
    assert result.turn_decision.next_best_questions == [
        item.content for item in result.turn_decision.suggestions
    ]


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
        "suggestions": [
            {
                "type": "direction",
                "label": "先聊个人用户",
                "content": "我想先从个人用户的场景开始聊。",
                "rationale": "个人用户更容易快速举例。",
                "priority": 1,
            }
        ],
    }

    mock_config = MagicMock()
    mock_config.base_url = "http://fake"
    mock_config.api_key = "key"
    mock_config.model = "gpt-4"

    with patch("app.agent.pm_mentor.call_pm_mentor_llm", return_value=fake_llm_output):
        result = run_pm_mentor({}, "我想做个任务管理工具", mock_config)

    assert isinstance(result, AgentResult)
    assert result.reply_mode == "local"
    assert result.reply
    assert result.turn_decision is not None
    assert result.state_patch.get("iteration") == 1
    assert result.turn_decision.suggestions[0].label == "先聊个人用户"


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
    assert result.reply
    assert result.turn_decision is not None
    assert result.turn_decision.suggestions == []
    assert result.turn_decision.next_best_questions == []
