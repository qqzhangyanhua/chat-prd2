import importlib

import pytest


REQUIRED_DIMENSIONS = {
    "goal_clarity",
    "scope_boundary",
    "success_metrics",
    "risk_exposure",
    "validation_completeness",
}


def _load_review_module():
    try:
        return importlib.import_module("app.services.prd_review")
    except ModuleNotFoundError as exc:
        pytest.fail(f"prd_review module missing: {exc}")


def _entry(text: str, assertion_state: str = "confirmed") -> dict[str, object]:
    return {
        "id": f"entry-{text}",
        "text": text,
        "assertion_state": assertion_state,
        "evidence_ref_ids": ["evidence-1"],
    }


def _draft_section(
    title: str,
    *entries: dict[str, object],
    completeness: str = "complete",
) -> dict[str, object]:
    return {
        "title": title,
        "entries": list(entries),
        "completeness": completeness,
    }


def _structured_ready_state() -> dict[str, object]:
    return {
        "prd_draft": {
            "status": "drafting",
            "sections": {
                "target_user": _draft_section("目标用户", _entry("独立开发者")),
                "problem": _draft_section("核心问题", _entry("需求确认成本高")),
                "solution": _draft_section("解决方案", _entry("AI 协作问答流")),
                "mvp_scope": _draft_section("MVP 范围", _entry("只做 Web 工作台")),
                "constraints": _draft_section("约束条件", _entry("首版不做私有化部署")),
                "success_metrics": _draft_section("成功指标", _entry("7 天留存 >= 20%")),
                "risks_to_validate": _draft_section("待验证 / 风险", _entry("模型回答稳定性")),
                "open_questions": _draft_section("待确认问题", _entry("是否支持多人协作")),
            },
        },
        "diagnostics": [],
        "diagnostic_summary": {
            "open_count": 0,
            "unknown_count": 0,
            "risk_count": 0,
            "to_validate_count": 0,
        },
    }


def test_build_prd_review_returns_pass_when_required_truth_is_ready():
    module = _load_review_module()

    review = module.build_prd_review(_structured_ready_state())

    assert review["verdict"] == "pass"
    assert review["status"] == "ready_for_confirmation"
    assert review["summary"]
    assert set(review["checks"].keys()) == REQUIRED_DIMENSIONS
    assert review["gaps"] == []
    assert review["checks"]["goal_clarity"]["verdict"] == "pass"
    assert review["checks"]["scope_boundary"]["verdict"] == "pass"
    assert review["checks"]["success_metrics"]["verdict"] == "pass"
    assert review["checks"]["risk_exposure"]["verdict"] == "pass"
    assert review["checks"]["validation_completeness"]["verdict"] == "pass"


def test_build_prd_review_degrades_when_required_sections_are_missing():
    module = _load_review_module()
    state = _structured_ready_state()
    state["prd_draft"]["sections"]["success_metrics"] = _draft_section("成功指标", completeness="missing")

    review = module.build_prd_review(state)

    assert review["verdict"] == "revise"
    assert review["status"] == "drafting"
    assert "success_metrics" in review["missing_sections"]
    assert review["checks"]["success_metrics"]["verdict"] == "missing"
    assert any("success_metrics" in gap for gap in review["gaps"])


def test_build_prd_review_marks_to_validate_and_open_risks_as_needs_input():
    module = _load_review_module()
    state = _structured_ready_state()
    state["prd_draft"]["sections"]["success_metrics"] = _draft_section(
        "成功指标",
        _entry("7 天留存 >= 20%", "to_validate"),
    )
    state["diagnostics"] = [
        {"bucket": "risk", "status": "open", "title": "目标用户仍需真实访谈验证"},
        {"bucket": "to_validate", "status": "open", "title": "成功指标缺少样本规模"},
    ]
    state["diagnostic_summary"] = {
        "open_count": 2,
        "unknown_count": 0,
        "risk_count": 1,
        "to_validate_count": 1,
    }

    review = module.build_prd_review(state)

    assert review["verdict"] == "needs_input"
    assert review["status"] == "needs_input"
    assert review["missing_sections"] == []
    assert review["checks"]["success_metrics"]["verdict"] == "needs_input"
    assert review["checks"]["risk_exposure"]["verdict"] == "needs_input"
    assert review["checks"]["validation_completeness"]["verdict"] == "needs_input"
    assert any("待验证" in gap or "风险" in gap for gap in review["gaps"])


def test_build_prd_review_falls_back_to_legacy_snapshot_when_structured_draft_missing():
    module = _load_review_module()
    state = {
        "workflow_stage": "refine_loop",
        "prd_snapshot": {
            "sections": {
                "target_user": {"content": "独立开发者", "status": "confirmed"},
                "problem": {"content": "需求确认成本高", "status": "confirmed"},
                "solution": {"content": "AI 协作问答流", "status": "confirmed"},
                "mvp_scope": {"content": "只做 Web 工作台", "status": "confirmed"},
                "constraints": {"content": "", "status": "missing"},
                "success_metrics": {"content": "", "status": "missing"},
            }
        },
    }

    review = module.build_prd_review(state)

    assert review["verdict"] == "revise"
    assert review["status"] == "drafting"
    assert review["summary"]
    assert set(review["checks"].keys()) == REQUIRED_DIMENSIONS
    assert "constraints" in review["missing_sections"]
    assert "success_metrics" in review["missing_sections"]
    assert review["checks"]["goal_clarity"]["verdict"] == "pass"
    assert review["checks"]["scope_boundary"]["verdict"] == "missing"
    assert review["checks"]["success_metrics"]["verdict"] == "missing"
