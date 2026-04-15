# Codebase Structure

**Analysis Date:** 2026-04-16

## Directory Layout

```text
[project-root]/
├── apps/                    # 可运行应用
│   ├── api/                 # FastAPI 后端
│   └── web/                 # Next.js 前端
├── docs/                    # 契约、设计、实现计划
├── scripts/                 # 本地启动脚本
├── .planning/codebase/      # 代码库映射文档
├── package.json             # monorepo 根清单
├── pnpm-workspace.yaml      # pnpm workspace 定义
└── README.md                # 项目总览与入口文档
```

## Directory Purposes

**`apps/web/src/app`**
- Purpose: Next.js App Router 页面入口，只放路由段与页面壳。
- Contains: `page.tsx`、`layout.tsx`、按路由分组的目录，如 `workspace/`、`login/`、`register/`、`admin/models/`
- Key files: `apps/web/src/app/page.tsx`, `apps/web/src/app/workspace/page.tsx`, `apps/web/src/app/admin/models/page.tsx`
- Subdirectories: `workspace/` 负责工作台入口路由，`admin/models/` 对应模型管理页

**`apps/web/src/components`**
- Purpose: 前端主要 UI 与交互实现层。
- Contains: 业务组件 `.tsx`
- Key files: `apps/web/src/components/workspace/workspace-session-shell.tsx`, `apps/web/src/components/workspace/workspace-left-nav.tsx`, `apps/web/src/components/auth/auth-form.tsx`
- Subdirectories: `workspace/` 为核心业务组件；`auth/` 为登录注册；`admin/` 为管理员页面；`home/` 为首页相关逻辑

**`apps/web/src/store`**
- Purpose: 前端状态容器与状态推导辅助函数。
- Contains: Zustand store 与 PRD 状态 helper
- Key files: `apps/web/src/store/auth-store.ts`, `apps/web/src/store/workspace-store.ts`, `apps/web/src/store/prd-store-helpers.ts`
- Subdirectories: 无二级目录，保持扁平

**`apps/web/src/lib`**
- Purpose: 前端与后端交互、SSE 解析、恢复动作与共享类型。
- Contains: API client、类型定义、流式工具、恢复动作映射
- Key files: `apps/web/src/lib/api.ts`, `apps/web/src/lib/sse.ts`, `apps/web/src/lib/types.ts`
- Subdirectories: 无二级目录，保持按文件职责拆分

**`apps/web/src/hooks`**
- Purpose: 客户端守卫与跨组件复用逻辑。
- Contains: 自定义 hooks
- Key files: `apps/web/src/hooks/use-auth-guard.ts`, `apps/web/src/hooks/use-schema-gate.ts`
- Subdirectories: 无

**`apps/web/src/test`**
- Purpose: 前端 Vitest 测试目录，集中存放组件、hook、store 与页面测试。
- Contains: `*.test.ts`、`*.test.tsx`、全局 `setup.ts`
- Key files: `apps/web/src/test/setup.ts`, `apps/web/src/test/workspace-session-shell.test.tsx`, `apps/web/src/test/api.test.ts`
- Subdirectories: 当前保持扁平

**`apps/api/app/api`**
- Purpose: FastAPI HTTP 边界层。
- Contains: 依赖注入与路由模块
- Key files: `apps/api/app/api/deps.py`, `apps/api/app/api/routes/sessions.py`, `apps/api/app/api/routes/messages.py`
- Subdirectories: `routes/` 按资源分文件组织接口

**`apps/api/app/services`**
- Purpose: 后端业务编排层。
- Contains: 认证、会话、消息、导出、完成确认等服务
- Key files: `apps/api/app/services/sessions.py`, `apps/api/app/services/messages.py`, `apps/api/app/services/finalize_session.py`
- Subdirectories: 当前保持扁平；通过多个 `message_*.py` 文件拆出消息流水线内部步骤

**`apps/api/app/repositories`**
- Purpose: 数据访问层。
- Contains: 按实体拆分的查询和写入函数
- Key files: `apps/api/app/repositories/sessions.py`, `apps/api/app/repositories/messages.py`, `apps/api/app/repositories/prd.py`
- Subdirectories: 无

