from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Literal


ExtractionConfidence = Literal["high", "medium", "low"]
ExtractionSource = Literal["rule", "model"]

GENERIC_CONTINUATIONS = {
    "继续",
    "继续吧",
    "继续推进",
    "继续下去",
    "好的",
    "好",
    "嗯",
    "ok",
    "okay",
}

UNCERTAIN_REPLY_PHRASES = (
    "还没想好",
    "还没有想好",
    "不确定",
    "不清楚",
    "待定",
    "之后再说",
    "再想想",
    "没想好",
)

SECTION_TITLES = {
    "target_user": "目标用户",
    "problem": "核心问题",
    "solution": "解决方案",
    "mvp_scope": "MVP 范围",
}

NEXT_STAGE_HINTS = {
    "target_user": "问题定义",
    "problem": "方案收敛",
    "solution": "MVP 收敛",
    "mvp_scope": "总结共识",
}


@dataclass(slots=True)
class StructuredExtractionResult:
    should_update: bool
    state_patch: dict = field(default_factory=dict)
    prd_patch: dict = field(default_factory=dict)
    confidence: ExtractionConfidence = "low"
    reasoning_summary: str = ""
    decision_log: list[dict[str, str]] = field(default_factory=list)
    source: ExtractionSource = "rule"


def normalize_text(user_input: str) -> str:
    return " ".join(user_input.split()).strip()


def is_missing(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, list):
        return len(value) == 0
    return False


def first_missing_section(state: dict) -> str | None:
    for key in ("target_user", "problem", "solution", "mvp_scope"):
        if is_missing(state.get(key)):
            return key
    return None


def should_capture(user_input: str) -> bool:
    normalized = normalize_text(user_input)
    return bool(normalized) and normalized.lower() not in GENERIC_CONTINUATIONS


def build_rule_extraction_result(state: dict, user_input: str) -> StructuredExtractionResult:
    current_missing_section = first_missing_section(state)
    if current_missing_section is None or not should_capture(user_input):
        return StructuredExtractionResult(
            should_update=False,
            confidence="low",
            reasoning_summary="规则提取未识别到可更新字段",
            source="rule",
        )

    normalized = normalize_text(user_input)
    next_iteration = int(state.get("iteration") or 0) + 1
    state_patch: dict[str, object] = {
        "iteration": next_iteration,
        "stage_hint": NEXT_STAGE_HINTS[current_missing_section],
    }
    if current_missing_section == "mvp_scope":
        state_patch["mvp_scope"] = [normalized]
    else:
        state_patch[current_missing_section] = normalized

    return StructuredExtractionResult(
        should_update=True,
        state_patch=state_patch,
        prd_patch={
            current_missing_section: {
                "title": SECTION_TITLES[current_missing_section],
                "content": normalized,
                "status": "confirmed",
            }
        },
        confidence="medium",
        reasoning_summary=f"规则提取将输入归入 {current_missing_section}",
        decision_log=[{"section": current_missing_section, "value": normalized}],
        source="rule",
    )


def choose_extraction_result(
    rule_result: StructuredExtractionResult,
    model_result: StructuredExtractionResult | None,
) -> StructuredExtractionResult:
    if (
        model_result is not None
        and model_result.should_update
        and model_result.confidence in {"high", "medium"}
    ):
        return model_result
    return rule_result


def _append_section_content(
    existing: dict[str, Any] | None,
    title: str,
    fragment: str,
    *,
    status: str = "confirmed",
) -> dict[str, str]:
    previous = ""
    if isinstance(existing, dict):
        previous = normalize_text(str(existing.get("content") or ""))

    next_fragment = normalize_text(fragment)
    if previous and next_fragment:
        content = f"{previous}\n{next_fragment}"
    else:
        content = previous or next_fragment

    normalized_status = status if status in {"missing", "draft", "inferred", "confirmed"} else "confirmed"
    return {
        "title": (existing or {}).get("title") or title,
        "content": content,
        "status": normalized_status if content else "missing",
    }


def _looks_like_out_of_scope_answer(text: str) -> bool:
    return any(
        token in text
        for token in ("不做", "暂不做", "先不做", "后面再做", "不是首版", "二期再说")
    )


