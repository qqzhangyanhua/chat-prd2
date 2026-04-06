# Workspace Regenerate Version History Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将工作区的“重新生成”升级为正式后端语义，为同一条 user message 持久化多版 assistant 回复，并在前端提供版本历史弹层，同时保持主时间线始终只基于 latest version 运转。

**Architecture:** 后端新增 `assistant_reply_groups` 与 `assistant_reply_versions` 两层模型，把 regenerate 从“重新发一条消息”改成“给既有 user turn 追加一个 assistant version”。前端继续沿用当前主时间线结构，只把 latest version 投影到主卡片，再增加版本历史读取、SSE 事件分发和历史弹层，保证查看旧版本不会改变继续对话的基线。

**Tech Stack:** FastAPI、SQLAlchemy、Alembic、pytest、Next.js App Router、React 19、Zustand、Vitest、Testing Library、SSE

---

## 文件结构与职责

### 后端

- Create: `apps/api/alembic/versions/0006_add_assistant_reply_versions.py`
  新增 `assistant_reply_groups` 与 `assistant_reply_versions` 表及索引。
- Modify: `apps/api/app/db/models.py`
  增加 reply group / version ORM，并为消息模型补充必要关系。
- Create: `apps/api/app/repositories/assistant_reply_groups.py`
  封装 reply group 的创建、查询、latest 更新。
- Create: `apps/api/app/repositories/assistant_reply_versions.py`
  封装 version 创建、按 group 查询历史、latest 查询。
- Modify: `apps/api/app/schemas/message.py`
  增加 regenerate 请求模型、version SSE 事件字段、读取响应扩展字段。
- Modify: `apps/api/app/schemas/session.py`
  扩展会话快照响应，返回 `assistant_reply_groups`。
- Modify: `apps/api/app/services/messages.py`
  重构消息写入路径，支持“新 user turn”与“同 turn regenerate”两种流式语义。
- Modify: `apps/api/app/services/sessions.py`
  读取 latest assistant 投影和版本历史，构造会话快照。
- Modify: `apps/api/app/api/routes/messages.py`
  新增 `POST /api/sessions/{session_id}/messages/{user_message_id}/regenerate`。
- Modify: `apps/api/tests/test_models.py`
- Modify: `apps/api/tests/test_messages_service.py`
- Modify: `apps/api/tests/test_messages_stream.py`
- Modify: `apps/api/tests/test_sessions.py`

### 前端

- Modify: `apps/web/src/lib/types.ts`
  增加 reply group、reply version、SSE 新事件与会话快照类型。
- Modify: `apps/web/src/lib/api.ts`
  增加 regenerate API。
- Modify: `apps/web/src/store/workspace-store.ts`
  从“单 assistant 消息”升级为“latest assistant + reply group history”状态模型。
- Modify: `apps/web/src/components/workspace/composer.tsx`
  区分 send 与 regenerate 的调用路径，并按 version 事件更新 store。
- Modify: `apps/web/src/components/workspace/conversation-panel.tsx`
  读取 latest assistant 视图与版本历史入口状态。
- Modify: `apps/web/src/components/workspace/assistant-turn-card.tsx`
  增加“重新生成历史”入口与历史弹层打开逻辑。
- Create: `apps/web/src/components/workspace/assistant-version-history-dialog.tsx`
  展示当前轮全部 assistant 版本，默认高亮 latest，支持切换查看。
- Modify: `apps/web/src/components/workspace/workspace-session-shell.tsx`
  会话加载后注入 reply groups 数据。
- Modify: `apps/web/src/test/workspace-store.test.ts`
- Modify: `apps/web/src/test/workspace-composer.test.tsx`
- Modify: `apps/web/src/test/assistant-turn-card.test.tsx`
- Modify: `apps/web/src/test/workspace-session-shell.test.tsx`
- Create: `apps/web/src/test/assistant-version-history-dialog.test.tsx`

## 任务分解

