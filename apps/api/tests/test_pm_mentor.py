import json
import re
from unittest.mock import MagicMock, patch


def _make_suggestion(
    label: str,
    content: str,
    *,
    priority: int,
    suggestion_type: str = "direction",
) -> dict[str, object]:
    return {
        "type": suggestion_type,
        "label": label,
        "content": content,
        "rationale": f"{label} 更适合作为当前回合的推进方向。",
        "priority": priority,
    }


def _make_pm_output(*, suggestions: list[dict[str, object]]) -> dict[str, object]:
    return {
        "observation": "用户已经给出一个初步产品想法，但还没有选定最适合继续展开的切入口。",
        "challenge": "如果不把下一步切入口收敛下来，对话很容易继续发散。",
        "suggestion": "这一轮应该给用户完整可发送的四个引导项，帮助快速继续。",
        "question": "你想先从哪个方向继续？",
        "reply": "我先给你四个可以直接继续的方向，你选一个最接近你的即可。",
        "prd_updates": {},
        "confidence": "medium",
        "next_focus": "problem",
        "next_move": "force_rank_or_choose",
        "recommendation": {"label": suggestions[0]["label"]},
        "suggestions": suggestions,
    }


def _build_mock_model_config() -> MagicMock:
    mock_config = MagicMock()
    mock_config.base_url = "http://fake"
    mock_config.api_key = "key"
    mock_config.model = "gpt-4"
    return mock_config


def _is_sendable_user_draft(content: str) -> bool:
    normalized = content.strip()
    if not normalized:
        return False
    if not normalized.endswith(("。", "！", "？")):
        return False
    if not re.match(r"^(我|先|请|麻烦|可以|直接|你先)", normalized):
        return False
    return bool(re.search(r"(想|要|请|帮|补充|明确|比较|说明|列|确认|继续|直接)", normalized))


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


def test_build_repair_prompt_uses_raw_suggestion_count():
    from app.agent.pm_mentor import _build_repair_prompt
    from app.agent.types import PmMentorOutput, Suggestion

    mentor_output = PmMentorOutput(
        observation="obs",
        challenge="challenge",
        suggestion="suggestion",
        question="question",
        reply="reply",
        confidence="medium",
        next_focus="problem",
        raw_suggestion_count=5,
        suggestions=[
            Suggestion(
                type="direction",
                label="先聊目标用户",
                content="我想先明确，这个产品第一版最想服务谁。",
                rationale="先锁定目标用户。",
                priority=1,
            ),
            Suggestion(
                type="direction",
                label="先聊核心问题",
                content="我想先讲清楚，这个产品到底想解决什么具体麻烦。",
                rationale="先把问题说透。",
                priority=2,
            ),
            Suggestion(
                type="direction",
                label="先聊核心功能",
                content="我想先列一下，我脑子里已经想到的核心功能。",
                rationale="先明确能力主线。",
                priority=3,
            ),
            Suggestion(
                type="direction",
                label="我直接补充",
                content="我不想选项，我直接补充我现在对这个产品的想法。",
                rationale="保留自由补充入口。",
                priority=4,
            ),
        ],
        recommendation={"label": "先聊目标用户", "content": "我想先明确，这个产品第一版最想服务谁。"},
    )

    prompt = _build_repair_prompt({}, "我想做一个任务管理工具", mentor_output)
    data = json.loads(prompt)

    assert data["invalid_output"]["suggestion_count"] == 5


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
    assert len(result.turn_decision.suggestions) == 4
    assert result.turn_decision.recommendation is not None
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


def test_run_pm_mentor_main_path_preserves_four_llm_suggestions():
    from app.agent.pm_mentor import run_pm_mentor

    fake_llm_output = _make_pm_output(
        suggestions=[
            _make_suggestion("先聊目标用户", "我想先明确，这个产品第一版最想服务谁。", priority=1),
            _make_suggestion("先聊核心问题", "我想先讲清楚，这个产品到底想解决什么具体麻烦。", priority=2),
            _make_suggestion("先聊核心功能", "我想先列一下，我脑子里已经想到的核心功能。", priority=3),
            _make_suggestion("我直接补充", "我不想选项，我直接补充我现在对这个产品的想法。", priority=4),
        ]
    )

    with patch("app.agent.pm_mentor.call_pm_mentor_llm", return_value=fake_llm_output) as mock_llm:
        result = run_pm_mentor({}, "我想做一个面向团队协作的任务工具", _build_mock_model_config())

    assert mock_llm.call_count == 1
    assert result.turn_decision is not None
    assert len(result.turn_decision.suggestions) == 4
    assert result.turn_decision.recommendation is not None
    assert result.turn_decision.next_best_questions == [
        item.content for item in result.turn_decision.suggestions
    ]


