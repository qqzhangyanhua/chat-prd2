# 模型管理与 OpenAI 兼容多模型对话 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 AI Co-founder 增加管理员模型配置页、工作台按消息选择启用模型、以及基于 OpenAI 兼容接口的真实对话调用链路。

**Architecture:** 后端在现有 FastAPI + SQLAlchemy + SSE 链路上新增平台级模型配置表、管理员白名单鉴权和 OpenAI 兼容网关；前端在现有 Next.js 工作台上新增管理员入口与模型选择器，并把 `model_config_id` 透传到消息发送接口。消息继续沿用当前状态驱动结构，但自然语言回复改由外部模型生成，同时把模型元数据写入消息 `meta`。

**Tech Stack:** FastAPI、SQLAlchemy、Alembic、pytest、Next.js 15、React 19、Zustand、Vitest、Fetch API

---

## 文件结构与职责

### 后端

- Create: `apps/api/app/core/admin.py`
  负责解析 `ADMIN_EMAILS` 并判断邮箱是否为管理员。
- Create: `apps/api/app/schemas/model_config.py`
  定义模型配置 CRUD、启用模型列表返回结构。
- Create: `apps/api/app/repositories/model_configs.py`
  封装模型配置读写查询。
- Create: `apps/api/app/services/model_gateway.py`
  负责 OpenAI 兼容接口调用与错误归一化。
- Create: `apps/api/app/api/routes/admin_model_configs.py`
  管理员模型配置 CRUD 路由。
- Create: `apps/api/app/api/routes/model_configs.py`
  普通用户可访问的启用模型列表路由。
- Create: `apps/api/alembic/versions/0005_add_llm_model_configs.py`
  新增 `llm_model_configs` 表迁移。
- Modify: `apps/api/app/core/config.py`
  增加 `admin_emails` 配置读取。
- Modify: `apps/api/app/db/models.py`
  增加 `LlmModelConfig` ORM。
- Modify: `apps/api/app/schemas/auth.py`
  在认证返回中加入 `is_admin`。
- Modify: `apps/api/app/schemas/message.py`
  给消息创建请求增加 `model_config_id`。
- Modify: `apps/api/app/api/routes/auth.py`
  返回管理员标记。
- Modify: `apps/api/app/api/routes/messages.py`
  接收并校验 `model_config_id`。
- Modify: `apps/api/app/services/messages.py`
  接入模型选择、网关调用和消息元数据写入。
- Modify: `apps/api/app/main.py`
  注册新路由。
- Modify: `apps/api/tests/test_config.py`
- Modify: `apps/api/tests/test_auth.py`
- Modify: `apps/api/tests/test_models.py`
- Modify: `apps/api/tests/test_messages_service.py`
- Modify: `apps/api/tests/test_messages_stream.py`
- Create: `apps/api/tests/test_model_gateway.py`
- Create: `apps/api/tests/test_model_configs.py`

### 前端

- Create: `apps/web/src/app/admin/models/page.tsx`
  管理页路由入口。
- Create: `apps/web/src/components/admin/model-config-admin-page.tsx`
  管理页表单与列表主组件。
- Create: `apps/web/src/components/workspace/model-selector.tsx`
  工作台模型选择器。
- Modify: `apps/web/src/lib/types.ts`
  增加管理员、模型配置与消息请求类型。
- Modify: `apps/web/src/lib/api.ts`
  新增模型管理/启用模型 API，并扩展 `sendMessage`。
- Modify: `apps/web/src/store/auth-store.ts`
  保存 `is_admin` 用户信息。
- Modify: `apps/web/src/store/workspace-store.ts`
  保存可用模型列表、当前选择、失效回退逻辑。
- Modify: `apps/web/src/components/workspace/composer.tsx`
  挂接模型选择器并发送 `model_config_id`。
- Modify: `apps/web/src/components/workspace/session-sidebar.tsx`
  为管理员增加模型管理入口。
- Modify: `apps/web/src/test/auth-form.test.tsx`
- Modify: `apps/web/src/test/session-sidebar.test.tsx`
- Modify: `apps/web/src/test/workspace-composer.test.tsx`
- Modify: `apps/web/src/test/workspace-session-shell.test.tsx`
- Create: `apps/web/src/test/model-config-admin-page.test.tsx`

### 文档

- Modify: `docs/startup.md`
  增加 `ADMIN_EMAILS` 与 OpenAI 兼容模型配置说明。

## 任务分解

### Task 1: 加入管理员白名单能力并让认证返回 `is_admin`

