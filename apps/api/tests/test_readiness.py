import importlib


def _readiness_module():
    return importlib.import_module("app.agent.readiness")


def _section(content: str, status: str = "confirmed") -> dict[str, str]:
    return {
        "content": content,
        "status": status,
    }


def test_evaluate_finalize_readiness_returns_not_ready_when_success_metrics_missing():
    module = _readiness_module()
    state = {
        "prd_draft": {
            "sections": {
                "target_user": _section("独立开发者"),
                "problem": _section("需求确认成本高"),
                "solution": _section("AI 协作问答流"),
                "mvp_scope": _section("只做 Web 端"),
                "constraints": _section("首版不做私有化"),
                "success_metrics": _section("", status="missing"),
            }
        }
    }

    result = module.evaluate_finalize_readiness(state)

    assert result["ready"] is False
    assert "success_metrics" in result["missing"]


def test_evaluate_finalize_readiness_returns_not_ready_when_core_problem_missing():
    module = _readiness_module()
    state = {
        "prd_draft": {
            "sections": {
                "target_user": _section("独立开发者"),
                "problem": _section("", status="missing"),
                "solution": _section("AI 协作问答流"),
                "mvp_scope": _section("只做 Web 端"),
                "constraints": _section("首版不做私有化"),
                "success_metrics": _section("7 天留存 >= 20%"),
            }
        }
    }

    result = module.evaluate_finalize_readiness(state)

    assert result["ready"] is False
    assert "problem" in result["missing"]


def test_evaluate_finalize_readiness_returns_ready_when_required_sections_complete():
    module = _readiness_module()
    state = {
        "prd_draft": {
            "sections": {
                "target_user": _section("独立开发者"),
                "problem": _section("需求确认成本高"),
                "solution": _section("AI 协作问答流"),
                "mvp_scope": _section("只做 Web 端"),
                "constraints": _section("首版不做私有化"),
                "success_metrics": _section("7 天留存 >= 20%"),
            }
        }
    }

    result = module.evaluate_finalize_readiness(state)

    assert result["ready"] is True
    assert result["missing"] == []
