[根目录](../../CLAUDE.md) > apps > **api**

# API 模块 -- FastAPI 后端

## 模块职责

提供 AI Co-founder 产品的全部后端能力：用户认证、会话管理、消息流式返回（SSE）、PRD 导出、LLM 模型配置管理（管理员 CRUD）、结构化 ApiError（含 `recovery_action`）。采用 Repository -> Service -> Route 三层架构。

## 入口与启动

- **入口文件**: `app/main.py` -- 创建 FastAPI 实例，挂载所有路由，注册 `ApiError` 全局异常处理
- **启动命令**: `python -m uvicorn app.main:app --reload --app-dir apps/api`
- **默认端口**: 8000
- **健康检查**: `GET /api/health`（返回 schema 状态，若 outdated 返回 503 + recovery_action）

如果你正在维护“生成 PRD”链路，先看：

- [`/Users/zhangyanhua/AI/chat-prd2/docs/contracts/README.md`](/Users/zhangyanhua/AI/chat-prd2/docs/contracts/README.md)
- [`/Users/zhangyanhua/AI/chat-prd2/docs/contracts/prd-runtime-contract.md`](/Users/zhangyanhua/AI/chat-prd2/docs/contracts/prd-runtime-contract.md)

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
| GET | `/api/sessions/{id}` | 获取会话完整快照（含 messages/reply_groups/turn_decisions） |
| PATCH | `/api/sessions/{id}` | 更新会话标题 |
| DELETE | `/api/sessions/{id}` | 级联删除会话及关联数据 |

### 消息 (`app/api/routes/messages.py`)

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/sessions/{id}/messages` | 发送消息，SSE 流式返回 |
| POST | `/api/sessions/{id}/messages/{msg_id}/regenerate` | 重新生成指定消息的 AI 回复 |

SSE 事件序列:
```
message.accepted -> reply_group.created -> assistant.version.started -> action.decided -> assistant.delta... -> assistant.done -> prd.updated (可选，携带 sections 和 meta)
```

### 导出 (`app/api/routes/exports.py`)

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/sessions/{id}/export` | 导出 PRD 为 Markdown |

### 模型配置（用户端） (`app/api/routes/model_configs.py`)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/model-configs/enabled` | 获取已启用模型列表（供前端选择模型） |

### 模型配置管理（管理员） (`app/api/routes/admin_model_configs.py`)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/admin/model-configs` | 列出所有模型配置 |
| POST | `/api/admin/model-configs` | 创建模型配置 |
| PATCH | `/api/admin/model-configs/{id}` | 更新模型配置 |
| DELETE | `/api/admin/model-configs/{id}` | 删除模型配置 (204) |

管理员认证：Bearer token + 邮箱在 `ADMIN_EMAILS` 环境变量中（`app/core/admin.py`）。

## 架构分层

```
app/
  main.py                     -- FastAPI 应用入口，路由挂载，ApiError 全局处理
  core/
    config.py                 -- 环境变量加载 + Settings dataclass（含 admin_emails）
    security.py               -- JWT + bcrypt 密码工具
    api_error.py              -- ApiError, build_api_error_payload, raise_api_error
    admin.py                  -- is_admin_email() 邮箱管理员校验
  api/
    deps.py                   -- 依赖注入 (get_db, get_current_user)
    routes/
      auth.py                 -- 认证路由
      sessions.py             -- 会话路由
      messages.py             -- 消息/重新生成路由
      exports.py              -- PRD 导出路由
      model_configs.py        -- 用户端模型配置路由
      admin_model_configs.py  -- 管理员模型配置路由
  schemas/
    auth.py                   -- 认证请求/响应 schema
    session.py                -- 会话 schema
    message.py                -- 消息/SSE 事件 schema（含 AgentTurnDecisionResponse、`prd.updated.meta`）
    prd.py                    -- PRD 快照 schema
    state.py                  -- StateSnapshot (完整 Pydantic 模型)
    model_config.py           -- 模型配置 schema（含 RecommendedScene Literal 类型）
  services/
    auth.py                   -- 认证业务逻辑
    sessions.py               -- 会话业务（含 SCHEMA_OUTDATED_DETAIL 常量）
    exports.py                -- PRD 导出业务
    messages.py               -- 消息发送/重新生成，Agent 调用，SSE 流组装
    prd_runtime.py            -- PRD 运行时 helper（预览 sections / meta，组装 `prd.updated` payload）
    model_gateway.py          -- LLM HTTP 客户端（httpx），流式/结构化提取
  repositories/
    auth.py                   -- 用户数据访问
    sessions.py               -- 会话数据访问
    messages.py               -- 消息数据访问
    prd.py                    -- PRD 快照数据访问
    state.py                  -- 状态版本数据访问
    model_configs.py          -- LLM 模型配置 CRUD
    assistant_reply_groups.py -- 回复组数据访问
    assistant_reply_versions.py -- 回复版本数据访问
    agent_turn_decisions.py   -- 决策记录数据访问
  db/
    models.py                 -- ORM 模型定义（9 张表）
    session.py                -- SQLAlchemy engine + SessionLocal
  agent/
    runtime.py                -- run_agent() 主入口，组合各子模块
    decision_engine.py        -- build_turn_decision()：策略/阶段/信心决策
    reply_composer.py         -- compose_reply()：TurnDecision -> 结构化回复文本
    suggestion_planner.py     -- build_suggestions()：生成推进方向建议
    understanding.py          -- understand_user_input()：理解层分析
    extractor.py              -- 规则提取 / first_missing_section / should_capture
    validation_flows.py       -- 验证流程常量（频率/转化阻力验证步骤）
    prompts.py                -- 固定回复模板常量
    types.py                  -- Agent 数据类型（NextAction, AgentResult, TurnDecision 等）
alembic/
  env.py                      -- Alembic 迁移环境
  versions/                   -- 迁移脚本（0001-0009）
```