**Files:**
- Create: `apps/api/app/core/admin.py`
- Modify: `apps/api/app/core/config.py`
- Modify: `apps/api/app/schemas/auth.py`
- Modify: `apps/api/app/api/routes/auth.py`
- Modify: `apps/api/tests/test_config.py`
- Modify: `apps/api/tests/test_auth.py`

- [ ] **Step 1: 先写管理员白名单相关失败测试**

```python
def test_settings_parse_admin_emails(monkeypatch):
    monkeypatch.setenv("ADMIN_EMAILS", "admin@example.com, owner@example.com ")
    settings = Settings()
    assert settings.admin_emails == ("admin@example.com", "owner@example.com")


def test_me_returns_is_admin_for_whitelisted_user(client):
    register = client.post("/api/auth/register", json={
        "email": "admin@example.com",
        "password": "secret123",
    })
    token = register.json()["access_token"]

    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["is_admin"] is True
```

- [ ] **Step 2: 运行认证与配置测试，确认它们先失败**

Run: `pytest apps/api/tests/test_config.py apps/api/tests/test_auth.py -q`

Expected: 至少出现 `admin_emails` 或 `is_admin` 缺失相关失败。

- [ ] **Step 3: 实现管理员邮箱解析与返回结构**

```python
def parse_admin_emails(raw: str | None) -> tuple[str, ...]:
    if not raw:
        return ()
    return tuple(email.strip().lower() for email in raw.split(",") if email.strip())


class UserResponse(BaseModel):
    id: str
    email: EmailStr
    is_admin: bool
```

- [ ] **Step 4: 在认证路由中补上 `is_admin`**

```python
def to_user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        is_admin=is_admin_email(user.email),
    )
```

- [ ] **Step 5: 重新运行认证与配置测试确认通过**

Run: `pytest apps/api/tests/test_config.py apps/api/tests/test_auth.py -q`

Expected: PASS

- [ ] **Step 6: 提交这一小步**

```bash
git add apps/api/app/core/admin.py apps/api/app/core/config.py apps/api/app/schemas/auth.py apps/api/app/api/routes/auth.py apps/api/tests/test_config.py apps/api/tests/test_auth.py
git commit -m "feat(api): add admin email whitelist auth flag"
```

### Task 2: 增加模型配置数据表、仓储和管理接口

**Files:**
- Create: `apps/api/alembic/versions/0005_add_llm_model_configs.py`
- Create: `apps/api/app/schemas/model_config.py`
- Create: `apps/api/app/repositories/model_configs.py`
- Create: `apps/api/app/api/routes/admin_model_configs.py`
- Create: `apps/api/app/api/routes/model_configs.py`
- Modify: `apps/api/app/db/models.py`
- Modify: `apps/api/app/main.py`
- Modify: `apps/api/tests/test_models.py`
- Create: `apps/api/tests/test_model_configs.py`

- [ ] **Step 1: 先写模型配置表与路由失败测试**

```python
def test_models_include_llm_model_configs_table():
    assert LlmModelConfig.__tablename__ == "llm_model_configs"


def test_enabled_model_configs_only_return_enabled_items(auth_client):
    response = auth_client.get("/api/model-configs/enabled")
    assert response.status_code == 200
    assert response.json() == {"models": []}
```

- [ ] **Step 2: 运行模型与模型配置测试确认失败**

Run: `pytest apps/api/tests/test_models.py apps/api/tests/test_model_configs.py -q`

Expected: 因 `LlmModelConfig` 和新路由不存在而失败。

- [ ] **Step 3: 增加 ORM、迁移和仓储**

```python
class LlmModelConfig(Base):
    __tablename__ = "llm_model_configs"
    id = mapped_column(String, primary_key=True)
    name = mapped_column(String)
    base_url = mapped_column(String)
    api_key = mapped_column(String)
    model = mapped_column(String)
    enabled = mapped_column(Boolean, default=True)
```

- [ ] **Step 4: 实现管理员 CRUD 和启用模型列表接口**

```python
@router.get("/api/model-configs/enabled")
def list_enabled_model_configs(...):
    return {"models": [EnabledModelConfigResponse.model_validate(item) for item in items]}
```

- [ ] **Step 5: 补管理员访问控制测试**

```python
def test_non_admin_cannot_create_model_config(auth_client):
    response = auth_client.post("/api/admin/model-configs", json={...})
    assert response.status_code == 403
```

- [ ] **Step 6: 运行后端模型配置相关测试**

Run: `pytest apps/api/tests/test_models.py apps/api/tests/test_model_configs.py -q`

