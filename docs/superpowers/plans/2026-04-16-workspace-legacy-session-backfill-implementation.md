# Workspace Legacy Session Backfill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为旧 `workspace` 会话增加“打开单个 session 时按需补算并写回”的兼容升级能力，让旧会话可以被当前闭环状态机稳定消费，但绝不直接补成 `completed`。

**Architecture:** 在 `get_session_snapshot()` 返回前新增一次按需编排：如果 latest state 缺少显式闭环字段，则调用独立的 legacy backfill service。该 service 只基于已有 `prd_draft / prd_snapshot` 推导显式状态，复用现有 readiness evaluator，写入新的 `state_version` 和 `prd_snapshot`，然后返回补算后的最新 snapshot。

**Tech Stack:** FastAPI, SQLAlchemy 2, Pydantic 2, pytest, TypeScript, Vitest

---

## 范围说明

本计划对应 [2026-04-16-workspace-legacy-session-backfill-design.md](/Users/zhangyanhua/AI/chat-prd2/docs/superpowers/specs/2026-04-16-workspace-legacy-session-backfill-design.md)。

本计划范围内必须完成：

- 旧会话在 `get_session_snapshot()` 时按需触发补算
- 补算结果写回数据库
- 旧会话补算后至少具备：
  - `workflow_stage`
  - `prd_draft`
  - `critic_result`
  - `finalization_ready`
- readiness 不足的旧会话补成 `refine_loop`
- readiness 满足的旧会话补成 `finalize`
- 旧会话绝不能直接补成 `completed`
- 补算失败时回滚并继续返回原始快照
- 前端能够稳定消费补算后的 legacy snapshot

本计划范围外暂不实现：

- 后台批量迁移旧会话
- 打开列表页时批量扫描补算
- 基于历史消息重放 agent 链
- 自动把旧会话补成 `completed`
- 额外数据库表

## 文件结构与职责

### 后端核心

- `apps/api/app/services/legacy_session_backfill.py`
  - 新增旧会话补算 service
  - 负责检测是否需要补算、抽取 sections、构造 backfilled state、写入新版本
- `apps/api/app/services/sessions.py`
  - 在 `get_session_snapshot()` 中按需调用 backfill service
  - 补算后重新读取最新 state / snapshot 再返回
- `apps/api/app/services/exports.py`
  - 保持 legacy backfill 后导出仍遵守“草稿 / 终稿”合同
- `apps/api/app/schemas/state.py`
  - 允许补算写入 `legacy_backfill_version`

### 后端测试

- `apps/api/tests/test_sessions.py`
  - 锁定 `get_session_snapshot()` 对 legacy session 的按需补算行为
- `apps/api/tests/test_finalize_session.py`
  - 锁定 legacy backfill 到 `finalize` 后仍需显式确认才能进入 `completed`
- `apps/api/tests/test_messages_service.py`
  - 锁定 backfill 失败时 session snapshot 仍可返回原始兼容数据
- `apps/api/tests/test_readiness.py`
  - 如需要，补充 readiness 在 legacy section 形态下的合同样例

### 前端回归

- `apps/web/src/test/workspace-store.test.ts`
  - 锁定 legacy backfilled snapshot 被 store 正确消费
- `apps/web/src/test/workspace-session-shell.test.tsx`
  - 锁定打开 legacy session 后 UI 状态稳定

## 关键实现约束

- 只在读取单个 session snapshot 时触发补算
- 只有缺失显式闭环字段时才触发补算
- 补算结果必须新建 `state_version` 与 `prd_snapshot`
- 补算最高只能到 `finalize`
- `completed` 仍然只允许通过显式 finalize 确认进入
- 补算失败必须回滚，不写半成品
- 补算失败不阻断继续聊天与导出

## 测试总策略

- 先锁定后端补算合同
- 再实现 backfill service 和 `get_session_snapshot()` 编排
- 最后补前端消费与导出 / finalize 回归

---

### Task 1: 锁定旧会话按需补算合同

**Files:**
- Modify: `apps/api/tests/test_sessions.py`
- Modify: `apps/api/tests/test_finalize_session.py`
- Modify: `apps/web/src/test/workspace-store.test.ts`
- Test: `apps/api/tests/test_sessions.py`
- Test: `apps/api/tests/test_finalize_session.py`
- Test: `apps/web/src/test/workspace-store.test.ts`

