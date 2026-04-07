# Workspace New Session Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复工作区“新建会话”入口，确保用户点击后始终进入空白创建页，而不会被旧会话自动重定向覆盖。

**Architecture:** 保留 `/workspace` 作为自动恢复最近会话的入口，新增 `/workspace/new` 作为显式新建入口。通过给 `WorkspaceEntry` 增加可配置的自动跳转开关，避免复制页面逻辑，并将所有“新建会话”交互统一路由到新入口。

**Tech Stack:** Next.js App Router、React 19、Vitest、Testing Library

---

### Task 1: 写失败测试覆盖新建入口行为

**Files:**
- Modify: `apps/web/src/test/workspace-entry.test.tsx`
- Modify: `apps/web/src/test/session-sidebar.test.tsx`
- Create: `apps/web/src/test/workspace-new-page.test.tsx`

- [ ] **Step 1: 写失败测试**

为以下行为补测试：
- `WorkspaceEntry` 在 `autoRedirectToLatest={false}` 且存在历史会话时不自动跳转。
- `SessionSidebar` 点击“新建会话”跳到 `/workspace/new`。
- `/workspace/new` 页面在存在历史会话时仍展示创建表单。

- [ ] **Step 2: 运行测试确认失败**

Run: `pnpm --dir apps/web test -- workspace-entry.test.tsx session-sidebar.test.tsx workspace-new-page.test.tsx`
Expected: 至少有一个断言失败，证明问题已被测试捕获。

### Task 2: 最小实现新建入口

**Files:**
- Modify: `apps/web/src/components/workspace/workspace-entry.tsx`
- Modify: `apps/web/src/components/workspace/session-sidebar.tsx`
- Create: `apps/web/src/app/workspace/new/page.tsx`

- [ ] **Step 1: 添加最小实现**

- 给 `WorkspaceEntry` 增加 `autoRedirectToLatest` 属性，默认值为 `true`。
- 在禁用自动跳转时跳过 `listSessions` 自动跳转逻辑，并直接结束 loading。
- 新增 `/workspace/new` 页面并传入 `autoRedirectToLatest={false}`。
- 更新“新建会话”按钮统一跳转 `/workspace/new`。

- [ ] **Step 2: 运行测试确认通过**

Run: `pnpm --dir apps/web test -- workspace-entry.test.tsx session-sidebar.test.tsx workspace-new-page.test.tsx workspace-page.test.tsx`
Expected: 全部通过。

### Task 3: 回归验证

**Files:**
- Modify: `apps/web/src/test/workspace-page.test.tsx`

- [ ] **Step 1: 校验旧行为仍成立**

确认 `/workspace` 仍会在存在历史会话时自动跳转到最近会话。

- [ ] **Step 2: 运行相关测试**

Run: `pnpm --dir apps/web test -- workspace-page.test.tsx`
Expected: PASS