Expected: PASS

- [ ] **Step 7: 提交这一小步**

```bash
git add apps/api/alembic/versions/0005_add_llm_model_configs.py apps/api/app/schemas/model_config.py apps/api/app/repositories/model_configs.py apps/api/app/api/routes/admin_model_configs.py apps/api/app/api/routes/model_configs.py apps/api/app/db/models.py apps/api/app/main.py apps/api/tests/test_models.py apps/api/tests/test_model_configs.py
git commit -m "feat(api): add model config admin routes"
```

### Task 3: 实现 OpenAI 兼容模型网关

**Files:**
- Create: `apps/api/app/services/model_gateway.py`
- Create: `apps/api/tests/test_model_gateway.py`

- [ ] **Step 1: 先写网关成功与失败测试**

```python
def test_generate_reply_calls_openai_compatible_chat_completions(httpx_mock):
    httpx_mock.add_response(
        json={"choices": [{"message": {"content": "你好，我建议先明确目标用户。"}}]}
    )

    reply = generate_reply(
        base_url="https://example.com/v1",
        api_key="secret",
        model="deepseek-chat",
        messages=[{"role": "user", "content": "你好"}],
    )

    assert "目标用户" in reply
```

- [ ] **Step 2: 运行网关测试确认失败**

Run: `pytest apps/api/tests/test_model_gateway.py -q`

Expected: 因 `generate_reply` 不存在而失败。

- [ ] **Step 3: 用最小实现接通 OpenAI 兼容接口**

```python
def generate_reply(base_url, api_key, model, messages):
    response = httpx.post(
        f"{base_url.rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"model": model, "messages": messages},
        timeout=30,
    )
    data = response.json()
    return data["choices"][0]["message"]["content"]
```

- [ ] **Step 4: 加上异常归一化**

```python
class ModelGatewayError(RuntimeError):
    pass
```

- [ ] **Step 5: 重新运行网关测试**

Run: `pytest apps/api/tests/test_model_gateway.py -q`

Expected: PASS

- [ ] **Step 6: 提交这一小步**

```bash
git add apps/api/app/services/model_gateway.py apps/api/tests/test_model_gateway.py
git commit -m "feat(api): add openai compatible model gateway"
```

### Task 4: 把消息接口切到“按消息选模型 + 真实外部调用”

**Files:**
- Modify: `apps/api/app/schemas/message.py`
- Modify: `apps/api/app/api/routes/messages.py`
- Modify: `apps/api/app/services/messages.py`
- Modify: `apps/api/app/repositories/messages.py`
- Modify: `apps/api/tests/test_messages_service.py`
- Modify: `apps/api/tests/test_messages_stream.py`

- [ ] **Step 1: 先写消息接口失败测试**

```python
def test_message_stream_requires_model_config_id(auth_client, seeded_session):
    response = auth_client.post(
        f"/api/sessions/{seeded_session}/messages",
        json={"content": "hello"},
    )
    assert response.status_code == 422


def test_message_stream_persists_model_meta(auth_client, seeded_session):
    with auth_client.stream(
        "POST",
        f"/api/sessions/{seeded_session}/messages",
        json={"content": "help me think", "model_config_id": "model-1"},
    ) as response:
        assert response.status_code == 200
```

- [ ] **Step 2: 运行消息相关测试确认失败**

Run: `pytest apps/api/tests/test_messages_service.py apps/api/tests/test_messages_stream.py -q`

Expected: 因 `model_config_id` 缺失和消息元数据断言失败。

- [ ] **Step 3: 扩展消息 schema 与路由入参**

```python
class MessageCreateRequest(BaseModel):
    content: str = Field(min_length=1)
    model_config_id: str = Field(min_length=1)
```

- [ ] **Step 4: 在消息服务中接入模型配置与外部调用**

```python
model_config = model_configs_repository.get_enabled_by_id(db, payload.model_config_id)
reply = generate_reply(
    base_url=model_config.base_url,
    api_key=model_config.api_key,
    model=model_config.model,
    messages=prompt_messages,
)
```

- [ ] **Step 5: 把模型元数据写入用户消息和助手消息**

```python
meta={
    "model_config_id": model_config.id,
    "model_name": model_config.model,
    "display_name": model_config.name,
    "base_url": model_config.base_url,
}
```

- [ ] **Step 6: 重新运行消息相关测试**

Run: `pytest apps/api/tests/test_messages_service.py apps/api/tests/test_messages_stream.py -q`

Expected: PASS

- [ ] **Step 7: 提交这一小步**

