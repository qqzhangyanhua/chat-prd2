from app.agent.types import TurnDecision
from app.services.message_state import build_decision_state_patch, merge_readiness_state_patch


def _build_turn_decision_with_diagnostics() -> TurnDecision:
    return TurnDecision(
        phase="problem",
        phase_goal="澄清核心问题",
        understanding={"summary": "用户问题仍不够稳定", "candidate_updates": {}, "ambiguous_points": []},
        assumptions=[{"id": "assumption-product-surface", "title": "默认先做 Web 端"}],
        gaps=["需要补方案主线"],
        challenges=["目标用户与问题主线还没有完全对齐。"],
        pm_risk_flags=["默认先做 Web 端"],
        next_move="probe_for_specificity",
        suggestions=[],
        recommendation=None,
        reply_brief={},
        state_patch={},
        prd_patch={},
        needs_confirmation=[],
        confidence="medium",
        conversation_strategy="clarify",
        diagnostics=[
            {
                "id": "contradiction-target-user",
                "type": "contradiction",
                "bucket": "to_validate",
                "status": "open",
                "title": "目标用户主线冲突",
                "detail": "用户从独立开发者切到小团队负责人。",
                "impact_scope": ["target_user"],
                "suggested_next_step": {
                    "action_kind": "ask_user",
                    "label": "先确认目标用户",
                    "prompt": "如果只能先服务一类人，你现在更想先服务谁？",
                },
                "confidence": "high",
            },
            {
                "id": "gap-solution",
                "type": "gap",
                "bucket": "unknown",
                "status": "open",
                "title": "方案主线缺失",
                "detail": "还没有说清楚第一版怎么解决问题。",
                "impact_scope": ["solution"],
                "suggested_next_step": {
                    "action_kind": "ask_user",
                    "label": "先说方案主线",
                    "prompt": "如果只保留一个核心动作，第一版到底怎么解决这个问题？",
                },
                "confidence": "medium",
            },
            {
                "id": "assumption-product-surface",
                "type": "assumption",
                "bucket": "risk",
                "status": "open",
                "title": "默认先做 Web 端",
                "detail": "当前推进默认第一版只做 Web 端，但用户还没确认。",
                "impact_scope": ["solution", "mvp_scope"],
                "suggested_next_step": {
                    "action_kind": "ask_user",
                    "label": "确认首发载体",
                    "prompt": "你是不是已经默认第一版只做 Web 端？",
                },
                "confidence": "medium",
            },
        ],
        diagnostic_summary={
            "open_count": 3,
            "unknown_count": 1,
            "risk_count": 1,
            "to_validate_count": 1,
        },
    )


def test_build_decision_state_patch_writes_diagnostics_and_summary():
    patch = build_decision_state_patch(_build_turn_decision_with_diagnostics())

    assert len(patch["diagnostics"]) == 3
    assert patch["diagnostic_summary"] == {
        "open_count": 3,
        "unknown_count": 1,
        "risk_count": 1,
        "to_validate_count": 1,
    }


def test_build_decision_state_patch_derives_compatibility_fields_from_diagnostics():
    patch = build_decision_state_patch(_build_turn_decision_with_diagnostics())

    assert patch["working_hypotheses"] == [
        {
            "id": "assumption-product-surface",
            "title": "默认先做 Web 端",
        }
    ]
    assert patch["pm_risk_flags"] == ["默认先做 Web 端"]
    assert patch["open_questions"] == [
        "如果只能先服务一类人，你现在更想先服务谁？",
        "如果只保留一个核心动作，第一版到底怎么解决这个问题？",
        "你是不是已经默认第一版只做 Web 端？",
    ]


def test_build_decision_state_patch_keeps_structured_prd_draft_and_evidence():
    decision = _build_turn_decision_with_diagnostics()
    decision.state_patch = {
        "prd_draft": {
            "version": 2,
            "status": "drafting",
            "sections": {
                "target_user": {
                    "title": "目标用户",
                    "completeness": "partial",
                    "entries": [
                        {
                            "id": "entry-target-user-1",
                            "text": "第一版先服务独立开发者。",
                            "assertion_state": "confirmed",
                            "evidence_ref_ids": ["evidence-user-1"],
                        }
                    ],
                }
            },
        },
        "evidence": [
            {
                "id": "evidence-user-1",
                "kind": "user_message",
                "excerpt": "我想先服务独立开发者。",
                "section_keys": ["target_user"],
                "message_id": "msg-1",
            }
        ],
    }

    patch = build_decision_state_patch(decision)

    assert patch["prd_draft"]["sections"]["target_user"]["entries"][0]["assertion_state"] == "confirmed"
    assert patch["prd_draft"]["sections"]["target_user"]["entries"][0]["evidence_ref_ids"] == ["evidence-user-1"]
    assert patch["evidence"][0]["kind"] == "user_message"


def test_merge_readiness_state_patch_keeps_to_validate_as_gap_without_marking_missing():
    state_patch = {
        "prd_draft": {
            "version": 3,
            "status": "drafting",
            "sections": {
                "target_user": {
                    "title": "目标用户",
                    "completeness": "complete",
                    "entries": [{"id": "entry-1", "text": "独立开发者", "assertion_state": "confirmed", "evidence_ref_ids": ["evidence-1"]}],
                },
                "problem": {
                    "title": "核心问题",
                    "completeness": "complete",
                    "entries": [{"id": "entry-2", "text": "需求确认成本高", "assertion_state": "confirmed", "evidence_ref_ids": ["evidence-2"]}],
                },
                "solution": {
                    "title": "解决方案",
                    "completeness": "complete",
                    "entries": [{"id": "entry-3", "text": "AI 协作问答流", "assertion_state": "confirmed", "evidence_ref_ids": ["evidence-3"]}],
                },
                "mvp_scope": {
                    "title": "MVP 范围",
                    "completeness": "complete",
                    "entries": [{"id": "entry-4", "text": "只做 Web 端", "assertion_state": "confirmed", "evidence_ref_ids": ["evidence-4"]}],
                },
                "constraints": {
                    "title": "约束条件",
                    "completeness": "complete",
                    "entries": [{"id": "entry-5", "text": "首版不做私有化", "assertion_state": "confirmed", "evidence_ref_ids": ["evidence-5"]}],
                },
                "success_metrics": {
                    "title": "成功指标",
                    "completeness": "complete",
                    "entries": [{"id": "entry-6", "text": "7 天留存 >= 20%", "assertion_state": "to_validate", "evidence_ref_ids": ["evidence-6"]}],
                },
            },
        },
        "diagnostic_summary": {
            "open_count": 1,
            "unknown_count": 0,
            "risk_count": 1,
            "to_validate_count": 1,
        },
    }

    merged = merge_readiness_state_patch(state_patch, current_state={})

    assert merged["finalization_ready"] is False
    assert merged["critic_result"]["status"] == "needs_input"
    assert merged["critic_result"]["missing_sections"] == []
    assert any("待验证" in prompt or "风险" in prompt for prompt in merged["critic_result"]["gap_prompts"])
