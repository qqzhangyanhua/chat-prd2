from app.agent.reply_composer import (
    CRITIC_VERDICT_PREFIX,
    DRAFT_SUMMARY_PREFIX,
    NEXT_QUESTION_PREFIX,
    build_reply_sections,
    compose_reply,
)
from app.agent.types import TurnDecision


def _make_decision(*, prd_draft=None, critic_result=None, gaps=None, next_best_questions=None, **overrides):
    base = {
        "phase": "refine_loop",
        "phase_goal": "补齐关键缺口",
        "understanding": {},
        "assumptions": [],
        "gaps": list(gaps or []),
        "challenges": [],
        "pm_risk_flags": [],
        "next_move": "assume_and_advance",
        "suggestions": [],
        "recommendation": None,
        "reply_brief": {},
        "state_patch": {},
        "prd_patch": {},
        "needs_confirmation": [],
        "confidence": "medium",
        "next_best_questions": list(next_best_questions or []),
        "strategy_reason": None,
        "conversation_strategy": "clarify",
    }
    if prd_draft is not None:
        base["state_patch"]["prd_draft"] = prd_draft
    if critic_result is not None:
        base["state_patch"]["critic_result"] = critic_result
    base.update(overrides)
    return TurnDecision(**base)


def test_compose_reply_prefers_first_critic_queue_entry():
    decision = _make_decision(
        prd_draft={"status": "draft_hypothesis"},
        critic_result={
            "overall_verdict": "block",
            "major_gaps": ["未明确文件格式"],
            "question_queue": [
                "第一版要支持哪些 3D/CAD 文件格式？",
                "是否需要标注？",
            ],
        },
        next_best_questions=["你也可以告诉我其他关注点"],
    )

    reply = compose_reply(decision)

    assert CRITIC_VERDICT_PREFIX in reply
    assert NEXT_QUESTION_PREFIX in reply
    assert "第一版要支持哪些 3D/CAD 文件格式？" in reply
    assert "是否需要标注？" not in reply
    assert "你也可以告诉我其他关注点" not in reply


def test_compose_reply_does_not_fallback_when_queue_head_is_blank():
    decision = _make_decision(
        critic_result={
            "overall_verdict": "revise",
            "major_gaps": [],
            "question_queue": ["", "第二版的核心须知是什么？"],
        },
        next_best_questions=["请问接下来希望我问什么？"],
    )

    reply = compose_reply(decision)

    assert "请问接下来希望我问什么？" not in reply
    assert "第二版的核心须知是什么？" not in reply
    assert "目前没有特别要问的问题" in reply


def test_compose_reply_supports_finalize_prompt_without_critic_result():
    decision = _make_decision(
        prd_draft={
            "status": "ready_for_finalize",
            "version": 2,
            "missing_information": [],
        },
        critic_result=None,
        gaps=[],
        next_best_questions=[],
        phase="finalize",
        phase_goal="整理最终版 PRD",
    )

    reply = compose_reply(decision)

    assert "当前 Critic 判断是 pass" in reply
    assert "关键缺口已补齐" in reply
    assert "如果当前摘要没有偏差，请直接回复“确认设计”" in reply


def test_compose_reply_does_not_fallback_to_legacy_next_question_when_question_queue_is_explicitly_empty():
    decision = _make_decision(
        prd_draft={
            "status": "ready_for_finalize",
            "version": 2,
            "missing_information": [],
        },
        critic_result={
            "overall_verdict": "pass",
            "major_gaps": [],
            "question_queue": [],
        },
        next_best_questions=["这是旧问题，不应继续出现"],
        phase="finalize",
        phase_goal="整理最终版 PRD",
    )

    reply = compose_reply(decision)

    assert "这是旧问题，不应继续出现" not in reply
    assert "如果当前摘要没有偏差，请直接回复“确认设计”" in reply


def test_compose_reply_summarizes_draft_and_critic_verdict():
    decision = _make_decision(
        prd_draft={
            "status": "draft_hypothesis",
            "version": 1,
            "assumptions": ["首版先支持浏览器内在线预览"],
            "missing_information": ["核心文件格式", "权限边界"],
        },
        critic_result={
            "overall_verdict": "revise",
            "major_gaps": ["未明确核心文件格式", "未明确权限边界"],
            "question_queue": ["第一版优先支持哪些文件格式？"],
        },
        phase="initial_draft",
        phase_goal="生成 PRD v1 草案",
    )

    reply = compose_reply(decision)

    assert DRAFT_SUMMARY_PREFIX in reply
    assert "PRD v1" in reply
    assert "draft_hypothesis" not in reply
    assert "首版先支持浏览器内在线预览" in reply
    assert "核心文件格式" in reply
    assert "当前 Critic 判断是 revise" in reply
    assert "未明确核心文件格式" in reply


