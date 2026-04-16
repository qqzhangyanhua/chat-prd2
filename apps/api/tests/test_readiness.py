import importlib

import pytest


def _load_readiness_module():
    try:
        return importlib.import_module("app.agent.readiness")
    except ModuleNotFoundError as exc:
        pytest.fail(f"readiness module missing: {exc}")


def _section(content: str, status: str = "confirmed") -> dict[str, str]:
    return {
        "content": content,
        "status": status,
    }


def _entry(text: str, assertion_state: str = "confirmed") -> dict[str, object]:
    return {
        "id": f"entry-{text}",
        "text": text,
        "assertion_state": assertion_state,
        "evidence_ref_ids": ["evidence-1"],
    }


def _draft_section(*entries: dict[str, object], completeness: str = "complete") -> dict[str, object]:
    return {
        "title": "section",
        "entries": list(entries),
        "completeness": completeness,
    }


def _structured_complete_sections(assertion_state: str = "confirmed") -> dict[str, dict[str, object]]:
    return {
        "target_user": _draft_section(_entry("独立开发者", assertion_state)),
        "problem": _draft_section(_entry("需求确认成本高", assertion_state)),
        "solution": _draft_section(_entry("AI 协作问答流", assertion_state)),
        "mvp_scope": _draft_section(_entry("只做 Web 端", assertion_state)),
        "constraints": _draft_section(_entry("首版不做私有化", assertion_state)),
        "success_metrics": _draft_section(_entry("7 天留存 >= 20%", assertion_state)),
    }


def _complete_sections() -> dict[str, dict[str, str]]:
    return {
        "target_user": _section("独立开发者"),
        "problem": _section("需求确认成本高"),
        "solution": _section("AI 协作问答流"),
        "mvp_scope": _section("只做 Web 端"),
        "constraints": _section("首版不做私有化"),
        "success_metrics": _section("7 天留存 >= 20%"),
    }


@pytest.mark.parametrize(
    "missing_field",
    [
        "target_user",
        "problem",
        "solution",
        "mvp_scope",
        "constraints",
        "success_metrics",
    ],
)
def test_evaluate_finalize_readiness_returns_not_ready_when_any_required_field_missing(missing_field: str):
    module = _load_readiness_module()
    sections = _complete_sections()
    sections[missing_field] = _section("", status="missing")
    state = {
        "prd_draft": {
            "sections": sections
        }
    }

    result = module.evaluate_finalize_readiness(state)

    assert result["ready"] is False
    assert missing_field in result["missing"]
    assert result["critic_result"]["overall_verdict"] == "revise"
    assert missing_field in result["critic_result"]["major_gaps"]
    assert result["critic_result"]["ready"] is False


def test_evaluate_finalize_readiness_returns_ready_when_required_sections_complete():
    module = _load_readiness_module()
    state = {
        "prd_draft": {
            "sections": _complete_sections()
        }
    }

    result = module.evaluate_finalize_readiness(state)

    assert result["ready"] is True
    assert result["missing"] == []
    assert result["critic_result"]["overall_verdict"] == "pass"
    assert result["critic_result"]["major_gaps"] == []
    assert result["critic_result"]["question_queue"] == []
    assert result["critic_result"]["required_sections"] == [
        "target_user",
        "problem",
        "solution",
        "mvp_scope",
        "constraints",
        "success_metrics",
    ]
    assert result["status"] == "ready_for_confirmation"
    assert result["ready_for_confirmation"] is True
    assert result["missing_sections"] == []
    assert result["gap_prompts"] == []


def test_evaluate_finalize_readiness_falls_back_to_prd_snapshot_sections():
    module = _load_readiness_module()
    state = {
        "prd_snapshot": {
            "sections": _complete_sections()
        }
    }

    result = module.evaluate_finalize_readiness(state)

    assert result["ready"] is True
    assert result["missing"] == []
    assert result["status"] == "ready_for_confirmation"


def test_evaluate_finalize_readiness_uses_structured_entries_and_marks_missing_sections():
    module = _load_readiness_module()
    state = {
        "prd_draft": {
            "sections": {
                **_structured_complete_sections(),
                "solution": _draft_section(completeness="missing"),
            }
        }
    }

    result = module.evaluate_finalize_readiness(state)

    assert result["ready"] is False
    assert result["ready_for_confirmation"] is False
    assert result["status"] == "drafting"
    assert "solution" in result["missing"]
    assert "solution" in result["missing_sections"]
    assert any("solution" in prompt for prompt in result["gap_prompts"])


def test_evaluate_finalize_readiness_treats_to_validate_as_needs_input_not_missing():
    module = _load_readiness_module()
    state = {
        "prd_draft": {
            "sections": _structured_complete_sections(),
        },
        "diagnostic_summary": {
            "open_count": 1,
            "unknown_count": 0,
            "risk_count": 1,
            "to_validate_count": 1,
        },
    }
    state["prd_draft"]["sections"]["success_metrics"] = _draft_section(
        _entry("7 天留存 >= 20%", "to_validate"),
        completeness="complete",
    )

    result = module.evaluate_finalize_readiness(state)

    assert result["ready"] is False
    assert result["ready_for_confirmation"] is False
    assert result["status"] == "needs_input"
    assert result["missing_sections"] == []
    assert any("待验证" in prompt or "风险" in prompt for prompt in result["gap_prompts"])


def test_evaluate_finalize_readiness_returns_finalized_for_final_draft():
    module = _load_readiness_module()
    state = {
        "prd_draft": {
            "status": "finalized",
            "sections": _structured_complete_sections(),
        }
    }

    result = module.evaluate_finalize_readiness(state)

    assert result["ready"] is True
    assert result["ready_for_confirmation"] is False
    assert result["status"] == "finalized"
