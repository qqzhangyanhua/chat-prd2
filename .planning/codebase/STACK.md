# Technology Stack

**Analysis Date:** 2026-04-16

## Languages

**Primary:**
- TypeScript 5.6.x - 前端应用代码、测试与构建配置，落在 `apps/web/src/**/*`、`apps/web/package.json`、`apps/web/tsconfig.json`
- Python 3.13+ - 后端 API、数据访问、迁移与测试，落在 `apps/api/app/**/*`、`apps/api/alembic/**/*`、`apps/api/pyproject.toml`、`apps/api/uv.lock`

**Secondary:**
- SQL - PostgreSQL 作为主数据库，通过 SQLAlchemy/Alembic 驱动，入口在 `apps/api/app/db/session.py`、`apps/api/alembic/env.py`
- CSS/Tailwind 配置 - 前端样式系统与 PostCSS 管线，落在 `apps/web/tailwind.config.ts`、`apps/web/postcss.config.mjs`

## Runtime

**Environment:**
- Node.js - 前端 Next.js 15 开发、构建、测试运行时；仓库未声明 `.nvmrc` 或 `engines`，命令定义在 `package.json`、`apps/web/package.json`
- Browser runtime - 前端在浏览器中运行，直接使用 `fetch`、`ReadableStream`、`localStorage`，实现位于 `apps/web/src/lib/api.ts`、`apps/web/src/store/auth-store.ts`
- Python 3.13+ - `apps/api/uv.lock` 明确锁定 `requires-python = ">=3.13"`；`docs/startup.md` 说明本地环境准备包含 Python 与 `uv`

**Package Manager:**
- pnpm 10.0.0 - Monorepo JavaScript 包管理器，定义在 `package.json`
- uv - Python 依赖安装与锁文件管理，使用痕迹在 `apps/api/uv.lock`、`docs/startup.md`
- Lockfile: `pnpm-lock.yaml` present, `apps/api/uv.lock` present

## Frameworks

**Core:**
- Next.js 15.0.0 - 前端应用框架，负责页面路由、开发服务器与生产构建，定义在 `apps/web/package.json`、`apps/web/next.config.ts`
- React 19.0.0 - 前端 UI 运行时，定义在 `apps/web/package.json`
- FastAPI 0.135.3 - 后端 HTTP API 框架，应用入口在 `apps/api/app/main.py`，锁定版本见 `apps/api/uv.lock`
- SQLAlchemy 2.x - ORM 与数据库会话层，入口在 `apps/api/app/db/models.py`、`apps/api/app/db/session.py`

**Testing:**
- Vitest 2.0.0 - 前端单元/组件测试，配置在 `apps/web/vitest.config.ts`
- Testing Library 16.x / jest-dom 6.x - 前端 DOM 断言与交互测试，定义在 `apps/web/package.json`
- pytest 8.4.x + pytest-asyncio 1.2.x + anyio 4.13.0 - 后端测试栈，锁定信息在 `apps/api/uv.lock`

**Build/Dev:**
- TypeScript 5.6.x - 前端类型检查与编译配置，定义在 `apps/web/package.json`、`apps/web/tsconfig.json`
- Tailwind CSS 3.4.13 + PostCSS 8.4.47 + Autoprefixer 10.4.20 - 前端样式构建链，定义在 `apps/web/package.json`、`apps/web/tailwind.config.ts`、`apps/web/postcss.config.mjs`
- Uvicorn 0.38.0 - FastAPI ASGI 开发服务器，启动命令在根 `package.json`，锁定版本见 `apps/api/uv.lock`
- Alembic 1.18.4 - 数据库迁移工具，配置在 `apps/api/alembic.ini`、`apps/api/alembic/env.py`

## Key Dependencies

**Critical:**
- `next` 15.0.0 - 前端应用框架核心，定义在 `apps/web/package.json`
- `react` / `react-dom` 19.0.0 - 前端组件渲染核心，定义在 `apps/web/package.json`
- `fastapi` 0.135.3 - 后端 API 路由与依赖注入核心，落在 `apps/api/app/main.py`、`apps/api/uv.lock`
- `sqlalchemy` 2.x - 所有持久化模型与仓储层基础，落在 `apps/api/app/db/models.py`、`apps/api/app/repositories/**/*`
- `httpx` 0.28.1 - 后端调用外部 OpenAI 兼容模型网关的 HTTP 客户端，落在 `apps/api/app/services/model_gateway.py`
- `sse-starlette` 3.0.3 - 后端向前端输出流式事件，落在 `apps/api/app/api/routes/messages.py`
- `python-jose[cryptography]` 3.5.0 - JWT 签发与校验，落在 `apps/api/app/core/security.py`

**Infrastructure:**
- `psycopg[binary]` 3.3.3 - PostgreSQL 驱动，数据库会话定义在 `apps/api/app/db/session.py`
- `passlib[bcrypt]` 1.7.4 与 `bcrypt` 5.0.0 - 密码哈希与校验，落在 `apps/api/app/core/security.py`
- `zustand` 5.0.0 - 前端认证状态持久化，落在 `apps/web/src/store/auth-store.ts`
- `@vitejs/plugin-react` 4.3.4 - Vitest 前端测试转换插件，配置在 `apps/web/vitest.config.ts`

## Configuration

**Environment:**
- 根目录 `.env` 存在，后端通过 `apps/api/app/core/config.py` 手动读取仓库根环境变量文件；关键键名来自 `DATABASE_URL`、`AUTH_SECRET_KEY`、`AUTH_ACCESS_TOKEN_EXPIRE_MINUTES`、`ADMIN_EMAILS`
- 前端存在 `apps/web/.env.local`，`apps/web/src/lib/api.ts` 读取 `NEXT_PUBLIC_API_BASE_URL`
- 仓库中存在 `docker-compose.yml`，提供本地 PostgreSQL 16 容器；使用说明在 `docs/startup.md`

**Build:**
- Monorepo 根脚本定义在 `package.json`
- Web 构建配置在 `apps/web/next.config.ts`、`apps/web/tsconfig.json`、`apps/web/tailwind.config.ts`、`apps/web/postcss.config.mjs`、`apps/web/vitest.config.ts`
- API 迁移与运行配置在 `apps/api/pyproject.toml`、`apps/api/alembic.ini`、`apps/api/alembic/env.py`

## Platform Requirements

**Development:**
- 需要 `pnpm` 10、Node.js、Python、`uv`、Docker Desktop；文档入口在 `docs/startup.md`
- 本地前端默认运行在 `http://localhost:3000`，后端默认运行在 `http://127.0.0.1:8000`，定义在 `apps/api/app/main.py`、`docs/startup.md`
- 本地数据库可使用 `docker-compose.yml` 中的 PostgreSQL 16，也可改用外部 PostgreSQL；切换方式说明在 `docs/startup.md`

**Production:**
- 未检测到 Vercel、Docker 镜像、Kubernetes 或 CI/CD 工作流配置；当前可确认的生产形态是独立部署 Next.js 前端与 FastAPI 后端，二者通过 `NEXT_PUBLIC_API_BASE_URL` 连接
- 后端对数据库迁移状态有运行时检查，健康检查位于 `apps/api/app/main.py`，要求部署前执行 `alembic upgrade head`

---

*Stack analysis: 2026-04-16*