- [ ] **Step 1: 在 `test_sessions.py` 写失败测试，锁定缺显式字段的旧会话会在读取 snapshot 时触发补算**

```python
def test_get_session_snapshot_backfills_legacy_state_when_explicit_closure_fields_missing(...):
    ...
    result = session_service.get_session_snapshot(db, session_id, user_id)
    assert result.state.workflow_stage == "refine_loop"
    assert result.state.prd_draft is not None
```

- [ ] **Step 2: 运行单测，确认补算合同当前为红灯**

Run: `/bin/zsh -lc 'PYTHONPATH=apps/api uv run pytest apps/api/tests/test_sessions.py -q -k backfills_legacy_state'`
Expected: FAIL，提示 snapshot 仍返回旧 state，缺少 `workflow_stage / prd_draft`

- [ ] **Step 3: 在 `test_sessions.py` 增加失败测试，锁定 readiness 满足的旧会话最多补到 `finalize`**

```python
def test_get_session_snapshot_backfills_ready_legacy_state_to_finalize_only(...):
    ...
    assert result.state.workflow_stage == "finalize"
    assert result.state.finalization_ready is True
```

- [ ] **Step 4: 运行单测，确认不会被直接推成 completed**

Run: `/bin/zsh -lc 'PYTHONPATH=apps/api uv run pytest apps/api/tests/test_sessions.py -q -k finalize_only'`
Expected: FAIL，当前没有 backfill 行为或阶段不正确

- [ ] **Step 5: 在 `test_finalize_session.py` 写失败测试，锁定 legacy backfill 后仍需显式确认才能进入 completed**

```python
def test_backfilled_legacy_session_still_requires_finalize_confirmation(...):
    ...
    with pytest.raises(HTTPException):
        finalize_session(...)
```
```

- [ ] **Step 6: 运行 finalize 定点测试，确认合同为红灯**

Run: `/bin/zsh -lc 'PYTHONPATH=apps/api uv run pytest apps/api/tests/test_finalize_session.py -q -k backfilled_legacy'`
Expected: FAIL，当前还没有 legacy backfill 语义

- [ ] **Step 7: 在 `workspace-store.test.ts` 写失败测试，锁定 legacy backfilled snapshot 能被 store 消费**

```ts
it("hydrates legacy backfilled snapshot with explicit closure fields", () => {
  store.getState().hydrateSession({
    ...snapshot,
    state: {
      workflow_stage: "finalize",
      finalization_ready: true,
      prd_draft: { version: 3, status: "draft_refined", sections: {} },
      critic_result: { overall_verdict: "pass", question_queue: [] },
    },
  });
  expect(store.getState().workflowStage).toBe("finalize");
});
```

- [ ] **Step 8: 运行前端定点测试，确认消费合同稳定**

Run: `pnpm --filter web exec vitest run src/test/workspace-store.test.ts -t "hydrates legacy backfilled snapshot with explicit closure fields"`
Expected: PASS 或在字段缺失时暴露明确失败点；若已覆盖则保留测试作为回归

- [ ] **Step 9: 提交红灯测试与状态消费合同**

```bash
git add apps/api/tests/test_sessions.py apps/api/tests/test_finalize_session.py apps/web/src/test/workspace-store.test.ts
git commit -m "test: lock legacy workspace backfill contracts"
```

---

### Task 2: 实现 legacy backfill service 与 snapshot 按需编排

**Files:**
- Create: `apps/api/app/services/legacy_session_backfill.py`
- Modify: `apps/api/app/services/sessions.py`
- Modify: `apps/api/app/schemas/state.py`
- Test: `apps/api/tests/test_sessions.py`

- [ ] **Step 1: 在 `legacy_session_backfill.py` 定义补算入口和检测函数**

```python
def needs_legacy_backfill(state: dict) -> bool:
    return "workflow_stage" not in state or "prd_draft" not in state or "finalization_ready" not in state


def backfill_legacy_session_state(db: Session, session_id: str, current_state: dict, latest_prd_snapshot: object) -> dict:
    ...
