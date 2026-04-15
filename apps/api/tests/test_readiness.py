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
