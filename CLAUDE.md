# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 仓库概览

AI Co-founder 是一个通过多轮对话逐步沉淀 PRD 的产品工作台。这是一个 `pnpm` monorepo：

- `apps/web`: Next.js 15 + React 19 前端
- `apps/api`: FastAPI + SQLAlchemy + Alembic 后端
- `docs/contracts`: PRD 运行时契约与共享样例
- `docs/superpowers`: 设计文档与实现计划

模块级细节分别写在 `apps/api/CLAUDE.md` 和 `apps/web/CLAUDE.md`。

## 快速启动

### 安装依赖

```bash
pnpm install
uv venv
source .venv/bin/activate
uv pip install -e "apps/api[dev]"
```

Windows PowerShell:
```powershell
.\.venv\Scripts\Activate.ps1
```

### 启动开发环境

```bash
pnpm dev:web      # 前端 (3000)
pnpm dev:api      # 后端 (8000)
```

Windows 一键启动：
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1
```

### 数据库迁移

```bash
cd apps/api && alembic upgrade head && cd ../..
```

如果 `/api/health` 返回 `schema: "outdated"`，或工作台能列出会话但加载具体会话失败，先跑迁移。

### 测试

```bash
# 前端
pnpm test:web
pnpm --filter web test -- src/test/workspace-store.test.ts
pnpm --filter web test -- -t "WorkspaceSessionShell"

# 后端
pnpm test:api
pytest apps/api/tests/test_health.py -q
pytest apps/api/tests/test_messages_stream.py -q -k prd_updated
```

### 构建

```bash
pnpm --filter web build
```

## 架构核心

### 1. 前端：工作台路由与状态管理

**路由结构**（不是动态目录）：
- `/workspace?session=<uuid>` — 工作台主页，通过 query 参数选择会话
- `/workspace` — 自动跳转到最近会话
- `/workspace/home` — 显式入口页（不自动跳转）
- `/workspace/new` — 新建会话页（不自动跳转）

**唯一网络边界** (`apps/web/src/lib/api.ts`)：
- 所有 HTTP 请求都从这里出去（认证、会话、消息、模型配置）
- `sendMessage()` / `regenerateMessage()` 返回 `ReadableStream`
- `apps/web/src/lib/sse.ts` 负责解析 SSE 流为 `WorkspaceEvent`
- `ApiError`、`recovery_action` 在此标准化，组件层不重复造轮子

**状态真相源** (`apps/web/src/store/workspace-store.ts`)：
- 维护消息列表、reply group、PRD 面板、decision guidance、流式状态、模型选择
- `hydrateSession()` 用后端快照初始化；`applyEvent()` 处理实时 SSE 增量
- 改工作台交互时，优先改 store 和其测试，不要把状态散落到组件

**错误恢复机制**：
- `apps/web/src/hooks/use-schema-gate.ts` — 进入工作台前检查 `/api/health`
- `apps/web/src/lib/recovery-action.ts` — 将 `recovery_action.type` 映射为可执行动作
- Schema 过期、登录失效、重试等交互已有统一通道

### 2. 后端：分层架构与消息管线

**分层结构** (`Route -> Service -> Repository`)：
- `apps/api/app/main.py` — FastAPI 入口，挂载所有路由，注册 `ApiError` 全局处理
- `apps/api/app/api/routes/` — 路由层，只负责 HTTP 协议转换
- `apps/api/app/services/` — 业务逻辑编排层
- `apps/api/app/repositories/` — 数据访问层

**消息/PRD 管线** (`apps/api/app/services/messages.py` 编排)：

SSE 事件顺序（以代码为准）：
```
message.accepted
-> reply_group.created
-> action.decided
-> assistant.version.started
-> assistant.delta ...
-> prd.updated
-> assistant.done
```

职责拆分：
- `message_preparation.py` — 准备上下文、模型配置、构建 MessageContext
- `message_state.py` — 状态版本管理
- `message_persistence.py` — 消息、回复版本、决策记录持久化
- `message_models.py` — 管线内部数据结构
- `prd_runtime.py` — 生成 `prd.updated` 的 sections/meta 预览

**Agent 模块** (`runtime.py` + `pm_mentor.py`)：
- `runtime.py` 处理边界条件：workflow 已完成 → 本地回复；无模型 → 降级回复；其他 → 委托 pm_mentor
- `pm_mentor.py` 调上游 LLM，校验白名单 JSON，生成 `AgentResult` / `TurnDecision` / `prd_patch`

### 3. 数据模型与持久化

**关键表**（9 张）：
- `users` — 用户账号
- `project_sessions` — 会话
- `project_state_versions` — 版本化 state
- `prd_snapshots` — 版本化 PRD
- `conversation_messages` — 对话消息
- `assistant_reply_groups` + `assistant_reply_versions` — 同一消息的多版本 AI 回复
- `agent_turn_decisions` — 决策记录（decision guidance 来源）
- `llm_model_configs` — LLM 模型配置

**模型配置两条链路**：
- 管理端 CRUD → `/api/admin/model-configs`（权限：`ADMIN_EMAILS`）
- 工作台只读 → `/api/model-configs/enabled`

改模型配置字段时，检查：admin 表单、enabled list、消息发送 payload、模型网关调用。

### 4. PRD 运行时契约

如果改"生成 PRD / 对话推进"链路，先读：
- `docs/contracts/README.md`
- `docs/contracts/prd-runtime-contract.md`
- `docs/contracts/prd-meta-cases.json`

## 测试约定

**前端** (`apps/web/src/test/`)：
- 框架：Vitest + @testing-library/react + jsdom
- 优先补：store 测试、SSE/API 边界测试、页面/组件测试

**后端** (`apps/api/tests/`)：
- 框架：pytest + FastAPI TestClient
- 测试数据库：SQLite in-memory（通过 `conftest.py` 注入）
- 优先补：消息流测试、agent 行为测试、持久化测试

## 代码库约束

- 使用 `pnpm`，不要用 `npm`
- 前端 TypeScript strict mode，不引入 `any`
- 共享前端类型集中在 `apps/web/src/lib/types.ts`
- 单文件超过 500 行就拆组件或 hooks
- 类型定义单独放 `type.ts`，不混在业务文件
- 不用 emoji，用合适的 icon 代替

## 环境变量

**根目录 `.env`**（后端读取）：
```env
DATABASE_URL=postgresql+psycopg://user:pass@host:5432/db
AUTH_SECRET_KEY=your-secret-key
ADMIN_EMAILS=admin@example.com
```

**`apps/web/.env.local`**（前端读取）：
```env
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

