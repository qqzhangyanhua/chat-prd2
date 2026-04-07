import pytest

from app.agent.suggestion_planner import _build_recommendation, build_suggestions
from app.agent.types import NextMove, Suggestion, TurnDecision


def _base_decision(next_move: NextMove) -> TurnDecision:
    return TurnDecision(
        phase="idea_clarification",
        phase_goal="收敛目标用户",
        understanding={
            "summary": "用户表述了：想做一个产品。",
            "candidate_updates": {},
            "ambiguous_points": [],
        },
        assumptions=[],
        gaps=["缺少明确的目标用户"],
        challenges=["目标用户范围过泛，需优先收敛"],
        pm_risk_flags=[],
        next_move=next_move,
        suggestions=[],
        recommendation=None,
        reply_brief={"focus": next_move, "must_include": []},
        state_patch={},
        prd_patch={},
        needs_confirmation=[],
        confidence="low",
    )


def test_build_suggestions_returns_recommendation_and_multiple_directions():
    decision = _base_decision("force_rank_or_choose")

    suggestions, recommendation = build_suggestions(decision)

    assert recommendation is not None
    direction_suggestions = [item for item in suggestions if item.type == "direction"]
    assert len(direction_suggestions) >= 2
    assert any(item.label == recommendation["label"] for item in suggestions)


@pytest.mark.parametrize(
    ("next_move", "expect_direction_count"),
    [
        ("probe_for_specificity", 1),
        ("assume_and_advance", 1),
        ("challenge_and_reframe", 1),
        ("summarize_and_confirm", 1),
        ("force_rank_or_choose", 2),
    ],
)
def test_build_suggestions_covers_all_next_moves(next_move: NextMove, expect_direction_count: int):
    decision = _base_decision(next_move)

    suggestions, recommendation = build_suggestions(decision)

    assert suggestions
    assert recommendation is not None
    assert any(item.label == recommendation["label"] for item in suggestions)
    direction_suggestions = [item for item in suggestions if item.type == "direction"]
    assert len(direction_suggestions) >= expect_direction_count


def test_build_suggestions_default_branch_is_reachable():
    decision = _base_decision("probe_for_specificity")
    decision.next_move = "unknown_move"  # type: ignore[assignment]

    suggestions, recommendation = build_suggestions(decision)

    assert suggestions
    assert recommendation is not None
    assert any(item.label == recommendation["label"] for item in suggestions)


def test_build_recommendation_prefers_recommendation_type():
    suggestions = [
        Suggestion(
            type="direction",
            label="方向 B",
            content="B",
            rationale="B",
            priority=1,
        ),
        Suggestion(
            type="recommendation",
            label="推荐 A",
            content="A",
            rationale="A",
            priority=3,
        ),
    ]

    recommendation = _build_recommendation(suggestions)

    assert recommendation is not None
    assert recommendation["label"] == "推荐 A"
    assert recommendation["label"] in {item.label for item in suggestions}


def test_build_recommendation_falls_back_to_priority_then_label():
    suggestions = [
        Suggestion(
            type="direction",
            label="方向 B",
            content="B",
            rationale="B",
            priority=1,
        ),
        Suggestion(
            type="direction",
            label="方向 A",
            content="A",
            rationale="A",
            priority=1,
        ),
        Suggestion(
            type="direction",
            label="方向 C",
            content="C",
            rationale="C",
            priority=2,
        ),
    ]

    recommendation = _build_recommendation(suggestions)

    assert recommendation is not None
    assert recommendation["label"] == "方向 A"
