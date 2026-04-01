# AI Co-founder V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个可登录、可持续对话、可实时沉淀 PRD、可导出结果的 AI Co-founder V1 MVP。

**Architecture:** 采用单仓多应用结构：`apps/web` 提供 Next.js 工作台与认证页面，`apps/api` 提供 FastAPI、智能体运行时、SSE 消息流和 Postgres 持久化。结构化状态与 PRD 快照由后端统一维护，前端通过流式事件同步更新对话区和右侧沉淀面板。

**Tech Stack:** Next.js 15、React、TypeScript、Tailwind CSS、shadcn/ui、FastAPI、SQLAlchemy、Alembic、Postgres、pytest、Vitest、SSE

---

## 文件结构

### 根目录

- Create: `package.json`
- Create: `pnpm-workspace.yaml`
- Create: `.gitignore`
- Create: `README.md`
- Create: `docker-compose.yml`

### 前端 `apps/web`

- Create: `apps/web/package.json`
- Create: `apps/web/tsconfig.json`
- Create: `apps/web/next.config.ts`
- Create: `apps/web/postcss.config.js`
- Create: `apps/web/tailwind.config.ts`
- Create: `apps/web/src/app/layout.tsx`
- Create: `apps/web/src/app/page.tsx`
- Create: `apps/web/src/app/login/page.tsx`
- Create: `apps/web/src/app/register/page.tsx`
- Create: `apps/web/src/app/workspace/page.tsx`
- Create: `apps/web/src/components/auth/auth-form.tsx`
- Create: `apps/web/src/components/workspace/session-sidebar.tsx`
- Create: `apps/web/src/components/workspace/conversation-panel.tsx`
- Create: `apps/web/src/components/workspace/assistant-turn-card.tsx`
- Create: `apps/web/src/components/workspace/action-options.tsx`
- Create: `apps/web/src/components/workspace/composer.tsx`
- Create: `apps/web/src/components/workspace/prd-panel.tsx`
- Create: `apps/web/src/components/workspace/prd-section-card.tsx`
- Create: `apps/web/src/lib/api.ts`
- Create: `apps/web/src/lib/types.ts`
- Create: `apps/web/src/lib/sse.ts`
- Create: `apps/web/src/store/workspace-store.ts`
- Create: `apps/web/src/test/auth-form.test.tsx`
- Create: `apps/web/src/test/workspace-page.test.tsx`

### 后端 `apps/api`

- Create: `apps/api/pyproject.toml`
- Create: `apps/api/alembic.ini`
- Create: `apps/api/alembic/env.py`
- Create: `apps/api/alembic/versions/0001_initial.py`
- Create: `apps/api/app/main.py`
- Create: `apps/api/app/core/config.py`
- Create: `apps/api/app/core/security.py`
- Create: `apps/api/app/db/session.py`
- Create: `apps/api/app/db/models.py`
- Create: `apps/api/app/schemas/auth.py`
- Create: `apps/api/app/schemas/session.py`
- Create: `apps/api/app/schemas/message.py`
- Create: `apps/api/app/schemas/state.py`
- Create: `apps/api/app/schemas/prd.py`
- Create: `apps/api/app/repositories/auth.py`
- Create: `apps/api/app/repositories/sessions.py`
- Create: `apps/api/app/repositories/messages.py`
- Create: `apps/api/app/repositories/state.py`
- Create: `apps/api/app/repositories/prd.py`
- Create: `apps/api/app/services/auth.py`
- Create: `apps/api/app/services/sessions.py`
- Create: `apps/api/app/services/exports.py`
- Create: `apps/api/app/agent/runtime.py`
- Create: `apps/api/app/agent/prompts.py`
- Create: `apps/api/app/agent/types.py`
- Create: `apps/api/app/api/deps.py`
- Create: `apps/api/app/api/routes/auth.py`
- Create: `apps/api/app/api/routes/sessions.py`
- Create: `apps/api/app/api/routes/messages.py`
- Create: `apps/api/app/api/routes/exports.py`
- Create: `apps/api/tests/conftest.py`
- Create: `apps/api/tests/test_health.py`
- Create: `apps/api/tests/test_auth.py`
- Create: `apps/api/tests/test_sessions.py`
- Create: `apps/api/tests/test_messages_stream.py`
- Create: `apps/api/tests/test_agent_runtime.py`