### Task 1: 建立 reply group / version 数据模型并用测试锁定写入边界

**Files:**
- Create: `apps/api/alembic/versions/0006_add_assistant_reply_versions.py`
- Modify: `apps/api/app/db/models.py`
- Create: `apps/api/app/repositories/assistant_reply_groups.py`
- Create: `apps/api/app/repositories/assistant_reply_versions.py`
- Modify: `apps/api/tests/test_models.py`
- Modify: `apps/api/tests/test_messages_service.py`

- [ ] **Step 1: 先在模型测试里写失败断言**

```python
def test_models_include_assistant_reply_group_tables():
    assert AssistantReplyGroup.__tablename__ == "assistant_reply_groups"
    assert AssistantReplyVersion.__tablename__ == "assistant_reply_versions"
```

- [ ] **Step 2: 在消息 service 测试里写 regenerate 的失败断言**

```python
def test_regenerate_creates_new_version_without_new_user_message(db_session):
    result = regenerate_assistant_reply(...)
    assert result.version_no == 2
    assert count_user_messages(db_session) == 1
```

- [ ] **Step 3: 运行测试确认失败**

Run: `pytest apps/api/tests/test_models.py apps/api/tests/test_messages_service.py -q`

Expected: 因 ORM、迁移、repository 或 regenerate 能力缺失而失败。

- [ ] **Step 4: 增加迁移和 ORM**

```python
class AssistantReplyGroup(Base):
    __tablename__ = "assistant_reply_groups"
    id = mapped_column(String, primary_key=True)
    session_id = mapped_column(ForeignKey("project_sessions.id"), index=True)
    user_message_id = mapped_column(ForeignKey("conversation_messages.id"), unique=True)
    latest_version_id = mapped_column(ForeignKey("assistant_reply_versions.id"), nullable=True)


class AssistantReplyVersion(Base):
    __tablename__ = "assistant_reply_versions"
    id = mapped_column(String, primary_key=True)
    reply_group_id = mapped_column(ForeignKey("assistant_reply_groups.id"), index=True)
    version_no = mapped_column(Integer)
    content = mapped_column(Text)
```

- [ ] **Step 5: 实现两个 repository 的最小读写接口**

```python
def create_reply_group(...): ...
def get_reply_group_by_user_message(...): ...
def create_reply_version(...): ...
def list_versions_for_group(...): ...
def set_latest_version(...): ...
```

- [ ] **Step 6: 重新运行测试确认通过**

Run: `pytest apps/api/tests/test_models.py apps/api/tests/test_messages_service.py -q`

Expected: PASS

- [ ] **Step 7: 提交这一小步**

```bash
git add apps/api/alembic/versions/0006_add_assistant_reply_versions.py apps/api/app/db/models.py apps/api/app/repositories/assistant_reply_groups.py apps/api/app/repositories/assistant_reply_versions.py apps/api/tests/test_models.py apps/api/tests/test_messages_service.py
git commit -m "feat(api): add assistant reply version models"
```

### Task 2: 重构消息服务，区分“新消息”与“regenerate”两条写链路

**Files:**
- Modify: `apps/api/app/services/messages.py`
- Modify: `apps/api/app/api/routes/messages.py`
- Modify: `apps/api/app/schemas/message.py`
- Modify: `apps/api/tests/test_messages_service.py`
- Modify: `apps/api/tests/test_messages_stream.py`

- [ ] **Step 1: 先写新 SSE 协议与 regenerate 接口测试**

```python
def test_regenerate_stream_emits_version_events(auth_client, seeded_session):
    with auth_client.stream("POST", f"/api/sessions/{seeded_session}/messages/{user_id}/regenerate", json={
        "model_config_id": config_id,
    }) as response:
        body = "".join(response.iter_text())
    assert "event: assistant.version.started" in body
    assert "event: assistant.done" in body
    assert "event: message.accepted" not in body
```

- [ ] **Step 2: 运行消息相关测试确认失败**

