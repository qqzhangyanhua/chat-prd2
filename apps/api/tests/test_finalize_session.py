import pytest
from sqlalchemy import select

from app.agent.finalize_flow import normalize_prd_draft_sections
from app.db.models import PrdSnapshot, ProjectStateVersion, User
from app.repositories import prd as prd_repository
from app.repositories import state as state_repository
from app.schemas.session import SessionCreateRequest
from app.services import finalize_session as finalize_service
from app.services import sessions as session_service


def _create_user_and_session(db_session):
    user = User(
        id="user-finalize-1",
        email="finalize@example.com",
        password_hash="hash",
    )
    db_session.add(user)
    db_session.commit()
    snapshot = session_service.create_session(
        db_session,
        user.id,
        SessionCreateRequest(
            title="Finalize Test",
            initial_idea="一个帮助团队快速整理需求的系统",
        ),
    )
    return user.id, snapshot.session.id


def _seed_finalize_ready_state(db_session, session_id: str, *, ready: bool):
    latest = state_repository.get_latest_state_version(db_session, session_id)
    assert latest is not None
    base_state = latest.state_json
    success_metrics_section = (
        {"title": "成功指标", "content": "7 天内完成一版 PRD", "status": "confirmed"}
        if ready else
        {"title": "成功指标", "content": "是否有人愿意持续使用仍需验证", "status": "draft"}
    )
    state_json = {
        **base_state,
        "workflow_stage": "finalize",
        "finalization_ready": ready,
        "prd_draft": {
            "version": latest.version + 1,
            "status": "draft_refined",
            "sections": {
                "summary": {"title": "一句话概述", "content": "智能需求助手", "status": "draft"},
                "target_user": {"title": "目标用户", "content": "产品团队", "status": "confirmed"},
                "problem": {"title": "核心问题", "content": "需求讨论低效", "status": "confirmed"},
                "solution": {"title": "解决方案", "content": "结构化澄清 + 输出 PRD", "status": "confirmed"},
                "mvp_scope": {"title": "MVP 范围", "content": "会话、总结、导出", "status": "confirmed"},
                "constraints": {"title": "约束条件", "content": "本季度上线", "status": "confirmed"},
                "success_metrics": success_metrics_section,
            },
        },
        "diagnostic_summary": {
            "open_count": 0,
            "unknown_count": 0,
            "risk_count": 0,
            "to_validate_count": 0 if ready else 1,
        },
    }
    state_repository.create_state_version(
        db=db_session,
        session_id=session_id,
        version=latest.version + 1,
        state_json=state_json,
    )
    prd_repository.create_prd_snapshot(
        db=db_session,
        session_id=session_id,
        version=latest.version + 1,
        sections=state_json["prd_draft"]["sections"],
    )
    db_session.commit()


def test_finalize_session_raises_when_state_not_ready(db_session):
    user_id, session_id = _create_user_and_session(db_session)
    _seed_finalize_ready_state(db_session, session_id, ready=False)

    with pytest.raises(Exception) as exc_info:
        finalize_service.finalize_session(
            db_session,
            session_id,
            user_id,
            confirmation_source="button",
        )

    error = exc_info.value
    assert getattr(error, "status_code", None) == 409
    assert getattr(error, "code", None) == "FINALIZE_NOT_READY"


@pytest.mark.parametrize("invalid_confirmation_source", ["", "invalid"])
def test_finalize_session_raises_when_ready_but_confirmation_source_missing_or_invalid(
    db_session,
    invalid_confirmation_source: str,
):
    user_id, session_id = _create_user_and_session(db_session)
    _seed_finalize_ready_state(db_session, session_id, ready=True)

    with pytest.raises(Exception) as exc_info:
        finalize_service.finalize_session(
            db_session,
            session_id,
            user_id,
            confirmation_source=invalid_confirmation_source,
        )

    error = exc_info.value
    assert getattr(error, "status_code", None) == 409
    assert getattr(error, "code", None) == "FINALIZE_CONFIRMATION_REQUIRED"