## 任务说明

说明：

- 该 spec 同时包含前端、后端、认证、智能体和导出，但它们不是独立子系统，而是同一个 MVP 主闭环的组成部分，因此保留为一份实现计划。
- 所有任务按 TDD 方式推进，优先建立最小可验证链路，再逐步补齐持久化、认证和体验。

### Task 1: 初始化仓库结构与开发工具

**Files:**
- Create: `package.json`
- Create: `pnpm-workspace.yaml`
- Create: `.gitignore`
- Create: `README.md`
- Create: `docker-compose.yml`
- Create: `apps/web/package.json`
- Create: `apps/api/pyproject.toml`

- [ ] **Step 1: 写根目录工具配置测试基准**

```json
{
  "name": "ai-cofounder",
  "private": true,
  "packageManager": "pnpm@10.0.0",
  "scripts": {
    "dev:web": "pnpm --filter web dev",
    "dev:api": "python -m uvicorn app.main:app --reload --app-dir apps/api",
    "test:web": "pnpm --filter web test",
    "test:api": "pytest apps/api/tests -q"
  }
}
```

```yaml
packages:
  - apps/*
```

- [ ] **Step 2: 写根目录文件**

```gitignore
node_modules
.next
.venv
__pycache__
.pytest_cache
.mypy_cache
.env
.env.*
dist
coverage
.DS_Store
.superpowers
```

```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: ai_cofounder
    ports:
      - "5432:5432"
```

- [ ] **Step 3: 写前后端包定义**

```json
{
  "name": "web",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "test": "vitest run"
  },
  "dependencies": {
    "next": "15.0.0",
    "react": "19.0.0",
    "react-dom": "19.0.0",
    "zustand": "^5.0.0"
  },
  "devDependencies": {
    "@testing-library/react": "^16.0.0",
    "@types/node": "^22.0.0",
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0",
    "typescript": "^5.6.0",
    "vitest": "^2.0.0"
  }
}
```

```toml
[project]
name = "ai-cofounder-api"
version = "0.1.0"
dependencies = [
  "fastapi>=0.115.0",
  "uvicorn>=0.30.0",
  "sqlalchemy>=2.0.0",
  "psycopg[binary]>=3.2.0",
  "alembic>=1.13.0",
  "pydantic[email]>=2.8.0",
  "python-jose[cryptography]>=3.3.0",
  "passlib[bcrypt]>=1.7.4",
  "httpx>=0.27.0",
  "sse-starlette>=2.1.0"
]

[project.optional-dependencies]
dev = [
  "pytest>=8.3.0",
  "pytest-asyncio>=0.24.0",
  "anyio>=4.4.0"
]
```

- [ ] **Step 4: 运行基础检查**

Run: `git status --short`
Expected: 显示上述新建文件为未跟踪状态

- [ ] **Step 5: 提交初始化结构**

```bash
git add package.json pnpm-workspace.yaml .gitignore README.md docker-compose.yml apps/web/package.json apps/api/pyproject.toml
git commit -m "chore: bootstrap monorepo structure"
```

### Task 2: 建立 FastAPI 应用壳与健康检查

**Files:**
- Create: `apps/api/app/main.py`
- Create: `apps/api/app/core/config.py`
- Create: `apps/api/tests/test_health.py`

- [ ] **Step 1: 写失败测试**

```python
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_healthcheck_returns_ok():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest apps/api/tests/test_health.py -q`
Expected: FAIL，提示 `ModuleNotFoundError` 或 `/api/health` 不存在

