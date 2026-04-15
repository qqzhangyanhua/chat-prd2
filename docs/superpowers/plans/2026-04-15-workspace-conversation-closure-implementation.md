# Workspace Conversation Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 `workspace` 新会话打通“草稿沉淀 -> 可终稿 -> 用户确认 -> 终稿生成 -> 自动 reopen -> 导出终稿”的完整对话闭环。

**Architecture:** 保留现有 `messages -> state_version -> prd_snapshot -> session snapshot -> workspace store` 主链，不重做协议。后端新增规则型 `readiness evaluator` 与独立 `finalize_session` 动作，把 `workflow_stage / prd_draft / critic_result / finalization_ready` 变成可靠真相源；前端只消费显式状态并补 finalize 交互，不自行猜测业务状态。

**Tech Stack:** FastAPI, SQLAlchemy 2, Pydantic 2, pytest, SSE, TypeScript, React 19, Next.js 15, Vitest, Testing Library

---

## 范围说明

本计划对应 [`2026-04-15-workspace-complete-conversation-closure-design.md`](/Users/zhangyanhua/AI/chat-prd2/docs/superpowers/specs/2026-04-15-workspace-complete-conversation-closure-design.md)。

本计划范围内必须完成：

- 修复当前后端测试链阻断问题，恢复 `test_messages_service.py` 可运行状态
- 为新会话建立显式状态机：`idea_parser -> refine_loop -> finalize -> completed`
- 引入规则型 readiness evaluator，只在满足业务门槛时进入 `finalize`
- 新增 `POST /api/sessions/{id}/finalize`，支持按钮确认与自然语言确认共用 finalize 语义
- `completed` 后继续输入自动 reopen 到 `refine_loop`
- 前端工作台明确展示“草稿中 / 可整理终稿 / 已生成终稿”，并接入 `生成最终版 PRD` 动作
- 导出在 `completed` 时默认导出 finalized `prd_draft`

本计划范围外暂不实现：

- 旧会话历史状态自动迁移或补算
- 独立 critic 模型调用
- 全新工作台布局
- 额外数据库表

## 文件结构与职责

### 后端核心

- `apps/api/app/agent/runtime.py`
  - 统一完成态、确认态、reopen 与普通对话的状态路由
- `apps/api/app/agent/pm_mentor.py`
  - 收窄为“草稿推进器”，移除直接写 `completed` 的权限
- `apps/api/app/agent/readiness.py`
  - 新增规则型 readiness evaluator，判断是否满足可终稿门槛
- `apps/api/app/agent/finalize_flow.py`
  - 正式接入最终版 PRD 生成逻辑
- `apps/api/app/services/message_state.py`
  - 统一合并 `state_patch / turn_decision / readiness result / finalized draft`
- `apps/api/app/services/finalize_session.py`
  - 新增 finalize 动作服务
- `apps/api/app/services/messages.py`
  - 在消息主链中识别“对话确认终稿”并委托 finalize service
- `apps/api/app/api/routes/finalize.py`
  - 新增 finalize 路由
- `apps/api/app/main.py`
  - 注册 finalize 路由
- `apps/api/app/services/exports.py`
  - 保持“completed 导出终稿，其他状态导出草稿/快照回退”的合同
- `apps/api/app/schemas/state.py`
  - 扩展或规范工作流字段的状态契约

### 后端测试

- `apps/api/tests/test_messages_service.py`
  - 修复语法错误并补闭环状态测试
- `apps/api/tests/test_messages_stream.py`
  - 补 `finalize_ready` / reopen 相关回归
- `apps/api/tests/test_sessions.py`
  - 锁定导出在草稿/终稿状态下的行为
- `apps/api/tests/test_agent_runtime.py`
  - 锁定 `completed` 后 reopen 与确认语义分支
- `apps/api/tests/test_message_service_modules.py`
  - 锁定 `message_state` 合并逻辑
- `apps/api/tests/test_finalize_session.py`
  - 新增 finalize service 单测
- `apps/api/tests/test_readiness.py`
  - 新增 readiness evaluator 单测

### 前端核心

- `apps/web/src/lib/api.ts`
  - 新增 `finalizeSession()`
- `apps/web/src/lib/types.ts`
  - 扩展 snapshot / finalize response / store 所需状态字段
