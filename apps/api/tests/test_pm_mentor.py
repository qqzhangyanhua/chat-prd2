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


def test_run_pm_mentor_emits_structured_prd_draft_entries_and_evidence_refs():
    from app.agent.pm_mentor import run_pm_mentor

    fake_llm_output = {
        "observation": "用户已经明确第一版先服务独立开发者。",
        "challenge": "还需要继续验证这个群体的第一痛点。",
        "suggestion": "先把目标用户和成功标准沉淀成首稿。",
        "question": "如果只保留一个最重要的成功标准，你最先看什么？",
        "reply": "我先把目前已确认和待验证的信息沉淀成首稿。",
        "prd_updates": {
            "target_user": {"content": "独立开发者", "status": "confirmed"},
            "success_metrics": {"content": "7 天内完成一次 PRD 初稿", "status": "draft"},
        },
        "confidence": "medium",
        "next_focus": "solution",
    }

    with patch("app.agent.pm_mentor.call_pm_mentor_llm", return_value=fake_llm_output):
        result = run_pm_mentor({}, "我想先服务独立开发者，后面再扩到小团队。", _build_mock_model_config())

    assert result.turn_decision is not None
    draft = result.turn_decision.state_patch["prd_draft"]
    assert draft["sections"]["target_user"]["entries"][0]["assertion_state"] == "confirmed"
    assert draft["sections"]["success_metrics"]["entries"][0]["assertion_state"] == "inferred"
    assert draft["sections"]["target_user"]["entries"][0]["evidence_ref_ids"]
    assert result.turn_decision.state_patch["evidence"][0]["kind"] in {"user_message", "system_inference"}


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


def test_run_pm_mentor_target_user_focus_generates_second_level_suggestions():
    from app.agent.pm_mentor import run_pm_mentor

    state = {
        "stage_hint": "target_user",
        "current_phase": "target_user",
        "prd_snapshot": {"sections": {}},
    }
    broken_output = _make_pm_output(
        suggestions=[
            _make_suggestion("先聊目标用户", "我想先明确，这个产品主要给谁用。", priority=1),
            _make_suggestion("先聊核心问题", "我想先讲清楚，这个产品到底想解决什么具体麻烦。", priority=2),
            _make_suggestion("先聊核心功能", "我想先列一下，我脑子里已经想到的这个产品核心功能。", priority=3),
            _make_suggestion("我直接补充", "我不想选项，我直接补充我现在对这个产品的想法。", priority=4),
        ]
    )

    with patch("app.agent.pm_mentor.call_pm_mentor_llm", return_value=broken_output):
        result = run_pm_mentor(state, "我想先明确这个产品主要给谁用", _build_mock_model_config())

    assert result.turn_decision is not None
    labels = [item.label for item in result.turn_decision.suggestions]
    assert "先聊核心问题" not in labels
    assert "先聊核心功能" not in labels
    assert any(
        "角色" in item.content or "场景" in item.content or "决策" in item.content
        for item in result.turn_decision.suggestions
    )


def test_run_pm_mentor_problem_focus_rejects_generic_top_level_menu():
    from app.agent.pm_mentor import run_pm_mentor

    state = {
        "stage_hint": "problem",
        "current_phase": "problem",
        "prd_snapshot": {"sections": {}},
    }
    broken_output = _make_pm_output(
        suggestions=[
            _make_suggestion("先聊目标用户", "我想先明确，这个产品主要给谁用。", priority=1),
            _make_suggestion("先聊核心问题", "我想先讲清楚，这个产品到底想解决什么具体麻烦。", priority=2),
            _make_suggestion("先聊核心功能", "我想先列一下，我脑子里已经想到的这个产品核心功能。", priority=3),
            _make_suggestion("我直接补充", "我不想选项，我直接补充我现在对这个产品的想法。", priority=4),
        ]
    )

    with patch("app.agent.pm_mentor.call_pm_mentor_llm", return_value=broken_output):
        result = run_pm_mentor(state, "我想先讲清楚这个产品到底解决什么问题", _build_mock_model_config())

    assert result.turn_decision is not None
    labels = [item.label for item in result.turn_decision.suggestions]
    assert "先聊目标用户" not in labels
    assert "先聊核心功能" not in labels
    assert any(
        "麻烦" in item.content or "高频" in item.content or "替代" in item.content or "场景" in item.content
        for item in result.turn_decision.suggestions
    )


