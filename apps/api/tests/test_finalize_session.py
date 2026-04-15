import pytest
from sqlalchemy import select

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
            },
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
