import importlib

import pytest


def _finalize_module():
    return importlib.import_module("app.services.finalize_session")


def _fake_db():
    return object()


def test_finalize_session_raises_when_state_not_ready():
    module = _finalize_module()

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


def test_finalize_session_raises_when_ready_but_confirmation_source_missing_or_invalid():
    module = _finalize_module()

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


def test_finalize_session_allows_completed_when_ready_and_confirmation_source_provided():
    module = _finalize_module()

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