```

- [ ] **Step 2: 运行后端定点测试，确认新文件引入后仍然失败在“未实现”而不是导入错误**

Run: `/bin/zsh -lc 'PYTHONPATH=apps/api uv run pytest apps/api/tests/test_sessions.py -q -k backfills_legacy_state'`
Expected: FAIL，但不出现 ImportError

- [ ] **Step 3: 在 `legacy_session_backfill.py` 实现 section 抽取优先级**

```python
def _extract_legacy_sections(current_state: dict, latest_prd_snapshot: object) -> dict[str, dict]:
    prd_draft = current_state.get("prd_draft")
    if isinstance(prd_draft, dict) and isinstance(prd_draft.get("sections"), dict):
        return deepcopy(prd_draft["sections"])
    snapshot_sections = current_state.get("prd_snapshot", {}).get("sections")
    if isinstance(snapshot_sections, dict) and snapshot_sections:
        return deepcopy(snapshot_sections)
    return deepcopy(latest_prd_snapshot.sections if latest_prd_snapshot else {})
```

- [ ] **Step 4: 复用 readiness evaluator 生成 `critic_result / finalization_ready / workflow_stage`**

```python
readiness = evaluate_finalize_readiness({"prd_draft": {"sections": sections}})
next_stage = "finalize" if readiness["ready"] else "refine_loop"
```

- [ ] **Step 5: 构造最小 backfilled state，并写入 `legacy_backfill_version = "closure_v1"`**

```python
next_state = deepcopy(current_state)
next_state["prd_draft"] = {...}
next_state["critic_result"] = readiness["critic_result"]
next_state["finalization_ready"] = bool(readiness["ready"])
next_state["workflow_stage"] = next_stage
next_state["legacy_backfill_version"] = "closure_v1"
```

- [ ] **Step 6: 新建 `state_version` 与对应 `prd_snapshot`，禁止写入 completed**

```python
if next_state["workflow_stage"] == "completed":
    raise AssertionError("legacy backfill must never mark session completed")
```

- [ ] **Step 7: 在 `sessions.py` 的 `get_session_snapshot()` 中按需调用 backfill service**

```python
if legacy_backfill_service.needs_legacy_backfill(state_version.state_json):
    legacy_backfill_service.backfill_legacy_session_state(...)
    state_version = state_repository.get_latest_state_version(db, session_id)
    prd_snapshot = prd_repository.get_latest_prd_snapshot(db, session_id)
```

- [ ] **Step 8: 运行后端定点测试，验证 refactor 后读取 snapshot 可以自动升级旧会话**

Run: `/bin/zsh -lc 'PYTHONPATH=apps/api uv run pytest apps/api/tests/test_sessions.py -q -k "backfills_legacy_state or finalize_only"'`
Expected: PASS

- [ ] **Step 9: 在 `state.py` 中补充 `legacy_backfill_version` 合同字段**

```python
legacy_backfill_version: str | None = None
```

- [ ] **Step 10: 运行状态 schema 与 session 相关测试**

Run: `/bin/zsh -lc 'PYTHONPATH=apps/api uv run pytest apps/api/tests/test_sessions.py apps/api/tests/test_messages_service.py -q'`
Expected: PASS

- [ ] **Step 11: 提交 backfill service 与 snapshot 编排**

```bash
git add apps/api/app/services/legacy_session_backfill.py apps/api/app/services/sessions.py apps/api/app/schemas/state.py apps/api/tests/test_sessions.py
git commit -m "feat(api): backfill legacy workspace sessions on read"
```

---

### Task 3: 补失败回滚、导出与 finalize 回归

**Files:**
- Modify: `apps/api/tests/test_sessions.py`
- Modify: `apps/api/tests/test_messages_service.py`
- Modify: `apps/api/tests/test_finalize_session.py`
- Modify: `apps/web/src/test/workspace-session-shell.test.tsx`
- Test: `apps/api/tests/test_sessions.py`
- Test: `apps/api/tests/test_messages_service.py`
- Test: `apps/api/tests/test_finalize_session.py`
- Test: `apps/web/src/test/workspace-session-shell.test.tsx`

- [ ] **Step 1: 在 `test_sessions.py` 写失败测试，锁定补算失败时回滚并返回原始快照**

```python
def test_get_session_snapshot_rolls_back_legacy_backfill_failure(...):
    ...
    result = session_service.get_session_snapshot(db, session_id, user_id)
    assert result.state.prd_draft is None