- [ ] **Step 3: 实现最小 FastAPI 应用**

```python
from fastapi import FastAPI

app = FastAPI(title="AI Co-founder API")

@app.get("/api/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest apps/api/tests/test_health.py -q`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add apps/api/app/main.py apps/api/tests/test_health.py apps/api/app/core/config.py
git commit -m "feat: add api application shell"
```

### Task 3: 建立数据库层与初始表结构

**Files:**
- Create: `apps/api/app/db/session.py`
- Create: `apps/api/app/db/models.py`
- Create: `apps/api/alembic.ini`
- Create: `apps/api/alembic/env.py`
- Create: `apps/api/alembic/versions/0001_initial.py`
- Create: `apps/api/tests/conftest.py`

- [ ] **Step 1: 写模型存在性测试**

```python
from app.db.models import User, ProjectSession

def test_models_have_expected_tablenames():
    assert User.__tablename__ == "users"
    assert ProjectSession.__tablename__ == "project_sessions"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest apps/api/tests/test_health.py apps/api/tests/test_models.py -q`
Expected: FAIL，提示 `app.db.models` 不存在

- [ ] **Step 3: 写数据库与模型最小实现**

```python
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Text, ForeignKey

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String)

class ProjectSession(Base):
    __tablename__ = "project_sessions"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String)
    initial_idea: Mapped[str] = mapped_column(Text)
```

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/ai_cofounder"
engine = create_engine(DATABASE_URL, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
```

- [ ] **Step 4: 写 Alembic 初始迁移**

```python
def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("email", sa.String(), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(), nullable=False),
    )
    op.create_table(
        "project_sessions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("initial_idea", sa.Text(), nullable=False),
    )
```

- [ ] **Step 5: 运行测试并提交**

Run: `pytest apps/api/tests -q`
Expected: PASS

```bash
git add apps/api/app/db/session.py apps/api/app/db/models.py apps/api/alembic.ini apps/api/alembic/env.py apps/api/alembic/versions/0001_initial.py apps/api/tests/conftest.py
git commit -m "feat: add database models and initial migration"
```

### Task 4: 实现注册登录与当前用户查询

**Files:**
- Create: `apps/api/app/core/security.py`
- Create: `apps/api/app/schemas/auth.py`
- Create: `apps/api/app/repositories/auth.py`
- Create: `apps/api/app/services/auth.py`
- Create: `apps/api/app/api/deps.py`
- Create: `apps/api/app/api/routes/auth.py`
- Create: `apps/api/tests/test_auth.py`
- Modify: `apps/api/app/main.py`

- [ ] **Step 1: 写认证接口失败测试**

```python
def test_register_returns_token(client):
    response = client.post("/api/auth/register", json={
        "email": "user@example.com",
        "password": "secret123"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["user"]["email"] == "user@example.com"
    assert data["access_token"]
```

```python
def test_me_requires_auth(client):
    response = client.get("/api/auth/me")
    assert response.status_code == 401
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest apps/api/tests/test_auth.py -q`
Expected: FAIL，提示路由不存在

- [ ] **Step 3: 实现安全和 schema**

```python
from passlib.context import CryptContext
from jose import jwt

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)
```

```python
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str

class AuthResponse(BaseModel):
    user: UserResponse
    access_token: str
```

- [ ] **Step 4: 实现 auth 路由并挂载**

```python
router = APIRouter(prefix="/api/auth", tags=["auth"])

@router.post("/register", response_model=AuthResponse)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> AuthResponse:
    user = auth_service.register(db, payload)
    token = auth_service.issue_token(user)
    return AuthResponse(user=user, access_token=token)

@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(current_user)
```

```python
app.include_router(auth_router)
```

- [ ] **Step 5: 运行测试并提交**

Run: `pytest apps/api/tests/test_auth.py -q`
Expected: PASS

