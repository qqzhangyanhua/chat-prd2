# Architecture

**Analysis Date:** 2026-04-16

## Pattern Overview

**Overall:** 前后端分离的 monorepo，全栈分层架构

**Key Characteristics:**
- 前端 `apps/web` 使用 Next.js App Router，页面层只做路由分发和壳层拼装，主要交互逻辑下沉到 `src/components`、`src/store`、`src/lib`。
- 后端 `apps/api` 使用 FastAPI，按 `api/routes -> services -> repositories -> db/schemas` 分层，HTTP 边界与业务编排分离。
- “工作台会话”是主业务主线，围绕 `sessions`、`messages`、`finalize`、`export` 一组路由与服务展开。
- AI 对话决策链路单独收敛在 `apps/api/app/agent`，由服务层调用，不直接暴露为 HTTP 路由。

## Layers

**Web Route Layer:**
- Purpose: 承接 URL、选择页面入口、把参数交给客户端壳组件。
- Location: `apps/web/src/app`
- Contains: `page.tsx`、`layout.tsx`、按路由分组的目录，例如 `apps/web/src/app/workspace/page.tsx`、`apps/web/src/app/login/page.tsx`
- Depends on: `apps/web/src/components`
- Used by: Next.js App Router

**Web UI Composition Layer:**
- Purpose: 组织页面视觉结构、表单、会话面板、PRD 面板、管理员页面。
- Location: `apps/web/src/components`
- Contains: `apps/web/src/components/workspace/workspace-session-shell.tsx`、`apps/web/src/components/auth/auth-form.tsx`、`apps/web/src/components/admin/model-config-admin-page.tsx`
- Depends on: `apps/web/src/store`、`apps/web/src/lib`、`apps/web/src/hooks`
- Used by: `apps/web/src/app/*`

**Web State Layer:**
- Purpose: 保存认证态、工作台会话态、toast 状态，并把 SSE 事件应用到当前界面状态。
- Location: `apps/web/src/store`
- Contains: `apps/web/src/store/auth-store.ts`、`apps/web/src/store/workspace-store.ts`、`apps/web/src/store/toast-store.ts`
- Depends on: `apps/web/src/lib/types.ts` 与局部状态辅助函数 `apps/web/src/store/prd-store-helpers.ts`
- Used by: `apps/web/src/components/*`、`apps/web/src/lib/api.ts`

**Web Integration Layer:**
- Purpose: 统一前端与后端 API、SSE、恢复动作、临时草稿存储的交互方式。
- Location: `apps/web/src/lib`, `apps/web/src/hooks`
- Contains: `apps/web/src/lib/api.ts`、`apps/web/src/lib/sse.ts`、`apps/web/src/lib/recovery-action.ts`、`apps/web/src/hooks/use-auth-guard.ts`
- Depends on: 浏览器 `fetch`、环境变量、前端 store
- Used by: 组件层和页面壳层

**API Route Layer:**
- Purpose: 暴露 HTTP 接口、注入认证和数据库依赖、做最薄的请求分发。
- Location: `apps/api/app/api/routes`
- Contains: `auth.py`、`sessions.py`、`messages.py`、`finalize.py`、`exports.py`、`model_configs.py`、`admin_model_configs.py`
- Depends on: `apps/api/app/api/deps.py`、`apps/api/app/services/*`、少量 session 归属校验所需 repository
- Used by: `apps/api/app/main.py`

**Service Layer:**
- Purpose: 编排会话、消息、导出、认证、完成确认等业务流程，连接 agent、repository 与 schema。
- Location: `apps/api/app/services`
- Contains: `sessions.py`、`messages.py`、`finalize_session.py`、`exports.py`、`auth.py` 以及消息链路拆分模块 `message_preparation.py`、`message_persistence.py`、`message_state.py`
- Depends on: `repositories`、`schemas`、`agent`、`core`、`db.models`
- Used by: `api/routes`

**Agent Decision Layer:**
- Purpose: 根据历史会话、当前输入和 PRD 状态生成 turn decision、状态补丁与下一步动作。
- Location: `apps/api/app/agent`
- Contains: `runtime.py`、`readiness.py`、`finalize_flow.py`、`pm_mentor.py`、`prd_updater.py`、`types.py`
- Depends on: 内部类型定义与模型网关调用入口
- Used by: `apps/api/app/services/messages.py`、`apps/api/app/services/message_preparation.py`、`apps/api/app/services/legacy_session_backfill.py`

