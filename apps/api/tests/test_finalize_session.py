import importlib
from types import SimpleNamespace

import pytest


def _finalize_module():
    return importlib.import_module("app.services.finalize_session")


def _fake_db():
    return object()


def _patch_optional_finalize_dependencies(module, monkeypatch, *, latest_state: dict):
    calls = {"create_state_version": 0, "create_prd_snapshot": 0}

    def _get_latest_state(db, session_id):
        return latest_state

    def _create_state_version(db, session_id, version, state_json):
        calls["create_state_version"] += 1
        return SimpleNamespace(version=version, state_json=state_json)

    def _create_prd_snapshot(db, session_id, version, sections):
        calls["create_prd_snapshot"] += 1
        return SimpleNamespace(version=version, sections=sections)

    if hasattr(module, "state_repository"):
        monkeypatch.setattr(
            module,
            "state_repository",
            SimpleNamespace(
                get_latest_state=_get_latest_state,
                create_state_version=_create_state_version,
            ),
        )
    if hasattr(module, "session_service"):
        monkeypatch.setattr(
            module,
            "session_service",
            SimpleNamespace(
                get_session_snapshot=lambda db, session_id, user_id: {"session": {"id": session_id, "user_id": user_id}},
            ),
        )
    if hasattr(module, "prd_repository"):
        monkeypatch.setattr(
            module,
            "prd_repository",
            SimpleNamespace(create_prd_snapshot=_create_prd_snapshot),
        )
    if hasattr(module, "build_finalized_sections"):
        monkeypatch.setattr(
            module,
            "build_finalized_sections",
            lambda prd_draft, preference: {
                "summary": {"title": "一句话概述", "content": "可发布", "status": "confirmed"},
            },
        )

    return calls


def test_finalize_session_raises_when_state_not_ready(monkeypatch):
    module = _finalize_module()
    _patch_optional_finalize_dependencies(
        module,
        monkeypatch,
        latest_state={"workflow_stage": "finalize", "finalization_ready": False},
    )

    with pytest.raises(Exception) as exc_info:
        module.finalize_session(
            _fake_db(),
            "session-1",
            "user-1",
            confirmation_source="button",
        )

    error = exc_info.value
    status_code = getattr(error, "status_code", None)
    code = getattr(error, "code", None) or getattr(error, "error_code", None)
    assert status_code == 409 or code in {"FINALIZE_NOT_READY", "WORKFLOW_NOT_READY"}


def test_finalize_session_raises_when_ready_but_confirmation_source_missing_or_invalid(monkeypatch):
    module = _finalize_module()
    _patch_optional_finalize_dependencies(
        module,
        monkeypatch,
        latest_state={"workflow_stage": "finalize", "finalization_ready": True},
    )

    with pytest.raises(Exception) as exc_info:
        module.finalize_session(
            _fake_db(),
            "session-1",
            "user-1",
            confirmation_source="",
        )

    error = exc_info.value
    status_code = getattr(error, "status_code", None)
    code = getattr(error, "code", None) or getattr(error, "error_code", None)
    assert status_code == 409 or code in {"FINALIZE_CONFIRMATION_REQUIRED", "CONFIRMATION_REQUIRED"}


def test_finalize_session_allows_completed_when_ready_and_confirmation_source_provided(monkeypatch):
    module = _finalize_module()
    _patch_optional_finalize_dependencies(
        module,
        monkeypatch,
        latest_state={"workflow_stage": "finalize", "finalization_ready": True},
    )

    result = module.finalize_session(
        _fake_db(),
        "session-1",
        "user-1",
        confirmation_source="button",
        preference=None,
    )

    workflow_stage = None
    if isinstance(result, dict):
        workflow_stage = result.get("workflow_stage")
        if workflow_stage is None and isinstance(result.get("state"), dict):
            workflow_stage = result["state"].get("workflow_stage")
    else:
        workflow_stage = getattr(result, "workflow_stage", None)
        if workflow_stage is None and isinstance(getattr(result, "state", None), dict):
            workflow_stage = result.state.get("workflow_stage")

    assert workflow_stage == "completed"