- `apps/web/src/store/prd-store-helpers.ts`
  - 统一从显式状态推导 PRD 面板 meta
- `apps/web/src/store/workspace-store.ts`
  - 增加显式 `workflowStage / isFinalizeReady / isCompleted`
- `apps/web/src/components/workspace/prd-panel.tsx`
  - 展示“草稿中 / 可整理终稿 / 已生成终稿”和 finalize 按钮
- `apps/web/src/components/workspace/assistant-turn-card.tsx`
  - 展示 finalize action 与 completed 提示
- `apps/web/src/components/workspace/conversation-panel.tsx`
  - 把 finalize action 接入对话主区域
- `apps/web/src/components/workspace/composer.tsx`
  - 继续输入 completed 会话时正常发消息，依赖 snapshot 反映 reopen

### 前端测试

- `apps/web/src/test/workspace-store.test.ts`
  - 锁定 finalize/completed/reopen 的状态消费
- `apps/web/src/test/workspace-composer.test.tsx`
  - 锁定 finalize 按钮调用、completed 后继续输入、snapshot 刷新
- `apps/web/src/test/assistant-turn-card.test.tsx`
  - 锁定 finalize action / completed 提示
- `apps/web/src/test/workspace-session-shell.test.tsx`
  - 锁定加载后的显式状态渲染

## 关键实现约束

- 不新增数据库表，只在现有 `state_json` 中承载新状态
- 旧会话不补算，只保证新会话完整闭环
- 第一阶段 readiness 由规则决定，不依赖模型评分
- `pm_mentor` 不允许直接把 `workflow_stage` 写成 `completed`
- finalize 动作独立为普通 mutation，不塞进 SSE 主链
- 前端不自行判断 reopen，始终以最新 session snapshot 为准
- 所有行为改动必须先写失败测试，再写最小实现

## 测试总策略

- 先修后端测试阻断，再补闭环契约测试
- 后端先锁定“状态正确”，前端再锁定“状态说真话”
- 每个任务只跑最小必要测试，最后做一轮闭环回归

---

### Task 1: 恢复后端测试基线并锁定闭环契约

**Files:**
- Modify: `apps/api/tests/test_messages_service.py`
- Modify: `apps/api/tests/test_agent_runtime.py`
- Create: `apps/api/tests/test_readiness.py`
- Create: `apps/api/tests/test_finalize_session.py`
- Test: `apps/api/tests/test_messages_service.py`
- Test: `apps/api/tests/test_agent_runtime.py`
- Test: `apps/api/tests/test_readiness.py`
- Test: `apps/api/tests/test_finalize_session.py`

- [ ] **Step 1: 修复 `test_messages_service.py` 当前的缩进错误，先恢复 pytest 收集**

```python
def test_merge_state_patch_with_decision_reads_workflow_fields_from_turn_decision_top_level():
    turn_decision = SimpleNamespace(
        phase="problem",
        state_patch={"workflow_stage": "finalize"},
        prd_draft={"version": 2},
        critic_result={"overall_verdict": "pass", "question_queue": []},
        finalization_ready=True,
    )
    merged = merge_state_patch_with_decision({}, turn_decision, current_state={})
    assert merged["workflow_stage"] == "finalize"
```

- [ ] **Step 2: 新增 readiness 失败测试，锁定“核心 4 段 + 约束条件 + 成功指标”门槛**

```python
def test_evaluate_readiness_requires_core_and_required_extra_sections():
    state = {
        "prd_draft": {
            "sections": {
                "target_user": {"content": "独立开发者"},
                "problem": {"content": "难以快速沉淀想法"},
                "solution": {"content": "对话式 PRD 助手"},
                "mvp_scope": {"content": "首版只做 PRD 共创"},
                "constraints": {"content": "仅支持浏览器端"},
            }
        }
    }
    result = evaluate_finalize_readiness(state)
    assert result.is_ready_for_finalize is False
    assert "success_metrics" in result.missing_requirements
```

- [ ] **Step 3: 新增 finalize 失败测试，锁定“未 ready 不可 finalize，ready 且确认才可 completed”**

```python
def test_finalize_session_requires_ready_state_and_confirmation():
    with pytest.raises(HTTPException) as exc_info:
        finalize_session(db, session_id, user_id, confirmation_source="button")
    assert exc_info.value.status_code == 409
```

