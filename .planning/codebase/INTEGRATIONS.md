# External Integrations

**Analysis Date:** 2026-04-16

## APIs & External Services

**Frontend to Backend API:**
- FastAPI backend - 前端所有认证、会话、导出、模型配置与消息流式请求都经由后端 API
  - Integration method: 浏览器 `fetch` + `ReadableStream`
  - Base URL: `NEXT_PUBLIC_API_BASE_URL` in `apps/web/src/lib/api.ts`
  - Endpoints used: `/api/auth/*`、`/api/health`、`/api/sessions/*`、`/api/model-configs/enabled`、`/api/admin/model-configs`，调用实现位于 `apps/web/src/lib/api.ts`

**LLM Gateway Providers:**
- OpenAI 兼容模型服务 - 后端不绑定固定厂商，而是从数据库读取 `base_url`、`api_key`、`model` 后，按 OpenAI Chat Completions 协议发起请求
  - SDK/Client: `httpx` in `apps/api/app/services/model_gateway.py`
  - Auth: 上游 Bearer Token，密钥字段存于数据库表 `llm_model_configs.api_key`，模型配置接口在 `apps/api/app/api/routes/admin_model_configs.py`
  - Endpoints used: `base_url` 归一化为 `/chat/completions`，逻辑在 `apps/api/app/services/model_gateway.py`
  - Supported shape: 流式回复、普通 JSON 回复、结构化 JSON 提取，均在 `apps/api/app/services/model_gateway.py`

**Admin Model Configuration API:**
- 管理员模型配置接口 - 用于录入和维护上游模型网关地址及密钥
  - Integration method: FastAPI REST endpoints in `apps/api/app/api/routes/admin_model_configs.py`
  - Auth: 用户 Bearer Token + `ADMIN_EMAILS` 白名单，校验逻辑在 `apps/api/app/core/admin.py`、`apps/api/app/api/routes/admin_model_configs.py`
  - Data validated by: `apps/api/app/schemas/model_config.py`

## Data Storage

**Databases:**
- PostgreSQL - 主业务数据库，保存用户、会话、消息、PRD 快照、回复版本和模型配置
  - Connection: `DATABASE_URL` loaded by `apps/api/app/core/config.py`
  - Client: SQLAlchemy engine/session in `apps/api/app/db/session.py`
  - Models: `apps/api/app/db/models.py`
  - Migrations: Alembic in `apps/api/alembic.ini` and `apps/api/alembic/**/*`
- LLM model config persistence - 上游模型 `base_url`、`api_key`、`model` 直接存放在 `llm_model_configs` 表
  - Repository: `apps/api/app/repositories/model_configs.py`
  - Admin CRUD surface: `apps/api/app/api/routes/admin_model_configs.py`

**File Storage:**
- Local filesystem only - 仓库内未检测到 S3、OSS、Cloudinary、Supabase Storage 等对象存储客户端

**Caching:**
- None - 未检测到 Redis、Memcached 或应用级缓存层；前端仅使用 Zustand 本地持久化认证状态，代码在 `apps/web/src/store/auth-store.ts`

## Authentication & Identity

**Auth Provider:**
- Custom JWT auth - 后端使用邮箱/密码注册登录，自行签发 Bearer Token
  - Implementation: `apps/api/app/api/routes/auth.py` + `apps/api/app/core/security.py`
  - Password hashing: `bcrypt` via `hash_password` / `verify_password` in `apps/api/app/core/security.py`
  - Token storage: 前端保存在 `localStorage`，Zustand 持久化键为 `ai-cofounder-auth`，实现位于 `apps/web/src/store/auth-store.ts`
  - Session management: Bearer token 通过 `Authorization` 头发送，前端实现位于 `apps/web/src/lib/api.ts`，后端解析位于 `apps/api/app/api/deps.py`

**Authorization Extensions:**
- Admin whitelist - 管理员权限来源于环境变量 `ADMIN_EMAILS`
  - Enforcement: `apps/api/app/api/routes/admin_model_configs.py`
  - User payload: `/api/auth/*` 返回 `is_admin`，构造逻辑在 `apps/api/app/api/routes/auth.py`

## Monitoring & Observability

**Error Tracking:**
- None detected - 未检测到 Sentry、Datadog、Rollbar 等错误追踪集成

**Logs:**
- Application logging only - 后端在 `apps/api/app/services/model_gateway.py` 通过 Python `logging` 记录上游模型调用错误与响应格式问题
- Runtime health endpoint - `/api/health` 会检查迁移后必需表是否存在，定义在 `apps/api/app/main.py`

## CI/CD & Deployment

**Hosting:**
- Not detected - 仓库内未发现平台专用部署清单；已确认的运行方式是 `pnpm dev:web` 启动前端、`python -m uvicorn app.main:app --reload --app-dir apps/api` 启动后端，命令定义在根 `package.json`

**CI Pipeline:**
- None detected - `.github/workflows/` 未检测到工作流文件

## Environment Configuration

**Required env vars:**
- `DATABASE_URL` - 后端 PostgreSQL 连接串，读取点在 `apps/api/app/core/config.py`
- `AUTH_SECRET_KEY` - JWT 签名密钥，读取点在 `apps/api/app/core/config.py`、`apps/api/app/core/security.py`
- `AUTH_ACCESS_TOKEN_EXPIRE_MINUTES` - Token 生命周期，可选，读取点在 `apps/api/app/core/config.py`
- `ADMIN_EMAILS` - 管理员邮箱白名单，读取点在 `apps/api/app/core/config.py`
- `NEXT_PUBLIC_API_BASE_URL` - 前端 API 基地址，读取点在 `apps/web/src/lib/api.ts`

**Secrets location:**
- Backend env file: 根目录 `.env` 存在，由 `apps/api/app/core/config.py` 读取
- Frontend env file: `apps/web/.env.local` 存在，由 Next.js 前端读取
- Model provider secrets: 外部模型 `api_key` 持久化在数据库表 `llm_model_configs`，模型定义在 `apps/api/app/db/models.py`

## Webhooks & Callbacks

**Incoming:**
- None detected - 未检测到 Stripe webhook、第三方回调接收器或公开 webhook 路由

**Outgoing:**
- LLM HTTP requests - 在发送消息和结构化提取时由后端主动调用上游 OpenAI 兼容接口
  - Trigger: 用户发送消息或重生成消息后，业务流进入 `apps/api/app/services/messages.py` 并调用 `apps/api/app/services/model_gateway.py`
  - Retry logic: 未检测到显式重试；当前仅有异常映射与日志记录，逻辑位于 `apps/api/app/services/model_gateway.py`

---

*Integration audit: 2026-04-16*