## 常见问题

**Q: 进入工作台时看到 SchemaOutdatedNotice？**
A: 执行 `cd apps/api && alembic upgrade head` 后点击"重新检测"。

**Q: AI 回复为什么有多个版本？**
A: 用户点击"重新生成"时，后端创建新 `AssistantReplyVersion` 关联到同一 `AssistantReplyGroup`。前端通过版本历史对话框切换查看。

**Q: 管理员如何配置 LLM 模型？**
A: 邮箱需在 `ADMIN_EMAILS` 中，访问 `/admin/models` 进行 CRUD。

**Q: `/workspace` 和 `/workspace/home` 有什么区别？**
A: `/workspace` 自动跳转到最新会话（如果有），`/workspace/home` 和 `/workspace/new` 不自动跳转。

<!-- GSD:project-start source:PROJECT.md -->
## Project

**AI Brainstorming PRD Copilot**

这是一个面向个人开发者的想法压实产品。用户带着一句模糊、零散、半成形的产品念头进入系统，系统通过持续追问、识别矛盾与缺口、提供可反应选项、在合适时机推动确认，逐步把想法收敛成结构化 PRD 初稿。

当前代码库已经具备会话式工作台、AI 消息流、PRD 快照与导出能力；本项目当前阶段的重点不是从零搭建聊天产品，而是把现有工作台升级成更强的引导式需求澄清与 PRD 收敛系统。

**Core Value:** 把个人开发者脑中模糊的产品想法持续压实成可确认、可执行的 PRD，而不是停留在泛泛陪聊。

### Constraints

- **Tech stack**: 延续现有 Next.js + FastAPI + PostgreSQL 架构 — 当前产品已具备可运行工作台与后端能力，不适合为本轮目标推倒重来
- **Product focus**: 优先改善引导结构，其次追问深度，再到 PRD 沉淀 — 这是当前已确认的能力优先级
- **Default interaction**: 默认模式必须先探索再逐步收紧 — 需要在保持用户可表达空间的同时推进收敛
- **User segment**: 主要面向个人开发者 — 决定了交互、术语和产出物要偏“帮助想清楚”，而不是面向企业流程管理
- **Outcome quality**: 最终产物必须能落到结构化 PRD 初稿 — 成功标准不是聊得多，而是能明确用户、问题、方案和边界
<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->
## Technology Stack

