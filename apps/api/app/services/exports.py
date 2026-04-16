from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.repositories import prd as prd_repository
from app.repositories import sessions as sessions_repository
from app.repositories import state as state_repository
from app.services.finalize_session import build_finalize_delivery_milestone
from app.services.prd_review import build_prd_review
from app.services.prd_runtime import build_prd_updated_event_data


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
            panel_sections = build_prd_updated_event_data(state, {}, {}).get("sections", {})
            normalized = _normalize_export_sections_from_draft(raw_sections)
            normalized.update(
                {
                    key: value
                    for key, value in panel_sections.items()
                    if key in {"target_user", "problem", "solution", "mvp_scope", "constraints", "success_metrics", "risks_to_validate", "open_questions"}
                }
            )
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
        ("risks_to_validate", "待验证 / 风险"),
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


def _build_handoff_summary(review: dict) -> str:
    lines: list[str] = []
    checks = review.get("checks")
    if isinstance(checks, dict):
        for key in ("goal_clarity", "scope_boundary", "success_metrics", "risk_exposure", "validation_completeness"):
            value = checks.get(key)
            if not isinstance(value, dict):
                continue
            verdict = _compact_text(value.get("verdict"))
            if verdict:
                lines.append(f"{key}: {verdict}")
    missing_sections = review.get("missing_sections")
    if isinstance(missing_sections, list):
        section_order = {
            "target_user": 0,
            "problem": 1,
            "solution": 2,
            "mvp_scope": 3,
            "constraints": 4,
            "success_metrics": 5,
            "risks_to_validate": 6,
            "open_questions": 7,
        }
        normalized = sorted(
            [item for item in missing_sections if isinstance(item, str) and item.strip()],
            key=lambda item: section_order.get(item, 999),
        )
        if normalized:
            lines.append(f"missing_sections: {', '.join(normalized)}")
    return "\n".join(lines)


def _resolve_appendix_review_summary(review: dict) -> str:
    checks = review.get("checks")
    if isinstance(checks, dict):
        verdicts = {
            _compact_text(value.get("verdict"))
            for value in checks.values()
            if isinstance(value, dict)
        }
        if "missing" in verdicts:
            return "当前 PRD 仍缺少关键章节，尚不能作为稳定交付基线。"
        if "needs_input" in verdicts:
            return "当前 PRD 结构已成型，但仍有待验证项或开放风险需要补齐。"
    return _compact_text(review.get("summary"))


def _build_export_appendix(review: dict) -> dict[str, str]:
    return {
        "review_summary": _resolve_appendix_review_summary(review),
        "handoff_summary": _build_handoff_summary(review),
    }


def _append_delivery_appendix(markdown: str, appendix: dict[str, str]) -> str:
    appendix_blocks: list[str] = []
    review_summary = _compact_text(appendix.get("review_summary"))
    handoff_summary = _compact_text(appendix.get("handoff_summary"))
    if review_summary:
        appendix_blocks.extend(["", "## 交付附录", review_summary])
    if handoff_summary:
        if not appendix_blocks:
            appendix_blocks.extend(["", "## 交付附录"])
        appendix_blocks.extend(["", "### Handoff Summary", handoff_summary])
    if not appendix_blocks:
        return markdown
    return f"{markdown}\n" + "\n".join(appendix_blocks)


def export_markdown(db: Session, session_id: str, user_id: str) -> dict[str, object]:
    session = sessions_repository.get_session_for_user(db, session_id, user_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    file_name = "ai-cofounder-prd.md"
    latest_state = state_repository.get_latest_state(db, session_id) or {}
    snapshot = prd_repository.get_latest_prd_snapshot(db, session_id)
    sections, is_final = build_export_sections(
        latest_state,
        {"sections": snapshot.sections if snapshot else {}},
    )
    review = build_prd_review(latest_state)
    appendix = _build_export_appendix(review)
    content = _append_delivery_appendix(
        build_markdown_export(sections, is_final=is_final),
        appendix,
    )
    return {
        "file_name": file_name,
        "content": content,
        "appendix": appendix,
        "delivery_milestones": {
            "finalize": build_finalize_delivery_milestone(latest_state),
            "export": {
                "file_name": file_name,
                "exported_at": datetime.now(timezone.utc).isoformat(),
            },
        },
    }
