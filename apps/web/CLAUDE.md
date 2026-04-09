[根目录](../../CLAUDE.md) > apps > **web**

# Web 模块 -- Next.js 前端

## 模块职责

AI Co-founder 产品的前端应用。提供用户认证（登录/注册）、工作台会话管理、对话面板、PRD 实时面板、AI 回复版本历史、模型选择、管理后台（模型配置）等 UI，通过 HTTP API + SSE 与后端通信。包含完整的错误恢复体系（ApiError recovery_action 解析）和 schema 版本检测门控（useSchemaGate）。

## 入口与启动

- **框架**: Next.js 15 (App Router) + React 19
- **入口**: `src/app/layout.tsx` (根布局)
- **启动命令**: `pnpm dev:web` 或 `cd apps/web && pnpm dev`
- **默认端口**: 3000
- **构建**: `pnpm --filter web build`

如果你正在维护“生成 PRD”链路，先看：

- [`/Users/zhangyanhua/AI/chat-prd2/docs/contracts/README.md`](/Users/zhangyanhua/AI/chat-prd2/docs/contracts/README.md)
- [`/Users/zhangyanhua/AI/chat-prd2/docs/contracts/prd-runtime-contract.md`](/Users/zhangyanhua/AI/chat-prd2/docs/contracts/prd-runtime-contract.md)

## 页面路由

| 路由 | 文件 | 组件 | 说明 |
|------|------|------|------|
| `/` | `src/app/page.tsx` | HomeAuthRedirect | 根页面，检测登录状态后跳转 |
| `/login` | `src/app/login/page.tsx` | AuthForm (login) | 登录页 |
| `/register` | `src/app/register/page.tsx` | AuthForm (register) | 注册页 |
| `/workspace` | `src/app/workspace/page.tsx` | WorkspaceEntry | 工作台入口 |
| `/workspace/[sessionId]` | `src/app/workspace/[sessionId]/page.tsx` | WorkspaceSessionShell | 会话工作台 |
| `/admin/models` | `src/app/admin/models/page.tsx` | ModelConfigAdminPage | 模型配置管理后台 |

## 组件结构

### auth/
- **auth-form.tsx** -- 登录/注册表单，根据 `mode` prop 切换行为。提交后调用 API 并通过 auth-store 持久化 token。集成 SchemaOutdatedNotice + useSchemaGate 防护。

### workspace/
- **workspace-entry.tsx** -- 工作台入口页。加载会话列表，有会话则自动跳转最新；无则显示创建表单。含 useSchemaGate 前置检测。
- **workspace-session-shell.tsx** -- 会话页主壳。三栏布局：SessionSidebar + ConversationPanel + PrdPanel。加载会话快照 hydrate store。
- **conversation-panel.tsx** -- 对话面板。展示历史消息列表 + AssistantTurnCard（最新 AI 回复） + Composer。
- **composer.tsx** -- 消息输入框 + 发送/停止按钮。管理 SSE 流建立、事件分发、中断处理、重新生成、model-switch 提示。使用 `handleStreamError` 统一处理流错误，使用 `resolveRecoveryAction` 解析可执行动作。
- **assistant-turn-card.tsx** -- AI 回复卡片。显示对话内容、决策指引（判断/假设/建议/确认项/下一步）、快捷回复按钮。支持版本历史对话框（AssistantVersionHistoryDialog）和重新生成。
- **assistant-version-history-dialog.tsx** -- AI 回复版本历史对话框。展示每次重新生成的版本列表，支持切换对比。
- **action-options.tsx** -- 可选推进方式按钮组（接收字符串数组，渲染点击快捷输入）。
- **model-selector.tsx** -- 模型下拉选择器，从 workspace-store 读取可用模型列表。
- **prd-panel.tsx** -- PRD 实时面板。优先展示 `prd_draft.sections` 主 section，并展示 `prd.meta`、Critic 摘要、缺口、下一问和附加 section。
- **prd-section-card.tsx** -- 单个 PRD 部分卡片。显示标题、内容、状态徽章（已确认/AI推测/未定义）。
- **workspace-left-nav.tsx** -- 工作台左侧导航，支持折叠，含会话列表分组（按日期）。
- **workspace-layout.tsx** -- 工作台整体布局容器。
- **workspace-toast-viewport.tsx** -- 全局 toast 通知区域，2.4s 自动消失。
- **workspace-error-notice.tsx** -- 通用错误提示组件，可选渲染可操作按钮（actionLabel + onAction）。
- **schema-outdated-notice.tsx** -- DB schema 过期专用提示，展示缺失表、迁移命令、可点击"重新检测"按钮。
- **brand-icon.tsx** -- 品牌图标组件。
- **skeleton-card.tsx** -- 骨架屏占位卡片。
- **spinner.tsx** -- 加载动画。
- **section-label.tsx** -- 区块标签组件。

