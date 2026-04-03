[根目录](../../CLAUDE.md) > apps > **api**

# API 模块 -- FastAPI 后端

## 模块职责

提供 AI Co-founder 产品的全部后端能力：用户认证、会话管理、消息流式返回（SSE）、PRD 导出。采用 Repository -> Service -> Route 三层架构。

## 入口与启动

- **入口文件**: `app/main.py` -- 创建 FastAPI 实例，挂载 4 个路由模块
- **启动命令**: `python -m uvicorn app.main:app --reload --app-dir apps/api`
- **默认端口**: 8000
- **健康检查**: `GET /api/health`

## 对外接口

### 认证 (`app/api/routes/auth.py`)

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/register` | 注册，返回 user + access_token |
| POST | `/api/auth/login` | 登录，返回 user + access_token |
| GET | `/api/auth/me` | Bearer token 获取当前用户 |

### 会话 (`app/api/routes/sessions.py`)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/sessions` | 列出当前用户所有会话 |
| POST | `/api/sessions` | 创建会话（含初始 state + PRD 快照） |
| GET | `/api/sessions/{id}` | 获取会话完整快照 |
| PATCH | `/api/sessions/{id}` | 更新会话标题 |
| DELETE | `/api/sessions/{id}` | 级联删除会话及关联数据 |

### 消息 (`app/api/routes/messages.py`)

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/sessions/{id}/messages` | 发送消息，SSE 流式返回 |

SSE 事件序列: `message.accepted` -> `action.decided` -> `assistant.delta` -> `assistant.done`

### 导出 (`app/api/routes/exports.py`)

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/sessions/{id}/export` | 导出 PRD 为 Markdown |

## 架构分层

```
app/
  main.py              -- FastAPI 应用入口
  core/
    config.py          -- 环境变量加载 + Settings dataclass
    security.py        -- JWT + bcrypt 密码工具
  api/
    deps.py            -- 依赖注入 (get_db, get_current_user)
    routes/             -- 路由层 (4 个 router)
  schemas/              -- Pydantic 请求/响应模型
  services/             -- 业务逻辑层
  repositories/         -- 数据访问层 (SQLAlchemy 查询)
  db/
    models.py          -- ORM 模型定义 (5 张表)
    session.py         -- SQLAlchemy engine + SessionLocal
  agent/
    runtime.py         -- Agent 决策引擎 (当前为规则引擎)
    types.py           -- Agent 数据类型 (NextAction, AgentResult)
    prompts.py         -- 固定回复模板
alembic/
  env.py               -- Alembic 迁移环境
  versions/            -- 迁移脚本 (4 个版本)
```

## 关键依赖与配置

- **pyproject.toml**: FastAPI, SQLAlchemy 2, Alembic, Pydantic 2, python-jose, passlib, httpx, sse-starlette
- **环境变量**: `DATABASE_URL` (PostgreSQL 连接串), `AUTH_SECRET_KEY` (JWT 签名密钥)
- **配置加载**: `app/core/config.py` 自实现 .env 文件解析（不依赖 python-dotenv），通过 `os.environ.setdefault` 加载
- **alembic.ini**: 迁移配置，运行时由 `alembic/env.py` 覆盖 URL

## 数据模型

5 张表 (定义在 `app/db/models.py`):

| 表名 | 说明 | 关键字段 |
|------|------|----------|
| `users` | 用户 | id (PK), email (unique), password_hash |
| `project_sessions` | 会话 | id (PK), user_id (FK), title, initial_idea, created_at, updated_at |
| `project_state_versions` | 项目状态版本 | id (PK), session_id (FK), version, state_json (JSON) |
| `prd_snapshots` | PRD 快照 | id (PK), session_id (FK), version, sections (JSON) |
| `conversation_messages` | 对话消息 | id (PK), session_id (FK), role, content, message_type, meta (JSON) |

ID 均为 UUID 字符串。

### Agent 状态结构 (state_json)

```json
{
  "idea": "...",
  "stage_hint": "问题探索",
  "iteration": 0,
  "goal": null, "target_user": null, "problem": null, "solution": null,
  "mvp_scope": [], "success_metrics": [],
  "known_facts": {}, "assumptions": [], "risks": [],
  "unexplored_areas": [], "options": [], "decisions": [], "open_questions": [],
  "prd_snapshot": { "sections": {} }
}
```

## 测试与质量

- **框架**: pytest + FastAPI TestClient
- **测试数据库**: SQLite in-memory (通过 `conftest.py` fixture 注入)
- **目录**: `tests/`
- **fixture 链**: `testing_session_local` -> `client` -> `auth_client` -> `seeded_session`

| 测试文件 | 覆盖范围 |
|----------|----------|
| `test_health.py` | 健康检查端点 |
| `test_auth.py` | 注册、登录、token 校验 |
| `test_sessions.py` | 会话 CRUD |
| `test_messages_stream.py` | 消息发送 + SSE 流 |
| `test_models.py` | ORM 模型实例化 |
| `test_agent_runtime.py` | Agent 决策逻辑 |
| `test_config.py` | 环境变量加载 + Settings |

运行: `pytest apps/api/tests -q` 或 `pnpm test:api`

## 相关文件清单

```
apps/api/
  pyproject.toml
  alembic.ini
  alembic/env.py
  alembic/versions/0001_initial.py
  alembic/versions/0002_add_project_state_and_prd_snapshot.py
  alembic/versions/0003_add_conversation_messages.py
  alembic/versions/0003_add_project_session_created_at.py
  alembic/versions/0004_add_project_session_updated_at.py
  app/main.py
  app/core/config.py
  app/core/security.py
  app/api/deps.py
  app/api/routes/auth.py
  app/api/routes/sessions.py
  app/api/routes/messages.py
  app/api/routes/exports.py
  app/schemas/auth.py
  app/schemas/session.py
  app/schemas/message.py
  app/schemas/prd.py
  app/schemas/state.py
  app/services/auth.py
  app/services/sessions.py
  app/services/exports.py
  app/repositories/auth.py
  app/repositories/sessions.py
  app/repositories/messages.py
  app/repositories/messages_cleanup.py
  app/repositories/prd.py
  app/repositories/state.py
  app/db/models.py
  app/db/session.py
  app/agent/runtime.py
  app/agent/types.py
  app/agent/prompts.py
  tests/conftest.py
  tests/test_health.py
  tests/test_auth.py
  tests/test_sessions.py
  tests/test_messages_stream.py
  tests/test_models.py
  tests/test_agent_runtime.py
  tests/test_config.py
```

## 变更记录 (Changelog)

| 日期 | 操作 | 说明 |
|------|------|------|
| 2026-04-03 | CREATED | init-architect 首次生成模块文档 |
