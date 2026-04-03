[根目录](../../CLAUDE.md) > apps > **web**

# Web 模块 -- Next.js 前端

## 模块职责

AI Co-founder 产品的前端应用。提供用户认证（登录/注册）、工作台会话管理、对话面板、PRD 实时面板等 UI，通过 HTTP API + SSE 与后端通信。

## 入口与启动

- **框架**: Next.js 15 (App Router) + React 19
- **入口**: `src/app/layout.tsx` (根布局)
- **启动命令**: `pnpm dev:web` 或 `cd apps/web && pnpm dev`
- **默认端口**: 3000
- **构建**: `pnpm --filter web build`

## 页面路由

| 路由 | 文件 | 组件 | 说明 |
|------|------|------|------|
| `/login` | `src/app/login/page.tsx` | AuthForm (login) | 登录页 |
| `/register` | `src/app/register/page.tsx` | AuthForm (register) | 注册页 |
| `/workspace` | `src/app/workspace/page.tsx` | WorkspaceEntry | 工作台入口 |
| `/workspace/[sessionId]` | `src/app/workspace/[sessionId]/page.tsx` | WorkspaceSessionShell | 会话工作台 |

## 组件结构

### auth/
- **auth-form.tsx** -- 登录/注册表单，根据 `mode` prop 切换行为。提交后调用 API 并通过 auth-store 持久化 token。

### workspace/
- **workspace-entry.tsx** -- 工作台入口页。加载会话列表，有会话则自动跳转最新会话；无则显示创建表单。
- **workspace-session-shell.tsx** -- 会话页主壳。三栏布局：SessionSidebar + ConversationPanel + PrdPanel。加载会话快照 hydrate store。
- **conversation-panel.tsx** -- 对话面板。展示 AssistantTurnCard + Composer。
- **composer.tsx** -- 消息输入框 + 发送/停止按钮。管理 SSE 流的建立、事件分发、中断处理。
- **assistant-turn-card.tsx** -- AI 回复展示卡片。显示理解摘要、判断、风险点、可选推进方式、下一步问题。支持重新生成。
- **action-options.tsx** -- 可选推进方式按钮组。
- **prd-panel.tsx** -- PRD 实时面板。展示 4 个 section (target_user, problem, solution, mvp_scope)。
- **prd-section-card.tsx** -- 单个 PRD 部分卡片。显示标题、内容、状态徽章 (已确认/AI推测/未定义)。
- **session-sidebar.tsx** -- 会话侧栏。会话列表、重命名、删除、恢复、导出 PRD、新建会话。
- **workspace-toast-viewport.tsx** -- 全局 toast 通知区域，2.4s 自动消失。

## 状态管理

### auth-store.ts (Zustand + persist)
- 持久化到 localStorage (`ai-cofounder-auth`)
- 状态: `accessToken`, `user`, `isAuthenticated`
- 操作: `setAuth`, `clearAuth`

### workspace-store.ts (Zustand vanilla store)
- 非持久化，每次 session 切换重置
- 状态: `messages`, `prd`, `currentAction`, `isStreaming`, `streamPhase`, `inputValue`, `errorMessage`, `lastInterrupted`, `regenerateRequestId` 等
- 操作: `applyEvent` (SSE 事件处理), `startRequest`, `failRequest`, `hydrateSession`, `markInterrupted`, `startRegenerate`
- SSE 事件类型: `message.accepted`, `action.decided`, `assistant.delta`, `assistant.done`, `prd.updated`

### toast-store.ts (Zustand)
- 单条 toast，去重窗口 1.5s
- 状态: `toast` (id, message, tone)
- 操作: `showToast`, `clearToast`

## 关键依赖与配置

### package.json

- **dependencies**: next 15, react 19, react-dom 19, zustand 5
- **devDependencies**: TypeScript 5.6, Vitest 2, @testing-library/react 16, jsdom 25

### tsconfig.json

- strict mode, ES2022 target, bundler module resolution
- 路径别名: `@/*` -> `./src/*`

### next.config.ts

- `reactStrictMode: true`

### 环境变量

- `NEXT_PUBLIC_API_BASE_URL` (在 `.env.local` 中, 默认 `http://127.0.0.1:8000`)

## 网络层

### lib/api.ts
- `login`, `register` -- 认证 API
- `sendMessage` -- 发送消息，返回 SSE ReadableStream
- `listSessions`, `createSession`, `getSession`, `updateSession`, `deleteSession` -- 会话 CRUD
- `exportSession` -- PRD 导出

### lib/sse.ts
- `parseSseEventBlock` -- 解析单个 SSE 事件块
- `parseEventStream` -- AsyncGenerator，将 ReadableStream 转为 WorkspaceEvent 流

### lib/types.ts
- 共享 TypeScript 接口定义: `User`, `AuthResponse`, `SessionResponse`, `WorkspaceMessage`, `PrdSection`, `WorkspaceEvent` 等

## 测试与质量

- **框架**: Vitest + @testing-library/react + jsdom
- **配置**: `vitest.config.ts`, setup 文件 `src/test/setup.ts` (加载 jest-dom matchers)
- **运行**: `pnpm test:web` 或 `pnpm --filter web test`

| 测试文件 | 覆盖范围 |
|----------|----------|
| `auth-form.test.tsx` | 登录/注册表单渲染与交互 |
| `workspace-entry.test.tsx` | 工作台入口页 |
| `workspace-session-shell.test.tsx` | 会话壳组件加载 |
| `workspace-composer.test.tsx` | 消息输入与发送 |
| `workspace-page.test.tsx` | 工作台页面路由 |
| `workspace-store.test.ts` | Zustand store 逻辑 |
| `toast-store.test.ts` | Toast store 逻辑 |
| `session-sidebar.test.tsx` | 侧栏组件 |
| `assistant-turn-card.test.tsx` | AI 回复卡片 |
| `workspace-toast-viewport.test.tsx` | Toast 视图 |
| `root-page.test.tsx` | 根页面 |

## 相关文件清单

```
apps/web/
  package.json
  tsconfig.json
  next.config.ts
  vitest.config.ts
  next-env.d.ts
  .env.local
  src/
    app/
      layout.tsx
      login/page.tsx
      register/page.tsx
      workspace/page.tsx
      workspace/[sessionId]/page.tsx
    components/
      auth/auth-form.tsx
      workspace/action-options.tsx
      workspace/assistant-turn-card.tsx
      workspace/composer.tsx
      workspace/conversation-panel.tsx
      workspace/prd-panel.tsx
      workspace/prd-section-card.tsx
      workspace/session-sidebar.tsx
      workspace/workspace-entry.tsx
      workspace/workspace-session-shell.tsx
      workspace/workspace-toast-viewport.tsx
    lib/
      api.ts
      sse.ts
      types.ts
    store/
      auth-store.ts
      workspace-store.ts
      toast-store.ts
    test/
      setup.ts
      auth-form.test.tsx
      workspace-entry.test.tsx
      workspace-session-shell.test.tsx
      workspace-composer.test.tsx
      workspace-page.test.tsx
      workspace-store.test.ts
      toast-store.test.ts
      session-sidebar.test.tsx
      assistant-turn-card.test.tsx
      workspace-toast-viewport.test.tsx
      root-page.test.tsx
```

## 变更记录 (Changelog)

| 日期 | 操作 | 说明 |
|------|------|------|
| 2026-04-03 | CREATED | init-architect 首次生成模块文档 |