Run: `pytest apps/api/tests/test_messages_service.py apps/api/tests/test_messages_stream.py -q`

Expected: 因 regenerate 路由、事件名或事件字段缺失而失败。

- [ ] **Step 3: 为消息写链路拆出两个入口**

```python
def stream_user_message_events(...): ...
def stream_regenerate_message_events(...): ...
```

- [ ] **Step 4: 抽出公共的 version 持久化函数**

```python
def _persist_assistant_version(...):
    version = create_reply_version(...)
    set_latest_version(...)
    upsert_latest_assistant_message(...)
    create_state_version(...)
    create_prd_snapshot(...)
```

- [ ] **Step 5: 给路由增加 regenerate 端点**

```python
@router.post("/{user_message_id}/regenerate")
def regenerate_message(...):
    ...
```

- [ ] **Step 6: 确认取消、失败时不落空版本**

补 service 测试覆盖：
- 上游中断时不新增 version
- regenerate 失败时不更新 latest

- [ ] **Step 7: 重新运行消息相关测试确认通过**

Run: `pytest apps/api/tests/test_messages_service.py apps/api/tests/test_messages_stream.py -q`

Expected: PASS

- [ ] **Step 8: 提交这一小步**

```bash
git add apps/api/app/services/messages.py apps/api/app/api/routes/messages.py apps/api/app/schemas/message.py apps/api/tests/test_messages_service.py apps/api/tests/test_messages_stream.py
git commit -m "feat(api): add explicit regenerate message flow"
```

### Task 3: 扩展会话快照读取，返回 latest assistant 投影和版本历史

**Files:**
- Modify: `apps/api/app/services/sessions.py`
- Modify: `apps/api/app/schemas/session.py`
- Modify: `apps/api/app/schemas/message.py`
- Modify: `apps/api/tests/test_sessions.py`

- [ ] **Step 1: 先写会话快照响应测试**

```python
def test_get_session_returns_assistant_reply_groups(auth_client, seeded_session):
    response = auth_client.get(f"/api/sessions/{seeded_session}")
    assert response.status_code == 200
    assert "assistant_reply_groups" in response.json()
```

- [ ] **Step 2: 运行会话测试确认失败**

Run: `pytest apps/api/tests/test_sessions.py -q`

Expected: 因返回结构缺少 `assistant_reply_groups` 或 latest 投影逻辑未改而失败。

- [ ] **Step 3: 扩展 schema**

```python
class AssistantReplyVersionResponse(BaseModel): ...
class AssistantReplyGroupResponse(BaseModel): ...

class SessionCreateResponse(BaseModel):
    ...
    assistant_reply_groups: list[AssistantReplyGroupResponse] = Field(default_factory=list)
```

- [ ] **Step 4: 在 session service 中构建 latest assistant 投影**

```python
def build_timeline_messages(raw_messages, reply_groups):
    # 每条 user message 后只拼 latest assistant version
```

- [ ] **Step 5: 为老会话补兼容兜底**

如果没有 reply group 数据：
- 仍返回旧 `messages`
- `assistant_reply_groups` 为空数组

- [ ] **Step 6: 重新运行会话测试确认通过**

Run: `pytest apps/api/tests/test_sessions.py -q`

Expected: PASS

- [ ] **Step 7: 提交这一小步**

```bash
git add apps/api/app/services/sessions.py apps/api/app/schemas/session.py apps/api/app/schemas/message.py apps/api/tests/test_sessions.py
git commit -m "feat(api): expose assistant reply history in session snapshot"
```

### Task 4: 升级前端类型与 store，支持 version-aware 状态模型

**Files:**
- Modify: `apps/web/src/lib/types.ts`
- Modify: `apps/web/src/lib/api.ts`
- Modify: `apps/web/src/store/workspace-store.ts`
- Modify: `apps/web/src/test/workspace-store.test.ts`

- [ ] **Step 1: 先写 store 失败测试**