### admin/
- **model-config-admin-page.tsx** -- LLM 模型配置管理页。列出所有配置（CRUD），表单含 name/recommended_scene/recommended_usage/base_url/api_key/model/enabled 字段。

### home/
- **home-auth-redirect.tsx** -- 首页认证重定向逻辑组件。

## Hooks

### hooks/use-auth-guard.ts
- 检测登录状态，未登录自动跳转 `/login`

### hooks/use-schema-gate.ts
- `checkSchemaGate()` -- 调用 `/api/health`，若 schema outdated 则阻塞并返回 `"outdated"`
- `syncSchemaFromError(error)` -- 从已捕获错误判断是否为 schema 过期，同步更新 UI 状态
- `syncSchemaFromErrorMessage(message)` -- 从错误字符串判断
- 返回: `{ isSchemaOutdated, schemaHealth, isCheckingSchema, checkSchemaGate, clearSchemaHealth, syncSchemaFromError, syncSchemaFromErrorMessage }`

## 状态管理

### auth-store.ts (Zustand + persist)
- 持久化到 localStorage (`ai-cofounder-auth`)
- 状态: `accessToken`, `user`, `isAuthenticated`
- 操作: `setAuth`, `clearAuth`

### workspace-store.ts (Zustand vanilla store)
- 非持久化，每次 session 切换重置
- 关键状态:
  - `messages` / `replyGroups` -- 消息列表和 AI 回复组（含多版本）
  - `prd` -- PRD 状态（主 section、补充 section、`meta`、版本信息）
  - `decisionGuidance` -- 决策指引（strategy/label/reason/questions）
  - `currentAction`, `isStreaming`, `streamPhase`
  - `selectedModelConfigId`, `availableModelConfigs`
  - `collaborationModeLabel`, `currentModelScene`
  - `selectedHistoryGroupId`, `selectedHistoryVersionId`
  - `isLeftNavCollapsed`
- 操作: `applyEvent`, `startRequest`, `startRegenerate`, `failRequest`, `hydrateSession`, `refreshSessionSnapshot`, `markInterrupted`, `resetError`, `cancelPendingRequest`, `setAvailableModelConfigs`, `selectModelConfig`

### prd-store-helpers.ts
- PRD 运行时派生逻辑单点
- 负责:
  - `hydrate` / `refresh` 时主 section、补充 section、`meta` 派生
  - `prd.updated` 事件的主 section / 补充 section 分流
  - `refreshSessionSnapshot()` 的“保留更新版本”保护，避免旧快照覆盖更新 SSE 状态

### toast-store.ts (Zustand)
- 单条 toast，去重窗口 1.5s
- 操作: `showToast`, `clearToast`

## 网络与错误处理

### lib/api.ts
- 认证: `login`, `register`
- 消息: `sendMessage`（返回 SSE ReadableStream）, `regenerateMessage`
- 会话: `listSessions`, `createSession`, `getSession`, `updateSession`, `deleteSession`
- 导出: `exportSession`
- 健康: `getHealthStatus`（`SCHEMA_OUTDATED_DETAIL` 常量供前端判断）
- 模型配置（用户端）: `listEnabledModelConfigs`
- 模型配置（管理员）: `listAdminModelConfigs`, `createAdminModelConfig`, `updateAdminModelConfig`, `deleteAdminModelConfig`

