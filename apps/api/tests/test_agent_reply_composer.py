from app.agent.reply_composer import (
    ASSUMPTION_PREFIX,
    CONFIRM_ITEMS_PREFIX,
    JUDGEMENT_PREFIX,
    NEXT_STEP_PREFIX,
    SUGGEST_PREFIX,
    SUGGEST_PREFIX_RECOMMEND,
    build_reply_sections,
    compose_reply,
)
from app.agent.suggestion_planner import build_suggestions
from app.agent.types import NextMove, TurnDecision


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


def test_compose_reply_contains_required_prefixes():
    decision = _base_decision("force_rank_or_choose")
    suggestions, recommendation = build_suggestions(decision)
    decision.suggestions = suggestions
    decision.recommendation = recommendation
    decision.assumptions = [{"label": "目标用户愿意先接受访谈验证", "source": "user_input"}]
    decision.needs_confirmation = ["目标用户是否准确"]

    reply = compose_reply(decision)

    assert JUDGEMENT_PREFIX in reply
    assert ASSUMPTION_PREFIX in reply
    assert SUGGEST_PREFIX_RECOMMEND in reply
    assert CONFIRM_ITEMS_PREFIX in reply
    assert NEXT_STEP_PREFIX in reply
    assert "目标用户愿意先接受访谈验证" in reply
    assert suggestions[0].label in reply


def test_compose_reply_falls_back_without_suggestions():
    decision = _base_decision("probe_for_specificity")

    reply = compose_reply(decision)

    assert JUDGEMENT_PREFIX in reply
    assert ASSUMPTION_PREFIX in reply
    assert SUGGEST_PREFIX in reply
    assert CONFIRM_ITEMS_PREFIX in reply
    assert NEXT_STEP_PREFIX in reply
    assert "当前不额外补假设" in reply
    assert "没有新增确认项" in reply
    assert "先收敛关键信息" in reply
    assert "请你先把明确的目标用户补具体" in reply


def test_compose_reply_confirmation_section_uses_specific_target():
    decision = _base_decision("assume_and_advance")
    suggestions, recommendation = build_suggestions(decision)
    decision.suggestions = suggestions
    decision.recommendation = recommendation
    decision.needs_confirmation = ["是否先聚焦独立开发者"]
    decision.next_best_questions = ["你现在最想先验证频率、付费意愿，还是转化阻力？"]

    reply = compose_reply(decision)

    assert f"{CONFIRM_ITEMS_PREFIX}是否先聚焦独立开发者" in reply
    assert "如果你认可这个推进点" in reply
    assert "我下一轮最建议你直接回答" in reply
    assert "你现在最想先验证频率、付费意愿，还是转化阻力？" in reply


def test_compose_reply_next_step_changes_by_next_move():
    decision_choose = _base_decision("force_rank_or_choose")
    suggestions, recommendation = build_suggestions(decision_choose)
    decision_choose.suggestions = suggestions
    decision_choose.recommendation = recommendation

    reply_choose = compose_reply(decision_choose)
    assert "请你直接在上面方向里做取舍" in reply_choose

    decision_confirm = _base_decision("summarize_and_confirm")
    suggestions, recommendation = build_suggestions(decision_confirm)
    decision_confirm.suggestions = suggestions
    decision_confirm.recommendation = recommendation
    decision_confirm.needs_confirmation = ["目标用户是否准确"]

    reply_confirm = compose_reply(decision_confirm)
    assert "请你先确认目标用户是否准确" in reply_confirm
    assert "确认后我会继续按" in reply_confirm

    decision_refute = _base_decision("challenge_and_reframe")
    suggestions, recommendation = build_suggestions(decision_refute)
    decision_refute.suggestions = suggestions
    decision_refute.recommendation = recommendation

    reply_refute = compose_reply(decision_refute)
    assert "如果当前问题判断不对你直接指出" in reply_refute


def test_compose_reply_uses_specific_confirmation_target_in_confirm_section():
    decision = _base_decision("summarize_and_confirm")
    suggestions, recommendation = build_suggestions(decision)
    decision.suggestions = suggestions
    decision.recommendation = recommendation
    decision.needs_confirmation = ["目标用户是否准确"]

    reply = compose_reply(decision)

    assert CONFIRM_ITEMS_PREFIX in reply
    assert "目标用户是否准确" in reply
    assert "请你先确认目标用户是否准确" in reply


def test_compose_reply_confirm_stage_offers_direct_confirmation_template_and_followup():
    decision = _base_decision("summarize_and_confirm")
    suggestions, recommendation = build_suggestions(decision)
    decision.suggestions = suggestions
    decision.recommendation = recommendation
    decision.needs_confirmation = ["目标用户是否准确"]
    decision.next_best_questions = ["如果判断没偏，你就直接回复“确认，继续下一步”。"]

    reply = compose_reply(decision)

    assert "确认后我会继续按" in reply
    assert "你也可以直接回复" in reply
    assert "确认，继续下一步" in reply


def test_compose_reply_next_step_falls_back_without_next_best_question():
    decision = _base_decision("challenge_and_reframe")
    suggestions, recommendation = build_suggestions(decision)
    decision.suggestions = suggestions
    decision.recommendation = recommendation

    reply = compose_reply(decision)

    assert "我下一轮最建议你直接回答" not in reply


def test_build_reply_sections_returns_fixed_five_section_protocol():
    decision = _base_decision("summarize_and_confirm")
    suggestions, recommendation = build_suggestions(decision)
    decision.suggestions = suggestions
    decision.recommendation = recommendation
    decision.assumptions = [{"label": "目标用户愿意接受早期访谈", "source": "user_input"}]
    decision.needs_confirmation = ["目标用户是否准确"]

    sections = build_reply_sections(decision)

    assert [section["key"] for section in sections] == [
        "judgement",
        "assumption",
        "suggestion",
        "confirmation",
        "next_step",
    ]
    assert [section["title"] for section in sections] == [
        JUDGEMENT_PREFIX,
        ASSUMPTION_PREFIX,
        SUGGEST_PREFIX_RECOMMEND,
        CONFIRM_ITEMS_PREFIX,
        NEXT_STEP_PREFIX,
    ]
    assert all(section["content"] for section in sections)


def test_build_reply_sections_includes_next_best_question_in_next_step_content():
    decision = _base_decision("force_rank_or_choose")
    suggestions, recommendation = build_suggestions(decision)
    decision.suggestions = suggestions
    decision.recommendation = recommendation
    decision.next_best_questions = ["如果只能先选一个主线，你更愿意先收敛用户还是问题？"]

    sections = build_reply_sections(decision)

    next_step_section = next(section for section in sections if section["key"] == "next_step")

    assert "我下一轮最建议你直接回答" in next_step_section["content"]
    assert "如果只能先选一个主线，你更愿意先收敛用户还是问题？" in next_step_section["content"]