def _looks_like_metric_answer(text: str) -> bool:
    return any(
        token in text
        for token in ("转化率", "留存", "付费率", "活跃", "使用率", "成功率", "分钟", "%", "天")
    )


def _merge_answer_into_sections(
    sections: dict[str, Any],
    user_input: str,
    signals: dict[str, bool],
    critic_result: dict[str, Any] | None,
) -> dict[str, Any]:
    next_sections = deepcopy(sections or {})
    text = normalize_text(user_input)
    if not text:
        return next_sections

    wrote_formal_section = False

    if signals.get("file_format"):
        next_sections["mvp_scope"] = _append_section_content(
            next_sections.get("mvp_scope"),
            "MVP 范围",
            f"首版支持的核心文件格式：{text}",
        )
        wrote_formal_section = True

    if signals.get("preview_depth"):
        next_sections["solution"] = _append_section_content(
            next_sections.get("solution"),
            "解决方案",
            f"首版预览交互能力：{text}",
        )
        wrote_formal_section = True

    if signals.get("permission_boundary"):
        next_sections["constraints"] = _append_section_content(
            next_sections.get("constraints"),
            "约束条件",
            f"权限边界：{text}",
        )
        wrote_formal_section = True

    if _looks_like_out_of_scope_answer(text):
        next_sections["out_of_scope"] = _append_section_content(
            next_sections.get("out_of_scope"),
            "不做清单",
            text,
            status="draft",
        )
        wrote_formal_section = True

    if _looks_like_metric_answer(text):
        next_sections["success_metrics"] = _append_section_content(
            next_sections.get("success_metrics"),
            "成功指标",
            text,
            status="draft",
        )
        wrote_formal_section = True

    if not wrote_formal_section and critic_result:
        question_queue = critic_result.get("question_queue")
        first_question = question_queue[0] if isinstance(question_queue, list) and question_queue else ""
        if first_question:
            next_sections["open_questions"] = _append_section_content(
                next_sections.get("open_questions"),
                "待确认问题",
                f"围绕问题“{first_question}”补充：{text}",
                status="draft",
            )

    notes = dict(next_sections.get("refine_notes") or {})
    previous_notes = normalize_text(str(notes.get("content") or ""))
    notes["title"] = notes.get("title") or "补充记录"
    notes["status"] = notes.get("status") or "draft"
    notes["content"] = f"{previous_notes}\n- {text}".strip() if previous_notes else f"- {text}"
    next_sections["refine_notes"] = notes

    return next_sections


def merge_refine_input_into_prd_draft(
    prd_draft: dict[str, Any],
    critic_result: dict[str, Any] | None,
    user_input: str,
) -> tuple[dict[str, Any], dict[str, bool]]:
    """把 refine_loop 的用户补充写回 PRD 草稿，并推进到下一个草稿版本。"""

    next_draft = deepcopy(prd_draft or {})
    raw_missing = list(next_draft.get("missing_information") or [])

    normalized = normalize_text(user_input)
    upper = normalized.upper()

    format_tokens = ("DWG", "DXF", "PDF", "IFC", "STEP", "GLTF", "OBJ")
    preview_tokens = ("测量", "标注", "剖切", "旋转", "缩放", "构件选择")
    permission_tokens = ("访客", "成员", "管理员", "权限", "分享", "下载限制", "到期")

    signals = {
        "file_format": any(tok in upper for tok in format_tokens),
        "preview_depth": any(tok in normalized for tok in preview_tokens),
        "permission_boundary": any(tok in normalized for tok in permission_tokens),
    }
    if _contains_uncertain_reply(normalized):
        signals = {
            "file_format": False,
            "preview_depth": False,
            "permission_boundary": False,
        }

    def _keep(item: str) -> bool:
        text = str(item)
        if signals["file_format"] and _is_file_format_gap(text):
            return False
        if signals["preview_depth"] and _is_preview_depth_gap(text):
            return False
        if signals["permission_boundary"] and _is_permission_boundary_gap(text):
            return False
        return True

    next_draft["missing_information"] = [item for item in raw_missing if _keep(str(item))]

    sections = deepcopy(next_draft.get("sections") or {})
    sections = _merge_answer_into_sections(
        sections,
        normalized,
        signals,
        critic_result,
    )
    next_draft["sections"] = sections

    next_draft["version"] = int(next_draft.get("version") or 1) + 1
    next_draft["status"] = "draft_refined"
    next_draft["critic_ready"] = True

    return next_draft, signals


