from app.agent.understanding import understand_user_input


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