## 关键依赖与配置

- **pyproject.toml**: FastAPI, SQLAlchemy 2, Alembic, Pydantic 2, python-jose, passlib, httpx, sse-starlette
- **环境变量**:
  - `DATABASE_URL` -- PostgreSQL 连接串
  - `AUTH_SECRET_KEY` -- JWT 签名密钥
  - `ADMIN_EMAILS` -- 管理员邮箱列表（逗号分隔），控制 `/api/admin/*` 访问
  - `AUTH_ACCESS_TOKEN_EXPIRE_MINUTES` -- token 有效期（默认 7 天）
- **配置加载**: `app/core/config.py` 自实现 .env 文件解析（不依赖 python-dotenv），通过 `os.environ.setdefault` 加载
- **alembic.ini**: 迁移配置，运行时由 `alembic/env.py` 覆盖 URL

## 数据模型

9 张表（定义在 `app/db/models.py`）:

| 表名 | 说明 | 关键字段 |
|------|------|----------|
| `users` | 用户账号 | id (PK), email (unique), password_hash |
| `project_sessions` | 会话 | id (PK), user_id (FK), title, initial_idea, created_at, updated_at |
| `project_state_versions` | 项目状态版本 | id (PK), session_id (FK), version, state_json (JSON) |
| `prd_snapshots` | PRD 快照 | id (PK), session_id (FK), version, sections (JSON) |
| `conversation_messages` | 对话消息 | id (PK), session_id (FK), role, content, message_type, meta (JSON), created_at |
| `assistant_reply_groups` | AI 回复组 | id (PK), session_id (FK), user_message_id (unique FK), latest_version_id, created_at, updated_at |
| `assistant_reply_versions` | AI 回复版本 | id (PK), reply_group_id (FK), version_no, content, action_snapshot (JSON), model_meta (JSON), state_version_id, prd_snapshot_version |
| `agent_turn_decisions` | Agent 决策记录 | id (PK), session_id (FK), user_message_id (unique FK), phase, next_move, understanding_summary, assumptions/risks/suggestions (JSON), confidence |
| `llm_model_configs` | LLM 模型配置 | id (PK), name, model, base_url, api_key, enabled, recommended_scene, recommended_usage |

ID 均为 UUID 字符串。

### Agent 状态结构 (state_json 关键字段)

```json
{
  "idea": "", "stage_hint": "", "iteration": 0,
  "goal": null, "target_user": null, "problem": null, "solution": null,
  "mvp_scope": [], "success_metrics": [],
  "current_phase": "idea_clarification",
  "conversation_strategy": "clarify",
  "current_model_scene": "general",
  "pending_confirmations": [], "working_hypotheses": [],
  "evidence": [], "pm_risk_flags": [],
  "prd_snapshot": { "sections": {} }
}
```

### LLM 模型配置字段说明

- `recommended_scene`: `"general" | "reasoning" | "fallback"` -- 推荐使用场景
- `recommended_usage`: 自由文本说明，供管理员标注用途
- `enabled`: 是否对用户端可见

## 错误体系 (`app/core/api_error.py`)

```python
class ApiError(HTTPException):
    code: str          # 机器可读错误码，如 "SCHEMA_OUTDATED"
    message: str       # 人类可读中文描述
    recovery_action:   # 可选：前端可执行的恢复动作
        type: str      # "run_migration" | "retry" | "login" 等
        label: str     # 界面按钮文字
        target: str    # 命令或路由
```

`ApiError` 注册为全局异常处理器，统一序列化为 JSON 返回。健康检查 503 和 schema 相关 503 均携带 `recovery_action`。

## Agent 模块概述

`run_agent()` 执行流程（优先级由高到低）：