def test_run_pm_mentor_problem_focus_marks_high_uncertainty_as_options_first():
    from app.agent.pm_mentor import run_pm_mentor

    state = {
        "stage_hint": "problem",
        "current_phase": "problem",
        "prd_snapshot": {"sections": {}},
    }
    broken_output = _make_pm_output(
        suggestions=[
            _make_suggestion("先讲高频麻烦", "我想先讲清楚，这个产品里最高频出现的那个麻烦是什么。", priority=1),
            _make_suggestion("先讲最痛一刻", "我想先描述用户最崩溃的一次具体场景，你帮我抽出核心问题。", priority=2),
            _make_suggestion("先讲替代方案", "我想先说说，用户现在是怎么勉强解决这个问题的。", priority=3),
            _make_suggestion("我直接补充", "我直接补充我现在对这个产品核心问题的判断。", priority=4),
        ]
    )

    with patch("app.agent.pm_mentor.call_pm_mentor_llm", return_value=broken_output):
        result = run_pm_mentor(state, "我还不确定到底哪个问题最值得先解决", _build_mock_model_config())

    assert result.turn_decision is not None
    assert result.turn_decision.response_mode == "options_first"
    assert result.turn_decision.guidance_mode == "explore"
    assert result.turn_decision.guidance_step == "choose"
    assert result.turn_decision.focus_dimension == "problem"
    assert result.turn_decision.transition_trigger == "high_uncertainty"
    assert result.turn_decision.transition_reason
    assert 2 <= len(result.turn_decision.option_cards) <= 4
    assert all(card["id"] for card in result.turn_decision.option_cards)
    assert result.turn_decision.freeform_affordance == {
        "label": "都不对，我补充",
        "value": "freeform",
        "kind": "freeform",
    }
    assert result.turn_decision.available_mode_switches


def test_run_pm_mentor_greeting_result_exposes_structured_guidance_contract():
    from app.agent.runtime import _build_greeting_result

    result = _build_greeting_result({"iteration": 0})

    assert result.turn_decision is not None
    assert result.turn_decision.response_mode == "options_first"
    assert result.turn_decision.guidance_mode == "explore"
    assert result.turn_decision.guidance_step == "choose"
    assert result.turn_decision.focus_dimension == "target_user"
    assert len(result.turn_decision.option_cards) == 4
    assert result.turn_decision.freeform_affordance == {
        "label": "都不对，我补充",
        "value": "freeform",
        "kind": "freeform",
    }


def test_run_pm_mentor_solution_focus_rejects_generic_top_level_menu():
    from app.agent.pm_mentor import run_pm_mentor

    state = {
        "stage_hint": "solution",
        "current_phase": "solution",
        "prd_snapshot": {"sections": {}},
    }
    broken_output = _make_pm_output(
        suggestions=[
            _make_suggestion("先聊目标用户", "我想先明确，这个产品主要给谁用。", priority=1),
            _make_suggestion("先聊核心问题", "我想先讲清楚，这个产品到底想解决什么具体麻烦。", priority=2),
            _make_suggestion("先聊核心功能", "我想先列一下，我脑子里已经想到的这个产品核心功能。", priority=3),
            _make_suggestion("我直接补充", "我不想选项，我直接补充我现在对这个产品的想法。", priority=4),
        ]
    )

    with patch("app.agent.pm_mentor.call_pm_mentor_llm", return_value=broken_output):
        result = run_pm_mentor(state, "我想先说明这个产品第一版到底怎么解决问题", _build_mock_model_config())

    assert result.turn_decision is not None
    labels = [item.label for item in result.turn_decision.suggestions]
    assert "先聊目标用户" not in labels
    assert "先聊核心问题" not in labels
    assert any(
        "解决方式" in item.content or "流程" in item.content or "差异" in item.content
        for item in result.turn_decision.suggestions
    )


def test_run_pm_mentor_mvp_scope_focus_rejects_generic_top_level_menu():
    from app.agent.pm_mentor import run_pm_mentor

    state = {
        "stage_hint": "mvp_scope",
        "current_phase": "mvp_scope",
        "prd_snapshot": {"sections": {}},
    }
    broken_output = _make_pm_output(
        suggestions=[
            _make_suggestion("先聊目标用户", "我想先明确，这个产品主要给谁用。", priority=1),
            _make_suggestion("先聊核心问题", "我想先讲清楚，这个产品到底想解决什么具体麻烦。", priority=2),
            _make_suggestion("先聊核心功能", "我想先列一下，我脑子里已经想到的这个产品核心功能。", priority=3),
            _make_suggestion("我直接补充", "我不想选项，我直接补充我现在对这个产品的想法。", priority=4),
        ]
    )

    with patch("app.agent.pm_mentor.call_pm_mentor_llm", return_value=broken_output):
        result = run_pm_mentor(state, "我想先确定这个产品第一版必须做和不做什么", _build_mock_model_config())

    assert result.turn_decision is not None
    labels = [item.label for item in result.turn_decision.suggestions]
    assert "先聊目标用户" not in labels
    assert "先聊核心问题" not in labels
    assert any(
        "必须" in item.content or "不做" in item.content or "完成标准" in item.content
        for item in result.turn_decision.suggestions
    )


