# Workspace 决策引导卡 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在工作区聊天界面中接入后端 `turn_decisions`，展示最新一轮的阶段标签、推进原因和推荐下一问，并支持点击按钮只填入输入框不自动发送。

**Architecture:** 保持现有工作区布局不变，在 `workspace-store` 中把会话快照里的 `turn_decisions` 派生为 UI 可直接消费的 `decisionGuidance`，再由 `ConversationPanel` 传给 `AssistantTurnCard` 渲染。前端优先从 `decision_sections[].meta` 读取 guidance，`state_patch_json` 作为兜底，从而兼容当前后端返回结构并避免未来字段波动直接打断主聊天流。

**Tech Stack:** Next.js 15、React 19、TypeScript、Zustand、Vitest、Testing Library

---

### Task 1: 为 turn decisions 建立类型与 store 派生

**Files:**
- Modify: `apps/web/src/lib/types.ts`
- Modify: `apps/web/src/store/workspace-store.ts`
- Modify: `apps/web/src/test/workspace-store.test.ts`

- [ ] **Step 1: 写失败测试**

在 `apps/web/src/test/workspace-store.test.ts` 补以下断言：
- `hydrateSession()` 能从 `turn_decisions` 里派生出 `decisionGuidance`
- guidance 优先读取 `decision_sections[].meta`
- 当 `meta` 缺失时会回退到 `state_patch_json`
- 多条决策并存时按 `created_at` 选择最新一条
- `next_best_questions` 会过滤空值、去重，并最多保留前 4 条
- 当推荐项裁剪后为空时不生成 guidance

- [ ] **Step 2: 运行测试确认失败**

Run: `pnpm --dir apps/web test -- src/test/workspace-store.test.ts`
Expected: 新增断言失败，证明当前 store 还没有接入 `turn_decisions`。

- [ ] **Step 3: 写最小实现**

实现以下最小改动：
- 在 `apps/web/src/lib/types.ts` 增加 `AgentTurnDecision`、`AgentTurnDecisionSection` 及其嵌套 `meta/state_patch_json` 类型
- 扩展 `SessionSnapshotResponse`，增加可选 `turn_decisions`
- 在 `apps/web/src/store/workspace-store.ts` 新增 `decisionGuidance` 状态和解析 helper
- 让 `hydrateSession()` 在处理 snapshot 时同步派生 `decisionGuidance`
- 将 latest 选择、字段优先级、推荐项裁剪逻辑封装在 store 内部 helper，避免组件重复判断

- [ ] **Step 4: 运行测试确认通过**

Run: `pnpm --dir apps/web test -- src/test/workspace-store.test.ts`
Expected: PASS

- [ ] **Step 5: 提交这一批改动**

```bash
git add apps/web/src/lib/types.ts apps/web/src/store/workspace-store.ts apps/web/src/test/workspace-store.test.ts
git commit -m "feat(web): hydrate turn decision guidance in workspace store"
```

### Task 2: 在助手卡中渲染决策引导区并接入点击填充

**Files:**
- Modify: `apps/web/src/components/workspace/conversation-panel.tsx`
- Modify: `apps/web/src/components/workspace/assistant-turn-card.tsx`
- Create: `apps/web/src/test/assistant-turn-card.test.tsx`

- [ ] **Step 1: 写失败测试**

新增 `apps/web/src/test/assistant-turn-card.test.tsx`，至少覆盖：
- 存在 guidance 时展示阶段标签、推进原因和 1 到 4 个推荐按钮
- 阶段标签优先展示后端 `strategyLabel`，没有时才使用前端映射
- 点击推荐按钮会调用 `workspaceStore.getState().setInputValue(...)`
- 没有 guidance 时不展示该引导区

- [ ] **Step 2: 运行测试确认失败**

Run: `pnpm --dir apps/web test -- src/test/assistant-turn-card.test.tsx`
Expected: FAIL，当前组件还没有 guidance UI。

- [ ] **Step 3: 写最小实现**

实现以下最小改动：
- 在 `ConversationPanel` 中从 store 读取 `decisionGuidance`
- 将 `decisionGuidance` 作为显式 prop 传给 `AssistantTurnCard`
- 在 `AssistantTurnCard` 中增加轻量“下一步建议”区
- 保持现有重生成、版本历史、深度分析开关不变
- 推荐按钮点击后只执行 `setInputValue(question)`，不触发发送、不修改 streaming 状态

- [ ] **Step 4: 运行测试确认通过**

Run: `pnpm --dir apps/web test -- src/test/assistant-turn-card.test.tsx`
Expected: PASS

- [ ] **Step 5: 提交这一批改动**

```bash
git add apps/web/src/components/workspace/conversation-panel.tsx apps/web/src/components/workspace/assistant-turn-card.tsx apps/web/src/test/assistant-turn-card.test.tsx
git commit -m "feat(web): render turn decision guidance in assistant card"
```

### Task 3: 做会话加载与交互回归验证

**Files:**
- Modify: `apps/web/src/test/workspace-session-shell.test.tsx`
- Modify: `apps/web/src/test/workspace-composer.test.tsx`

- [ ] **Step 1: 补回归测试**

增加以下测试：
- `WorkspaceSessionShell` 从 `getSession()` 返回的 snapshot 中成功 hydrate `turn_decisions`
- `ConversationPanel` 在真实 store 流程下能显示最新 guidance
- 点击推荐按钮后，输入框内容被覆盖为推荐文本
- 无 `turn_decisions` 时现有空态、消息渲染、重生成行为不受影响

- [ ] **Step 2: 运行针对性测试**

Run: `pnpm --dir apps/web test -- src/test/workspace-session-shell.test.tsx src/test/workspace-composer.test.tsx src/test/assistant-turn-card.test.tsx src/test/workspace-store.test.ts`
Expected: 新增测试全部通过。

- [ ] **Step 3: 运行工作区前端回归集**

Run: `pnpm --dir apps/web test -- src/test/workspace-session-shell.test.tsx src/test/workspace-composer.test.tsx src/test/workspace-store.test.ts`
Expected: PASS，确认当前工作区核心交互未回归。

- [ ] **Step 4: 提交最终集成改动**

```bash
git add apps/web/src/test/workspace-session-shell.test.tsx apps/web/src/test/workspace-composer.test.tsx apps/web/src/test/assistant-turn-card.test.tsx apps/web/src/test/workspace-store.test.ts
git commit -m "test(web): cover workspace turn decision guidance flow"
```