1. 验证焦点切换命令（`_build_validation_switch_result`）
2. 模糊验证回复兜底（`_build_vague_validation_result`）
3. 验证追问流程（`_build_validation_followup_result`）
4. 确认继续命令（`_build_confirm_continue_result`）
5. 纠错/回滚命令（`_build_correction_result`）
6. 通用路径：`understand_user_input` + 规则提取 + `build_turn_decision` + `compose_reply`

`reply_mode`:
- `"local"` -- 使用本地规则生成回复（快捷命令路径）
- `"gateway"` -- 调用 LLM 模型网关生成回复

## 测试与质量

- **框架**: pytest + FastAPI TestClient
- **测试数据库**: SQLite in-memory（通过 `conftest.py` fixture 注入）
- **目录**: `tests/`
- **fixture 链**: `testing_session_local` -> `client` -> `auth_client` -> `seeded_session`

| 测试文件 | 覆盖范围 |
|----------|----------|
| `test_health.py` | 健康检查端点（ready / outdated / missing_tables） |
| `test_auth.py` | 注册、登录、token 校验 |
| `test_sessions.py` | 会话 CRUD |
| `test_messages_stream.py` | 消息发送 + SSE 流事件序列、`prd.updated` payload |
| `test_messages_service.py` | 消息服务单元测试、regenerate 持久化、PRD runtime 契约 |
| `test_models.py` | ORM 模型实例化 |
| `test_agent_runtime.py` | Agent run_agent() 完整路径 |
| `test_agent_decision_engine.py` | build_turn_decision() 策略逻辑 |
| `test_agent_reply_composer.py` | compose_reply() 文本生成 |
| `test_agent_understanding.py` | understand_user_input() 理解层 |
| `test_agent_suggestion_planner.py` | build_suggestions() 建议规划 |
| `test_agent_types_contract.py` | 类型契约/dataclass 字段 |
| `test_model_gateway.py` | LLM 网关错误处理 |
| `test_model_configs.py` | 模型配置 CRUD 端点 |
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
  alembic/versions/0005_add_llm_model_configs.py
  alembic/versions/0006_add_assistant_reply_versions.py
  alembic/versions/0007_add_agent_turn_decisions.py
  alembic/versions/0008_add_recommended_usage_to_llm_model_configs.py
  alembic/versions/0009_add_recommended_scene_to_llm_model_configs.py
  app/main.py
  app/core/config.py
  app/core/security.py
  app/core/api_error.py
  app/core/admin.py
  app/api/deps.py
  app/api/routes/auth.py
  app/api/routes/sessions.py
  app/api/routes/messages.py
  app/api/routes/exports.py
  app/api/routes/model_configs.py
  app/api/routes/admin_model_configs.py
  app/schemas/auth.py
  app/schemas/session.py
  app/schemas/message.py
  app/schemas/prd.py
  app/schemas/state.py
  app/schemas/model_config.py
  app/services/auth.py
  app/services/sessions.py
  app/services/exports.py
  app/services/messages.py
  app/services/prd_runtime.py
  app/services/model_gateway.py
  app/repositories/auth.py
  app/repositories/sessions.py
  app/repositories/messages.py
  app/repositories/prd.py
  app/repositories/state.py
  app/repositories/model_configs.py
  app/repositories/assistant_reply_groups.py
  app/repositories/assistant_reply_versions.py
  app/repositories/agent_turn_decisions.py
  app/db/models.py
  app/db/session.py
  app/agent/runtime.py
  app/agent/decision_engine.py
  app/agent/reply_composer.py
  app/agent/suggestion_planner.py
  app/agent/understanding.py
  app/agent/extractor.py
  app/agent/validation_flows.py
  app/agent/prompts.py
  app/agent/types.py
  tests/conftest.py
  tests/test_health.py
  tests/test_auth.py
  tests/test_sessions.py
  tests/test_messages_stream.py
  tests/test_messages_service.py
  tests/test_models.py
  tests/test_agent_runtime.py
  tests/test_agent_decision_engine.py
  tests/test_agent_reply_composer.py
  tests/test_agent_understanding.py
  tests/test_agent_suggestion_planner.py
  tests/test_agent_types_contract.py
  tests/test_model_gateway.py
  tests/test_model_configs.py
  tests/test_config.py
```

## 变更记录 (Changelog)

| 日期 | 操作 | 说明 |
|------|------|------|
| 2026-04-09 | UPDATED | 同步 PRD 运行时结构：补充 `docs/contracts` 入口、`prd_runtime.py`、`prd.updated.meta` 与 regenerate 持久化说明 |
| 2026-04-08 | UPDATED | 新增 ApiError/recovery_action、模型配置管理路由、recommended_scene/usage 字段、迁移 0008/0009、Agent 子模块详解（validation_flows, suggestion_planner 等）、重新生成接口、完整测试文件列表 |
| 2026-04-03 | CREATED | init-architect 首次生成模块文档 |