## Languages
- TypeScript 5.6.x - 前端应用代码、测试与构建配置，落在 `apps/web/src/**/*`、`apps/web/package.json`、`apps/web/tsconfig.json`
- Python 3.13+ - 后端 API、数据访问、迁移与测试，落在 `apps/api/app/**/*`、`apps/api/alembic/**/*`、`apps/api/pyproject.toml`、`apps/api/uv.lock`
- SQL - PostgreSQL 作为主数据库，通过 SQLAlchemy/Alembic 驱动，入口在 `apps/api/app/db/session.py`、`apps/api/alembic/env.py`
- CSS/Tailwind 配置 - 前端样式系统与 PostCSS 管线，落在 `apps/web/tailwind.config.ts`、`apps/web/postcss.config.mjs`
## Runtime
- Node.js - 前端 Next.js 15 开发、构建、测试运行时；仓库未声明 `.nvmrc` 或 `engines`，命令定义在 `package.json`、`apps/web/package.json`
- Browser runtime - 前端在浏览器中运行，直接使用 `fetch`、`ReadableStream`、`localStorage`，实现位于 `apps/web/src/lib/api.ts`、`apps/web/src/store/auth-store.ts`
- Python 3.13+ - `apps/api/uv.lock` 明确锁定 `requires-python = ">=3.13"`；`docs/startup.md` 说明本地环境准备包含 Python 与 `uv`
- pnpm 10.0.0 - Monorepo JavaScript 包管理器，定义在 `package.json`
- uv - Python 依赖安装与锁文件管理，使用痕迹在 `apps/api/uv.lock`、`docs/startup.md`
- Lockfile: `pnpm-lock.yaml` present, `apps/api/uv.lock` present
## Frameworks
- Next.js 15.0.0 - 前端应用框架，负责页面路由、开发服务器与生产构建，定义在 `apps/web/package.json`、`apps/web/next.config.ts`
- React 19.0.0 - 前端 UI 运行时，定义在 `apps/web/package.json`
- FastAPI 0.135.3 - 后端 HTTP API 框架，应用入口在 `apps/api/app/main.py`，锁定版本见 `apps/api/uv.lock`
- SQLAlchemy 2.x - ORM 与数据库会话层，入口在 `apps/api/app/db/models.py`、`apps/api/app/db/session.py`
- Vitest 2.0.0 - 前端单元/组件测试，配置在 `apps/web/vitest.config.ts`
- Testing Library 16.x / jest-dom 6.x - 前端 DOM 断言与交互测试，定义在 `apps/web/package.json`
- pytest 8.4.x + pytest-asyncio 1.2.x + anyio 4.13.0 - 后端测试栈，锁定信息在 `apps/api/uv.lock`
- TypeScript 5.6.x - 前端类型检查与编译配置，定义在 `apps/web/package.json`、`apps/web/tsconfig.json`
- Tailwind CSS 3.4.13 + PostCSS 8.4.47 + Autoprefixer 10.4.20 - 前端样式构建链，定义在 `apps/web/package.json`、`apps/web/tailwind.config.ts`、`apps/web/postcss.config.mjs`
- Uvicorn 0.38.0 - FastAPI ASGI 开发服务器，启动命令在根 `package.json`，锁定版本见 `apps/api/uv.lock`
- Alembic 1.18.4 - 数据库迁移工具，配置在 `apps/api/alembic.ini`、`apps/api/alembic/env.py`
## Key Dependencies
- `next` 15.0.0 - 前端应用框架核心，定义在 `apps/web/package.json`
- `react` / `react-dom` 19.0.0 - 前端组件渲染核心，定义在 `apps/web/package.json`
- `fastapi` 0.135.3 - 后端 API 路由与依赖注入核心，落在 `apps/api/app/main.py`、`apps/api/uv.lock`
- `sqlalchemy` 2.x - 所有持久化模型与仓储层基础，落在 `apps/api/app/db/models.py`、`apps/api/app/repositories/**/*`
- `httpx` 0.28.1 - 后端调用外部 OpenAI 兼容模型网关的 HTTP 客户端，落在 `apps/api/app/services/model_gateway.py`
- `sse-starlette` 3.0.3 - 后端向前端输出流式事件，落在 `apps/api/app/api/routes/messages.py`
- `python-jose[cryptography]` 3.5.0 - JWT 签发与校验，落在 `apps/api/app/core/security.py`
- `psycopg[binary]` 3.3.3 - PostgreSQL 驱动，数据库会话定义在 `apps/api/app/db/session.py`
- `passlib[bcrypt]` 1.7.4 与 `bcrypt` 5.0.0 - 密码哈希与校验，落在 `apps/api/app/core/security.py`
- `zustand` 5.0.0 - 前端认证状态持久化，落在 `apps/web/src/store/auth-store.ts`
- `@vitejs/plugin-react` 4.3.4 - Vitest 前端测试转换插件，配置在 `apps/web/vitest.config.ts`
## Configuration
- 根目录 `.env` 存在，后端通过 `apps/api/app/core/config.py` 手动读取仓库根环境变量文件；关键键名来自 `DATABASE_URL`、`AUTH_SECRET_KEY`、`AUTH_ACCESS_TOKEN_EXPIRE_MINUTES`、`ADMIN_EMAILS`
- 前端存在 `apps/web/.env.local`，`apps/web/src/lib/api.ts` 读取 `NEXT_PUBLIC_API_BASE_URL`
- 仓库中存在 `docker-compose.yml`，提供本地 PostgreSQL 16 容器；使用说明在 `docs/startup.md`
- Monorepo 根脚本定义在 `package.json`
- Web 构建配置在 `apps/web/next.config.ts`、`apps/web/tsconfig.json`、`apps/web/tailwind.config.ts`、`apps/web/postcss.config.mjs`、`apps/web/vitest.config.ts`
- API 迁移与运行配置在 `apps/api/pyproject.toml`、`apps/api/alembic.ini`、`apps/api/alembic/env.py`
## Platform Requirements
- 需要 `pnpm` 10、Node.js、Python、`uv`、Docker Desktop；文档入口在 `docs/startup.md`
- 本地前端默认运行在 `http://localhost:3000`，后端默认运行在 `http://127.0.0.1:8000`，定义在 `apps/api/app/main.py`、`docs/startup.md`
- 本地数据库可使用 `docker-compose.yml` 中的 PostgreSQL 16，也可改用外部 PostgreSQL；切换方式说明在 `docs/startup.md`
- 未检测到 Vercel、Docker 镜像、Kubernetes 或 CI/CD 工作流配置；当前可确认的生产形态是独立部署 Next.js 前端与 FastAPI 后端，二者通过 `NEXT_PUBLIC_API_BASE_URL` 连接
- 后端对数据库迁移状态有运行时检查，健康检查位于 `apps/api/app/main.py`，要求部署前执行 `alembic upgrade head`
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