```ts
it("appends a new assistant version into the existing reply group on regenerate", () => {
  const store = createWorkspaceStore();
  store.getState().applyEvent({
    type: "assistant.version.started",
    data: { reply_group_id: "g1", assistant_version_id: "v2", version_no: 2, is_regeneration: true },
  });
  expect(store.getState().replyGroups["g1"].versions).toHaveLength(2);
});
```

- [ ] **Step 2: 运行前端 store 测试确认失败**

Run: `pnpm --dir apps/web test -- workspace-store.test.ts`

Expected: 因新类型、新事件或 reply group 状态缺失而失败。

- [ ] **Step 3: 扩展类型定义**

```ts
export interface AssistantReplyVersion { ... }
export interface AssistantReplyGroup { ... }
export type WorkspaceEvent =
  | { type: "assistant.version.started"; data: ... }
  | ...
```

- [ ] **Step 4: 在 store 中增加 reply group 状态**

```ts
replyGroups: Record<string, AssistantReplyGroup>
selectedHistoryGroupId: string | null
selectedHistoryVersionId: string | null
```

- [ ] **Step 5: 重写 regenerate 相关状态流转**

确保：
- regenerate 不再依赖“删掉最后一条 assistant 消息”作为主机制
- latest assistant 由 `assistant.done` 事件明确推进
- old version 仍保存在 reply group 里

- [ ] **Step 6: 增加 regenerate API 调用封装**

```ts
export function regenerateMessage(sessionId: string, userMessageId: string, accessToken?: string | null, signal?: AbortSignal, modelConfigId?: string)
```

- [ ] **Step 7: 重新运行 store 测试确认通过**

Run: `pnpm --dir apps/web test -- workspace-store.test.ts`

Expected: PASS

- [ ] **Step 8: 提交这一小步**

```bash
git add apps/web/src/lib/types.ts apps/web/src/lib/api.ts apps/web/src/store/workspace-store.ts apps/web/src/test/workspace-store.test.ts
git commit -m "feat(web): add reply version aware workspace state"
```

### Task 5: 接入 composer 与对话面板，让 regenerate 走新接口

**Files:**
- Modify: `apps/web/src/components/workspace/composer.tsx`
- Modify: `apps/web/src/components/workspace/conversation-panel.tsx`
- Modify: `apps/web/src/test/workspace-composer.test.tsx`
- Modify: `apps/web/src/test/workspace-session-shell.test.tsx`

- [ ] **Step 1: 先写组件失败测试**

```ts
it("calls regenerate endpoint instead of sendMessage when replaying the latest assistant turn", async () => {
  expect(regenerateMessage).toHaveBeenCalledWith(
    "demo-session",
    "user-1",
    null,
    expect.any(AbortSignal),
    "model-openai",
  );
});
```

- [ ] **Step 2: 运行组件测试确认失败**

Run: `pnpm --dir apps/web test -- workspace-composer.test.tsx workspace-session-shell.test.tsx`

Expected: 因 composer 仍走 `sendMessage` 或快照注入 reply groups 缺失而失败。

- [ ] **Step 3: 在 composer 中区分 send / regenerate**

```ts
if (pendingRequestMode === "regenerate") {
  return regenerateMessage(...);
}
return sendMessage(...);
```

- [ ] **Step 4: 让 shell 在 hydrate 时注入 reply groups**

确保 `WorkspaceSessionShell` 在拿到新快照后能把 `assistant_reply_groups` 一并传入 store。

- [ ] **Step 5: 校验停止生成仍然只重置本地流式状态**

补测试覆盖：
- regenerate 途中点击“停止生成”不会写出新 latest
- 现有 info toast 保持不变

- [ ] **Step 6: 重新运行组件测试确认通过**

Run: `pnpm --dir apps/web test -- workspace-composer.test.tsx workspace-session-shell.test.tsx`

Expected: PASS

- [ ] **Step 7: 提交这一小步**