def test_finalize_session_allows_completed_when_ready_and_confirmation_source_provided(db_session):
    user_id, session_id = _create_user_and_session(db_session)
    _seed_finalize_ready_state(db_session, session_id, ready=True)

    before_state_count = len(
        db_session.execute(
            select(ProjectStateVersion).where(ProjectStateVersion.session_id == session_id)
        ).scalars().all()
    )
    before_prd_count = len(
        db_session.execute(
            select(PrdSnapshot).where(PrdSnapshot.session_id == session_id)
        ).scalars().all()
    )

    result = finalize_service.finalize_session(
        db_session,
        session_id,
        user_id,
        confirmation_source="button",
        preference="technical",
    )

    assert result.state.workflow_stage == "completed"
    assert result.state.finalization_ready is True
    assert result.state.prd_draft["status"] == "finalized"
    assert result.state.prd_draft["sections"]["summary"]["content"] == "智能需求助手"
    latest_state = state_repository.get_latest_state_version(db_session, session_id)
    assert latest_state is not None
    delivery_milestone = latest_state.state_json["delivery_milestone"]
    assert delivery_milestone["status"] == "finalized"
    assert delivery_milestone["confirmation_source"] == "button"
    assert delivery_milestone["finalize_preference"] == "technical"
    assert delivery_milestone["prd_snapshot_version"] == latest_state.version

    after_state_count = len(
        db_session.execute(
            select(ProjectStateVersion).where(ProjectStateVersion.session_id == session_id)
        ).scalars().all()
    )
    after_prd_count = len(
        db_session.execute(
            select(PrdSnapshot).where(PrdSnapshot.session_id == session_id)
        ).scalars().all()
    )
    assert after_state_count == before_state_count + 1
    assert after_prd_count == before_prd_count + 1


def test_finalize_session_uses_readiness_projector_not_stale_ready_flag(db_session):
    user_id, session_id = _create_user_and_session(db_session)
    latest = state_repository.get_latest_state_version(db_session, session_id)
    assert latest is not None
    state_json = {
        **latest.state_json,
        "workflow_stage": "finalize",
        "finalization_ready": True,
        "prd_draft": {
            "version": latest.version + 1,
            "status": "draft_refined",
            "sections": {
                "target_user": {
                    "title": "目标用户",
                    "completeness": "complete",
                    "entries": [
                        {"id": "entry-user-1", "text": "产品团队", "assertion_state": "confirmed"}
                    ],
                },
                "problem": {
                    "title": "核心问题",
                    "completeness": "complete",
                    "entries": [
                        {"id": "entry-problem-1", "text": "需求讨论低效", "assertion_state": "confirmed"}
                    ],
                },
                "solution": {
                    "title": "解决方案",
                    "completeness": "complete",
                    "entries": [
                        {"id": "entry-solution-1", "text": "结构化澄清 + 输出 PRD", "assertion_state": "confirmed"}
                    ],
                },
                "mvp_scope": {
                    "title": "MVP 范围",
                    "completeness": "complete",
                    "entries": [
                        {"id": "entry-scope-1", "text": "会话、总结、导出", "assertion_state": "confirmed"}
                    ],
                },
                "constraints": {
                    "title": "约束条件",
                    "completeness": "complete",
                    "entries": [
                        {"id": "entry-constraint-1", "text": "本季度上线", "assertion_state": "confirmed"}
                    ],
                },
                "success_metrics": {
                    "title": "成功指标",
                    "completeness": "partial",
                    "entries": [
                        {"id": "entry-metric-1", "text": "验证愿意持续使用", "assertion_state": "to_validate"}
                    ],
                },
            },
        },
        "diagnostic_summary": {
            "open_count": 0,
            "unknown_count": 0,
            "risk_count": 0,
            "to_validate_count": 1,
        },
    }
    state_repository.create_state_version(
        db=db_session,
        session_id=session_id,
        version=latest.version + 1,
        state_json=state_json,
    )
    prd_repository.create_prd_snapshot(
        db=db_session,
        session_id=session_id,
        version=latest.version + 1,
        sections={},
    )
    db_session.commit()

    with pytest.raises(Exception) as exc_info:
        finalize_service.finalize_session(
            db_session,
            session_id,
            user_id,
            confirmation_source="button",
        )

    error = exc_info.value
    assert getattr(error, "status_code", None) == 409
    assert getattr(error, "code", None) == "FINALIZE_NOT_READY"