## Naming Patterns
- 前端源码文件使用 kebab-case，路径样例见 `apps/web/src/hooks/use-auth-guard.ts`、`apps/web/src/lib/recovery-action.ts`、`apps/web/src/components/workspace/workspace-session-shell.tsx`。
- Next.js App Router 页面文件固定使用 `page.tsx` 与 `layout.tsx`，路径样例见 `apps/web/src/app/page.tsx`、`apps/web/src/app/login/page.tsx`、`apps/web/src/app/layout.tsx`。
- 前端测试文件集中放在 `apps/web/src/test`，命名使用 `*.test.ts` 或 `*.test.tsx`，样例见 `apps/web/src/test/api.test.ts`、`apps/web/src/test/auth-form.test.tsx`。
- 后端模块文件使用 `snake_case`，路径样例见 `apps/api/app/core/api_error.py`、`apps/api/app/services/model_gateway.py`、`apps/api/app/api/routes/auth.py`。
- 后端测试文件放在 `apps/api/tests`，命名使用 `test_*.py`，样例见 `apps/api/tests/test_auth.py`、`apps/api/tests/test_messages_service.py`。
- 前端函数、hook、store action 使用 `camelCase`，样例见 `apps/web/src/lib/api.ts` 中的 `requestJson`、`throwApiError`，`apps/web/src/store/workspace-store.ts` 中的 `normalizeSuggestionOptions`、`pickLatestDecision`。
- React 事件处理函数使用 `handleXxx` 命名，样例见 `apps/web/src/components/auth/auth-form.tsx` 中的 `handleSubmit`、`handleSchemaRetry`。
- React hook 使用 `useXxx` 命名，样例见 `apps/web/src/hooks/use-auth-guard.ts`、`apps/web/src/hooks/use-schema-gate.ts`。
- 后端函数使用 `snake_case`，内部辅助函数常以前导下划线标记，样例见 `apps/api/app/services/messages.py` 中的 `_build_assistant_error_event`、`_prepare_message_stream`，`apps/api/app/services/model_gateway.py` 中的 `_extract_json_object_content`。
- 前端局部变量与状态字段使用 `camelCase`，样例见 `apps/web/src/components/auth/auth-form.tsx` 中的 `schemaRecoveryAction`、`errorRecoveryAction`。
- 前端常量使用 `UPPER_SNAKE_CASE`，样例见 `apps/web/src/lib/api.ts` 中的 `API_BASE_URL`、`SCHEMA_OUTDATED_DETAIL`，`apps/web/src/components/workspace/assistant-turn-card.tsx` 中的 `DECISION_GUIDANCE_REASON_LABEL`。
- 后端模块级常量使用 `UPPER_SNAKE_CASE`，样例见 `apps/api/app/services/messages.py` 中的 `SYSTEM_PROMPT`、`apps/api/tests/test_messages_service.py` 中的 `PRD_META_CONTRACT_CASES`。
- 后端临时对象与 fixture 名称保持 `snake_case`，样例见 `apps/api/tests/conftest.py` 中的 `testing_session_local`、`seeded_session`。
- 前端 TypeScript `interface`、`type`、组件 props 名称使用 `PascalCase`，不加 `I` 前缀，样例见 `apps/web/src/lib/types.ts` 中的 `SessionSnapshotResponse`、`PrdState`，`apps/web/src/components/auth/auth-form.tsx` 中的 `AuthFormProps`。
- 前端联合字面量类型多用于状态枚举，样例见 `apps/web/src/store/workspace-store.ts` 中的 `type StreamPhase = "idle" | "waiting" | "streaming"`。
- 后端异常类型和类名使用 `PascalCase`，样例见 `apps/api/app/core/api_error.py` 中的 `ApiError`、`apps/api/app/services/model_gateway.py` 中的 `ModelGatewayError`。
## Code Style
- 未检测到独立的 Prettier、ESLint 或 Biome 配置文件；`/Users/zhangyanhua/AI/chat-prd2` 与 `apps/web` 下均未发现 `.prettierrc`、`.eslintrc*`、`eslint.config.*`、`biome.json`。
- 前端代码以 TypeScript 严格模式为准，`apps/web/tsconfig.json` 开启 `strict: true`、`noEmit: true`、`moduleResolution: "bundler"`。
- 前端文件现状以 2 空格缩进、双引号、保留分号为主，样例见 `apps/web/src/lib/api.ts`、`apps/web/src/components/auth/auth-form.tsx`、`apps/web/vitest.config.ts`。
- 后端文件遵循 4 空格缩进、PEP 8 风格、显式类型标注优先，样例见 `apps/api/app/core/api_error.py`、`apps/api/app/services/auth.py`、`apps/api/app/services/model_gateway.py`。
- 未检测到可执行的前端 lint 脚本；根 `package.json` 仅定义 `dev:web`、`dev:api`、`test:web`、`test:api`，`apps/web/package.json` 仅定义 `dev`、`build`、`start`、`test`。
- 当前仓库的实际约束来自现有文件风格与 TypeScript/Python 编译或运行时校验，而不是独立 lint 配置。
## Import Organization
- 前端导入组之间通常留一个空行；样例见 `apps/web/src/components/auth/auth-form.tsx`、`apps/web/src/test/workspace-page.test.tsx`。
- 后端导入通常按“标准库 / 第三方 / 本地 app 模块”分组，组间留空行；样例见 `apps/api/tests/conftest.py`、`apps/api/app/services/messages.py`。
- 后端多个同源导入通常拆成逐行 `from ... import ...`，而不是一行导入多个名字，样例见 `apps/api/app/services/messages.py`、`apps/api/tests/test_messages_stream.py`。
- `apps/web/tsconfig.json` 定义了 `@/* -> ./src/*`，`apps/web/vitest.config.ts` 也同步配置了 `@` 别名。
- 现有前端源码大多仍使用相对路径；新增代码应优先延续所在目录现有风格，不要强行混用别名与相对路径。
## Error Handling
- 前端 API 层统一把非 2xx 响应转换为 `ApiError`，样例见 `apps/web/src/lib/api.ts` 中的 `throwApiError`、`requestJson`、`requestVoid`。
- 前端组件或 hook 在边界层 `try/catch`，把异常落为 UI 状态或恢复动作，样例见 `apps/web/src/components/auth/auth-form.tsx` 中的 `handleSubmit`、`handleSchemaRetry`，`apps/web/src/lib/stream-error.ts`。
- 后端业务层对可预期业务错误优先使用 `raise_api_error(...)` 返回结构化错误，样例见 `apps/api/app/core/api_error.py`、`apps/api/app/services/auth.py`、`apps/api/app/services/message_preparation.py`。
- 后端对数据库或网关调用常用 `try/except` 包裹，并在失败时 `rollback`、记录日志或转译异常，样例见 `apps/api/app/services/auth.py`、`apps/api/app/services/model_gateway.py`、`apps/api/app/services/messages.py`。
- 前端对需要登录的请求在 401 时清理状态并重定向，样例见 `apps/web/src/lib/api.ts` 中的 `redirectToLogin`。
- 后端对认证失效返回带 `code`、`message`、`recovery_action` 的统一错误对象，样例见 `apps/api/app/services/auth.py` 与 `apps/api/tests/test_auth.py`。
- 需要兼容 FastAPI 默认行为的地方仍直接抛 `HTTPException`，样例见 `apps/api/app/services/auth.py` 的重复注册/密码错误，`apps/api/app/api/routes/admin_model_configs.py` 的 403/404。
## Logging
- 后端使用标准库 `logging`，通过 `logging.getLogger(__name__)` 创建模块 logger，样例见 `apps/api/app/services/model_gateway.py`、`apps/api/app/services/messages.py`、`apps/api/app/services/legacy_session_backfill.py`。
- 前端没有统一日志封装；少量组件直接使用 `console.error` 记录边界失败，样例见 `apps/web/src/components/workspace/conversation-panel.tsx`、`apps/web/src/components/workspace/prd-panel.tsx`、`apps/web/src/components/workspace/composer.tsx`。
- 后端日志主要记录上游请求失败、非 JSON 响应、流式解析异常和回退路径，样例见 `apps/api/app/services/model_gateway.py`、`apps/api/app/agent/pm_mentor.py`。
- 日志消息倾向附带上下文信息，如 `url`、`status`、`content_type`、`body_preview`，样例见 `apps/api/app/services/model_gateway.py`。
- 新增前端代码不要扩散 `console.log`；若必须记录客户端异常，保持在边界组件并沿用 `console.error("中文说明", error)` 这种格式。
## Comments
- 前端仅在非显然 API 约束或组件尺寸约束处使用简短注释，样例见 `apps/web/src/components/workspace/spinner.tsx`、`apps/web/src/components/workspace/brand-icon.tsx`、`apps/web/src/lib/stream-error.ts`。
- 后端在规则判断、兼容逻辑和复杂编排处使用中文注释或 docstring 解释“为什么”，样例见 `apps/api/app/agent/runtime.py`、`apps/api/app/services/message_preparation.py`、`apps/api/app/agent/prd_updater.py`。
- 测试里允许用注释标注需求映射或特殊约束，样例见 `apps/web/src/test/workspace-left-nav-grouping-pbt.test.tsx`、`apps/api/tests/test_prd_updater.py`。
- 前端不是普遍使用 JSDoc/TSDoc；仅在少数 props 或辅助结构上使用块注释，样例见 `apps/web/src/store/auth-store.ts`、`apps/web/src/lib/stream-error.ts`。
- 后端更常用 Python docstring，尤其在 agent 或服务辅助函数上，样例见 `apps/api/app/services/model_gateway.py`、`apps/api/app/agent/runtime.py`。
- 未检测到活跃的 TODO 约定在前端或后端主代码中大规模使用；新增 TODO 时应附明确上下文，避免无指向的占位备注。
## Function Design
- 前端简单工具函数保持小而纯，复杂状态逻辑会拆到 helper 函数，样例见 `apps/web/src/store/prd-store-helpers.ts`、`apps/web/src/lib/recovery-action.ts`。
- 后端复杂服务文件允许较大体量，但通过 `_helper` 函数拆分流程，样例见 `apps/api/app/services/messages.py`、`apps/api/app/services/model_gateway.py`。
- 前端组件 props 使用对象参数并显式定义 `Props` 接口，样例见 `apps/web/src/components/auth/auth-form.tsx`、`apps/web/src/components/workspace/workspace-entry.tsx`。
- 前端 API/工具函数在参数较少时保留位置参数，样例见 `apps/web/src/lib/api.ts` 中的 `login(email, password)`、`sendMessage(sessionId, content, accessToken?, signal?, modelConfigId?)`。
- 后端服务函数常把依赖资源放在前面，例如 `db: Session`、`session_id: str`，样例见 `apps/api/app/services/auth.py`、`apps/api/app/services/messages.py`。
- 前端大量使用早返回和显式 `null`/空数组保护，样例见 `apps/web/src/store/workspace-store.ts` 中的 `normalizeBestQuestions`、`normalizeSuggestionOptions`。
- 后端返回类型尽量显式声明，辅助函数常返回 `str | None`、`dict[str, Any]`、具名 schema 或 ORM 模型，样例见 `apps/api/app/services/model_gateway.py`、`apps/api/app/api/routes/auth.py`。
## Module Design
- 前端普通模块优先命名导出，样例见 `apps/web/src/lib/api.ts`、`apps/web/src/store/workspace-store.ts`、`apps/web/src/components/workspace/workspace-entry.tsx`。
- Next.js 路由文件使用默认导出页面组件，样例见 `apps/web/src/app/page.tsx`、`apps/web/src/app/workspace/page.tsx`、`apps/web/src/app/admin/models/page.tsx`。
- 后端模块通过显式函数和类暴露能力，不依赖 barrel file，样例见 `apps/api/app/core/api_error.py`、`apps/api/app/services/auth.py`。
- 前端 `apps/web/src` 下未检测到 `index.ts`/`index.tsx` barrel file。
- 后端按包目录组织，但导入时直接引用具体模块路径 `app.services.messages`、`app.repositories.sessions`，不要新增含糊的聚合出口。
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