def test_run_pm_mentor_solution_focus_replaces_low_diversity_guidance():
    from app.agent.pm_mentor import run_pm_mentor

    state = {
        "stage_hint": "solution",
        "current_phase": "solution",
        "prd_snapshot": {"sections": {}},
    }
    low_diversity_output = _make_pm_output(
        suggestions=[
            _make_suggestion("先讲方案主线", "我想先说明这个产品第一版的核心解决方式。", priority=1),
            _make_suggestion("先讲方案细节", "我想先补充这个产品第一版的核心解决方式细节。", priority=2),
            _make_suggestion("先讲方案补充", "我想继续说明这个产品第一版的核心解决方式。", priority=3),
            _make_suggestion("我直接补充方案", "我直接补充这个产品第一版的核心解决方式想法。", priority=4),
        ]
    )

    with patch("app.agent.pm_mentor.call_pm_mentor_llm", return_value=low_diversity_output):
        result = run_pm_mentor(state, "我想先说明这个产品第一版到底怎么解决问题", _build_mock_model_config())

    assert result.turn_decision is not None
    labels = [item.label for item in result.turn_decision.suggestions]
    assert "先讲差异化" in labels or "先讲关键流程" in labels
    assert any("差异" in item.content or "流程" in item.content for item in result.turn_decision.suggestions)


def test_run_pm_mentor_detects_contradiction_gap_and_assumption_diagnostics():
    from app.agent.pm_mentor import run_pm_mentor

    state = {
        "stage_hint": "problem",
        "current_phase": "problem",
        "prd_snapshot": {
            "sections": {
                "target_user": {"content": "独立开发者", "status": "confirmed"},
                "problem": {"content": "任务经常忘记跟进", "status": "confirmed"},
                "solution": {"content": "", "status": "missing"},
                "mvp_scope": {"content": "", "status": "missing"},
            }
        },
    }
    output = _make_pm_output(
        suggestions=[
            _make_suggestion("先讲最高频麻烦", "我想先讲清楚最高频的那个麻烦。", priority=1),
            _make_suggestion("先讲最痛一刻", "我想先描述最痛的一次场景。", priority=2),
            _make_suggestion("先讲替代方案", "我想先说说现在怎么勉强解决。", priority=3),
            _make_suggestion("我直接补充", "我直接补充我对核心问题的判断。", priority=4),
        ]
    )
    output["next_focus"] = "problem"
    output["reply"] = "我们先把问题和假设压实。"
    output["prd_updates"] = {
        "problem": {"content": "其实更像是找不到合适的协作者", "status": "draft"},
    }

    with patch("app.agent.pm_mentor.call_pm_mentor_llm", return_value=output):
        result = run_pm_mentor(
            state,
            "其实我改主意了，这个产品应该面向小团队负责人，而且我默认先做 Web 端。",
            _build_mock_model_config(),
        )

    assert result.turn_decision is not None
    diagnostics = result.turn_decision.diagnostics
    assert {item["type"] for item in diagnostics} >= {"contradiction", "gap", "assumption"}
    contradiction = next(item for item in diagnostics if item["type"] == "contradiction")
    assert contradiction["impact_scope"] == ["target_user"]
    assert contradiction["suggested_next_step"]["action_kind"] == "ask_user"
    gap = next(item for item in diagnostics if item["type"] == "gap")
    assert gap["impact_scope"] == ["solution"]
    assert gap["suggested_next_step"]["prompt"]
    assumption = next(item for item in diagnostics if item["type"] == "assumption")
    assert assumption["bucket"] == "risk"
    assert assumption["suggested_next_step"]["prompt"]
    assert result.turn_decision.gaps
    assert result.turn_decision.assumptions


def test_run_pm_mentor_does_not_misclassify_exploratory_input_as_contradiction():
    from app.agent.pm_mentor import run_pm_mentor

    state = {
        "stage_hint": "target_user",
        "current_phase": "target_user",
        "prd_snapshot": {
            "sections": {
                "target_user": {"content": "独立开发者", "status": "draft"},
            }
        },
    }
    output = _make_pm_output(
        suggestions=[
            _make_suggestion("先聊角色", "我想先聊用户是什么角色。", priority=1),
            _make_suggestion("先聊场景", "我想先聊用户在什么场景下会用。", priority=2),
            _make_suggestion("先聊动机", "我想先聊用户为什么会在意这件事。", priority=3),
            _make_suggestion("我直接补充", "我直接补充我对目标用户的判断。", priority=4),
        ]
    )
    output["next_focus"] = "target_user"

    with patch("app.agent.pm_mentor.call_pm_mentor_llm", return_value=output):
        result = run_pm_mentor(
            state,
            "也可能是独立开发者，也可能是小团队负责人，我还没完全想清楚。",
            _build_mock_model_config(),
        )

    assert result.turn_decision is not None
    assert all(item["type"] != "contradiction" for item in result.turn_decision.diagnostics)


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