def test_run_pm_mentor_recommendation_must_belong_to_final_suggestions():
    from app.agent.pm_mentor import run_pm_mentor

    fake_llm_output = _make_pm_output(
        suggestions=[
            _make_suggestion("先聊目标用户", "我想先明确，这个产品第一版最想服务谁。", priority=1),
            _make_suggestion("先聊核心问题", "我想先讲清楚，这个产品到底想解决什么具体麻烦。", priority=2),
            _make_suggestion("先聊核心功能", "我想先列一下，我脑子里已经想到的核心功能。", priority=3),
            _make_suggestion("我直接补充", "我不想选项，我直接补充我现在对这个产品的想法。", priority=4),
        ]
    )
    fake_llm_output["recommendation"] = {
        "label": "游离推荐",
        "content": "我想先聊一个不在四个选项里的方向。",
    }

    with patch("app.agent.pm_mentor.call_pm_mentor_llm", return_value=fake_llm_output):
        result = run_pm_mentor({}, "我想做一个面向团队协作的任务工具", _build_mock_model_config())

    assert result.turn_decision is not None
    assert result.turn_decision.recommendation is not None
    final_pairs = {
        (item.label, item.content)
        for item in result.turn_decision.suggestions
    }
    assert (
        result.turn_decision.recommendation["label"],
        result.turn_decision.recommendation["content"],
    ) in final_pairs


def test_run_pm_mentor_treats_raw_more_than_four_suggestions_as_contract_failure():
    from app.agent.pm_mentor import run_pm_mentor

    first_output = _make_pm_output(
        suggestions=[
            _make_suggestion("先聊目标用户", "我想先明确，这个产品第一版最想服务谁。", priority=1),
            _make_suggestion("先聊核心问题", "我想先讲清楚，这个产品到底想解决什么具体麻烦。", priority=2),
            _make_suggestion("先聊核心功能", "我想先列一下，我脑子里已经想到的核心功能。", priority=3),
            _make_suggestion("我直接补充", "我不想选项，我直接补充我现在对这个产品的想法。", priority=4),
            _make_suggestion("先聊竞品", "我想先比较一下，现有竞品和这个产品的差异。", priority=5),
        ]
    )
    second_output = _make_pm_output(
        suggestions=[
            _make_suggestion("先聊目标用户", "我想先明确，这个产品第一版最想服务谁。", priority=1),
            _make_suggestion("先聊核心问题", "我想先讲清楚，这个产品到底想解决什么具体麻烦。", priority=2),
            _make_suggestion("先聊核心功能", "我想先列一下，我脑子里已经想到的核心功能。", priority=3),
            _make_suggestion("我直接补充", "我不想选项，我直接补充我现在对这个产品的想法。", priority=4),
        ]
    )

    with patch("app.agent.pm_mentor.call_pm_mentor_llm", side_effect=[first_output, second_output]) as mock_llm:
        result = run_pm_mentor({}, "我想做一个面向团队协作的任务工具", _build_mock_model_config())

    assert mock_llm.call_count == 2
    assert result.turn_decision is not None
    assert len(result.turn_decision.suggestions) == 4