```bash
git add apps/api/app/core/security.py apps/api/app/schemas/auth.py apps/api/app/repositories/auth.py apps/api/app/services/auth.py apps/api/app/api/deps.py apps/api/app/api/routes/auth.py apps/api/app/main.py apps/api/tests/test_auth.py
git commit -m "feat: add email password authentication"
```

### Task 5: 实现会话、状态版本与 PRD 快照模型

**Files:**
- Create: `apps/api/app/schemas/session.py`
- Create: `apps/api/app/schemas/state.py`
- Create: `apps/api/app/schemas/prd.py`
- Create: `apps/api/app/repositories/sessions.py`
- Create: `apps/api/app/repositories/state.py`
- Create: `apps/api/app/repositories/prd.py`
- Create: `apps/api/app/services/sessions.py`
- Create: `apps/api/app/api/routes/sessions.py`
- Create: `apps/api/tests/test_sessions.py`
- Modify: `apps/api/app/db/models.py`
- Modify: `apps/api/app/main.py`

- [ ] **Step 1: 写会话创建测试**

```python
def test_create_session_returns_initial_state(auth_client):
    response = auth_client.post("/api/sessions", json={
        "title": "AI Co-founder",
        "initial_idea": "我想做一个帮助独立开发者验证产品想法的工具"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["session"]["title"] == "AI Co-founder"
    assert data["state"]["stage_hint"] == "理解想法"
    assert data["prd_snapshot"]["sections"] == {}
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest apps/api/tests/test_sessions.py -q`
Expected: FAIL，提示 `/api/sessions` 不存在

- [ ] **Step 3: 扩展数据库模型**

```python
class ProjectStateVersion(Base):
    __tablename__ = "project_state_versions"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("project_sessions.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    state_json: Mapped[dict] = mapped_column(JSON)

class PrdSnapshot(Base):
    __tablename__ = "prd_snapshots"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("project_sessions.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    sections: Mapped[dict] = mapped_column(JSON)
```

- [ ] **Step 4: 实现 session 路由和服务**

```python
@router.post("", response_model=SessionCreateResponse)
def create_session(
    payload: SessionCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SessionCreateResponse:
    return session_service.create_session(db, current_user.id, payload)
```

```python
def build_initial_state(initial_idea: str) -> dict:
    return {
        "idea": initial_idea,
        "stage_hint": "理解想法",
        "iteration": 0,
        "goal": None,
        "target_user": None,
        "problem": None,
        "solution": None,
        "mvp_scope": [],
        "success_metrics": [],
        "known_facts": {},
        "assumptions": [],
        "risks": [],
        "unexplored_areas": [],
        "options": [],
        "decisions": [],
        "open_questions": [],
        "prd_snapshot": {},
        "last_action": None,
    }
```

- [ ] **Step 5: 运行测试并提交**

Run: `pytest apps/api/tests/test_sessions.py -q`
Expected: PASS

```bash
git add apps/api/app/schemas/session.py apps/api/app/schemas/state.py apps/api/app/schemas/prd.py apps/api/app/repositories/sessions.py apps/api/app/repositories/state.py apps/api/app/repositories/prd.py apps/api/app/services/sessions.py apps/api/app/api/routes/sessions.py apps/api/app/db/models.py apps/api/app/main.py apps/api/tests/test_sessions.py
git commit -m "feat: add session state and prd snapshot persistence"
```

### Task 6: 实现智能体运行时与结构化动作决策

**Files:**
- Create: `apps/api/app/agent/types.py`
- Create: `apps/api/app/agent/prompts.py`
- Create: `apps/api/app/agent/runtime.py`
- Create: `apps/api/tests/test_agent_runtime.py`

- [ ] **Step 1: 写动作决策失败测试**

```python
from app.agent.runtime import decide_next_action

def test_decide_next_action_prefers_probe_when_target_user_missing():
    state = {
        "target_user": None,
        "problem": None,
        "unexplored_areas": []
    }
    action = decide_next_action(state, "我想做一个帮助开发者的工具")
    assert action.action == "probe_deeper"
    assert action.target == "target_user"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest apps/api/tests/test_agent_runtime.py -q`