```

- [ ] **Step 2: 运行定点测试，确认失败处理当前为红灯**

Run: `/bin/zsh -lc 'PYTHONPATH=apps/api uv run pytest apps/api/tests/test_sessions.py -q -k rolls_back_legacy_backfill_failure'`
Expected: FAIL

- [ ] **Step 3: 在 `legacy_session_backfill.py` 增加事务保护和日志记录**

```python
try:
    ...
except Exception:
    db.rollback()
    logger.exception("legacy session backfill failed", extra={"session_id": session_id})
    return False
```

- [ ] **Step 4: 在 `sessions.py` 中处理 backfill 失败后的原始快照回退**

```python
backfilled = legacy_backfill_service.backfill_legacy_session_state(...)
if backfilled:
    state_version = state_repository.get_latest_state_version(db, session_id)
```

- [ ] **Step 5: 在 `test_finalize_session.py` 增加回归，锁定 backfilled legacy session 进入 finalize 后仍需显式确认**

```python
def test_backfilled_finalize_ready_session_requires_explicit_finalize_call(...):
    ...
    snapshot = get_session_snapshot(...)
    assert snapshot.state.workflow_stage == "finalize"
```

- [ ] **Step 6: 在 `workspace-session-shell.test.tsx` 增加回归，锁定打开 legacy session 后 UI 能稳定显示可终稿或草稿态**

```tsx
it("renders legacy backfilled finalize state without extra client-side guessing", async () => {
  ...
  expect(screen.getByText("可整理终稿")).toBeInTheDocument();
});
```

- [ ] **Step 7: 运行前后端最小回归**

Run: `/bin/zsh -lc 'PYTHONPATH=apps/api uv run pytest apps/api/tests/test_sessions.py apps/api/tests/test_finalize_session.py apps/api/tests/test_messages_service.py -q'`
Expected: PASS

Run: `pnpm --filter web exec vitest run src/test/workspace-store.test.ts src/test/workspace-session-shell.test.tsx`
Expected: PASS

- [ ] **Step 8: 提交失败回滚与 UI 回归**

```bash
git add apps/api/tests/test_sessions.py apps/api/tests/test_finalize_session.py apps/api/tests/test_messages_service.py apps/web/src/test/workspace-session-shell.test.tsx
git commit -m "test: verify legacy workspace session backfill flows"
```

---

### Task 4: 运行完整回归并收口文档

**Files:**
- Modify: `docs/superpowers/specs/2026-04-16-workspace-legacy-session-backfill-design.md`
- Test: `apps/api/tests/test_messages_stream.py`
- Test: `apps/api/tests/test_messages_service.py`
- Test: `apps/api/tests/test_sessions.py`
- Test: `apps/api/tests/test_agent_runtime.py`
- Test: `apps/api/tests/test_finalize_session.py`
- Test: `apps/api/tests/test_readiness.py`
- Test: `apps/web/src/test/workspace-store.test.ts`
- Test: `apps/web/src/test/workspace-composer.test.tsx`
- Test: `apps/web/src/test/assistant-turn-card.test.tsx`
- Test: `apps/web/src/test/workspace-session-shell.test.tsx`

- [ ] **Step 1: 运行后端完整回归**

Run: `/bin/zsh -lc 'PYTHONPATH=apps/api uv run pytest apps/api/tests/test_messages_stream.py apps/api/tests/test_messages_service.py apps/api/tests/test_sessions.py apps/api/tests/test_agent_runtime.py apps/api/tests/test_finalize_session.py apps/api/tests/test_readiness.py -q'`
Expected: PASS

- [ ] **Step 2: 运行前端完整回归**

Run: `pnpm --filter web exec vitest run src/test/workspace-store.test.ts src/test/workspace-composer.test.tsx src/test/assistant-turn-card.test.tsx src/test/workspace-session-shell.test.tsx`
Expected: PASS

- [ ] **Step 3: 运行类型检查**

Run: `pnpm --filter web exec tsc --noEmit`
Expected: PASS

- [ ] **Step 4: 回写 spec 中的最终落地说明与边界备注**

```md
- 已实现：单 session 打开时按需补算并写回
- 未实现：批量迁移 / 历史消息重放
```

- [ ] **Step 5: 提交最终回归与文档收口**

```bash
git add docs/superpowers/specs/2026-04-16-workspace-legacy-session-backfill-design.md
git commit -m "docs: finalize legacy workspace backfill delivery notes"
```
