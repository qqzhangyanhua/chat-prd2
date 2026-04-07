# AI Co-founder V1

AI Co-founder 是一个通过持续对话帮助用户挖掘想法、收敛方向，并逐步沉淀为 PRD 的产品工作台。

当前仓库是一个 monorepo，主要包含：

- `apps/web`：Next.js 15 + React 19 前端
- `apps/api`：FastAPI 后端
- `docs/startup.md`：本地启动文档
- `docs/superpowers/specs`：设计文档
- `docs/superpowers/plans`：实现计划

## 快速启动

如果你只是想尽快把项目跑起来，先看：

- [启动文档](D:/AI/chat-prd/docs/startup.md)

如果你已经创建好 `.venv` 并装好依赖，可以直接用一键脚本：

```powershell
Set-Location D:\AI\chat-prd
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1
```

如果这次不想跑数据库迁移：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -SkipMigrate
```

## 环境变量

当前项目主要使用两份环境变量文件：

- [`.env`](D:/AI/chat-prd/.env)
- [`apps/web/.env.local`](D:/AI/chat-prd/apps/web/.env.local)

当前最关键的变量有：

```env
DATABASE_URL=postgresql+psycopg://aimovie:xtCGcStxwnJS3T6R@111.228.37.74:5432/aimovie
AUTH_SECRET_KEY=ai-cofounder-local-dev-secret-change-me
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

说明：

- 后端现在会从根目录 `.env` 读取 `DATABASE_URL`
- 前端会从 `apps/web/.env.local` 读取 `NEXT_PUBLIC_API_BASE_URL`

## 常用命令

### 前端开发

```powershell
pnpm dev:web
```

### 后端开发

```powershell
python -m uvicorn app.main:app --reload --app-dir apps/api
```

### 前端测试

```powershell
pnpm --filter web test
```

### 前端构建

```powershell
pnpm --filter web build
```

### 后端测试

```powershell
python -m pytest apps/api/tests -q
```

### 数据库迁移

```powershell
Set-Location .\apps\api
alembic upgrade head
Set-Location ..\..
```

如果你能登录、也能创建会话，但打开具体会话时看到 `Failed to fetch` 或 `当前会话加载失败`，先重新执行一次这条迁移命令。最近新增的会话决策表如果没升级到最新 revision，会在读取会话快照时直接报错。

## 当前能力

V1 当前已经包含这些核心能力：

- 用户注册 / 登录
- token 持久化
- 会话创建、切换、重命名、删除
- 工作台消息流式返回
- 停止生成 / 重新生成
- PRD 面板实时更新
- 全局 toast 反馈

## 建议阅读顺序

如果你是第一次接手这个项目，建议按这个顺序看：

1. [启动文档](D:/AI/chat-prd/docs/startup.md)
2. [设计文档](D:/AI/chat-prd/docs/superpowers/specs/2026-04-01-ai-cofounder-v1-design.md)
3. [实现计划](D:/AI/chat-prd/docs/superpowers/plans/2026-04-01-ai-cofounder-v1-implementation.md)
