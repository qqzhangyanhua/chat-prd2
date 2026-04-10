import pytest
from app.agent.prd_updater import merge_prd_updates, should_emit_prd_updated


def test_merge_creates_new_draft_section():
    current = {"sections": {}}
    updates = {"target_user": {"content": "小微企业主", "status": "draft"}}
    result = merge_prd_updates(current, updates)
    assert result["sections"]["target_user"]["content"] == "小微企业主"
    assert result["sections"]["target_user"]["status"] == "draft"


def test_merge_overwrites_existing_section():
    current = {"sections": {"target_user": {"content": "旧内容", "status": "draft"}}}
    updates = {"target_user": {"content": "新内容", "status": "confirmed"}}
    result = merge_prd_updates(current, updates)
    assert result["sections"]["target_user"]["content"] == "新内容"
    assert result["sections"]["target_user"]["status"] == "confirmed"


def test_merge_missing_status_preserves_old_content():
    current = {"sections": {"target_user": {"content": "已有内容", "status": "draft"}}}
    updates = {"target_user": {"content": "需要补充场景", "status": "missing"}}
    result = merge_prd_updates(current, updates)
    # 保留旧 content，只更新 status
    assert result["sections"]["target_user"]["content"] == "已有内容"
    assert result["sections"]["target_user"]["status"] == "missing"
    assert result["sections"]["target_user"]["missing_reason"] == "需要补充场景"


def test_merge_missing_status_no_old_section():
    current = {"sections": {}}
    updates = {"problem": {"content": "需要明确问题", "status": "missing"}}
    result = merge_prd_updates(current, updates)
    assert result["sections"]["problem"]["status"] == "missing"
    assert result["sections"]["problem"]["missing_reason"] == "需要明确问题"


def test_merge_empty_updates_returns_copy():
    current = {"sections": {"target_user": {"content": "x", "status": "draft"}}}
    result = merge_prd_updates(current, {})
    assert result == current
    assert result is not current  # deep copy


def test_merge_ignores_non_dict_update_values():
    current = {"sections": {}}
    updates = {"target_user": "invalid"}
    result = merge_prd_updates(current, updates)
    assert "target_user" not in result["sections"]


def test_should_emit_prd_updated_when_changed():
    old = {"sections": {}}
    new = {"sections": {"target_user": {"content": "x", "status": "draft"}}}
    assert should_emit_prd_updated(old, new) is True


def test_should_emit_prd_updated_when_unchanged():
    prd = {"sections": {"target_user": {"content": "x", "status": "draft"}}}
    assert should_emit_prd_updated(prd, prd) is False


def test_should_emit_prd_updated_equal_dicts():
    old = {"sections": {"x": {"content": "a"}}}
    new = {"sections": {"x": {"content": "a"}}}
    assert should_emit_prd_updated(old, new) is False
