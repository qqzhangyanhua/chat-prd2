from __future__ import annotations

from copy import deepcopy
from typing import Any


def merge_prd_updates(
    current_prd: dict[str, Any],
    prd_updates: dict[str, Any],
) -> dict[str, Any]:
    """把 LLM 返回的 prd_updates 合并进当前 PRD 状态。

    规则：
    - status confirmed/draft → 写入，覆盖旧内容
    - status missing → 保留旧 content，更新 status 和缺口描述
    - 无旧记录 → 新建 section
    - prd_updates 为空 {} → 返回原 PRD 的深拷贝，不触发变更
    - 非 dict 的 update value → 忽略
    """
    if not prd_updates:
        return deepcopy(current_prd)

    result = deepcopy(current_prd)
    sections = result.setdefault("sections", {})

    for key, update in prd_updates.items():
        if not isinstance(update, dict):
            continue

        status = update.get("status", "draft")
        content = update.get("content", "")

        if status == "missing":
            old = sections.get(key) or {}
            sections[key] = {
                "content": old.get("content", ""),  # 保证 content 键始终存在
                **old,
                "status": "missing",
                "missing_reason": content,
            }
        else:
            sections[key] = {
                "content": content,
                "status": status,
                "title": update.get("title", key),
            }

    return result


def should_emit_prd_updated(old_prd: dict[str, Any], new_prd: dict[str, Any]) -> bool:
    """只要 PRD 对象发生任何变化就返回 True。"""
    return old_prd != new_prd