## Pattern Overview
- 前端 `apps/web` 使用 Next.js App Router，页面层只做路由分发和壳层拼装，主要交互逻辑下沉到 `src/components`、`src/store`、`src/lib`。
- 后端 `apps/api` 使用 FastAPI，按 `api/routes -> services -> repositories -> db/schemas` 分层，HTTP 边界与业务编排分离。
- “工作台会话”是主业务主线，围绕 `sessions`、`messages`、`finalize`、`export` 一组路由与服务展开。
- AI 对话决策链路单独收敛在 `apps/api/app/agent`，由服务层调用，不直接暴露为 HTTP 路由。
## Layers
- Purpose: 承接 URL、选择页面入口、把参数交给客户端壳组件。
- Location: `apps/web/src/app`
- Contains: `page.tsx`、`layout.tsx`、按路由分组的目录，例如 `apps/web/src/app/workspace/page.tsx`、`apps/web/src/app/login/page.tsx`
- Depends on: `apps/web/src/components`
- Used by: Next.js App Router
- Purpose: 组织页面视觉结构、表单、会话面板、PRD 面板、管理员页面。
- Location: `apps/web/src/components`
- Contains: `apps/web/src/components/workspace/workspace-session-shell.tsx`、`apps/web/src/components/auth/auth-form.tsx`、`apps/web/src/components/admin/model-config-admin-page.tsx`
- Depends on: `apps/web/src/store`、`apps/web/src/lib`、`apps/web/src/hooks`
- Used by: `apps/web/src/app/*`
- Purpose: 保存认证态、工作台会话态、toast 状态，并把 SSE 事件应用到当前界面状态。
- Location: `apps/web/src/store`
- Contains: `apps/web/src/store/auth-store.ts`、`apps/web/src/store/workspace-store.ts`、`apps/web/src/store/toast-store.ts`
- Depends on: `apps/web/src/lib/types.ts` 与局部状态辅助函数 `apps/web/src/store/prd-store-helpers.ts`
- Used by: `apps/web/src/components/*`、`apps/web/src/lib/api.ts`
- Purpose: 统一前端与后端 API、SSE、恢复动作、临时草稿存储的交互方式。
- Location: `apps/web/src/lib`, `apps/web/src/hooks`
- Contains: `apps/web/src/lib/api.ts`、`apps/web/src/lib/sse.ts`、`apps/web/src/lib/recovery-action.ts`、`apps/web/src/hooks/use-auth-guard.ts`
- Depends on: 浏览器 `fetch`、环境变量、前端 store
- Used by: 组件层和页面壳层
- Purpose: 暴露 HTTP 接口、注入认证和数据库依赖、做最薄的请求分发。
- Location: `apps/api/app/api/routes`
- Contains: `auth.py`、`sessions.py`、`messages.py`、`finalize.py`、`exports.py`、`model_configs.py`、`admin_model_configs.py`
- Depends on: `apps/api/app/api/deps.py`、`apps/api/app/services/*`、少量 session 归属校验所需 repository
- Used by: `apps/api/app/main.py`
- Purpose: 编排会话、消息、导出、认证、完成确认等业务流程，连接 agent、repository 与 schema。
- Location: `apps/api/app/services`
- Contains: `sessions.py`、`messages.py`、`finalize_session.py`、`exports.py`、`auth.py` 以及消息链路拆分模块 `message_preparation.py`、`message_persistence.py`、`message_state.py`
- Depends on: `repositories`、`schemas`、`agent`、`core`、`db.models`
- Used by: `api/routes`
- Purpose: 根据历史会话、当前输入和 PRD 状态生成 turn decision、状态补丁与下一步动作。
- Location: `apps/api/app/agent`
- Contains: `runtime.py`、`readiness.py`、`finalize_flow.py`、`pm_mentor.py`、`prd_updater.py`、`types.py`
- Depends on: 内部类型定义与模型网关调用入口
- Used by: `apps/api/app/services/messages.py`、`apps/api/app/services/message_preparation.py`、`apps/api/app/services/legacy_session_backfill.py`
- Purpose: 封装数据库查询和写入，提供按实体划分的数据访问函数。
- Location: `apps/api/app/repositories`
- Contains: `sessions.py`、`messages.py`、`prd.py`、`state.py`、`model_configs.py`、`assistant_reply_versions.py`
- Depends on: `apps/api/app/db/models.py`、SQLAlchemy Session
- Used by: `services`
- Purpose: 定义数据库模型、数据库连接、Pydantic 输入输出契约。
- Location: `apps/api/app/db`, `apps/api/app/schemas`
- Contains: `apps/api/app/db/models.py`、`apps/api/app/db/session.py`、`apps/api/app/schemas/session.py`、`apps/api/app/schemas/message.py`
- Depends on: SQLAlchemy / Pydantic
- Used by: `repositories`、`services`、`api/routes`
## Data Flow
- 前端使用 Zustand；认证态与工作台态分离，分别位于 `apps/web/src/store/auth-store.ts` 和 `apps/web/src/store/workspace-store.ts`。
- 后端请求处理本身是无状态的；跨请求业务状态落在数据库，由 `ProjectSession`、`ConversationMessage`、`PrdSnapshot`、`ProjectStateVersion`、`AssistantReplyGroup`、`AssistantReplyVersion`、`AgentTurnDecision` 等模型承载。
- URL 查询参数和 `sessionStorage` 只用于工作台首条 idea 草稿传递，见 `apps/web/src/components/workspace/workspace-entry.tsx` 与 `apps/web/src/lib/new-session-draft.ts`。
## Key Abstractions
- Purpose: 给前端工作台一次性返回会话、消息、PRD、状态、决策与回复版本。
- Examples: `apps/api/app/services/sessions.py`, `apps/api/app/schemas/session.py`
- Pattern: service 聚合多个 repository 结果，再映射为 response schema
- Purpose: 表示同一条用户消息对应的一组助手回复版本，支持 regenerate 与历史回看。
- Examples: `apps/api/app/db/models.py`, `apps/api/app/repositories/assistant_reply_groups.py`, `apps/web/src/components/workspace/assistant-version-history-dialog.tsx`
- Pattern: group + latest_version 指针
- Purpose: 承载 agent 的策略判断、下一问、建议选项、状态补丁。
- Examples: `apps/api/app/agent/types.py`, `apps/api/app/repositories/agent_turn_decisions.py`, `apps/web/src/store/workspace-store.ts`
- Pattern: agent 输出结构化决策，service 持久化，前端从 session snapshot 和 SSE 中消费
- Purpose: 把后端错误恢复建议映射为前端可执行动作。
- Examples: `apps/api/app/core/api_error.py`, `apps/web/src/lib/recovery-action.ts`, `apps/web/src/components/workspace/schema-outdated-notice.tsx`
- Pattern: 后端返回结构化 `recovery_action`，前端统一解析并执行跳转、重试或迁移提示
## Entry Points
- Location: `apps/web/src/app/layout.tsx`
- Triggers: Next.js 启动任意页面时
- Responsibilities: 注入全局样式 `globals.css` 并包裹全站 HTML 壳
- Location: `apps/web/src/app/page.tsx`
- Triggers: 访问 `/`
- Responsibilities: 提供营销首页和登录/注册入口，不承担工作台业务状态
- Location: `apps/web/src/app/workspace/page.tsx`
- Triggers: 访问 `/workspace`
- Responsibilities: 根据 `searchParams.session` 决定进入会话壳还是工作台入口
- Location: `apps/api/app/main.py`
- Triggers: `python -m uvicorn app.main:app --reload --app-dir apps/api`
- Responsibilities: 创建 FastAPI 实例、挂载路由、中间件与 `ApiError` 异常处理、提供 `/api/health`
- Location: `apps/api/app/api/deps.py`
- Triggers: 任意受保护路由请求
- Responsibilities: 提供 SQLAlchemy session、解析 Bearer token、获取当前用户
## Error Handling
- 路由层通过 `apps/api/app/api/deps.py` 和 `apps/api/app/core/api_error.py` 做认证失败、未找到、Schema 过旧等快速失败。
- `apps/api/app/main.py` 注册全局 `ApiError` handler，把异常统一转为 JSON。
- `apps/api/app/services/sessions.py` 对数据库缺表场景做 schema outdated 检测，并返回 `run_migration` 恢复动作。
- 前端 `apps/web/src/lib/api.ts` 在 `401` 时清理 `auth-store` 并跳转 `/login`。
- 工作台壳组件 `apps/web/src/components/workspace/workspace-session-shell.tsx` 与 `workspace-entry.tsx` 根据错误类型展示 `SchemaOutdatedNotice` 或 `WorkspaceErrorNotice`。
## Cross-Cutting Concerns
- 后端消息服务 `apps/api/app/services/messages.py` 初始化了模块 logger；日志不是独立一层，仍由 service 模块局部负责。
- API 输入输出通过 `apps/api/app/schemas/*.py` 定义；路由函数直接使用 Pydantic schema 作为请求与响应模型。
- 前端状态入库前会做轻量标准化，例如 `apps/web/src/store/workspace-store.ts` 内的 workflow stage、suggestion、question 归一化。
- 后端受保护接口统一依赖 `apps/api/app/api/deps.py:get_current_user`。
- 前端受保护页面通过 `apps/web/src/hooks/use-auth-guard.ts` 做客户端跳转控制，管理员入口额外依赖 `user.is_admin`，见 `apps/web/src/components/admin/model-config-admin-page.tsx`。
- 后端 `apps/api/app/main.py` 的 `/api/health` 会检查关键表是否存在。
- 前端 `apps/web/src/hooks/use-schema-gate.ts` 与相关 notice 组件在工作台入口和会话壳里统一拦截“数据库未迁移”场景。
<!-- GSD:architecture-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd:quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd:debug` for investigation and bug fixing
- `/gsd:execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd:profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
