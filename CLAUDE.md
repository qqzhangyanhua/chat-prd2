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