```bash
git add apps/web/src/components/workspace/composer.tsx apps/web/src/components/workspace/conversation-panel.tsx apps/web/src/test/workspace-composer.test.tsx apps/web/src/test/workspace-session-shell.test.tsx
git commit -m "feat(web): route regenerate through versioned message API"
```

### Task 6: 增加“重新生成历史”弹层并完成 UI 回归

**Files:**
- Create: `apps/web/src/components/workspace/assistant-version-history-dialog.tsx`
- Modify: `apps/web/src/components/workspace/assistant-turn-card.tsx`
- Modify: `apps/web/src/test/assistant-turn-card.test.tsx`
- Create: `apps/web/src/test/assistant-version-history-dialog.test.tsx`

- [ ] **Step 1: 先写历史弹层失败测试**

```ts
it("shows all assistant versions in the history dialog and highlights the latest one", () => {
  render(<AssistantVersionHistoryDialog ... />);
  expect(screen.getByText("版本 3")).toBeInTheDocument();
  expect(screen.getByText("当前版本")).toBeInTheDocument();
});
```

- [ ] **Step 2: 运行 UI 测试确认失败**

Run: `pnpm --dir apps/web test -- assistant-turn-card.test.tsx assistant-version-history-dialog.test.tsx`

Expected: 因新组件和历史入口尚不存在而失败。

- [ ] **Step 3: 实现历史弹层**

```tsx
export function AssistantVersionHistoryDialog({ group, selectedVersionId, onSelectVersion, open, onOpenChange }: Props) {
  ...
}
```

- [ ] **Step 4: 在当前分析卡增加历史入口**

要求：
- 默认只在存在多个版本时显示
- 点击后打开弹层
- 切换版本只影响弹层内容，不改变主卡和 composer 基线

- [ ] **Step 5: 重新运行 UI 测试确认通过**

Run: `pnpm --dir apps/web test -- assistant-turn-card.test.tsx assistant-version-history-dialog.test.tsx`

Expected: PASS

- [ ] **Step 6: 提交这一小步**

```bash
git add apps/web/src/components/workspace/assistant-version-history-dialog.tsx apps/web/src/components/workspace/assistant-turn-card.tsx apps/web/src/test/assistant-turn-card.test.tsx apps/web/src/test/assistant-version-history-dialog.test.tsx
git commit -m "feat(web): add assistant version history dialog"
```

### Task 7: 做全链路回归并补会话恢复兼容验证

**Files:**
- Modify: `apps/api/tests/test_messages_stream.py`
- Modify: `apps/api/tests/test_sessions.py`
- Modify: `apps/web/src/test/workspace-store.test.ts`
- Modify: `apps/web/src/test/workspace-session-shell.test.tsx`

- [ ] **Step 1: 增加跨刷新语义回归测试**

验证：
- regenerate 后刷新会话，不会出现重复 user message
- 最新版本仍正确展示
- 历史版本仍在弹层数据里

- [ ] **Step 2: 运行后端完整相关测试**

Run: `pytest apps/api/tests/test_models.py apps/api/tests/test_messages_service.py apps/api/tests/test_messages_stream.py apps/api/tests/test_sessions.py -q`

Expected: PASS

- [ ] **Step 3: 运行前端完整相关测试**

Run: `pnpm --dir apps/web test -- workspace-store.test.ts workspace-composer.test.tsx assistant-turn-card.test.tsx assistant-version-history-dialog.test.tsx workspace-session-shell.test.tsx`

Expected: PASS

- [ ] **Step 4: 运行一次全量工作区相关测试**

Run: `pnpm --dir apps/web test -- workspace`

Expected: 所有 workspace 相关测试通过，没有旧 regenerate 语义残留断言。

- [ ] **Step 5: 提交回归与收尾**

```bash
git add apps/api/tests/test_messages_stream.py apps/api/tests/test_sessions.py apps/web/src/test/workspace-store.test.ts apps/web/src/test/workspace-session-shell.test.tsx
git commit -m "test: cover regenerate version history flow"
```