Expected: FAIL，提示 `decide_next_action` 不存在

- [ ] **Step 3: 定义智能体类型**

```python
class NextAction(BaseModel):
    action: Literal[
        "probe_deeper",
        "challenge_assumption",
        "offer_options",
        "summarize_understanding",
        "confirm_decision",
        "generate_prd_package",
    ]
    target: str | None = None
    reason: str
```

```python
class AgentResult(BaseModel):
    reply: str
    action: NextAction
    state_patch: dict
    prd_patch: dict
    decision_log: list[dict]
```

- [ ] **Step 4: 实现最小运行时**

```python
def decide_next_action(state: dict, user_input: str) -> NextAction:
    if not state.get("target_user"):
        return NextAction(
            action="probe_deeper",
            target="target_user",
            reason="当前目标用户仍然缺失，需要优先收窄人群和场景。",
        )
    return NextAction(
        action="summarize_understanding",
        target=None,
        reason="已有基础信息，先反射当前理解并继续推进。",
    )
```

```python
def run_agent(state: dict, user_input: str) -> AgentResult:
    action = decide_next_action(state, user_input)
    reply = "我先卡在目标用户这里，因为这一步如果不收窄，后面的 MVP 会持续失控。你更接近哪一类用户？"
    return AgentResult(
        reply=reply,
        action=action,
        state_patch={},
        prd_patch={},
        decision_log=[],
    )
```

- [ ] **Step 5: 运行测试并提交**

Run: `pytest apps/api/tests/test_agent_runtime.py -q`
Expected: PASS

```bash
git add apps/api/app/agent/types.py apps/api/app/agent/prompts.py apps/api/app/agent/runtime.py apps/api/tests/test_agent_runtime.py
git commit -m "feat: add agent runtime action selection"
```

### Task 7: 实现消息持久化与 SSE 流式接口

**Files:**
- Create: `apps/api/app/schemas/message.py`
- Create: `apps/api/app/repositories/messages.py`
- Create: `apps/api/app/api/routes/messages.py`
- Create: `apps/api/tests/test_messages_stream.py`
- Modify: `apps/api/app/db/models.py`
- Modify: `apps/api/app/main.py`

- [ ] **Step 1: 写消息流失败测试**

```python
def test_message_stream_emits_action_and_done_events(auth_client, seeded_session):
    response = auth_client.post(
        f"/api/sessions/{seeded_session}/messages",
        json={"content": "我想服务第一次做产品的独立开发者"},
    )
    assert response.status_code == 200
    body = response.text
    assert "action.decided" in body
    assert "assistant.done" in body
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest apps/api/tests/test_messages_stream.py -q`
Expected: FAIL，提示消息接口不存在

- [ ] **Step 3: 扩展消息模型**

```python
class ConversationMessage(Base):
    __tablename__ = "conversation_messages"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("project_sessions.id"), index=True)
    role: Mapped[str] = mapped_column(String)
    content: Mapped[str] = mapped_column(Text)
    message_type: Mapped[str] = mapped_column(String, default="chat")
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
```

- [ ] **Step 4: 实现 SSE 路由**

```python
@router.post("")
async def create_message(...):
    async def event_generator():
        yield {"event": "action.decided", "data": action.model_dump_json()}
        yield {"event": "assistant.delta", "data": json.dumps({"delta": agent_result.reply})}
        yield {"event": "assistant.done", "data": json.dumps({"message_id": assistant_message.id})}
    return EventSourceResponse(event_generator())
```

- [ ] **Step 5: 运行测试并提交**

Run: `pytest apps/api/tests/test_messages_stream.py -q`
Expected: PASS

```bash
git add apps/api/app/schemas/message.py apps/api/app/repositories/messages.py apps/api/app/api/routes/messages.py apps/api/app/db/models.py apps/api/app/main.py apps/api/tests/test_messages_stream.py
git commit -m "feat: add message streaming endpoint"
```

