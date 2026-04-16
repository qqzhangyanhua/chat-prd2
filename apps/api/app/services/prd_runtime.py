from __future__ import annotations

from collections import OrderedDict

from app.agent.readiness import evaluate_finalize_readiness
from app.schemas.message import PrdUpdatedEventData


PRIMARY_SECTION_TITLES = OrderedDict(
    [
        ("target_user", "目标用户"),
        ("problem", "核心问题"),
        ("solution", "解决方案"),
        ("mvp_scope", "MVP 范围"),
        ("constraints", "约束条件"),
        ("success_metrics", "成功指标"),
        ("risks_to_validate", "待验证 / 风险"),
        ("open_questions", "待确认问题"),
    ]
)


def _apply_prd_patch_preview(current_state: dict, patch: dict) -> dict:
    if not patch:
        return current_state
    current_sections = current_state.get("prd_snapshot", {}).get("sections", {})
    current_state["prd_snapshot"] = {"sections": {**current_sections, **patch}}
    return current_state


def _section_content_from_draft(section: object) -> tuple[str, str]:
    if not isinstance(section, dict):
        return "", "missing"
    entries = section.get("entries")
    completeness = section.get("completeness")
    if isinstance(entries, list):
        texts = [
            str(item.get("text")).strip()
            for item in entries
            if isinstance(item, dict) and isinstance(item.get("text"), str) and item.get("text").strip()
        ]
        if not texts or completeness == "missing":
            return "", "missing"
        assertion_states = {
            item.get("assertion_state")
            for item in entries
            if isinstance(item, dict)
        }
        status = "confirmed"
        if "to_validate" in assertion_states or "inferred" in assertion_states or completeness != "complete":
            status = "inferred"
        return "\n".join(texts), status
    content = section.get("content")
    status = section.get("status")
    if isinstance(content, str) and content.strip():
        return content.strip(), status if status in {"confirmed", "inferred", "missing"} else "inferred"
    return "", "missing"


def _build_risk_summary(next_state: dict) -> tuple[str, str]:
    lines: list[str] = []
    prd_draft = next_state.get("prd_draft") if isinstance(next_state.get("prd_draft"), dict) else {}
    sections = prd_draft.get("sections") if isinstance(prd_draft.get("sections"), dict) else {}
    for key, section in sections.items():
        if not isinstance(section, dict):
            continue
        entries = section.get("entries")
        if not isinstance(entries, list):
            continue
        section_title = section.get("title") if isinstance(section.get("title"), str) else key
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            text = entry.get("text")
            if entry.get("assertion_state") != "to_validate" or not isinstance(text, str) or not text.strip():
                continue
            lines.append(f"{section_title}：{text.strip()}（待验证）")
    diagnostics = next_state.get("diagnostics")
    if isinstance(diagnostics, list):
        for item in diagnostics:
            if not isinstance(item, dict) or item.get("status") != "open":
                continue
            if item.get("bucket") not in {"risk", "to_validate"}:
                continue
            title = item.get("title")
            if isinstance(title, str) and title.strip():
                lines.append(f"需确认：{title.strip()}")
    deduped = list(dict.fromkeys(lines))
    if not deduped:
        return "", "missing"
    return "\n".join(deduped), "inferred"


def _build_open_questions_summary(next_state: dict, readiness: dict[str, object]) -> tuple[str, str]:
    prompts: list[str] = []
    gap_prompts = readiness.get("gap_prompts")
    if isinstance(gap_prompts, list):
        prompts.extend([item.strip() for item in gap_prompts if isinstance(item, str) and item.strip()])
    open_questions = next_state.get("open_questions")
    if isinstance(open_questions, list):
        prompts.extend([item.strip() for item in open_questions if isinstance(item, str) and item.strip()])
    deduped = list(dict.fromkeys(prompts))
    if not deduped:
        return "", "missing"
    return "\n".join(deduped), "inferred"


def _project_panel_sections(next_state: dict, readiness: dict[str, object]) -> dict[str, dict[str, str]]:
    projected: dict[str, dict[str, str]] = {}
    prd_draft = next_state.get("prd_draft") if isinstance(next_state.get("prd_draft"), dict) else {}
    draft_sections = prd_draft.get("sections") if isinstance(prd_draft.get("sections"), dict) else {}
    fallback_sections = next_state.get("prd_snapshot", {}).get("sections", {})
    if not isinstance(fallback_sections, dict):
        fallback_sections = {}

    for key, title in PRIMARY_SECTION_TITLES.items():
        if key == "risks_to_validate":
            content, status = _build_risk_summary(next_state)
        elif key == "open_questions":
            content, status = _build_open_questions_summary(next_state, readiness)
        else:
            content, status = _section_content_from_draft(draft_sections.get(key))
            if not content:
                content, status = _section_content_from_draft(fallback_sections.get(key))
        projected[key] = {
            "title": title,
            "content": content,
            "status": status,
        }
    return projected


