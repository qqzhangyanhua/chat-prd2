from __future__ import annotations

from typing import Any, Dict, List

from app.agent.types import IdeaParseResult, UnderstandingResult

from app.agent.extractor import (
    first_missing_section,
    is_missing,
    normalize_text,
    should_capture,
)

USER_TOO_BROAD_PHRASES = (
    "所有创业者",
    "所有用户",
    "面向所有人",
    "泛互联网用户",
)
PROBLEM_TOO_VAGUE_PHRASES = ("效率低", "不方便", "体验不好")
SOLUTION_INDICATORS = ("方案", "产品", "功能", "平台", "工具", "服务")
ASSUMPTION_PHRASES = ("我猜", "可能", "也许", "大概")
AMBIGUOUS_PHRASES = ("还不清楚", "不确定", "待明确", "不知道", "模糊")

IDEA_INTENT_PREFIXES = ("我想做", "我想要做", "我要做", "我打算做", "想做", "希望打造")
IDEA_FILLER_PREFIXES = ("一个", "一款", "一座", "一次", "一段")
DOMAIN_KEYWORDS = (
    ("3d", "3D"),
    ("图纸", "图纸"),
    ("预览", "预览"),
    ("平台", "平台"),
    ("在线", "在线"),
)


def _build_candidate_updates(state: dict, normalized_input: str) -> Dict[str, Any]:
    # 理解层的最小候选字段映射，后续会与决策层解耦
    updates: Dict[str, Any] = {}
    missing = first_missing_section(state)
    if not missing:
        return updates

    if missing == "mvp_scope":
        updates["mvp_scope"] = [normalized_input]
    else:
        updates[missing] = normalized_input

    return updates


def _detect_assumptions(normalized_input: str) -> List[str]:
    normalized = normalized_input.lower()
    for phrase in ASSUMPTION_PHRASES:
        if phrase in normalized:
            return [normalized_input]
    return []


def _detect_ambiguous_points(normalized_input: str) -> List[str]:
    normalized = normalized_input.lower()
    points: List[str] = []
    for phrase in AMBIGUOUS_PHRASES:
        if phrase in normalized:
            points.append(f"表达尚不明确：{phrase}")
    return points


def _detect_risk_hints(state: dict, normalized_input: str) -> List[str]:
    normalized = normalized_input.lower()
    hints: List[str] = []
    if any(phrase in normalized for phrase in USER_TOO_BROAD_PHRASES):
        hints.append("user_too_broad")
    if any(phrase in normalized for phrase in PROBLEM_TOO_VAGUE_PHRASES):
        hints.append("problem_too_vague")
    if is_missing(state.get("problem")):
        if any(indicator in normalized for indicator in SOLUTION_INDICATORS):
            hints.append("solution_before_problem")
    return hints


def _build_summary(normalized_input: str) -> str:
    if not normalized_input:
        return "本轮输入未提供具体内容。"
    return f"用户表述了：{normalized_input}。"


def _trim_product_descriptor(normalized: str) -> str:
    text = normalized
    for prefix in IDEA_INTENT_PREFIXES:
        if text.startswith(prefix):
            text = text[len(prefix) :]
            break
    for filler in IDEA_FILLER_PREFIXES:
        if text.startswith(filler):
            text = text[len(filler) :]
            break
    return text.strip("。！？!?").strip()


def _collect_domain_signals(normalized: str) -> List[str]:
    lowered = normalized.lower()
    signals: List[str] = []
    for keyword, label in DOMAIN_KEYWORDS:
        if keyword.isascii():
            if keyword in lowered:
                signals.append(label)
        else:
            if keyword in normalized:
                signals.append(label)
    if "3d" in lowered and "预览" in normalized:
        signals.append("3D预览")
    return list(dict.fromkeys(signals))


def _collect_explicit_requirements(normalized: str) -> List[str]:
    requirements: List[str] = []
    lowered = normalized.lower()
    if "预览" in normalized:
        requirements.append("提供可交互的预览功能")
    if "3d" in lowered:
        requirements.append("支持 3D 渲染或展示")
    if "平台" in normalized:
        requirements.append("搭建面向用户的在线平台入口")
    if "在线" in normalized:
        requirements.append("通过浏览器即可访问")
    if "图纸" in normalized:
        requirements.append("兼容展示多种图纸层级结构")
    return list(dict.fromkeys(requirements))


def _collect_implicit_assumptions(normalized: str) -> List[str]:
    assumptions: List[str] = []
    lowered = normalized.lower()
    if "在线" in normalized:
        assumptions.append("用户拥有可用的网络连接")
    if "3d" in lowered:
        assumptions.append("已有 3D 数据可供预览")
    if "图纸" in normalized:
        assumptions.append("图纸内容可以数字化处理")
    return list(dict.fromkeys(assumptions))


def _build_open_questions(product_type: str | None) -> List[str]:
    questions: List[str] = [
        "需要支持哪些图纸格式？",
        "如何规划不同角色的权限访问？",
    ]
    if product_type:
        questions.append(f"{product_type} 首批要解决的核心场景是什么？")
    questions.append("是否需要同步更新图纸底层数据？")
    return questions


def parse_idea_input(user_input: str) -> IdeaParseResult:
    normalized = normalize_text(user_input)
    idea_summary = (
        f"产品想法：{normalized}" if normalized else "未提供可解析的产品想法"
    )
    product_type = _trim_product_descriptor(normalized)
    domain_signals = _collect_domain_signals(normalized)
    explicit_requirements = _collect_explicit_requirements(normalized)
    implicit_assumptions = _collect_implicit_assumptions(normalized)
    open_questions = _build_open_questions(product_type)
    confidence = "medium" if domain_signals else "low"
    return IdeaParseResult(
        idea_summary=idea_summary,
        product_type=product_type or None,
        domain_signals=domain_signals,
        explicit_requirements=explicit_requirements,
        implicit_assumptions=implicit_assumptions,
        open_questions=open_questions,
        confidence=confidence,
    )


def understand_user_input(state: dict, user_input: str) -> UnderstandingResult:
    if state.get("workflow_stage") == "idea_parser":
        idea_result = parse_idea_input(user_input)
        return UnderstandingResult(
            summary=idea_result.idea_summary,
            candidate_updates={},
            assumption_candidates=list(idea_result.implicit_assumptions),
            ambiguous_points=list(idea_result.open_questions),
            risk_hints=[],
        )
    normalized = normalize_text(user_input)
    summary = _build_summary(normalized)
    candidate_updates: Dict[str, Any] = {}
    if normalized and should_capture(user_input):
        candidate_updates = _build_candidate_updates(state, normalized)

    assumption_candidates = _detect_assumptions(normalized)
    ambiguous_points = _detect_ambiguous_points(normalized)
    risk_hints = _detect_risk_hints(state, normalized)

    return UnderstandingResult(
        summary=summary,
        candidate_updates=candidate_updates,
        assumption_candidates=assumption_candidates,
        ambiguous_points=ambiguous_points,
        risk_hints=risk_hints,
    )
