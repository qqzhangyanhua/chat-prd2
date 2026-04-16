from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.repositories import prd as prd_repository
from app.repositories import sessions as sessions_repository
from app.repositories import state as state_repository


def _compact_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_export_sections_from_draft(raw_sections: dict) -> dict:
    def _content_from_entries(value: dict) -> tuple[str, str]:
        entries = value.get("entries")
        if not isinstance(entries, list):
            return "", "missing"
        texts: list[str] = []
        statuses: list[str] = []
        for item in entries:
            if not isinstance(item, dict):
                continue
            text = _compact_text(item.get("text"))
            if not text:
                continue
            assertion_state = item.get("assertion_state")
            if assertion_state == "to_validate":
                texts.append(f"待验证：{text}")
                statuses.append("draft")
            else:
                texts.append(text)
                statuses.append("confirmed" if assertion_state == "confirmed" else "draft")
        if not texts:
            return "", "missing"
        status = "confirmed" if statuses and all(item == "confirmed" for item in statuses) else "draft"
        return "\n".join(texts), status

    def _get_dict(key: str) -> dict:
        value = raw_sections.get(key)
        return value if isinstance(value, dict) else {}

    def _get_content(key: str) -> tuple[str, str]:
        value = _get_dict(key)
        direct_content = _compact_text(value.get("content"))
        if direct_content:
            return direct_content, value.get("status", "draft")
        return _content_from_entries(value)

    summary = _get_dict("summary")
    if not _compact_text(summary.get("content")):
        one_liner = _get_dict("one_liner")
        positioning = _get_dict("positioning")
        if _compact_text(one_liner.get("content")):
            summary = {
                "title": "一句话概述",
                "content": _compact_text(one_liner.get("content")),
                "status": one_liner.get("status", "draft"),
            }
        elif _compact_text(positioning.get("content")):
            summary = {
                "title": "一句话概述",
                "content": _compact_text(positioning.get("content")),
                "status": positioning.get("status", "draft"),
            }

    return {
        "summary": {
            "title": "一句话概述",
            "content": _compact_text(summary.get("content")),
            "status": summary.get("status", "draft"),
        },
        "target_user": {
            "title": "目标用户",
            "content": _get_content("target_user")[0],
            "status": _get_content("target_user")[1],
        },
        "problem": {
            "title": "核心问题",
            "content": _get_content("problem")[0],
            "status": _get_content("problem")[1],
        },
        "solution": {
            "title": "解决方案",
            "content": _get_content("solution")[0],
            "status": _get_content("solution")[1],
        },
        "mvp_scope": {
            "title": "MVP 范围",
            "content": _get_content("mvp_scope")[0],
            "status": _get_content("mvp_scope")[1],
        },
        "constraints": {
            "title": "约束条件",
            "content": _get_content("constraints")[0],
            "status": _get_content("constraints")[1],
        },
        "success_metrics": {
            "title": "成功指标",
            "content": _get_content("success_metrics")[0],
            "status": _get_content("success_metrics")[1],
        },
        "out_of_scope": {
            "title": "不做清单",
            "content": _get_content("out_of_scope")[0],
            "status": _get_content("out_of_scope")[1],
        },
        "open_questions": {
            "title": "待确认问题",
            "content": _get_content("open_questions")[0],
            "status": _get_content("open_questions")[1],
        },
    }


def build_export_sections(state: dict, snapshot: dict) -> tuple[dict, bool]:
    prd_draft = state.get("prd_draft") if isinstance(state, dict) else None
    if isinstance(prd_draft, dict):
        raw_sections = prd_draft.get("sections")
        if isinstance(raw_sections, dict) and raw_sections:
            normalized = _normalize_export_sections_from_draft(raw_sections)
            return normalized, prd_draft.get("status") == "finalized"

    snapshot_sections = snapshot.get("sections", {}) if isinstance(snapshot, dict) else {}
    return {
        "target_user": snapshot_sections.get("target_user", {}),
        "problem": snapshot_sections.get("problem", {}),
        "solution": snapshot_sections.get("solution", {}),
        "mvp_scope": snapshot_sections.get("mvp_scope", {}),
    }, False


def build_markdown_export(sections: dict, *, is_final: bool) -> str:
    blocks = [
        "# PRD",
        "",
        f"状态：{'终稿' if is_final else '草稿'}",
    ]

    ordered = [
        ("summary", "一句话概述"),
        ("target_user", "目标用户"),
        ("problem", "核心问题"),
        ("solution", "解决方案"),
        ("mvp_scope", "MVP 范围"),
        ("constraints", "约束条件"),
        ("success_metrics", "成功指标"),
        ("out_of_scope", "不做清单"),
        ("open_questions", "待确认问题"),
    ]

    for key, fallback_title in ordered:
        value = sections.get(key)
        if not isinstance(value, dict):
            continue
        content = _compact_text(value.get("content"))
        if not content:
            continue
        title = _compact_text(value.get("title")) or fallback_title
        blocks.extend(["", f"## {title}", content])

    return "\n".join(blocks)


def export_markdown(db: Session, session_id: str, user_id: str) -> dict[str, str]:
    session = sessions_repository.get_session_for_user(db, session_id, user_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    latest_state = state_repository.get_latest_state(db, session_id) or {}
    snapshot = prd_repository.get_latest_prd_snapshot(db, session_id)
    sections, is_final = build_export_sections(
        latest_state,
        {"sections": snapshot.sections if snapshot else {}},
    )
    content = build_markdown_export(sections, is_final=is_final)
    return {"file_name": "ai-cofounder-prd.md", "content": content}
