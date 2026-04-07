from typing import get_args

from app.agent.types import NextMove, Suggestion, SuggestionType, TurnDecision
from app.schemas.state import StateSnapshot


def test_next_move_enforces_phase1_white_list():
    required_moves = {
        "probe_for_specificity",
        "assume_and_advance",
        "challenge_and_reframe",
        "summarize_and_confirm",
        "force_rank_or_choose",
    }

    assert required_moves.issubset(set(get_args(NextMove)))


def test_suggestion_supports_required_fields():
    suggestion = Suggestion(
        type="direction",
        label="聚焦独立开发者",
        content="描述将目标用户缩窄到独立开发者",
        rationale="用户描述过于泛，先切入小众用户更易验证",
        priority=1,
    )

    assert suggestion.type == "direction"
    assert suggestion.label.startswith("聚焦")
    assert suggestion.priority == 1


def test_turn_decision_contains_suggestions_and_state_patch():
    decision = TurnDecision(
        phase="target_user_narrowing",
        phase_goal="收敛目标用户",
        understanding={"summary": "用户正在描述目标用户"},
        assumptions=[{"label": "独立开发者更合适"}],
        gaps=["缺少细分场景"],
        challenges=["用户先讲方案再讲问题"],
        pm_risk_flags=["user_too_broad"],
        next_move="probe_for_specificity",
        suggestions=[
            Suggestion(
                type="direction",
                label="推荐先聚焦独立开发者",
                content="描述场景",
                rationale="更小的用户群便于验证",
                priority=1,
            )
        ],
        recommendation={"label": "优先独立开发者", "content": "理由"},
        reply_brief={"must_include": ["判断", "建议"]},
        state_patch={"current_phase": "target_user_narrowing"},
        prd_patch={"target_user": {"title": "目标用户", "content": "独立开发者"}},
        needs_confirmation=["是否聚焦独立开发者"],
        confidence="medium",
        strategy_reason="当前问题仍不够清晰，需要继续澄清",
    )

    assert decision.next_move == "probe_for_specificity"
    assert all(isinstance(s, Suggestion) for s in decision.suggestions)
    assert "current_phase" in decision.state_patch
    assert decision.confidence == "medium"
    assert decision.next_best_questions == []
    assert decision.strategy_reason


def test_state_snapshot_exposes_new_fields():
    snapshot = StateSnapshot(
        idea="AI 助手",
        stage_hint="问题探索",
        iteration=0,
        goal=None,
        target_user=None,
        problem=None,
        solution=None,
        mvp_scope=[],
        success_metrics=[],
        known_facts={},
        assumptions=[],
        risks=[],
        unexplored_areas=[],
        options=[],
        decisions=[],
        open_questions=[],
        prd_snapshot={},
    )

    assert snapshot.working_hypotheses == []
    assert snapshot.pm_risk_flags == []
    assert snapshot.recommended_directions == []
    assert snapshot.pending_confirmations == []
    assert snapshot.next_best_questions == []
    assert snapshot.decision_readiness is None
    assert snapshot.current_phase == "idea_clarification"
    assert snapshot.conversation_strategy == "clarify"
    assert snapshot.strategy_reason is None


def test_state_snapshot_accepts_legacy_state_without_current_phase():
    snapshot = StateSnapshot(
        idea="AI 助手",
        stage_hint="问题探索",
        iteration=0,
        goal=None,
        target_user=None,
        problem=None,
        solution=None,
        mvp_scope=[],
        success_metrics=[],
        known_facts={},
        assumptions=[],
        risks=[],
        unexplored_areas=[],
        options=[],
        decisions=[],
        open_questions=[],
        prd_snapshot={},
    )

    assert snapshot.current_phase == "idea_clarification"
    assert snapshot.conversation_strategy == "clarify"
    assert snapshot.strategy_reason is None