### Task 8: 搭建前端认证页面与 API 客户端

**Files:**
- Create: `apps/web/tsconfig.json`
- Create: `apps/web/next.config.ts`
- Create: `apps/web/src/app/layout.tsx`
- Create: `apps/web/src/app/login/page.tsx`
- Create: `apps/web/src/app/register/page.tsx`
- Create: `apps/web/src/components/auth/auth-form.tsx`
- Create: `apps/web/src/lib/api.ts`
- Create: `apps/web/src/lib/types.ts`
- Create: `apps/web/src/test/auth-form.test.tsx`

- [ ] **Step 1: 写认证表单失败测试**

```tsx
import { render, screen } from "@testing-library/react";
import { AuthForm } from "../components/auth/auth-form";

it("renders email and password inputs", () => {
  render(<AuthForm mode="login" />);
  expect(screen.getByLabelText("邮箱")).toBeInTheDocument();
  expect(screen.getByLabelText("密码")).toBeInTheDocument();
});
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pnpm --filter web test`
Expected: FAIL，提示组件不存在

- [ ] **Step 3: 实现最小认证页面**

```tsx
export function AuthForm({ mode }: { mode: "login" | "register" }) {
  return (
    <form className="space-y-4">
      <label>
        邮箱
        <input name="email" type="email" />
      </label>
      <label>
        密码
        <input name="password" type="password" />
      </label>
      <button type="submit">{mode === "login" ? "登录" : "注册"}</button>
    </form>
  );
}
```

```tsx
export default function LoginPage() {
  return <AuthForm mode="login" />;
}
```

- [ ] **Step 4: 实现 API 客户端骨架**

```ts
export async function login(email: string, password: string) {
  const response = await fetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  return response.json();
}
```

- [ ] **Step 5: 运行测试并提交**

Run: `pnpm --filter web test`
Expected: PASS

```bash
git add apps/web/tsconfig.json apps/web/next.config.ts apps/web/src/app/layout.tsx apps/web/src/app/login/page.tsx apps/web/src/app/register/page.tsx apps/web/src/components/auth/auth-form.tsx apps/web/src/lib/api.ts apps/web/src/lib/types.ts apps/web/src/test/auth-form.test.tsx
git commit -m "feat: add auth pages and api client"
```

### Task 9: 搭建工作台页面与三栏骨架

**Files:**
- Create: `apps/web/src/app/workspace/page.tsx`
- Create: `apps/web/src/components/workspace/session-sidebar.tsx`
- Create: `apps/web/src/components/workspace/conversation-panel.tsx`
- Create: `apps/web/src/components/workspace/assistant-turn-card.tsx`
- Create: `apps/web/src/components/workspace/action-options.tsx`
- Create: `apps/web/src/components/workspace/composer.tsx`
- Create: `apps/web/src/components/workspace/prd-panel.tsx`
- Create: `apps/web/src/components/workspace/prd-section-card.tsx`
- Create: `apps/web/src/test/workspace-page.test.tsx`

- [ ] **Step 1: 写工作台布局失败测试**

```tsx
import { render, screen } from "@testing-library/react";
import WorkspacePage from "../app/workspace/page";

it("renders sidebar conversation and prd panel", () => {
  render(<WorkspacePage />);
  expect(screen.getByText("项目")).toBeInTheDocument();
  expect(screen.getByText("对话")).toBeInTheDocument();
  expect(screen.getByText("PRD")).toBeInTheDocument();
});
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pnpm --filter web test`
Expected: FAIL，提示工作台页面不存在

- [ ] **Step 3: 实现三栏页面骨架**

```tsx
export default function WorkspacePage() {
  return (
    <main className="grid min-h-screen grid-cols-[260px_1fr_360px]">
      <SessionSidebar />
      <ConversationPanel />
      <PrdPanel />
    </main>
  );
}
```