**Repository Layer:**
- Purpose: 封装数据库查询和写入，提供按实体划分的数据访问函数。
- Location: `apps/api/app/repositories`
- Contains: `sessions.py`、`messages.py`、`prd.py`、`state.py`、`model_configs.py`、`assistant_reply_versions.py`
- Depends on: `apps/api/app/db/models.py`、SQLAlchemy Session
- Used by: `services`

**Persistence & Contract Layer:**
- Purpose: 定义数据库模型、数据库连接、Pydantic 输入输出契约。
- Location: `apps/api/app/db`, `apps/api/app/schemas`
- Contains: `apps/api/app/db/models.py`、`apps/api/app/db/session.py`、`apps/api/app/schemas/session.py`、`apps/api/app/schemas/message.py`
- Depends on: SQLAlchemy / Pydantic
- Used by: `repositories`、`services`、`api/routes`

## Data Flow

**Workspace Session Load:**

1. 浏览器访问 `apps/web/src/app/workspace/page.tsx`，根据 `session` 查询参数决定渲染 `WorkspaceEntry` 还是 `WorkspaceSessionShell`。
2. `apps/web/src/components/workspace/workspace-session-shell.tsx` 调用 `apps/web/src/lib/api.ts` 中的 `getSession()` 与 `listEnabledModelConfigs()`。
3. 后端入口 `apps/api/app/main.py` 已挂载 `apps/api/app/api/routes/sessions.py` 与 `apps/api/app/api/routes/model_configs.py`。
4. 路由通过 `apps/api/app/api/deps.py` 注入当前用户和数据库会话，再转给 `apps/api/app/services/sessions.py` 或对应 repository。
5. `apps/api/app/services/sessions.py` 汇总 session、message、reply group、turn decision、PRD snapshot、state snapshot。
6. 前端 `apps/web/src/store/workspace-store.ts` 通过 `hydrateSession()` 把快照规范化到工作台状态。

**Workspace Message Streaming:**

1. `apps/web/src/components/workspace/conversation-panel.tsx` 与 `composer.tsx` 触发发送。
2. 前端经 `apps/web/src/lib/api.ts` 的 `sendMessage()` 或 `regenerateMessage()` 请求 `/api/sessions/{session_id}/messages...`。
3. `apps/api/app/api/routes/messages.py` 校验会话归属后，调用 `apps/api/app/services/messages.py`。
4. `apps/api/app/services/messages.py` 先通过 `message_preparation.py` 准备上下文，再调用 `apps/api/app/agent/runtime.py` 的 `run_agent()`。
5. service 层按 agent 决策调用 `model_gateway.py`、`message_persistence.py`、`message_state.py`，持续产出 SSE 事件。
6. 前端 `apps/web/src/lib/sse.ts` 解析事件，`apps/web/src/store/workspace-store.ts` 的 `applyEvent()` 更新消息流、版本历史、PRD 快照和决策提示。

**Authentication Flow:**

1. 登录页 `apps/web/src/app/login/page.tsx` 渲染 `apps/web/src/components/auth/auth-form.tsx`。
2. 表单通过 `apps/web/src/lib/api.ts` 的 `login()` / `register()` 调用后端 `apps/api/app/api/routes/auth.py`。
3. `apps/api/app/services/auth.py` 联合 `apps/api/app/core/security.py` 和 `apps/api/app/repositories/auth.py` 完成用户认证。
4. 前端 `apps/web/src/store/auth-store.ts` 持久化 token 和用户信息，`apps/web/src/hooks/use-auth-guard.ts` 为受保护页面做跳转守卫。

**State Management:**
- 前端使用 Zustand；认证态与工作台态分离，分别位于 `apps/web/src/store/auth-store.ts` 和 `apps/web/src/store/workspace-store.ts`。
- 后端请求处理本身是无状态的；跨请求业务状态落在数据库，由 `ProjectSession`、`ConversationMessage`、`PrdSnapshot`、`ProjectStateVersion`、`AssistantReplyGroup`、`AssistantReplyVersion`、`AgentTurnDecision` 等模型承载。
- URL 查询参数和 `sessionStorage` 只用于工作台首条 idea 草稿传递，见 `apps/web/src/components/workspace/workspace-entry.tsx` 与 `apps/web/src/lib/new-session-draft.ts`。

## Key Abstractions

**Workspace Session Snapshot:**
- Purpose: 给前端工作台一次性返回会话、消息、PRD、状态、决策与回复版本。
- Examples: `apps/api/app/services/sessions.py`, `apps/api/app/schemas/session.py`
- Pattern: service 聚合多个 repository 结果，再映射为 response schema