### lib/sse.ts
- `parseSseEventBlock` -- 解析单个 SSE 事件块
- `parseEventStream` -- AsyncGenerator，将 ReadableStream 转为 `WorkspaceEvent` 流

### lib/stream-error.ts
- `handleStreamError()` -- SSE 流错误统一处理器：AbortError 区分（用户主动停止）vs 网络/业务错误，调用对应 store 动作和 toast 通知

### lib/recovery-action.ts
- `getRecoveryActionFromError(error)` -- 从 error 对象中提取 `ApiRecoveryAction`
- `resolveRecoveryAction(action, handlers)` -- 将 `recovery_action.type` 映射为可调用的 `onAction` 函数
- 支持类型: `login`, `open_workspace_home`, `reload_session`, `retry`, `run_migration`, `select_available_model`

### lib/types.ts
- 所有共享 TypeScript 接口（`User`, `SessionResponse`, `WorkspaceEvent`, `AgentTurnDecision`, `DecisionGuidance`, `ApiRecoveryAction`, `AdminModelConfigItem` 等）

### lib/new-session-draft.ts
- 新建会话草稿状态工具

## SSE 事件类型 (`WorkspaceEvent` union)

```
message.accepted | reply_group.created | assistant.version.started
| action.decided | assistant.delta | assistant.done | prd.updated
```

## 关键依赖与配置

### package.json

- **dependencies**: next 15, react 19, zustand 5, lucide-react, clsx, tailwind-merge, class-variance-authority
- **devDependencies**: TypeScript 5.6, Vitest 2, @testing-library/react 16, jsdom 25, fast-check 4

### tsconfig.json

- strict mode, ES2022 target, bundler module resolution
- 路径别名: `@/*` -> `./src/*`

### next.config.ts

- `reactStrictMode: true`

### 环境变量

- `NEXT_PUBLIC_API_BASE_URL` (在 `.env.local` 中, 默认 `http://127.0.0.1:8000`)

## 测试与质量

- **框架**: Vitest + @testing-library/react + jsdom
- **属性测试 (PBT)**: fast-check (`workspace-left-nav-grouping-pbt.test.tsx`)
- **配置**: `vitest.config.ts`, setup 文件 `src/test/setup.ts`（加载 jest-dom matchers）
- **运行**: `pnpm test:web` 或 `pnpm --filter web test`

| 测试文件 | 覆盖范围 |
|----------|----------|
| `auth-form.test.tsx` | 登录/注册表单渲染、schema 防护 |
| `workspace-entry.test.tsx` | 工作台入口页、useSchemaGate 集成 |
| `workspace-session-shell.test.tsx` | 会话壳组件加载、快照 hydrate |
| `workspace-composer.test.tsx` | 消息输入、发送、recovery_action 渲染 |
| `workspace-store.test.ts` | Zustand store：applyEvent/hydrateSession/replyGroups、`prd.meta` 共享契约 |
| `prd-panel.test.tsx` | PRD 面板：`meta`、补充 section、实时更新渲染 |
| `workspace-page.test.tsx` | 工作台页面路由 |
| `workspace-toast-viewport.test.tsx` | Toast 视图渲染 |
| `workspace-left-nav-grouping.test.tsx` | 左侧导航会话分组（单元） |
| `workspace-left-nav-grouping-pbt.test.tsx` | 左侧导航分组（PBT 属性测试） |
| `session-sidebar.test.tsx` | 侧栏组件交互 |
| `assistant-turn-card.test.tsx` | AI 回复卡片（decisionGuidance / 版本历史）|
| `assistant-version-history-dialog.test.tsx` | 版本历史对话框 |
| `model-config-admin-page.test.tsx` | 管理员模型配置页 CRUD |
| `toast-store.test.ts` | Toast store 去重逻辑 |
| `root-page.test.tsx` | 根页面重定向 |
| `home-auth-redirect.test.tsx` | 首页认证重定向 |
| `api.test.ts` | API 层（含 ApiError 结构、recovery_action 字段） |
| `recovery-action.test.ts` | resolveRecoveryAction() 映射逻辑 |
| `use-schema-gate.test.ts` | useSchemaGate hook 逻辑 |
| `use-auth-guard.test.ts` | useAuthGuard hook |

