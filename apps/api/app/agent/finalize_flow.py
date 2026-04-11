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


def normalize_section(title: str, content: str | None, status: str = "confirmed") -> dict[str, str]:
    normalized_content = normalize_text(content or "")
    normalized_status = status if status in {"missing", "draft", "inferred", "confirmed"} else "confirmed"
    return {
        "title": title,
        "content": normalized_content,
        "status": normalized_status if normalized_content else "missing",
    }


def normalize_prd_draft_sections(prd_draft: dict) -> dict[str, dict[str, str]]:
    raw_sections = deepcopy((prd_draft or {}).get("sections") or {})

    def _read_content(key: str) -> str:
        value = raw_sections.get(key)
        if isinstance(value, dict):
            return normalize_text(str(value.get("content") or ""))
        return ""

    summary_content = _read_content("summary")
    if not summary_content:
        summary_content = _read_content("one_liner") or _read_content("positioning")

    return {
        "summary": normalize_section("一句话概述", summary_content, "draft"),
        "target_user": normalize_section("目标用户", _read_content("target_user"), "confirmed"),
        "problem": normalize_section("核心问题", _read_content("problem"), "confirmed"),
        "solution": normalize_section("解决方案", _read_content("solution"), "confirmed"),
        "mvp_scope": normalize_section("MVP 范围", _read_content("mvp_scope"), "confirmed"),
        "constraints": normalize_section("约束条件", _read_content("constraints"), "draft"),
        "success_metrics": normalize_section("成功指标", _read_content("success_metrics"), "draft"),
        "out_of_scope": normalize_section("不做清单", _read_content("out_of_scope"), "draft"),
        "open_questions": normalize_section("待确认问题", _read_content("open_questions"), "draft"),
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