```tsx
export function SessionSidebar() {
  return <aside><h2>项目</h2></aside>;
}
```

```tsx
export function ConversationPanel() {
  return <section><h2>对话</h2><Composer /></section>;
}
```

```tsx
export function PrdPanel() {
  return <aside><h2>PRD</h2></aside>;
}
```

- [ ] **Step 4: 实现核心卡片与输入组件最小版本**

```tsx
export function AssistantTurnCard({ understanding }: { understanding: string }) {
  return <article><h3>我当前的理解</h3><p>{understanding}</p></article>;
}
```

```tsx
export function Composer() {
  return (
    <form>
      <textarea placeholder="继续描述你的想法..." />
      <button type="submit">发送</button>
    </form>
  );
}
```

- [ ] **Step 5: 运行测试并提交**

Run: `pnpm --filter web test`
Expected: PASS

```bash
git add apps/web/src/app/workspace/page.tsx apps/web/src/components/workspace/session-sidebar.tsx apps/web/src/components/workspace/conversation-panel.tsx apps/web/src/components/workspace/assistant-turn-card.tsx apps/web/src/components/workspace/action-options.tsx apps/web/src/components/workspace/composer.tsx apps/web/src/components/workspace/prd-panel.tsx apps/web/src/components/workspace/prd-section-card.tsx apps/web/src/test/workspace-page.test.tsx
git commit -m "feat: add workspace layout skeleton"
```

### Task 10: 接入消息流、状态流和 PRD 流

**Files:**
- Create: `apps/web/src/lib/sse.ts`
- Create: `apps/web/src/store/workspace-store.ts`
- Modify: `apps/web/src/components/workspace/conversation-panel.tsx`
- Modify: `apps/web/src/components/workspace/prd-panel.tsx`
- Modify: `apps/web/src/components/workspace/action-options.tsx`
- Modify: `apps/web/src/components/workspace/composer.tsx`
- Modify: `apps/web/src/lib/api.ts`

- [ ] **Step 1: 写流式更新失败测试**

```tsx
it("updates prd panel when prd.updated event arrives", async () => {
  const store = createWorkspaceStore();
  store.getState().applyEvent({
    type: "prd.updated",
    data: {
      sections: {
        target_user: {
          content: "第一次做产品的独立开发者",
          status: "inferred"
        }
      }
    }
  });
  expect(store.getState().prd.sections.target_user.content).toBe("第一次做产品的独立开发者");
});
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pnpm --filter web test`
Expected: FAIL，提示 store 不存在

- [ ] **Step 3: 实现工作台 store**

```ts
export const createWorkspaceStore = () =>
  createStore<WorkspaceState>((set) => ({
    messages: [],
    prd: { sections: {} },
    applyEvent: (event) =>
      set((state) => {
        if (event.type === "prd.updated") {
          return {
            ...state,
            prd: {
              ...state.prd,
              sections: {
                ...state.prd.sections,
                ...event.data.sections,
              },
            },
          };
        }
        return state;
      }),
  }));
```

- [ ] **Step 4: 实现 SSE 解析与界面接线**

```ts
export async function* parseEventStream(stream: ReadableStream<Uint8Array>) {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    yield decoder.decode(value);
  }
}
```

```tsx
async function handleSubmit(content: string) {
  const stream = await sendMessage(sessionId, content);
  for await (const event of parseEventStream(stream)) {
    applyEvent(parseSseChunk(event));
  }
}
```

- [ ] **Step 5: 运行测试并提交**

Run: `pnpm --filter web test`
Expected: PASS

```bash
git add apps/web/src/lib/sse.ts apps/web/src/store/workspace-store.ts apps/web/src/components/workspace/conversation-panel.tsx apps/web/src/components/workspace/prd-panel.tsx apps/web/src/components/workspace/action-options.tsx apps/web/src/components/workspace/composer.tsx apps/web/src/lib/api.ts
git commit -m "feat: wire workspace to streaming agent events"
```