def test_backfilled_legacy_session_still_requires_finalize_confirmation(db_session):
    user_id, session_id = _create_user_and_session(db_session)
    latest = state_repository.get_latest_state_version(db_session, session_id)
    assert latest is not None
    legacy_sections = {
        "target_user": {"title": "目标用户", "content": "产品团队", "status": "confirmed"},
        "problem": {"title": "核心问题", "content": "需求沟通低效", "status": "confirmed"},
        "solution": {"title": "解决方案", "content": "结构化协作", "status": "confirmed"},
        "mvp_scope": {"title": "MVP 范围", "content": "会话 + 导出", "status": "confirmed"},
        "constraints": {"title": "约束条件", "content": "暂不做批量迁移", "status": "confirmed"},
        "success_metrics": {"title": "成功指标", "content": "旧会话可以稳定进入终稿前态", "status": "confirmed"},
    }
    legacy_state = {
        **latest.state_json,
        "prd_snapshot": {"sections": legacy_sections},
    }
    legacy_state.pop("workflow_stage", None)
    legacy_state.pop("prd_draft", None)
    legacy_state.pop("critic_result", None)
    legacy_state.pop("finalization_ready", None)
    state_repository.create_state_version(
        db=db_session,
        session_id=session_id,
        version=latest.version + 1,
        state_json=legacy_state,
    )
    prd_repository.create_prd_snapshot(
        db=db_session,
        session_id=session_id,
        version=latest.version + 1,
        sections=legacy_sections,
    )
    db_session.commit()

    snapshot = session_service.get_session_snapshot(db_session, session_id, user_id)
    assert snapshot.state.workflow_stage == "finalize"
    assert snapshot.state.finalization_ready is True

    with pytest.raises(Exception) as exc_info:
        finalize_service.finalize_session(
            db_session,
            session_id,
            user_id,
            confirmation_source="",
        )

    error = exc_info.value
    assert getattr(error, "status_code", None) == 409
    assert getattr(error, "code", None) == "FINALIZE_CONFIRMATION_REQUIRED"


def test_normalize_prd_draft_sections_accepts_enriched_entry_sections():
    sections = normalize_prd_draft_sections(
        {
            "sections": {
                "target_user": {
                    "title": "目标用户",
                    "completeness": "partial",
                    "entries": [
                        {
                            "id": "entry-target-user-1",
                            "text": "第一版先服务独立开发者。",
                            "assertion_state": "confirmed",
                            "evidence_ref_ids": ["evidence-user-1"],
                        }
                    ],
                },
                "open_questions": {
                    "title": "待确认问题",
                    "completeness": "partial",
                    "entries": [
                        {
                            "id": "entry-open-question-1",
                            "text": "还需要验证这个群体是否愿意持续使用。",
                            "assertion_state": "to_validate",
                            "evidence_ref_ids": ["evidence-inference-1"],
                        }
                    ],
                },
            }
        }
    )

    assert sections["target_user"]["content"] == "第一版先服务独立开发者。"
    assert sections["target_user"]["status"] == "confirmed"
    assert sections["open_questions"]["content"] == "还需要验证这个群体是否愿意持续使用。"
    assert sections["open_questions"]["status"] == "draft"