**`apps/api/app/agent`**
- Purpose: AI 决策与 PRD 推进逻辑。
- Contains: runtime、finalize、readiness、mentor、types 等模块
- Key files: `apps/api/app/agent/runtime.py`, `apps/api/app/agent/finalize_flow.py`, `apps/api/app/agent/readiness.py`
- Subdirectories: 无

**`apps/api/app/db`**
- Purpose: 数据库连接和 ORM 模型定义。
- Contains: SQLAlchemy engine / session、模型定义
- Key files: `apps/api/app/db/session.py`, `apps/api/app/db/models.py`
- Subdirectories: 无

**`apps/api/app/schemas`**
- Purpose: 后端请求响应与内部序列化契约。
- Contains: Pydantic schema
- Key files: `apps/api/app/schemas/session.py`, `apps/api/app/schemas/message.py`, `apps/api/app/schemas/prd.py`
- Subdirectories: 无

**`apps/api/tests`**
- Purpose: 后端 pytest 测试目录。
- Contains: `test_*.py` 与 `conftest.py`
- Key files: `apps/api/tests/conftest.py`, `apps/api/tests/test_sessions.py`, `apps/api/tests/test_messages_stream.py`
- Subdirectories: 当前保持扁平

**`docs/contracts`**
- Purpose: PRD 运行时契约和共享样例。
- Contains: Markdown 契约文档与 JSON 样例
- Key files: `docs/contracts/prd-runtime-contract.md`, `docs/contracts/prd-meta-cases.json`
- Subdirectories: 无

**`docs/superpowers/specs`**
- Purpose: 设计文档归档。
- Contains: 以日期开头的 `*-design.md`
- Key files: `docs/superpowers/specs/2026-04-10-pm-mentor-architecture-design.md`, `docs/superpowers/specs/2026-04-16-workspace-legacy-session-backfill-design.md`
- Subdirectories: 无

**`docs/superpowers/plans`**
- Purpose: 实施计划归档。
- Contains: 以日期开头的 `*-implementation.md`、架构计划文档
- Key files: `docs/superpowers/plans/2026-04-10-pm-mentor-architecture.md`, `docs/superpowers/plans/2026-04-16-backend-brainstorming-enhancement-implementation.md`
- Subdirectories: 无

**`scripts`**
- Purpose: 本地开发一键启动脚本。
- Contains: Shell / PowerShell 启动脚本
- Key files: `scripts/dev.sh`, `scripts/dev.ps1`
- Subdirectories: 无

## Key File Locations

**Entry Points:**
- `apps/web/src/app/layout.tsx`: 前端全局布局入口
- `apps/web/src/app/page.tsx`: 前端首页入口
- `apps/web/src/app/workspace/page.tsx`: 工作台动态入口，根据 query 参数决定渲染分支
- `apps/api/app/main.py`: FastAPI 应用入口
- `apps/api/app/api/deps.py`: 受保护 API 的依赖注入入口

**Configuration:**
- `package.json`: monorepo 根命令入口
- `pnpm-workspace.yaml`: workspace 范围定义
- `apps/web/package.json`: 前端脚本与依赖
- `apps/web/tsconfig.json`: 前端 TypeScript 配置与 `@/*` 别名
- `apps/web/next.config.ts`: Next.js 构建配置
- `apps/api/pyproject.toml`: 后端依赖与测试配置
- `apps/api/alembic.ini`: Alembic 迁移配置
- `.env`, `apps/web/.env.local`: 环境变量文件存在；只在这里记录位置，不记录内容

**Core Logic:**
- `apps/web/src/components/workspace`: 工作台主要交互与布局
- `apps/web/src/store/workspace-store.ts`: 工作台会话状态、SSE 事件归并、PRD 状态更新
- `apps/web/src/lib/api.ts`: 前端后端通信入口
- `apps/api/app/services/messages.py`: 消息流式主流程
- `apps/api/app/services/sessions.py`: 会话快照聚合与列表读写
- `apps/api/app/agent/runtime.py`: AI 决策主入口
- `apps/api/app/repositories`: 后端实体级数据访问

**Testing:**
- `apps/web/src/test`: 前端 Vitest 测试
- `apps/api/tests`: 后端 pytest 测试

**Documentation:**
- `README.md`: 仓库总览
- `docs/startup.md`: 本地启动文档
- `docs/contracts`: PRD 契约与样例
- `docs/superpowers/specs`: 设计说明
- `docs/superpowers/plans`: 实施计划