### Task 11: 实现会话恢复与 PRD 导出

**Files:**
- Create: `apps/api/app/services/exports.py`
- Create: `apps/api/app/api/routes/exports.py`
- Modify: `apps/api/app/api/routes/sessions.py`
- Modify: `apps/web/src/components/workspace/session-sidebar.tsx`
- Modify: `apps/web/src/lib/api.ts`

- [ ] **Step 1: 写导出接口失败测试**

```python
def test_export_returns_markdown(auth_client, seeded_session):
    response = auth_client.post(f"/api/sessions/{seeded_session}/export", json={"format": "md"})
    assert response.status_code == 200
    assert response.json()["content"].startswith("# PRD")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest apps/api/tests/test_sessions.py apps/api/tests/test_messages_stream.py -q`
Expected: FAIL，提示导出接口不存在

- [ ] **Step 3: 实现后端导出服务**

```python
def build_markdown_export(snapshot: dict) -> str:
    return "\n".join([
        "# PRD",
        "## 目标用户",
        snapshot["sections"].get("target_user", {}).get("content", ""),
        "## 核心问题",
        snapshot["sections"].get("problem", {}).get("content", ""),
    ])
```

```python
@router.post("/api/sessions/{session_id}/export")
def export_session(...):
    content = export_service.export_markdown(...)
    return {"file_name": "ai-cofounder-prd.md", "content": content}
```

- [ ] **Step 4: 实现前端会话列表与导出按钮**

```tsx
export function SessionSidebar() {
  return (
    <aside>
      <h2>项目</h2>
      <button type="button">新建项目</button>
      <button type="button">导出 PRD</button>
    </aside>
  );
}
```

- [ ] **Step 5: 运行测试并提交**

Run: `pytest apps/api/tests -q && pnpm --filter web test`
Expected: PASS

```bash
git add apps/api/app/services/exports.py apps/api/app/api/routes/exports.py apps/api/app/api/routes/sessions.py apps/web/src/components/workspace/session-sidebar.tsx apps/web/src/lib/api.ts
git commit -m "feat: add session recovery and markdown export"
```

### Task 12: 收口、验证与发布前检查

**Files:**
- Modify: `README.md`
- Modify: `docs/superpowers/specs/2026-04-01-ai-cofounder-v1-design.md`
- Modify: `docs/superpowers/plans/2026-04-01-ai-cofounder-v1-implementation.md`

- [ ] **Step 1: 补 README 运行说明**

```md
## 本地启动

1. `docker compose up -d`
2. `pnpm install`
3. `pip install -e ".[dev]"`
4. `pnpm dev:web`
5. `python -m uvicorn app.main:app --reload --app-dir apps/api`
```

- [ ] **Step 2: 运行完整验证**

Run: `pytest apps/api/tests -q`
Expected: PASS

Run: `pnpm --filter web test`
Expected: PASS

Run: `pnpm --filter web build`
Expected: BUILD SUCCESS

- [ ] **Step 3: 手工验收**

```text
1. 注册一个新账号
2. 登录并创建一个 idea 会话
3. 发送三轮消息，确认右侧 PRD 有实时更新
4. 刷新页面，确认会话与 PRD 恢复
5. 导出 Markdown，确认包含目标用户、问题、方案、MVP 和执行建议
```

- [ ] **Step 4: 检查计划与 spec 一致性**

```text
- 认证：已覆盖 Task 4
- 单会话闭环：已覆盖 Task 5-10
- PRD 快照与导出：已覆盖 Task 5、11
- 历史恢复：已覆盖 Task 11
- MVP 体验收口：已覆盖 Task 12
```

- [ ] **Step 5: 提交最终整理**

```bash
git add README.md docs/superpowers/specs/2026-04-01-ai-cofounder-v1-design.md docs/superpowers/plans/2026-04-01-ai-cofounder-v1-implementation.md
git commit -m "docs: finalize v1 implementation plan"
```
