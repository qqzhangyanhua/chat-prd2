from app.services.messages import apply_prd_patch, apply_state_patch


def test_apply_state_patch_empty_patch_returns_original():
    state = {"idea": "test", "target_user": None}
    result = apply_state_patch(state, {})
    assert result is state


def test_apply_state_patch_merges_keys():
    state = {"idea": "test", "target_user": None, "problem": None}
    result = apply_state_patch(state, {"target_user": "developers", "problem": "too slow"})
    assert result["target_user"] == "developers"
    assert result["problem"] == "too slow"
    assert result["idea"] == "test"


def test_apply_prd_patch_empty_patch_returns_original():
    state = {"prd_snapshot": {"sections": {}}}
    result = apply_prd_patch(state, {})
    assert result is state


def test_apply_prd_patch_merges_sections():
    state = {
        "prd_snapshot": {
            "sections": {"target_user": {"content": "old"}}
        }
    }
    result = apply_prd_patch(state, {"problem": {"content": "new problem"}})
    assert result["prd_snapshot"]["sections"]["target_user"]["content"] == "old"
    assert result["prd_snapshot"]["sections"]["problem"]["content"] == "new problem"


def test_apply_prd_patch_overwrites_existing_section():
    state = {
        "prd_snapshot": {
            "sections": {"target_user": {"content": "old"}}
        }
    }
    result = apply_prd_patch(state, {"target_user": {"content": "updated"}})
    assert result["prd_snapshot"]["sections"]["target_user"]["content"] == "updated"
