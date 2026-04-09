from __future__ import annotations

from app.schemas.message import PrdUpdatedEventData


def preview_prd_sections(state: dict, patch: dict) -> dict:
    sections = state.get("prd_snapshot", {}).get("sections", {})
    if not patch:
        return sections
    return {**sections, **patch}


def preview_prd_meta(state: dict, state_patch: dict) -> dict:
    next_state = apply_state_patch_preview(dict(state), state_patch or {})
    workflow_stage = next_state.get("workflow_stage")
    finalization_ready = bool(next_state.get("finalization_ready"))
    prd_draft = next_state.get("prd_draft") if isinstance(next_state.get("prd_draft"), dict) else {}
    critic_result = next_state.get("critic_result") if isinstance(next_state.get("critic_result"), dict) else {}
    draft_version = prd_draft.get("version") if isinstance(prd_draft.get("version"), int) else None
    draft_status = prd_draft.get("status") if isinstance(prd_draft.get("status"), str) else None
    overall_verdict = critic_result.get("overall_verdict") if isinstance(critic_result.get("overall_verdict"), str) else None
    major_gaps = [
        item for item in critic_result.get("major_gaps", [])
        if isinstance(item, str) and item.strip()
    ]
    question_queue = [
        item for item in critic_result.get("question_queue", [])
        if isinstance(item, str) and item.strip()
    ]
    next_question = question_queue[0] if question_queue else None

    stage_label = "探索中"
    stage_tone = "draft"
    if workflow_stage == "completed" or draft_status == "finalized":
        stage_label = "已生成终稿"
        stage_tone = "final"
    elif workflow_stage == "finalize" or finalization_ready or overall_verdict == "pass":
        stage_label = "可整理终稿"
        stage_tone = "ready"
    elif workflow_stage == "refine_loop":
        stage_label = "草稿中"
        stage_tone = "draft"

    critic_summary = "系统正在持续沉淀当前 PRD 草稿。"
    if stage_label == "已生成终稿":
        critic_summary = "当前会话已经整理出最终版 PRD，后续修改会基于终稿增量更新。"
    elif overall_verdict == "pass":
        critic_summary = "Critic 已通过，可以整理最终版 PRD。"
    elif major_gaps:
        critic_summary = f"Critic 认为还有 {len(major_gaps)} 个关键缺口待补齐。"
    elif question_queue:
        critic_summary = f"Critic 还在等待 {len(question_queue)} 个问题的补充。"

    return {
        "stageLabel": stage_label,
        "stageTone": stage_tone,
        "criticSummary": critic_summary,
        "criticGaps": major_gaps,
        "draftVersion": draft_version,
        "nextQuestion": next_question,
    }


def build_prd_updated_event_data(state: dict, state_patch: dict, prd_patch: dict) -> dict:
    return PrdUpdatedEventData(
        sections=preview_prd_sections(state, prd_patch),
        meta=preview_prd_meta(state, state_patch),
    ).model_dump()


def apply_state_patch_preview(current_state: dict, patch: dict) -> dict:
    if not patch:
        return current_state
    return {**current_state, **patch}