- [ ] **Step 4: 在 `test_agent_runtime.py` 新增失败测试，锁定 `completed` 后实质修改输入会 reopen**

```python
def test_run_agent_reopens_completed_workflow_for_followup_edit():
    state = {"workflow_stage": "completed", "prd_snapshot": {"sections": {}}}
    result = run_agent(state, "把目标用户改成小团队负责人", model_config=MagicMock())
    assert result.state_patch["workflow_stage"] == "refine_loop"
```

- [ ] **Step 5: 运行最小测试集合，确认至少有一批失败点来自 readiness/finalize/reopen 缺失**

Run: `/bin/zsh -lc 'PYTHONPATH=apps/api uv run pytest apps/api/tests/test_messages_service.py apps/api/tests/test_agent_runtime.py apps/api/tests/test_readiness.py apps/api/tests/test_finalize_session.py -q'`

Expected: `test_messages_service.py` 已能被收集；新增闭环测试失败，提示 readiness/finalize/reopen 尚未实现。

- [ ] **Step 6: 提交测试基线修复与红灯测试**

```bash
git add apps/api/tests/test_messages_service.py apps/api/tests/test_agent_runtime.py apps/api/tests/test_readiness.py apps/api/tests/test_finalize_session.py
git commit -m "test(api): lock workspace closure workflow contracts"
```

---

### Task 2: 实现 readiness evaluator 与统一状态合并

**Files:**
- Create: `apps/api/app/agent/readiness.py`
- Modify: `apps/api/app/services/message_state.py`
- Modify: `apps/api/app/schemas/state.py`
- Modify: `apps/api/tests/test_readiness.py`
- Modify: `apps/api/tests/test_message_service_modules.py`
- Test: `apps/api/tests/test_readiness.py`
- Test: `apps/api/tests/test_message_service_modules.py`

- [ ] **Step 1: 在 `readiness.py` 中定义结构化结果类型与最小评估入口**

```python
@dataclass(slots=True)
class ReadinessResult:
    is_ready_for_finalize: bool
    missing_requirements: list[str]
    readiness_summary: str
    critic_result: dict[str, Any]


def evaluate_finalize_readiness(state: dict) -> ReadinessResult:
    ...
```

- [ ] **Step 2: 按业务规则实现最小门槛判定**

```python
required_core = ("target_user", "problem", "solution", "mvp_scope")
required_extra = ("constraints", "success_metrics")

sections = ((state.get("prd_draft") or {}).get("sections") or {})
missing = [key for key in (*required_core, *required_extra) if not _has_meaningful_content(sections.get(key))]
is_ready = len(missing) == 0
```

- [ ] **Step 3: 生成统一 `critic_result` 结构，供前端与导出共用**

```python
critic_result = {
    "overall_verdict": "pass" if is_ready else "revise",
    "major_gaps": [f"还缺 {item}" for item in missing],
    "question_queue": [] if is_ready else [_build_next_question(missing[0])],
}
```

- [ ] **Step 4: 在 `message_state.py` 中新增 readiness 合并入口**

```python
def merge_readiness_state(current_state: dict, readiness: ReadinessResult) -> dict:
    next_state = dict(current_state)
    next_state["critic_result"] = readiness.critic_result
    next_state["finalization_ready"] = readiness.is_ready_for_finalize
    next_state["workflow_stage"] = "finalize" if readiness.is_ready_for_finalize else "refine_loop"
    return next_state
```

- [ ] **Step 5: 更新 `StateSnapshot` 契约，允许 `workflow_stage=finalize` 且显式透传 `finalization_ready / critic_result / prd_draft`**

```python
class StateSnapshot(BaseModel):
    workflow_stage: WorkflowStage = Field(default="idea_parser")
    prd_draft: dict[str, Any] | None = None
    critic_result: dict[str, Any] | None = None
    finalization_ready: bool = False
```

- [ ] **Step 6: 运行 readiness 与 state 模块测试**

Run: `/bin/zsh -lc 'PYTHONPATH=apps/api uv run pytest apps/api/tests/test_readiness.py apps/api/tests/test_message_service_modules.py -q'`

Expected: PASS，`finalize` 阶段与 `critic_result` 合同稳定。

- [ ] **Step 7: 提交 readiness 与状态合并实现**

