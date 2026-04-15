import importlib


def _finalize_module():
    return importlib.import_module("app.services.finalize_session")


def _build_state(*, ready: bool) -> dict:
    return {
        "workflow_stage": "finalize",
        "finalization_ready": ready,
    }


def test_finalize_rejects_when_not_ready_even_if_confirmed():
    module = _finalize_module()
    state = _build_state(ready=False)

    result = module.finalize_session(
        state=state,
        user_confirmed=True,
    )

    assert result.allowed is False
    assert result.state["workflow_stage"] != "completed"


def test_finalize_rejects_when_ready_but_not_explicitly_confirmed():
    module = _finalize_module()
    state = _build_state(ready=True)

    result = module.finalize_session(
        state=state,
        user_confirmed=False,
    )

    assert result.allowed is False
    assert result.state["workflow_stage"] != "completed"


def test_finalize_allows_completed_when_ready_and_explicitly_confirmed():
    module = _finalize_module()
    state = _build_state(ready=True)

    result = module.finalize_session(
        state=state,
        user_confirmed=True,
    )

    assert result.allowed is True
    assert result.state["workflow_stage"] == "completed"
