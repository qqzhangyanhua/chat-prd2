from app.agent.understanding import parse_idea_input, understand_user_input


def _phase1_state(**overrides):
    base = {
        "idea": "做一个 AI Co-founder",
        "target_user": None,
        "problem": None,
        "solution": None,
        "mvp_scope": [],
        "iteration": 0,
        "stage_hint": "问题探索",
    }
    base.update(overrides)
    return base


def test_understanding_builds_target_user_update():
    state = _phase1_state()
    user_input = "独立开发者团队"

    result = understand_user_input(state, user_input)

    assert "target_user" in result.candidate_updates
    assert result.candidate_updates["target_user"] == user_input
    assert result.summary.startswith("用户表述了")
    assert result.assumption_candidates == []
    assert result.ambiguous_points == []
    assert result.risk_hints == []


def test_understanding_does_not_capture_continuation():
    state = _phase1_state()
    result = understand_user_input(state, "继续")
    assert result.candidate_updates == {}


def test_understanding_handles_mvp_scope_branch():
    state = _phase1_state(
        target_user="独立开发者",
        problem="需求",
        solution="方案",
        mvp_scope=[],
    )
    user_input = "创建会话功能"
    result = understand_user_input(state, user_input)
    assert result.candidate_updates == {"mvp_scope": [user_input]}


def test_understanding_skips_updates_when_state_complete():
    state = _phase1_state(
        target_user="独立开发者",
        problem="需求",
        solution="方案",
        mvp_scope=["已完成"],
    )
    result = understand_user_input(state, "还有不确定的地方")
    assert result.candidate_updates == {}


def test_understanding_detects_risks_and_assumptions():
    state = _phase1_state(target_user="独立开发者", problem=None)
    user_input = "我猜我们可以为所有创业者提供一个产品，虽然还不清楚具体形态"

    result = understand_user_input(state, user_input)

    assert "problem" in result.candidate_updates
    assert result.candidate_updates["problem"].startswith("我猜")
    assert "user_too_broad" in result.risk_hints
    assert "solution_before_problem" in result.risk_hints
    assert result.assumption_candidates == [user_input]
    assert any("表达尚不明确" in point for point in result.ambiguous_points)


def test_parse_idea_input_extracts_domain_signals_and_questions():
    result = parse_idea_input("我想做一个在线3D图纸预览平台")
    assert "3D图纸预览平台" in result.idea_summary
    assert result.product_type == "在线3D图纸预览平台"
    assert "3D预览" in result.domain_signals
    assert any("格式" in question for question in result.open_questions)
    assert any("权限" in question for question in result.open_questions)
    assert "提供可交互的预览功能" in result.explicit_requirements
    assert "用户拥有可用的网络连接" in result.implicit_assumptions
    assert result.confidence == "medium"


def test_understand_user_input_idea_parser_stage_returns_idea_result():
    user_input = "我想做一个在线3D图纸预览平台"
    state = _phase1_state(workflow_stage="idea_parser")
    result = understand_user_input(state, user_input)
    idea_result = parse_idea_input(user_input)

    assert result.candidate_updates == {}
    assert result.summary == idea_result.idea_summary
    assert result.assumption_candidates == idea_result.implicit_assumptions
    assert result.ambiguous_points == idea_result.open_questions
    assert result.risk_hints == []