```bash
git add apps/api/app/agent/readiness.py apps/api/app/services/message_state.py apps/api/app/schemas/state.py apps/api/tests/test_readiness.py apps/api/tests/test_message_service_modules.py
git commit -m "feat(api): add finalize readiness evaluator"
```

---

### Task 3: 收窄 `pm_mentor`，把普通对话轮次稳定落到 `refine_loop / finalize`

**Files:**
- Modify: `apps/api/app/agent/pm_mentor.py`
- Modify: `apps/api/app/agent/runtime.py`
- Modify: `apps/api/tests/test_agent_runtime.py`
- Modify: `apps/api/tests/test_messages_service.py`
- Test: `apps/api/tests/test_agent_runtime.py`
- Test: `apps/api/tests/test_messages_service.py`

- [ ] **Step 1: 写失败测试，锁定 `pm_mentor` 不再直接把 `workflow_stage` 写成 `completed`**

```python
def test_pm_mentor_done_focus_no_longer_marks_completed_directly(...):
    result = run_pm_mentor(state, user_input, model_config)
    assert result.state_patch.get("workflow_stage") != "completed"
```

- [ ] **Step 2: 从 `pm_mentor.py` 删除“`next_focus == done` 直接 completed”逻辑**

```python
state_patch = {
    "iteration": ...,
    "stage_hint": mentor_output.next_focus,
    "conversation_strategy": conversation_strategy,
    "next_best_questions": next_best_questions,
}
```

- [ ] **Step 3: 在 `runtime.py` 中把普通对话主链改成“先跑 mentor，再由 readiness evaluator 决定 refine/finalize”**

```python
agent_result = run_pm_mentor(...)
candidate_state = apply_state_patch_preview(state, agent_result.state_patch)
candidate_state = apply_prd_patch_preview(candidate_state, agent_result.prd_patch)
readiness = evaluate_finalize_readiness(candidate_state)
agent_result.state_patch = merge_runtime_state_patch(agent_result.state_patch, readiness)
```

- [ ] **Step 4: 在 `runtime.py` 中补 `completed` 后 reopen 逻辑**

```python
if state.get("workflow_stage") == "completed" and _should_reopen_completed_workflow(user_input):
    return run_pm_mentor(
        {**state, "workflow_stage": "refine_loop", "finalization_ready": False},
        user_input,
        model_config,
        conversation_history=conversation_history,
    )
```

- [ ] **Step 5: 在 `runtime.py` 中补 `finalize + 明确确认语义` 分支，返回显式 finalize action**

```python
if state.get("workflow_stage") == "finalize" and is_finalize_confirm_input(user_input):
    return AgentResult(
        reply="收到，我现在整理最终版 PRD。",
        phase="finalize",
        action={
            "type": "finalize",
            "confirmation_source": "message",
            "preference": resolve_finalize_preference(user_input),
        },
        state_patch={},
        prd_patch={},
        turn_decision=...,
    )
```

- [ ] **Step 6: 运行 runtime 与消息服务测试**

Run: `/bin/zsh -lc 'PYTHONPATH=apps/api uv run pytest apps/api/tests/test_agent_runtime.py apps/api/tests/test_messages_service.py -q'`

Expected: PASS，普通对话轮次只能落到 `refine_loop` 或 `finalize`，不会绕过用户确认直接 completed。

- [ ] **Step 7: 提交普通对话状态机改造**

```bash
git add apps/api/app/agent/pm_mentor.py apps/api/app/agent/runtime.py apps/api/tests/test_agent_runtime.py apps/api/tests/test_messages_service.py
git commit -m "feat(api): route workspace turns through readiness states"
```

---

### Task 4: 新增 finalize service 与 finalize 路由，打通“按钮确认 / 自然语言确认”

**Files:**
- Create: `apps/api/app/services/finalize_session.py`
- Create: `apps/api/app/api/routes/finalize.py`
- Modify: `apps/api/app/agent/finalize_flow.py`
- Modify: `apps/api/app/main.py`
- Modify: `apps/api/app/services/messages.py`
- Modify: `apps/api/app/services/message_persistence.py`
- Modify: `apps/api/tests/test_finalize_session.py`
- Modify: `apps/api/tests/test_messages_stream.py`
- Modify: `apps/api/tests/test_sessions.py`
- Test: `apps/api/tests/test_finalize_session.py`
- Test: `apps/api/tests/test_messages_stream.py`
- Test: `apps/api/tests/test_sessions.py`