```bash
git add apps/api/app/schemas/message.py apps/api/app/api/routes/messages.py apps/api/app/services/messages.py apps/api/app/repositories/messages.py apps/api/tests/test_messages_service.py apps/api/tests/test_messages_stream.py
git commit -m "feat(api): route messages through selected model config"
```

### Task 5: 给 Web 端补管理员态、模型类型和管理 API 客户端

**Files:**
- Modify: `apps/web/src/lib/types.ts`
- Modify: `apps/web/src/lib/api.ts`
- Modify: `apps/web/src/store/auth-store.ts`
- Modify: `apps/web/src/test/auth-form.test.tsx`

- [ ] **Step 1: 先写前端类型与认证失败测试**

```tsx
it("persists admin flag after login", async () => {
  loginMock.mockResolvedValue({
    access_token: "token",
    user: { id: "u1", email: "admin@example.com", is_admin: true },
  });
});
```

- [ ] **Step 2: 运行认证表单测试确认失败**

Run: `pnpm --filter web test -- src/test/auth-form.test.tsx`

Expected: 因 `is_admin` 缺失或类型不匹配失败。

- [ ] **Step 3: 扩展前端类型与 API 客户端**

```ts
export interface User {
  id: string;
  email: string;
  is_admin: boolean;
}

export interface EnabledModelConfig {
  id: string;
  name: string;
  model: string;
}
```

- [ ] **Step 4: 增加模型配置相关 API 方法**

```ts
export function listEnabledModelConfigs(accessToken?: string | null) {
  return requestJson<EnabledModelConfigListResponse>("/api/model-configs/enabled", { ... });
}
```

- [ ] **Step 5: 重新运行认证表单测试**

Run: `pnpm --filter web test -- src/test/auth-form.test.tsx`

Expected: PASS

- [ ] **Step 6: 提交这一小步**

```bash
git add apps/web/src/lib/types.ts apps/web/src/lib/api.ts apps/web/src/store/auth-store.ts apps/web/src/test/auth-form.test.tsx
git commit -m "feat(web): add admin and model config client types"
```

### Task 6: 实现管理员模型管理页

**Files:**
- Create: `apps/web/src/app/admin/models/page.tsx`
- Create: `apps/web/src/components/admin/model-config-admin-page.tsx`
- Modify: `apps/web/src/components/workspace/session-sidebar.tsx`
- Create: `apps/web/src/test/model-config-admin-page.test.tsx`
- Modify: `apps/web/src/test/session-sidebar.test.tsx`

- [ ] **Step 1: 先写管理页失败测试**

```tsx
it("renders model configs for admin user", async () => {
  render(<ModelConfigAdminPage />);
  expect(await screen.findByText("模型管理")).toBeInTheDocument();
});

it("hides admin entry for non-admin users", () => {
  // render sidebar with non-admin user
});
```

- [ ] **Step 2: 运行管理页与侧栏测试确认失败**

Run: `pnpm --filter web test -- src/test/model-config-admin-page.test.tsx src/test/session-sidebar.test.tsx`

Expected: 因组件和入口不存在而失败。

- [ ] **Step 3: 实现管理页 UI 与管理员守卫**

```tsx
if (!user?.is_admin) {
  return <p>无权访问模型管理</p>;
}
```

- [ ] **Step 4: 实现表单与列表交互**

```tsx
const [draft, setDraft] = useState({
  name: "",
  base_url: "",
  model: "",
  api_key: "",
  enabled: true,
});
```

- [ ] **Step 5: 在工作台侧栏为管理员增加入口**

```tsx
{user?.is_admin ? (
  <button onClick={() => router.push("/admin/models")}>模型管理</button>
) : null}
```

- [ ] **Step 6: 重新运行管理页与侧栏测试**

Run: `pnpm --filter web test -- src/test/model-config-admin-page.test.tsx src/test/session-sidebar.test.tsx`

Expected: PASS

- [ ] **Step 7: 提交这一小步**

```bash
git add apps/web/src/app/admin/models/page.tsx apps/web/src/components/admin/model-config-admin-page.tsx apps/web/src/components/workspace/session-sidebar.tsx apps/web/src/test/model-config-admin-page.test.tsx apps/web/src/test/session-sidebar.test.tsx
git commit -m "feat(web): add admin model config management page"
```

### Task 7: 在工作台中增加模型选择器并透传到消息发送