def test_run_pm_mentor_retries_once_when_first_llm_response_has_fewer_than_four_suggestions():
    from app.agent.pm_mentor import run_pm_mentor

    first_output = _make_pm_output(
        suggestions=[
            _make_suggestion("先聊目标用户", "我想先明确，这个产品第一版最想服务谁。", priority=1),
            _make_suggestion("先聊核心问题", "我想先讲清楚，这个产品到底想解决什么具体麻烦。", priority=2),
            _make_suggestion("先聊核心功能", "我想先列一下，我脑子里已经想到的核心功能。", priority=3),
        ]
    )
    second_output = _make_pm_output(
        suggestions=[
            _make_suggestion("先聊目标用户", "我想先明确，这个产品第一版最想服务谁。", priority=1),
            _make_suggestion("先聊核心问题", "我想先讲清楚，这个产品到底想解决什么具体麻烦。", priority=2),
            _make_suggestion("先聊核心功能", "我想先列一下，我脑子里已经想到的核心功能。", priority=3),
            _make_suggestion("我直接补充", "我不想选项，我直接补充我现在对这个产品的想法。", priority=4),
        ]
    )

    with patch("app.agent.pm_mentor.call_pm_mentor_llm", side_effect=[first_output, second_output]) as mock_llm:
        result = run_pm_mentor({}, "我想做一个面向团队协作的任务工具", _build_mock_model_config())

    assert mock_llm.call_count == 2
    assert result.turn_decision is not None
    assert len(result.turn_decision.suggestions) == 4


def test_run_pm_mentor_uses_programmatic_fallback_after_two_broken_llm_responses():
    from app.agent.pm_mentor import run_pm_mentor

    first_output = _make_pm_output(
        suggestions=[
            _make_suggestion("先聊目标用户", "我想先明确，这个产品第一版最想服务谁。", priority=1),
            _make_suggestion("先聊核心问题", "我想先讲清楚，这个产品到底想解决什么具体麻烦。", priority=2),
            _make_suggestion("先聊核心功能", "我想先列一下，我脑子里已经想到的核心功能。", priority=3),
        ]
    )
    second_output = _make_pm_output(
        suggestions=[
            _make_suggestion("先聊目标用户", "我想先明确，这个产品第一版最想服务谁。", priority=1),
            _make_suggestion("先聊核心问题", "我想先讲清楚，这个产品到底想解决什么具体麻烦。", priority=2),
        ]
    )

    with patch("app.agent.pm_mentor.call_pm_mentor_llm", side_effect=[first_output, second_output]) as mock_llm:
        result = run_pm_mentor({}, "我想做一个面向团队协作的任务工具", _build_mock_model_config())

    assert mock_llm.call_count == 2
    assert result.turn_decision is not None
    assert len(result.turn_decision.suggestions) == 4
    original_pairs = {
        (item["label"], item["content"])
        for item in second_output["suggestions"]
    }
    final_pairs = {
        (item.label, item.content)
        for item in result.turn_decision.suggestions
    }
    assert original_pairs <= final_pairs

    added_items = [
        item for item in result.turn_decision.suggestions
        if (item.label, item.content) not in original_pairs
    ]
    assert len(added_items) == 2
    for item in added_items:
        assert item.label.strip()
        assert _is_sendable_user_draft(item.content)


def test_run_pm_mentor_suggestion_content_must_be_sendable_complete_sentences():
    from app.agent.pm_mentor import run_pm_mentor

    fake_llm_output = _make_pm_output(
        suggestions=[
            _make_suggestion("目标用户方向", "围绕目标用户展开", priority=1),
            _make_suggestion("核心问题方向", "继续聊核心问题", priority=2),
            _make_suggestion("功能收敛方向", "先收敛功能", priority=3),
            _make_suggestion("自由补充方向", "自由补充想法", priority=4),
        ]
    )

    with patch("app.agent.pm_mentor.call_pm_mentor_llm", return_value=fake_llm_output):
        result = run_pm_mentor({}, "我想做一个面向团队协作的任务工具", _build_mock_model_config())

    assert result.turn_decision is not None
    assert len(result.turn_decision.suggestions) == 4
    for item in result.turn_decision.suggestions:
        assert _is_sendable_user_draft(item.content)
    assert result.turn_decision.recommendation is not None
    assert _is_sendable_user_draft(result.turn_decision.recommendation["content"])


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
    assert len(result.turn_decision.suggestions) == 4
    assert result.turn_decision.recommendation is not None
    assert result.turn_decision.next_best_questions == [
        item.content for item in result.turn_decision.suggestions
    ]