**Reply Group / Reply Version:**
- Purpose: 表示同一条用户消息对应的一组助手回复版本，支持 regenerate 与历史回看。
- Examples: `apps/api/app/db/models.py`, `apps/api/app/repositories/assistant_reply_groups.py`, `apps/web/src/components/workspace/assistant-version-history-dialog.tsx`
- Pattern: group + latest_version 指针

**Turn Decision:**
- Purpose: 承载 agent 的策略判断、下一问、建议选项、状态补丁。
- Examples: `apps/api/app/agent/types.py`, `apps/api/app/repositories/agent_turn_decisions.py`, `apps/web/src/store/workspace-store.ts`
- Pattern: agent 输出结构化决策，service 持久化，前端从 session snapshot 和 SSE 中消费

**Recovery Action:**
- Purpose: 把后端错误恢复建议映射为前端可执行动作。
- Examples: `apps/api/app/core/api_error.py`, `apps/web/src/lib/recovery-action.ts`, `apps/web/src/components/workspace/schema-outdated-notice.tsx`
- Pattern: 后端返回结构化 `recovery_action`，前端统一解析并执行跳转、重试或迁移提示

## Entry Points

**Web Root Layout:**
- Location: `apps/web/src/app/layout.tsx`
- Triggers: Next.js 启动任意页面时
- Responsibilities: 注入全局样式 `globals.css` 并包裹全站 HTML 壳

**Web Home Route:**
- Location: `apps/web/src/app/page.tsx`
- Triggers: 访问 `/`
- Responsibilities: 提供营销首页和登录/注册入口，不承担工作台业务状态

**Web Workspace Route:**
- Location: `apps/web/src/app/workspace/page.tsx`
- Triggers: 访问 `/workspace`
- Responsibilities: 根据 `searchParams.session` 决定进入会话壳还是工作台入口

**API Application Entry:**
- Location: `apps/api/app/main.py`
- Triggers: `python -m uvicorn app.main:app --reload --app-dir apps/api`
- Responsibilities: 创建 FastAPI 实例、挂载路由、中间件与 `ApiError` 异常处理、提供 `/api/health`

**API Dependency Entry:**
- Location: `apps/api/app/api/deps.py`
- Triggers: 任意受保护路由请求
- Responsibilities: 提供 SQLAlchemy session、解析 Bearer token、获取当前用户

## Error Handling

**Strategy:** 后端使用结构化 `ApiError` 和 `raise_api_error()` 向前端返回统一错误体；前端把错误映射成 notice、toast 或跳转恢复动作。

**Patterns:**
- 路由层通过 `apps/api/app/api/deps.py` 和 `apps/api/app/core/api_error.py` 做认证失败、未找到、Schema 过旧等快速失败。
- `apps/api/app/main.py` 注册全局 `ApiError` handler，把异常统一转为 JSON。
- `apps/api/app/services/sessions.py` 对数据库缺表场景做 schema outdated 检测，并返回 `run_migration` 恢复动作。
- 前端 `apps/web/src/lib/api.ts` 在 `401` 时清理 `auth-store` 并跳转 `/login`。
- 工作台壳组件 `apps/web/src/components/workspace/workspace-session-shell.tsx` 与 `workspace-entry.tsx` 根据错误类型展示 `SchemaOutdatedNotice` 或 `WorkspaceErrorNotice`。

## Cross-Cutting Concerns

**Logging:**  
- 后端消息服务 `apps/api/app/services/messages.py` 初始化了模块 logger；日志不是独立一层，仍由 service 模块局部负责。

**Validation:**  
- API 输入输出通过 `apps/api/app/schemas/*.py` 定义；路由函数直接使用 Pydantic schema 作为请求与响应模型。
- 前端状态入库前会做轻量标准化，例如 `apps/web/src/store/workspace-store.ts` 内的 workflow stage、suggestion、question 归一化。

**Authentication:**  
- 后端受保护接口统一依赖 `apps/api/app/api/deps.py:get_current_user`。
- 前端受保护页面通过 `apps/web/src/hooks/use-auth-guard.ts` 做客户端跳转控制，管理员入口额外依赖 `user.is_admin`，见 `apps/web/src/components/admin/model-config-admin-page.tsx`。

**Schema Health / Migration Gate:**  
- 后端 `apps/api/app/main.py` 的 `/api/health` 会检查关键表是否存在。
- 前端 `apps/web/src/hooks/use-schema-gate.ts` 与相关 notice 组件在工作台入口和会话壳里统一拦截“数据库未迁移”场景。

---

*Architecture analysis: 2026-04-16*