- [ ] **Step 1: 在 `finalize_session.py` 中实现最小 finalize 入口**

```python
def finalize_session(
    db: Session,
    session_id: str,
    user_id: str,
    *,
    confirmation_source: str,
    preference: str | None = None,
) -> SessionCreateResponse:
    ...
```

- [ ] **Step 2: 校验当前会话必须处于 `finalize` 且 `finalization_ready=True`**

```python
state = state_repository.get_latest_state(db, session_id)
if state.get("workflow_stage") != "finalize" or not state.get("finalization_ready"):
    raise_api_error(status_code=409, code="FINALIZE_NOT_READY", message="Session is not ready to finalize")
```

- [ ] **Step 3: 正式调用 `finalize_flow.build_finalized_sections()`，生成 finalized `prd_draft` 与 completed state**

```python
preference = preference or "balanced"
finalized_sections = build_finalized_sections(state.get("prd_draft") or {}, preference)
next_state = {
    **state,
    "workflow_stage": "completed",
    "finalization_ready": True,
    "prd_draft": {
        **(state.get("prd_draft") or {}),
        "status": "finalized",
        "sections": finalized_sections,
    },
}
```

- [ ] **Step 4: 写新 state version 与 prd snapshot，并返回最新 session snapshot**

```python
state_repository.create_state_version(...)
prd_repository.create_prd_snapshot(...)
db.commit()
return session_service.get_session_snapshot(db, session_id, user_id)
```

- [ ] **Step 5: 在 `messages.py` 中消费 `action.type == "finalize"`，让对话确认语义复用 finalize service**

```python
if action.get("type") == "finalize":
    snapshot = finalize_session(
        db,
        session_id,
        session.user_id,
        confirmation_source="message",
        preference=action.get("preference"),
    )
    return build_finalize_message_result(
        user_message=user_message,
        session_snapshot=snapshot,
        reply="已根据当前内容生成最终版 PRD。",
    )
```

- [ ] **Step 6: 新增 `routes/finalize.py` 并在 `main.py` 注册**

```python
router = APIRouter(prefix="/api/sessions/{session_id}/finalize", tags=["finalize"])

@router.post("")
def finalize_session_route(...):
    return finalize_service.finalize_session(...)
```

- [ ] **Step 7: 运行 finalize、消息确认与 session 导出测试**

Run: `/bin/zsh -lc 'PYTHONPATH=apps/api uv run pytest apps/api/tests/test_finalize_session.py apps/api/tests/test_messages_stream.py apps/api/tests/test_sessions.py -q'`

Expected: PASS，按钮确认与对话确认都能进入 `completed`，导出优先终稿。

- [ ] **Step 8: 提交 finalize 动作链路**

```bash
git add apps/api/app/services/finalize_session.py apps/api/app/api/routes/finalize.py apps/api/app/agent/finalize_flow.py apps/api/app/main.py apps/api/app/services/messages.py apps/api/app/services/message_persistence.py apps/api/tests/test_finalize_session.py apps/api/tests/test_messages_stream.py apps/api/tests/test_sessions.py
git commit -m "feat(api): add explicit workspace finalize action"
```

---

### Task 5: 扩展前端 API、store 与 PRD meta，让显式状态成为唯一真相源

**Files:**
- Modify: `apps/web/src/lib/api.ts`
- Modify: `apps/web/src/lib/types.ts`
- Modify: `apps/web/src/store/prd-store-helpers.ts`
- Modify: `apps/web/src/store/workspace-store.ts`
- Modify: `apps/web/src/test/workspace-store.test.ts`
- Modify: `apps/web/src/test/workspace-session-shell.test.tsx`
- Test: `apps/web/src/test/workspace-store.test.ts`
- Test: `apps/web/src/test/workspace-session-shell.test.tsx`

- [ ] **Step 1: 写失败测试，锁定 snapshot 中的 `workflow_stage / finalization_ready / prd_draft / critic_result` 会被 store 正确消费**

