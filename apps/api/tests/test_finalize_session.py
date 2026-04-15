import importlib
from types import SimpleNamespace

import pytest


def _load_finalize_module():
    try:
        return importlib.import_module("app.services.finalize_session")
    except ModuleNotFoundError as exc:
        pytest.fail(f"finalize service module missing: {exc}")


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

    monkeypatch.setattr(
        module,
        "state_repository",
        SimpleNamespace(
            get_latest_state=_get_latest_state,
            create_state_version=_create_state_version,
        ),
        raising=False,
    )
    monkeypatch.setattr(
        module,
        "session_service",
        SimpleNamespace(
            get_session_snapshot=lambda db, session_id, user_id: {
                "session": {"id": session_id, "user_id": user_id},
                "state": latest_state,
            },
        ),
        raising=False,
    )
    monkeypatch.setattr(
        module,
        "prd_repository",
        SimpleNamespace(create_prd_snapshot=_create_prd_snapshot),
        raising=False,
    )
    monkeypatch.setattr(
        module,
        "build_finalized_sections",
        lambda prd_draft, preference: {
            "summary": {"title": "一句话概述", "content": "可发布", "status": "confirmed"},
        },
        raising=False,
    )

    return calls


def test_finalize_session_raises_when_state_not_ready(monkeypatch):
    module = _load_finalize_module()
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


@pytest.mark.parametrize("invalid_confirmation_source", ["", "invalid"])
def test_finalize_session_raises_when_ready_but_confirmation_source_missing_or_invalid(
    monkeypatch,
    invalid_confirmation_source: str,
):
    module = _load_finalize_module()
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
            confirmation_source=invalid_confirmation_source,
        )

    error = exc_info.value
    status_code = getattr(error, "status_code", None)
    code = getattr(error, "code", None) or getattr(error, "error_code", None)
    assert status_code == 409 or code in {"FINALIZE_CONFIRMATION_REQUIRED", "CONFIRMATION_REQUIRED"}


def test_finalize_session_allows_completed_when_ready_and_confirmation_source_provided(monkeypatch):
    module = _load_finalize_module()
    calls = _patch_optional_finalize_dependencies(
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

    nested_state = None
    if isinstance(result, dict):
        nested_state = result.get("state")
    else:
        nested_state = getattr(result, "state", None)

    assert isinstance(nested_state, dict)
    assert nested_state.get("workflow_stage") == "completed"
    assert calls["create_state_version"] >= 1
    assert calls["create_prd_snapshot"] >= 1