**Files:**
- Create: `apps/web/src/components/workspace/model-selector.tsx`
- Modify: `apps/web/src/store/workspace-store.ts`
- Modify: `apps/web/src/components/workspace/composer.tsx`
- Modify: `apps/web/src/components/workspace/workspace-session-shell.tsx`
- Modify: `apps/web/src/test/workspace-composer.test.tsx`
- Modify: `apps/web/src/test/workspace-session-shell.test.tsx`

- [ ] **Step 1: 先写工作台模型选择失败测试**

```tsx
it("sends selected model config id with the message", async () => {
  sendMessageMock.mockResolvedValue(mockStream);
  render(<ConversationPanel sessionId="session-1" />);
  // select model-1 and send
  expect(sendMessageMock).toHaveBeenCalledWith(
    "session-1",
    "请帮我梳理目标用户。",
    "model-1",
    "token",
    expect.any(AbortSignal),
  );
});
```

- [ ] **Step 2: 运行工作台相关测试确认失败**

Run: `pnpm --filter web test -- src/test/workspace-composer.test.tsx src/test/workspace-session-shell.test.tsx`

Expected: 因新参数、模型选择器和加载逻辑不存在而失败。

- [ ] **Step 3: 在 store 中增加模型状态**

```ts
interface WorkspaceState {
  availableModels: EnabledModelConfig[];
  selectedModelConfigId: string | null;
  hydrateAvailableModels: (models: EnabledModelConfig[]) => void;
  setSelectedModelConfigId: (value: string) => void;
}
```

- [ ] **Step 4: 在 `WorkspaceSessionShell` 加载启用模型并处理空态**

```tsx
const modelResponse = await listEnabledModelConfigs(accessToken);
workspaceStore.getState().hydrateAvailableModels(modelResponse.models);
```

- [ ] **Step 5: 在 `Composer` 中渲染选择器并发送 `model_config_id`**

```tsx
const selectedModelConfigId = useWorkspaceStore((state) => state.selectedModelConfigId);
const stream = await sendMessage(
  sessionId,
  normalizedContent,
  selectedModelConfigId,
  accessToken,
  abortController.signal,
);
```

- [ ] **Step 6: 重新运行工作台相关测试**

Run: `pnpm --filter web test -- src/test/workspace-composer.test.tsx src/test/workspace-session-shell.test.tsx`

Expected: PASS

- [ ] **Step 7: 提交这一小步**

```bash
git add apps/web/src/components/workspace/model-selector.tsx apps/web/src/store/workspace-store.ts apps/web/src/components/workspace/composer.tsx apps/web/src/components/workspace/workspace-session-shell.tsx apps/web/src/test/workspace-composer.test.tsx apps/web/src/test/workspace-session-shell.test.tsx
git commit -m "feat(web): add per-message model selection in workspace"
```

### Task 8: 文档、全量验证与收尾

**Files:**
- Modify: `docs/startup.md`

- [ ] **Step 1: 更新启动文档**

```md
ADMIN_EMAILS=admin@example.com

# 管理员进入 `/admin/models` 维护启用模型
```

- [ ] **Step 2: 运行后端全量测试**

Run: `pytest apps/api/tests -q`

Expected: 全部 PASS

- [ ] **Step 3: 运行前端全量测试**

Run: `pnpm --filter web test`

Expected: 全部 PASS

- [ ] **Step 4: 运行前端构建**

Run: `pnpm --filter web build`

Expected: BUILD SUCCESS

- [ ] **Step 5: 检查工作区变更**

Run: `git status --short`

Expected: 只剩本次实现相关文件。

- [ ] **Step 6: 提交收尾**

```bash
git add docs/startup.md
git commit -m "docs: document model management environment setup"
```

## 实施注意事项

1. 保持 TDD 顺序，不要先写生产代码。
2. 不要把“管理员判定”塞进前端硬编码，唯一事实来源应是后端返回的 `is_admin`。
3. `api_key` 本期按需求明文处理，但不要在普通用户 API 或工作台中回传。
4. `sendMessage` 参数顺序要统一修改测试桩，避免前后端接口已改但测试仍在使用旧签名。
5. 模型选择是消息级行为，不要把它错误地设计成会话级锁定字段。
6. 外部模型调用失败时明确报错，不做自动切换和静默降级。

## 建议验证路径

1. 用管理员邮箱登录。
2. 进入 `/admin/models` 创建并启用一个 OpenAI 兼容模型。
3. 用普通用户登录工作台，确认能看到该模型。
4. 选择模型发送消息，确认接口成功并产出真实回复。
5. 检查数据库中的 `conversation_messages.meta`，确认保留 `model_config_id` 和模型元数据。