## Naming Conventions

**Files:**
- `page.tsx` / `layout.tsx`: Next.js App Router 约定入口，例如 `apps/web/src/app/workspace/page.tsx`
- kebab-case `.tsx` / `.ts`: 前端组件、hook、工具文件，例如 `apps/web/src/components/workspace/workspace-left-nav.tsx`, `apps/web/src/hooks/use-auth-guard.ts`
- snake_case `.py`: 后端模块，例如 `apps/api/app/services/finalize_session.py`, `apps/api/app/repositories/model_configs.py`
- `test_*.py`: 后端测试，例如 `apps/api/tests/test_sessions.py`
- `*.test.ts` / `*.test.tsx`: 前端测试，例如 `apps/web/src/test/workspace-store.test.ts`

**Directories:**
- 路由目录按 URL 段命名，例如 `apps/web/src/app/admin/models`, `apps/web/src/app/workspace/new`
- 前端组件目录按业务域分组，例如 `apps/web/src/components/workspace`, `apps/web/src/components/auth`
- 后端目录按层命名而不是按功能域命名，例如 `services`, `repositories`, `schemas`, `db`

**Special Patterns:**
- `message_*.py`: 后端把复杂消息流水线拆成 preparation / persistence / state / models 等子模块
- 日期前缀文档：`docs/superpowers/specs/*.md` 与 `docs/superpowers/plans/*.md`

## Where to Add New Code

**New Frontend Route:**
- Definition: `apps/web/src/app/{route-segments}/page.tsx`
- UI implementation: `apps/web/src/components/{domain}/...`
- Tests: `apps/web/src/test/{feature-name}.test.tsx`
- Notes: `src/app` 页面文件应尽量薄，只做参数读取和组件装配

**New Workspace UI Feature:**
- Primary code: `apps/web/src/components/workspace`
- Shared state: `apps/web/src/store/workspace-store.ts` 或新增同目录 store 文件
- API integration: `apps/web/src/lib/api.ts`，SSE 相关放 `apps/web/src/lib/sse.ts`
- Tests: `apps/web/src/test`

**New Auth or Admin UI Feature:**
- Auth UI: `apps/web/src/components/auth`
- Admin UI: `apps/web/src/components/admin`
- Route entry: `apps/web/src/app/login`, `apps/web/src/app/register`, `apps/web/src/app/admin/...`

**New Backend Route:**
- Definition: `apps/api/app/api/routes/{resource}.py`
- Service handler: `apps/api/app/services/{resource}.py`
- Response/request schema: `apps/api/app/schemas/{resource}.py`
- Data access: `apps/api/app/repositories/{resource}.py`
- Notes: 路由文件保持薄，只做依赖注入和 service 转发

**New Agent / Conversation Logic:**
- Decision logic: `apps/api/app/agent`
- Message pipeline hook-up: `apps/api/app/services/messages.py` 或相关 `message_*.py`
- Contract updates: 如涉及状态或事件结构，同步改 `apps/api/app/schemas/message.py`, `apps/web/src/lib/types.ts`, `apps/web/src/store/workspace-store.ts`

**Utilities:**
- Frontend shared helpers: `apps/web/src/lib`
- Frontend reusable hook: `apps/web/src/hooks`
- Backend shared business helper: 优先放到已有 service 子模块；只有明确是数据访问时才放 `apps/api/app/repositories`

## Special Directories

**`.planning/codebase`**
- Purpose: GSD 代码库映射文档输出目录
- Source: 手工生成
- Committed: Yes

**`apps/api/alembic`**
- Purpose: 数据库迁移版本
- Source: Alembic 生成与维护
- Committed: Yes

**`apps/web/.next`**
- Purpose: Next.js 构建产物
- Source: `next dev` / `next build`
- Committed: No

**`node_modules`, `apps/web/node_modules`**
- Purpose: 依赖安装产物
- Source: `pnpm install`
- Committed: No

**`.worktrees`, `.claude/worktrees`**
- Purpose: 并行开发工作树
- Source: 本地工作流生成
- Committed: No

**`output/playwright`**
- Purpose: 浏览器自动化输出与记录
- Source: Playwright 运行结果
- Committed: 视本仓库策略而定；当前目录存在，应避免把应用源码放到这里

---

*Structure analysis: 2026-04-16*
