# Workspace Explicit Entry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复工作区显式入口，确保用户点击“新建会话”或 “Home” 后始终进入对应的空白入口页，而不会被旧会话自动重定向覆盖。

**Architecture:** 保留 `/workspace` 作为自动恢复最近会话的默认入口，新增 `/workspace/new` 与 `/workspace/home` 作为显式入口。通过复用 `WorkspaceEntry` 并关闭自动跳转，避免复制页面逻辑，同时把用户的显式入口意图从查询参数提升为稳定路由。

**Tech Stack:** Next.js App Router、React 19、Vitest、Testing Library

---

### Task 1: 写失败测试覆盖显式入口行为

**Files:**
- Modify: `apps/web/src/test/workspace-entry.test.tsx`
- Modify: `apps/web/src/test/session-sidebar.test.tsx`
- Create: `apps/web/src/test/workspace-explicit-entry-pages.test.tsx`

- [ ] **Step 1: 写失败测试**

为以下行为补测试：
- `WorkspaceEntry` 在 `autoRedirectToLatest={false}` 且存在历史会话时不自动跳转。
- `SessionSidebar` 点击“新建会话”跳到 `/workspace/new`。
- `SessionSidebar` 点击 “Home” 跳到 `/workspace/home`。
- `/workspace/new` 与 `/workspace/home` 页面在存在历史会话时仍展示创建表单。

- [ ] **Step 2: 运行测试确认失败**

Run: `pnpm --dir apps/web test -- workspace-entry.test.tsx session-sidebar.test.tsx workspace-session-shell.test.tsx workspace-explicit-entry-pages.test.tsx`
Expected: 至少有一个断言失败，证明问题已被测试捕获。

### Task 2: 最小实现显式入口

**Files:**
- Modify: `apps/web/src/components/workspace/workspace-entry.tsx`
- Modify: `apps/web/src/components/workspace/workspace-left-nav.tsx`
- Modify: `apps/web/src/components/workspace/workspace-session-shell.tsx`
- Create: `apps/web/src/app/workspace/new/page.tsx`
- Create: `apps/web/src/app/workspace/home/page.tsx`

- [ ] **Step 1: 添加最小实现**

- 给 `WorkspaceEntry` 增加 `autoRedirectToLatest` 属性，默认值为 `true`。
- 在禁用自动跳转时跳过 `listSessions` 自动跳转逻辑，并直接结束 loading。
- 新增 `/workspace/new` 与 `/workspace/home` 页面并传入 `autoRedirectToLatest={false}`。
- 更新显式入口按钮与恢复动作，统一跳转到清晰路由。

- [ ] **Step 2: 运行测试确认通过**

Run: `pnpm --dir apps/web test -- workspace-entry.test.tsx session-sidebar.test.tsx workspace-session-shell.test.tsx workspace-explicit-entry-pages.test.tsx workspace-page.test.tsx`
Expected: 全部通过。

### Task 3: 回归验证

**Files:**
- Modify: `apps/web/src/test/workspace-page.test.tsx`

- [ ] **Step 1: 校验旧行为仍成立**

确认 `/workspace` 仍会在存在历史会话时自动跳转到最近会话。

- [ ] **Step 2: 运行相关测试**

Run: `pnpm --dir apps/web test -- workspace-page.test.tsx`
Expected: PASS
