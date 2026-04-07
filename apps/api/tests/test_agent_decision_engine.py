from app.agent.decision_engine import build_turn_decision
from app.agent.types import UnderstandingResult


def _phase1_state(**overrides):
    base = {
        "idea": "做一个 AI Co-founder",
        "target_user": None,
        "problem": None,
        "solution": None,
        "mvp_scope": [],
        "iteration": 0,
        "stage_hint": "问题探索",
        "current_phase": "idea_clarification",
        "phase_goal": None,
        "working_hypotheses": [],
        "evidence": [],
        "decision_readiness": None,
        "pm_risk_flags": [],
        "recommended_directions": [],
        "pending_confirmations": [],
        "rejected_options": [],
        "next_best_questions": [],
    }
    base.update(overrides)
    return base


def _understanding(**overrides):
    base = {
        "summary": "用户提供了方向",
        "candidate_updates": {},
        "assumption_candidates": [],
        "ambiguous_points": [],
        "risk_hints": [],
    }
    base.update(overrides)
    return UnderstandingResult(**base)


def test_decision_engine_force_rank_when_user_too_broad():
    state = _phase1_state()
    understanding = _understanding(risk_hints=["user_too_broad"])

    decision = build_turn_decision(state, understanding, state_patch={}, prd_patch={})

    assert decision.conversation_strategy == "choose"
    assert decision.next_move == "force_rank_or_choose"
    assert decision.next_best_questions
    assert "只能先选一个主线" in decision.next_best_questions[0]
    assert "目标用户仍然过泛" in decision.strategy_reason
    assert "user_too_broad" in decision.pm_risk_flags


def test_decision_engine_assume_and_advance_when_direction_but_gaps_exist():
    state = _phase1_state(target_user="独立开发者", problem=None)
    understanding = _understanding(
        candidate_updates={"problem": "不知道先验证哪个需求"},
        risk_hints=[],
    )

    decision = build_turn_decision(
        state,
        understanding,
        state_patch={"problem": "不知道先验证哪个需求"},
        prd_patch={
            "problem": {
                "title": "核心问题",
                "content": "不知道先验证哪个需求",
                "status": "confirmed",
            }
        },
    )

    assert decision.conversation_strategy == "converge"
    assert decision.next_move == "assume_and_advance"
    assert decision.next_best_questions
    assert "最想先验证" in decision.next_best_questions[0]
    assert "已有方向信号" in decision.strategy_reason
    assert any("方案" in gap or "MVP" in gap for gap in decision.gaps)


def test_decision_engine_challenge_when_solution_before_problem():
    state = _phase1_state(problem=None)
    understanding = _understanding(risk_hints=["solution_before_problem"])

    decision = build_turn_decision(state, understanding, state_patch={}, prd_patch={})

    assert decision.conversation_strategy == "clarify"
    assert decision.next_move == "challenge_and_reframe"
    assert decision.next_best_questions


def test_decision_engine_probe_when_problem_too_vague():
    state = _phase1_state(
        target_user="独立开发者",
        problem="体验不好",
        solution="提供自动梳理方案",
        mvp_scope=["引导提问"],
    )
    understanding = _understanding(risk_hints=["problem_too_vague"])

    decision = build_turn_decision(state, understanding, state_patch={}, prd_patch={})

    assert decision.conversation_strategy == "clarify"
    assert decision.next_move == "probe_for_specificity"
    assert decision.next_best_questions


def test_decision_engine_needs_confirmation_prefers_pending():
    state = _phase1_state(
        target_user="独立开发者",
        problem="不知道先验证哪个需求",
        solution="结构化追问",
        mvp_scope=["追问"],
        pending_confirmations=["确认目标用户是否正确"],
    )
    understanding = _understanding()

    decision = build_turn_decision(state, understanding, state_patch={}, prd_patch={})

    assert decision.needs_confirmation == ["确认目标用户是否正确"]


def test_decision_engine_needs_confirmation_defaults_on_summarize():
    state = _phase1_state(
        target_user="独立开发者",
        problem="不知道先验证哪个需求",
        solution="结构化追问",
        mvp_scope=["追问"],
        pending_confirmations=[],
    )
    understanding = _understanding()

    decision = build_turn_decision(state, understanding, state_patch={}, prd_patch={})

    assert decision.conversation_strategy == "confirm"
    assert decision.next_move == "summarize_and_confirm"
    assert decision.needs_confirmation == ["请确认当前理解是否准确"]
    assert decision.next_best_questions == ["请确认当前理解是否准确"]
    assert "核心信息已基本齐备" in decision.strategy_reason


def test_decision_engine_choose_advances_to_converge_after_user_makes_choice():
    state = _phase1_state(
        conversation_strategy="choose",
        problem="不知道先验证哪个需求",
    )
    understanding = _understanding(
        candidate_updates={"target_user": "独立开发者"},
        risk_hints=[],
    )

    decision = build_turn_decision(
        state,
        understanding,
        state_patch={"target_user": "独立开发者"},
        prd_patch={
            "target_user": {
                "title": "目标用户",
                "content": "独立开发者",
                "status": "confirmed",
            }
        },
    )

    assert decision.conversation_strategy == "converge"
    assert decision.next_move == "assume_and_advance"
    assert "用户已经给出明确取舍信号" in decision.strategy_reason


def test_decision_engine_converge_does_not_fall_back_on_vague_reply():
    state = _phase1_state(
        conversation_strategy="converge",
        target_user="独立开发者",
        problem=None,
    )
    understanding = _understanding(
        ambiguous_points=["用户这轮没有补充更多可执行细节"],
        risk_hints=[],
    )

    decision = build_turn_decision(state, understanding, state_patch={}, prd_patch={})

    assert decision.conversation_strategy == "converge"
    assert decision.next_move == "assume_and_advance"


def test_decision_engine_confirm_does_not_fall_back_on_vague_reply_without_new_risk():
    state = _phase1_state(
        conversation_strategy="confirm",
        target_user="独立开发者",
        problem="不知道先验证哪个需求",
        solution="结构化追问",
        mvp_scope=["追问"],
    )
    understanding = _understanding(
        ambiguous_points=["用户这轮没有新增信息"],
        risk_hints=[],
    )

    decision = build_turn_decision(state, understanding, state_patch={}, prd_patch={})

    assert decision.conversation_strategy == "confirm"
    assert decision.next_move == "summarize_and_confirm"
    assert "没有新增风险" in decision.strategy_reason
