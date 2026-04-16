from __future__ import annotations

from copy import deepcopy

from app.agent.extractor import normalize_text

FINALIZE_CONFIRM_PHRASES = (
    "确认设计",
    "确认无误",
    "开始整理",
    "输出最终版",
    "生成最终版",
)

BUSINESS_PREFERENCE_PHRASES = (
    "业务版",
    "偏业务",
    "业务描述",
)

TECHNICAL_PREFERENCE_PHRASES = (
    "技术版",
    "偏技术",
    "技术细节",
    "技术实现",
)

FINALIZE_PREFERENCES = ("balanced", "business", "technical")


def normalize_section(title: str, content: str | None, status: str = "confirmed") -> dict[str, str]:
    normalized_content = normalize_text(content or "")
    normalized_status = status if status in {"missing", "draft", "inferred", "confirmed"} else "confirmed"
    return {
        "title": title,
        "content": normalized_content,
        "status": normalized_status if normalized_content else "missing",
    }


def _section_content_from_entries(value: dict) -> tuple[str, str]:
    entries = value.get("entries")
    if not isinstance(entries, list):
        return "", "missing"
    texts: list[str] = []
    statuses: list[str] = []
    for item in entries:
        if not isinstance(item, dict):
            continue
        text = normalize_text(str(item.get("text") or ""))
        if not text:
            continue
        texts.append(text)
        assertion_state = item.get("assertion_state")
        if assertion_state == "confirmed":
            statuses.append("confirmed")
        else:
            statuses.append("draft")
    if not texts:
        return "", "missing"
    status = "confirmed" if statuses and all(item == "confirmed" for item in statuses) else "draft"
    return "\n".join(texts), status


def normalize_prd_draft_sections(prd_draft: dict) -> dict[str, dict[str, str]]:
    raw_sections = deepcopy((prd_draft or {}).get("sections") or {})

    def _read_content(key: str) -> str:
        value = raw_sections.get(key)
        if isinstance(value, dict):
            direct_content = normalize_text(str(value.get("content") or ""))
            if direct_content:
                return direct_content
            entry_content, _ = _section_content_from_entries(value)
            return entry_content
        return ""

    def _read_status(key: str, fallback: str) -> str:
        value = raw_sections.get(key)
        if isinstance(value, dict):
            status = value.get("status")
            if isinstance(status, str) and status:
                return status
            _, entry_status = _section_content_from_entries(value)
            if entry_status != "missing":
                return entry_status
        return fallback

    summary_content = _read_content("summary")
    if not summary_content:
        summary_content = _read_content("one_liner") or _read_content("positioning")

    return {
        "summary": normalize_section("一句话概述", summary_content, _read_status("summary", "draft")),
        "target_user": normalize_section("目标用户", _read_content("target_user"), _read_status("target_user", "confirmed")),
        "problem": normalize_section("核心问题", _read_content("problem"), _read_status("problem", "confirmed")),
        "solution": normalize_section("解决方案", _read_content("solution"), _read_status("solution", "confirmed")),
        "mvp_scope": normalize_section("MVP 范围", _read_content("mvp_scope"), _read_status("mvp_scope", "confirmed")),
        "constraints": normalize_section("约束条件", _read_content("constraints"), _read_status("constraints", "draft")),
        "success_metrics": normalize_section("成功指标", _read_content("success_metrics"), _read_status("success_metrics", "draft")),
        "out_of_scope": normalize_section("不做清单", _read_content("out_of_scope"), _read_status("out_of_scope", "draft")),
        "open_questions": normalize_section("待确认问题", _read_content("open_questions"), _read_status("open_questions", "draft")),
    }


def is_finalize_confirm_input(user_input: str) -> bool:
    normalized = normalize_text(user_input)
    if not normalized:
        return False
    return any(phrase in normalized for phrase in FINALIZE_CONFIRM_PHRASES) or "确认" in normalized


def resolve_finalize_preference(user_input: str) -> str:
    normalized = normalize_text(user_input)
    if any(phrase in normalized for phrase in TECHNICAL_PREFERENCE_PHRASES):
        return "technical"
    if any(phrase in normalized for phrase in BUSINESS_PREFERENCE_PHRASES):
        return "business"
    return "balanced"


def normalize_finalize_preference(preference: str | None) -> str | None:
    if preference is None:
        return None
    normalized = normalize_text(preference)
    return normalized if normalized in FINALIZE_PREFERENCES else None


def build_finalized_sections(prd_draft: dict, preference: str) -> dict[str, dict[str, str]]:
    sections = normalize_prd_draft_sections(prd_draft)

    summary = sections["summary"]["content"]
    target_user = sections["target_user"]["content"]
    problem = sections["problem"]["content"]
    solution = sections["solution"]["content"]
    mvp_scope = sections["mvp_scope"]["content"]
    constraints = sections["constraints"]["content"]
    success_metrics = sections["success_metrics"]["content"]
    out_of_scope = sections["out_of_scope"]["content"]
    open_questions = sections["open_questions"]["content"]

    if preference == "technical" and constraints:
        solution = f"{solution}\n\n技术约束：{constraints}".strip()
    elif preference == "business" and out_of_scope:
        mvp_scope = f"{mvp_scope}\n\n本阶段明确不做：{out_of_scope}".strip()

    return {
        "summary": normalize_section("一句话概述", summary, "confirmed" if summary else "missing"),
        "target_user": normalize_section("目标用户", target_user, "confirmed" if target_user else "missing"),
        "problem": normalize_section("核心问题", problem, "confirmed" if problem else "missing"),
        "solution": normalize_section("解决方案", solution, "confirmed" if solution else "missing"),
        "mvp_scope": normalize_section("MVP 范围", mvp_scope, "confirmed" if mvp_scope else "missing"),
        "constraints": normalize_section("约束条件", constraints, "confirmed" if constraints else "missing"),
        "success_metrics": normalize_section("成功指标", success_metrics, "confirmed" if success_metrics else "missing"),
        "out_of_scope": normalize_section("不做清单", out_of_scope, "confirmed" if out_of_scope else "missing"),
        "open_questions": normalize_section("待确认问题", open_questions, "draft" if open_questions else "missing"),
    }
