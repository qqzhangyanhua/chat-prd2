from types import SimpleNamespace

from app.services.message_models import (
    LocalReplyStream,
    MessageResult,
    MessageStreamEvent,
    PreparedMessageStream,
    PreparedRegenerateStream,
)
from app.services.message_state import (
    apply_prd_patch,
    apply_state_patch,
    merge_state_patch_with_decision,
)


def _phase1_state(**overrides):
    base = {
        "idea": "做一个 AI 产品经理",
        "stage_hint": "问题探索",
        "iteration": 0,
        "goal": None,
        "target_user": None,
        "problem": None,
        "solution": None,
        "mvp_scope": [],
        "success_metrics": [],
        "known_facts": {},
        "assumptions": [],
        "risks": [],
        "unexplored_areas": [],
        "options": [],
        "decisions": [],
        "open_questions": [],
        "prd_snapshot": {"sections": {}},
        "current_phase": "idea_clarification",
        "phase_goal": None,
        "current_model_scene": "general",
        "collaboration_mode_label": "通用协作模式",
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


def test_local_reply_stream_yields_reply_once():
    stream = LocalReplyStream("第一段回复")

    assert list(stream) == ["第一段回复"]
    assert stream.close() is None


def test_message_models_dataclasses_keep_expected_fields():
    result = MessageResult(
        user_message_id="user-1",
        assistant_message_id="assistant-1",
        action={"action": "probe_deeper"},
        reply="继续补充信息",
    )
    event = MessageStreamEvent(type="assistant.done", data={"message_id": "assistant-1"})
    prepared = PreparedMessageStream(
        user_message_id="user-1",
        reply_group_id="group-1",
        assistant_version_id="version-1",
        next_version_no=1,
        action={"action": "probe_deeper"},
        turn_decision=SimpleNamespace(),
        state={"prd_snapshot": {"sections": {}}},
        state_patch={"current_phase": "idea_clarification"},
        prd_patch={},
        model_meta={"model_config_id": "model-1"},
        reply_stream=LocalReplyStream("继续补充信息"),
    )
    regenerate = PreparedRegenerateStream(
        user_message_id=prepared.user_message_id,
        reply_group_id=prepared.reply_group_id,
        assistant_version_id=prepared.assistant_version_id,
        next_version_no=prepared.next_version_no,
        action=prepared.action,
        turn_decision=prepared.turn_decision,
        state=prepared.state,
        state_patch=prepared.state_patch,
        prd_patch=prepared.prd_patch,
        model_meta=prepared.model_meta,
        reply_stream=prepared.reply_stream,
        assistant_message_id="assistant-1",
    )

    assert result.reply == "继续补充信息"
    assert event.type == "assistant.done"
    assert prepared.next_version_no == 1
    assert regenerate.assistant_message_id == "assistant-1"


def test_apply_state_patch_keeps_original_when_patch_empty():
    state = {"idea": "test", "target_user": None}

    result = apply_state_patch(state, {})

    assert result is state


def test_apply_prd_patch_merges_sections():
    state = {"prd_snapshot": {"sections": {"target_user": {"content": "old"}}}}

    result = apply_prd_patch(state, {"problem": {"content": "new problem"}})

    assert result["prd_snapshot"]["sections"]["target_user"]["content"] == "old"
    assert result["prd_snapshot"]["sections"]["problem"]["content"] == "new problem"


def test_merge_state_patch_with_decision_prefers_workflow_fields_from_turn_decision():
    turn_decision = SimpleNamespace(
        phase="refine_loop",
        conversation_strategy="clarify",
        strategy_reason=None,
        phase_goal="补齐关键缺口",
        assumptions=[],
        pm_risk_flags=[],
        suggestions=[],
        recommendation=None,
        needs_confirmation=[],
        next_best_questions=["来自 turn_decision 的下一问"],
        workflow_stage="finalize",
        idea_parse_result={"idea_summary": "来自 turn_decision"},
        prd_draft={"version": 3},
        critic_result={"overall_verdict": "pass", "question_queue": []},
        refine_history=[{"source": "turn_decision"}],
        finalization_ready=True,
        state_patch={},
    )

    merged = merge_state_patch_with_decision(
        state_patch={
            "workflow_stage": "refine_loop",
            "idea_parse_result": {"idea_summary": "来自 agent_result.state_patch"},
            "prd_draft": {"version": 1},
            "critic_result": {"overall_verdict": "block", "question_queue": ["旧问题"]},
            "refine_history": [{"source": "agent_result.state_patch"}],
            "finalization_ready": False,
        },
        turn_decision=turn_decision,
        current_state=_phase1_state(),
    )

    assert merged["workflow_stage"] == "finalize"
    assert merged["idea_parse_result"]["idea_summary"] == "来自 turn_decision"
    assert merged["prd_draft"]["version"] == 3
    assert merged["critic_result"]["overall_verdict"] == "pass"
    assert merged["refine_history"] == [{"source": "turn_decision"}]
    assert merged["finalization_ready"] is True