def test_compose_reply_uses_state_patch_for_real_turndecision_inputs():
    decision = _make_decision(
        prd_draft={
            "status": "draft_refined",
            "version": 2,
            "assumptions": ["先支持浏览器直开"],
            "missing_information": [],
        },
        critic_result={
            "overall_verdict": "block",
            "major_gaps": ["未明确权限边界"],
            "question_queue": ["首版权限要区分几种角色？"],
        },
        gaps=["这个旧 gaps 不该覆盖新 critic 结果"],
    )

    reply = compose_reply(decision)

    assert "PRD v2" in reply
    assert "先支持浏览器直开" in reply
    assert "当前 Critic 判断是 block" in reply
    assert "未明确权限边界" in reply
    assert "首版权限要区分几种角色？" in reply
    assert "这个旧 gaps 不该覆盖新 critic 结果" not in reply


def test_compose_reply_prefers_top_level_fields_over_state_patch():
    decision = _make_decision(
        prd_draft={"status": "draft_hypothesis", "version": 1},
        critic_result={
            "overall_verdict": "revise",
            "major_gaps": ["state_patch 的 critic 不应生效"],
            "question_queue": ["state_patch 的问题不应生效"],
        },
    )
    decision = object.__new__(type("DecisionCarrier", (), {}))
    decision.phase = "refine_loop"
    decision.phase_goal = "补齐关键缺口"
    decision.gaps = []
    decision.next_best_questions = []
    decision.state_patch = {
        "prd_draft": {"status": "draft_refined", "version": 2},
        "critic_result": {
            "overall_verdict": "block",
            "major_gaps": ["state_patch 的 critic 不应生效"],
            "question_queue": ["state_patch 的问题不应生效"],
        },
    }
    decision.prd_draft = {"status": "ready_for_finalize", "version": 3, "missing_information": []}
    decision.critic_result = {
        "overall_verdict": "pass",
        "major_gaps": [],
        "question_queue": [],
    }

    reply = compose_reply(decision)

    assert "PRD v3" in reply
    assert "当前 Critic 判断是 pass" in reply
    assert "state_patch 的 critic 不应生效" not in reply
    assert "state_patch 的问题不应生效" not in reply


def test_compose_reply_does_not_fallback_to_legacy_gaps_when_new_lists_are_explicitly_empty():
    decision = _make_decision(
        prd_draft={
            "status": "draft_refined",
            "version": 2,
            "missing_information": [],
        },
        critic_result={
            "overall_verdict": "pass",
            "major_gaps": [],
            "question_queue": [],
        },
        gaps=["旧 gaps 不应回流"],
        phase="finalize",
        phase_goal="整理最终版 PRD",
        next_best_questions=[],
    )

    reply = compose_reply(decision)

    assert "旧 gaps 不应回流" not in reply
    assert "关键缺口已补齐" in reply
    assert "如果当前摘要没有偏差，请直接回复“确认设计”" in reply


def test_build_reply_sections_keeps_legacy_keys():
    decision = _make_decision(
        prd_draft={"status": "draft_refined", "version": 2},
        critic_result={
            "overall_verdict": "revise",
            "major_gaps": ["未明确权限边界"],
            "question_queue": ["需要区分访客、成员和管理员吗？"],
        },
    )

    sections = build_reply_sections(decision)

    assert [section["key"] for section in sections] == [
        "judgement",
        "critic_verdict",
        "next_step",
    ]
    assert [section["title"] for section in sections] == [
        DRAFT_SUMMARY_PREFIX,
        CRITIC_VERDICT_PREFIX,
        NEXT_QUESTION_PREFIX,
    ]
    assert all(section["content"] for section in sections)


def test_compose_reply_joins_sections_in_order():
    decision = _make_decision(
        prd_draft={"status": "draft_refined", "version": 2},
        critic_result={
            "overall_verdict": "revise",
            "major_gaps": ["未明确权限边界"],
            "question_queue": ["需要区分访客、成员和管理员吗？"],
        },
    )

    sections = build_reply_sections(decision)
    reply = compose_reply(decision)

    assert reply == "\n\n".join(f"{section['title']}{section['content']}" for section in sections)