```ts
it("hydrates explicit finalize state from session snapshot", () => {
  store.getState().hydrateSession({
    ...snapshot,
    state: {
      ...snapshot.state,
      workflow_stage: "finalize",
      finalization_ready: true,
      prd_draft: { version: 2, status: "draft_refined", sections: {...} },
      critic_result: { overall_verdict: "pass", question_queue: [] },
    },
  });
  expect(store.getState().prd.meta.stageTone).toBe("ready");
});
```

- [ ] **Step 2: 在 `types.ts` 中补充 finalize mutation 与显式状态字段类型**

```ts
export interface FinalizeSessionRequest {
  confirmation_source: "button" | "message";
  preference?: "balanced" | "business" | "technical";
}
```

- [ ] **Step 3: 在 `api.ts` 中新增 `finalizeSession()`**

```ts
export function finalizeSession(
  sessionId: string,
  payload: FinalizeSessionRequest,
  accessToken?: string | null,
): Promise<SessionSnapshotResponse> {
  return requestJson(`/api/sessions/${sessionId}/finalize`, { ... });
}
```

- [ ] **Step 4: 在 `prd-store-helpers.ts` 中让 PRD meta 优先从显式状态推导**

```ts
if (workflowStage === "completed" || draftStatus === "finalized") {
  stageLabel = "已生成终稿";
  stageTone = "final";
} else if (workflowStage === "finalize" || finalizationReady || overallVerdict === "pass") {
  stageLabel = "可整理终稿";
  stageTone = "ready";
}
```

- [ ] **Step 5: 在 `workspace-store.ts` 中补显式阶段判断辅助字段，并确保 refresh snapshot 后不会丢掉 completed/reopen 状态**

```ts
const workflowStage =
  snapshot.state.workflow_stage === "idea_parser" ||
  snapshot.state.workflow_stage === "refine_loop" ||
  snapshot.state.workflow_stage === "finalize" ||
  snapshot.state.workflow_stage === "completed"
    ? snapshot.state.workflow_stage
    : "idea_parser";
```

- [ ] **Step 6: 运行前端状态测试**

Run: `pnpm --filter web test -- workspace-store workspace-session-shell`

Expected: PASS，显式阶段能稳定驱动 PRD meta。

- [ ] **Step 7: 提交前端状态层改造**

```bash
git add apps/web/src/lib/api.ts apps/web/src/lib/types.ts apps/web/src/store/prd-store-helpers.ts apps/web/src/store/workspace-store.ts apps/web/src/test/workspace-store.test.ts apps/web/src/test/workspace-session-shell.test.tsx
git commit -m "feat(web): hydrate explicit workspace closure states"
```

---

### Task 6: 补 finalize UI、completed 提示与 reopen 交互

**Files:**
- Modify: `apps/web/src/components/workspace/prd-panel.tsx`
- Modify: `apps/web/src/components/workspace/assistant-turn-card.tsx`
- Modify: `apps/web/src/components/workspace/conversation-panel.tsx`
- Modify: `apps/web/src/components/workspace/composer.tsx`
- Modify: `apps/web/src/test/assistant-turn-card.test.tsx`
- Modify: `apps/web/src/test/workspace-composer.test.tsx`
- Test: `apps/web/src/test/assistant-turn-card.test.tsx`
- Test: `apps/web/src/test/workspace-composer.test.tsx`

- [ ] **Step 1: 写失败测试，锁定 `finalize` 阶段显示 `生成最终版 PRD`**

```tsx
it("shows finalize action when workflow is ready", () => {
  render(<AssistantTurnCard ... isFinalizeReady />);
  expect(screen.getByRole("button", { name: "生成最终版 PRD" })).toBeInTheDocument();
});
```

- [ ] **Step 2: 在 `PrdPanel` 中增加 ready/final 文案与 finalize 按钮槽位**

```tsx
{meta.stageTone === "ready" ? (
  <button type="button" onClick={onFinalize}>
    生成最终版 PRD
  </button>
) : null}
```

- [ ] **Step 3: 在 `AssistantTurnCard` 中增加 finalize action 与 completed 提示**

```tsx
{isFinalizeReady ? (
  <button type="button" onClick={onFinalize}>生成最终版 PRD</button>
) : null}
{isCompleted ? <p>当前已生成最终版，继续输入会重新打开编辑流程。</p> : null}
```

