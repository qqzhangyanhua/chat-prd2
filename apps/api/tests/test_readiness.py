from app.services import prd_runtime


def _section(title: str, content: str, status: str = "confirmed") -> dict[str, str]:
    return {
        "title": title,
        "content": content,
        "status": status,
    }


def test_preview_prd_meta_requires_all_core_sections_plus_constraints_and_success_metrics():
    state = {
        "workflow_stage": "refine_loop",
        "prd_snapshot": {
            "sections": {
                "target_user": _section("目标用户", "独立开发者"),
                "problem": _section("核心问题", "需求确认成本高"),
                "solution": _section("解决方案", "AI 协作问答流"),
                "mvp_scope": _section("MVP 范围", "只做 Web 端"),
                "constraints": _section("约束条件", "", "missing"),
                "success_metrics": _section("成功指标", "", "missing"),
            }
        },
    }

    meta = prd_runtime.preview_prd_meta(state, {"finalization_ready": True})

    assert meta["stageTone"] == "draft"
    assert meta["stageLabel"] != "可整理终稿"


def test_preview_prd_meta_marks_ready_when_core_and_guardrail_sections_are_confirmed():
    state = {
        "workflow_stage": "refine_loop",
        "prd_snapshot": {
            "sections": {
                "target_user": _section("目标用户", "独立开发者"),
                "problem": _section("核心问题", "需求确认成本高"),
                "solution": _section("解决方案", "AI 协作问答流"),
                "mvp_scope": _section("MVP 范围", "只做 Web 端"),
                "constraints": _section("约束条件", "首版不接企业私有化部署"),
                "success_metrics": _section("成功指标", "7 天留存 >= 20%"),
            }
        },
        "finalization_ready": False,
        "critic_result": {"overall_verdict": "block", "question_queue": []},
    }

    meta = prd_runtime.preview_prd_meta(state, {})

    assert meta["stageTone"] == "ready"
    assert meta["stageLabel"] == "可整理终稿"