def _is_file_format_gap(text: str) -> bool:
    return any(
        token in text
        for token in (
            "核心文件格式",
            "文件格式",
            "图纸格式",
            "模型格式",
            "支持哪些图纸格式",
            "支持哪些文件格式",
            "支持哪些图纸/模型格式",
            "导入方式",
        )
    )


def _is_preview_depth_gap(text: str) -> bool:
    return any(
        token in text
        for token in (
            "预览深度",
            "交互能力边界",
            "测量",
            "标注",
            "剖切",
            "爆炸",
        )
    )


def _is_permission_boundary_gap(text: str) -> bool:
    return any(
        token in text
        for token in (
            "权限边界",
            "权限与角色模型",
            "谁能看、谁能改、谁能分享",
            "不同角色的权限访问",
            "权限访问",
        )
    )


def _contains_uncertain_reply(text: str) -> bool:
    return any(phrase in text for phrase in UNCERTAIN_REPLY_PHRASES)


def _normalize_prd_section(section: str, value: Any) -> dict[str, str] | None:
    if not isinstance(value, dict):
        return None
    content = normalize_text(str(value.get("content", "")))
    if not content:
        return None
    title = normalize_text(str(value.get("title", ""))) or SECTION_TITLES[section]
    status = value.get("status")
    normalized_status = status if status in {"confirmed", "inferred"} else "confirmed"
    return {
        "title": title,
        "content": content,
        "status": normalized_status,
    }


def normalize_model_extraction_result(payload: dict[str, Any] | None) -> StructuredExtractionResult | None:
    if not isinstance(payload, dict) or not payload.get("should_update"):
        return None

    confidence_raw = payload.get("confidence")
    confidence: ExtractionConfidence = (
        confidence_raw if confidence_raw in {"high", "medium", "low"} else "low"
    )

    raw_state_patch = payload.get("state_patch")
    raw_prd_patch = payload.get("prd_patch")
    if not isinstance(raw_state_patch, dict):
        raw_state_patch = {}
    if not isinstance(raw_prd_patch, dict):
        raw_prd_patch = {}

    state_patch: dict[str, Any] = {}
    for key in ("target_user", "problem", "solution"):
        value = raw_state_patch.get(key)
        if isinstance(value, str) and normalize_text(value):
            state_patch[key] = normalize_text(value)

    mvp_scope = raw_state_patch.get("mvp_scope")
    if isinstance(mvp_scope, list):
        normalized_scope = [
            normalize_text(str(item))
            for item in mvp_scope
            if normalize_text(str(item))
        ]
        if normalized_scope:
            state_patch["mvp_scope"] = normalized_scope

    if isinstance(raw_state_patch.get("iteration"), int):
        state_patch["iteration"] = raw_state_patch["iteration"]
    if isinstance(raw_state_patch.get("stage_hint"), str) and normalize_text(raw_state_patch["stage_hint"]):
        state_patch["stage_hint"] = normalize_text(raw_state_patch["stage_hint"])

    prd_patch: dict[str, dict[str, str]] = {}
    for section in ("target_user", "problem", "solution", "mvp_scope"):
        normalized_section = _normalize_prd_section(section, raw_prd_patch.get(section))
        if normalized_section is not None:
            prd_patch[section] = normalized_section

    if not state_patch and not prd_patch:
        return None

    decision_log = [
        {"section": section, "value": details["content"]}
        for section, details in prd_patch.items()
    ]

    return StructuredExtractionResult(
        should_update=True,
        state_patch=state_patch,
        prd_patch=prd_patch,
        confidence=confidence,
        reasoning_summary=normalize_text(str(payload.get("reasoning_summary", ""))),
        decision_log=decision_log,
        source="model",
    )