## 常见问题 (FAQ)

**Q: 为什么进入工作台时看到 SchemaOutdatedNotice？**
A: 前端在进入工作台前调用 `GET /api/health`，若后端返回 `schema: "outdated"`（503），会展示黄色提示框并阻止操作。执行 `cd apps/api && alembic upgrade head` 后点击"重新检测"即可恢复。

**Q: AI 回复为什么有多个版本？**
A: 用户点击"重新生成"时，后端创建新的 `AssistantReplyVersion` 并关联到同一 `AssistantReplyGroup`。前端通过版本历史对话框（Layers 图标）切换查看。

**Q: 管理员如何配置 LLM 模型？**
A: 需后端 `ADMIN_EMAILS` 环境变量中包含登录用户邮箱，访问 `/admin/models` 页面进行 CRUD 操作。

## 相关文件清单

```
apps/web/
  package.json
  tsconfig.json
  next.config.ts
  vitest.config.ts
  next-env.d.ts
  src/
    app/
      layout.tsx
      page.tsx
      login/page.tsx
      register/page.tsx
      workspace/page.tsx
      workspace/[sessionId]/page.tsx
      admin/models/page.tsx
    components/
      home/home-auth-redirect.tsx
      auth/auth-form.tsx
      admin/model-config-admin-page.tsx
      workspace/action-options.tsx
      workspace/assistant-turn-card.tsx
      workspace/assistant-version-history-dialog.tsx
      workspace/brand-icon.tsx
      workspace/composer.tsx
      workspace/conversation-panel.tsx
      workspace/model-selector.tsx
      workspace/prd-panel.tsx
      workspace/prd-section-card.tsx
      workspace/schema-outdated-notice.tsx
      workspace/section-label.tsx
      workspace/skeleton-card.tsx
      workspace/spinner.tsx
      workspace/workspace-entry.tsx
      workspace/workspace-error-notice.tsx
      workspace/workspace-layout.tsx
      workspace/workspace-left-nav.tsx
      workspace/workspace-session-shell.tsx
      workspace/workspace-toast-viewport.tsx
    hooks/
      use-auth-guard.ts
      use-schema-gate.ts
    lib/
      api.ts
      new-session-draft.ts
      recovery-action.ts
      sse.ts
      stream-error.ts
      types.ts
    store/
      auth-store.ts
      prd-store-helpers.ts
      toast-store.ts
      workspace-store.ts
    test/
      setup.ts
      api.test.ts
      assistant-turn-card.test.tsx
      assistant-version-history-dialog.test.tsx
      auth-form.test.tsx
      home-auth-redirect.test.tsx
      model-config-admin-page.test.tsx
      prd-panel.test.tsx
      recovery-action.test.ts
      root-page.test.tsx
      session-sidebar.test.tsx
      toast-store.test.ts
      use-auth-guard.test.ts
      use-schema-gate.test.ts
      workspace-composer.test.tsx
      workspace-entry.test.tsx
      workspace-left-nav-grouping-pbt.test.tsx
      workspace-left-nav-grouping.test.tsx
      workspace-page.test.tsx
      workspace-session-shell.test.tsx
      workspace-store.test.ts
      workspace-toast-viewport.test.tsx
```

## 变更记录 (Changelog)

| 日期 | 操作 | 说明 |
|------|------|------|
| 2026-04-09 | UPDATED | 同步 PRD 运行时结构：补充 `docs/contracts` 入口、`prd-store-helpers.ts`、`prd.meta` / extra sections 展示与 `prd-panel.test.tsx` |
| 2026-04-08 | UPDATED | 新增：管理后台路由、ModelConfigAdminPage、useSchemaGate hook、SchemaOutdatedNotice、WorkspaceErrorNotice、AssistantVersionHistoryDialog、recovery-action 体系、stream-error 工具、fast-check PBT 测试、ModelSelector、workspace-left-nav 折叠/分组、hooks/ 目录完整描述 |
| 2026-04-03 | CREATED | init-architect 首次生成模块文档 |