- [ ] **Step 4: 在 `ConversationPanel` 中把 finalize action 连接到工作台主区域**

```tsx
<AssistantTurnCard
  ...
  isFinalizeReady={workflowStage === "finalize"}
  isCompleted={workflowStage === "completed"}
  onFinalize={() => workspaceStore.getState().requestFinalize()...}
/>
```

- [ ] **Step 5: 在 `Composer` 中实现 finalize mutation 调用与 toast，成功后刷新 session snapshot**

```tsx
const snapshot = await finalizeSession(sessionId, { confirmation_source: "button" }, accessToken);
workspaceStore.getState().refreshSessionSnapshot(snapshot);
showToast({ id: `finalize-${sessionId}`, message: "最终版 PRD 已生成", tone: "success" });
```

- [ ] **Step 6: 运行 UI 相关测试**

Run: `pnpm --filter web test -- assistant-turn-card workspace-composer`

Expected: PASS，ready/completed 提示与 finalize 交互稳定。

- [ ] **Step 7: 提交 finalize UI 改造**

```bash
git add apps/web/src/components/workspace/prd-panel.tsx apps/web/src/components/workspace/assistant-turn-card.tsx apps/web/src/components/workspace/conversation-panel.tsx apps/web/src/components/workspace/composer.tsx apps/web/src/test/assistant-turn-card.test.tsx apps/web/src/test/workspace-composer.test.tsx
git commit -m "feat(web): add finalize and reopen workspace interactions"
```

---

### Task 7: 跑完整闭环回归并修正导出/重生成边角

**Files:**
- Modify: `apps/api/tests/test_messages_stream.py`
- Modify: `apps/api/tests/test_sessions.py`
- Modify: `apps/web/src/test/workspace-store.test.ts`
- Modify: `apps/web/src/test/workspace-composer.test.tsx`
- Test: `apps/api/tests/test_messages_stream.py`
- Test: `apps/api/tests/test_messages_service.py`
- Test: `apps/api/tests/test_sessions.py`
- Test: `apps/web/src/test/workspace-store.test.ts`
- Test: `apps/web/src/test/workspace-composer.test.tsx`

- [ ] **Step 1: 新增后端回归测试，覆盖“达到 finalize_ready -> 按钮或对话确认 finalize -> reopen”主路径**

```python
def test_new_session_can_finalize_and_reopen(...):
    ...
    assert latest_state["workflow_stage"] == "completed"
    ...
    reopened_state = ...
    assert reopened_state["workflow_stage"] == "refine_loop"
```

- [ ] **Step 2: 新增导出回归测试，锁定 `completed` 导出终稿，reopen 后重新导出草稿**

```python
assert "状态：终稿" in export_completed["content"]
assert "状态：草稿" in export_reopened["content"]
```

- [ ] **Step 3: 新增前端回归测试，锁定 finalize 后 snapshot 刷新与 completed 后继续输入 reopen**

```tsx
expect(await screen.findByText("已生成终稿")).toBeInTheDocument();
fireEvent.change(textarea, { target: { value: "把目标用户改成小团队负责人" } });
fireEvent.click(screen.getByRole("button", { name: "发送消息" }));
expect(await screen.findByText("草稿中")).toBeInTheDocument();
```

- [ ] **Step 4: 运行后端完整回归**

Run: `/bin/zsh -lc 'PYTHONPATH=apps/api uv run pytest apps/api/tests/test_messages_stream.py apps/api/tests/test_messages_service.py apps/api/tests/test_sessions.py apps/api/tests/test_agent_runtime.py apps/api/tests/test_finalize_session.py apps/api/tests/test_readiness.py -q'`

Expected: PASS，消息流、状态机、导出与 finalize 全部通过。

- [ ] **Step 5: 运行前端完整回归**

Run: `pnpm --filter web test -- workspace-store workspace-composer assistant-turn-card workspace-session-shell`

Expected: PASS，store、composer、assistant turn、session shell 全部通过。

- [ ] **Step 6: 提交最终闭环回归**

```bash
git add apps/api/tests/test_messages_stream.py apps/api/tests/test_messages_service.py apps/api/tests/test_sessions.py apps/web/src/test/workspace-store.test.ts apps/web/src/test/workspace-composer.test.tsx
git commit -m "test: verify workspace conversation closure end to end"
```