def _resolve_sections_changed(next_state: dict, prd_patch: dict) -> list[str]:
    prd_draft = next_state.get("prd_draft")
    if isinstance(prd_draft, dict):
        summary = prd_draft.get("summary")
        if isinstance(summary, dict):
            section_keys = summary.get("section_keys")
            if isinstance(section_keys, list):
                return [item for item in section_keys if isinstance(item, str) and item.strip()]
    return [key for key in prd_patch.keys() if isinstance(key, str) and key.strip()]


def _has_structured_draft_signal(next_state: dict) -> bool:
    prd_draft = next_state.get("prd_draft")
    if not isinstance(prd_draft, dict):
        return False
    sections = prd_draft.get("sections")
    if not isinstance(sections, dict) or not sections:
        return False
    for section in sections.values():
        if not isinstance(section, dict):
            continue
        if isinstance(section.get("entries"), list):
            return True
        if isinstance(section.get("completeness"), str):
            return True
    return False


def preview_prd_sections(state: dict, patch: dict) -> dict:
    next_state = _apply_prd_patch_preview(apply_state_patch_preview(dict(state), {}), patch or {})
    readiness = evaluate_finalize_readiness(next_state)
    return _project_panel_sections(next_state, readiness)


def preview_prd_meta(state: dict, state_patch: dict) -> dict:
    next_state = apply_state_patch_preview(dict(state), state_patch or {})
    readiness = evaluate_finalize_readiness(next_state)
    workflow_stage = next_state.get("workflow_stage")
    structured_mode = _has_structured_draft_signal(next_state)
    finalization_ready = bool(next_state.get("finalization_ready")) or (
        structured_mode and bool(readiness.get("ready_for_confirmation"))
    )
    prd_draft = next_state.get("prd_draft") if isinstance(next_state.get("prd_draft"), dict) else {}
    critic_result = next_state.get("critic_result") if isinstance(next_state.get("critic_result"), dict) else {}
    if structured_mode and not critic_result:
        candidate = readiness.get("critic_result", {})
        if isinstance(candidate, dict):
            critic_result = candidate
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
    if workflow_stage == "completed" or draft_status == "finalized" or readiness.get("status") == "finalized":
        stage_label = "已生成终稿"
        stage_tone = "final"
    elif workflow_stage == "finalize" or finalization_ready or readiness.get("ready_for_confirmation") or overall_verdict == "pass":
        stage_label = "可确认初稿" if structured_mode else "可整理终稿"
        stage_tone = "ready"
    elif workflow_stage == "refine_loop" or (structured_mode and readiness.get("status") in {"drafting", "needs_input"}):
        stage_label = "草稿中"
        stage_tone = "draft"

    critic_summary = "系统正在持续沉淀当前 PRD 草稿。"
    if stage_label == "已生成终稿":
        critic_summary = "当前会话已经整理出最终版 PRD，后续修改会基于终稿增量更新。"
    elif readiness.get("ready_for_confirmation") or overall_verdict == "pass":
        critic_summary = (
            "关键信息已基本齐备，可以给用户确认当前 PRD 初稿。"
            if structured_mode else
            "Critic 已通过，可以整理最终版 PRD。"
        )
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
    next_state = apply_state_patch_preview(dict(state), state_patch or {})
    next_state = _apply_prd_patch_preview(next_state, prd_patch or {})
    readiness = evaluate_finalize_readiness(next_state)
    return PrdUpdatedEventData(
        sections=_project_panel_sections(next_state, readiness),
        meta=preview_prd_meta(state, state_patch),
        sections_changed=_resolve_sections_changed(next_state, prd_patch or {}),
        missing_sections=list(readiness.get("missing_sections", [])),
        gap_prompts=list(readiness.get("gap_prompts", [])),
        ready_for_confirmation=bool(readiness.get("ready_for_confirmation")),
    ).model_dump()


def build_prd_snapshot_payload(
    state: dict,
    *,
    snapshot_id: str,
    session_id: str,
    version: int,
) -> dict[str, object]:
    panel_payload = build_prd_updated_event_data(state, {}, {})
    return {
        "id": snapshot_id,
        "session_id": session_id,
        "version": version,
        "sections": panel_payload["sections"],
        "meta": panel_payload.get("meta"),
        "sections_changed": list(panel_payload.get("sections_changed", [])),
        "missing_sections": list(panel_payload.get("missing_sections", [])),
        "gap_prompts": list(panel_payload.get("gap_prompts", [])),
        "ready_for_confirmation": bool(panel_payload.get("ready_for_confirmation")),
    }


def apply_state_patch_preview(current_state: dict, patch: dict) -> dict:
    if not patch:
        return current_state
    return {**current_state, **patch}
