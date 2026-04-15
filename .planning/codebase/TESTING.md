# Testing Patterns

**Analysis Date:** 2026-04-16

## Test Framework

**Runner:**
- 前端使用 Vitest 2.x，依赖声明见 `apps/web/package.json`，配置文件见 `apps/web/vitest.config.ts`。
- 后端使用 `pytest` 8.x，依赖声明见 `apps/api/pyproject.toml`；未检测到单独的 `pytest.ini`。

**Assertion Library:**
- 前端使用 Vitest 内置 `expect`，并通过 `apps/web/src/test/setup.ts` 引入 `@testing-library/jest-dom/vitest` 扩展 DOM 断言。
- 前端组件测试依赖 `@testing-library/react`，样例见 `apps/web/src/test/auth-form.test.tsx`、`apps/web/src/test/workspace-page.test.tsx`。
- 后端使用 `pytest` 原生 `assert`，HTTP 接口通过 `fastapi.testclient.TestClient` 断言响应，样例见 `apps/api/tests/test_auth.py`、`apps/api/tests/test_messages_stream.py`。

**Run Commands:**
```bash
pnpm test:web                         # 运行前端测试（根 package.json -> pnpm --filter web test）
pnpm --filter web test                # 直接运行 web 包测试（实际执行 vitest run）
pnpm test:api                         # 运行后端测试（pytest apps/api/tests -q）
pytest apps/api/tests -q              # 直接运行后端测试
```

## Test File Organization

**Location:**
- 前端测试统一集中在 `apps/web/src/test`，不是与源码同目录共置；样例见 `apps/web/src/test/api.test.ts`、`apps/web/src/test/workspace-store.test.ts`。
- 后端测试统一放在 `apps/api/tests`；共享 fixture 在 `apps/api/tests/conftest.py`。

**Naming:**
- 前端单元/组件测试统一使用 `*.test.ts` 或 `*.test.tsx`，文件名通常对齐被测模块，如 `apps/web/src/test/use-auth-guard.test.ts`、`apps/web/src/test/workspace-entry.test.tsx`。
- 前端属性测试会在文件名中显式带 `pbt`，样例见 `apps/web/src/test/workspace-left-nav-grouping-pbt.test.tsx`。
- 后端统一使用 `test_*.py`，按接口、服务或模块命名，样例见 `apps/api/tests/test_auth.py`、`apps/api/tests/test_model_gateway.py`、`apps/api/tests/test_messages_service.py`。

**Structure:**
```text
apps/web/src/test/
  api.test.ts
  auth-form.test.tsx
  workspace-page.test.tsx
  workspace-store.test.ts
  workspace-left-nav-grouping-pbt.test.tsx
  setup.ts

apps/api/tests/
  conftest.py
  test_auth.py
  test_messages_stream.py
  test_messages_service.py
  test_model_gateway.py
```

## Test Structure

**Suite Organization:**
```typescript
import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

describe("WorkspacePage", () => {
  beforeEach(() => {
    listSessionsMock.mockReset();
    pushMock.mockReset();
    listSessionsMock.mockResolvedValue({ sessions: [] });
  });

  it("renders the session entry surface", async () => {
    render(<WorkspaceEntry />);
    expect(await screen.findByText("Describe your idea")).toBeInTheDocument();
  });
});
```

```python
def test_register_returns_token(client):
    response = client.post(
        "/api/auth/register",
        json={"email": "user@example.com", "password": "secret123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["user"]["email"] == "user@example.com"
```

**Patterns:**
- 前端以 `describe` + `it` 为主，`beforeEach` 用于重置 mock、store 和全局状态，样例见 `apps/web/src/test/api.test.ts`、`apps/web/src/test/auth-form.test.tsx`。
- 前端涉及异步渲染或副作用时使用 `await screen.findBy...` 或 `waitFor(...)`，样例见 `apps/web/src/test/workspace-page.test.tsx`、`apps/web/src/test/auth-form.test.tsx`。
- 后端测试多数直接采用“准备数据 -> 调用接口/函数 -> assert”三段式，不额外包 `class` 或 `describe`，样例见 `apps/api/tests/test_auth.py`、`apps/api/tests/test_model_gateway.py`。
- 后端复杂服务测试会在测试文件内先定义 helper 或 fake payload，再在多个测试中复用，样例见 `apps/api/tests/test_messages_service.py`、`apps/api/tests/test_messages_stream.py`。

## Mocking

**Framework:**
- 前端使用 Vitest 的 `vi.mock`、`vi.fn`、`vi.stubGlobal`、`vi.importActual`，样例见 `apps/web/src/test/workspace-page.test.tsx`、`apps/web/src/test/api.test.ts`。
- 后端使用 `pytest` 的 `monkeypatch` fixture 替换外部调用与 LLM 入口，样例见 `apps/api/tests/test_model_gateway.py`、`apps/api/tests/test_messages_stream.py`。

**Patterns:**
```typescript
const listSessionsMock = vi.fn();

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual("../lib/api");
  return {
    ...actual,
    listSessions: (...args: unknown[]) => listSessionsMock(...args),
  };
});
```

```typescript
vi.stubGlobal(
  "fetch",
  vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "未认证" }), { status: 401 })),
);
vi.stubGlobal("location", { assign: assignMock });
```

```python
def fake_post(url, *, headers, json, timeout):
    return DummyResponse({"choices": [{"message": {"content": "这是助手回复"}}]})

monkeypatch.setattr(httpx, "post", fake_post)
```

```python
monkeypatch.setattr(
    "app.agent.pm_mentor.call_pm_mentor_llm",
    lambda **_: _fake_pm_mentor_llm_response(),
)
```

**What to Mock:**
- 前端 mock `next/navigation`、`fetch`、`location`、API 模块和 store 读写边界，样例见 `apps/web/src/test/workspace-page.test.tsx`、`apps/web/src/test/use-auth-guard.test.ts`、`apps/web/src/test/api.test.ts`。
- 后端 mock `httpx.post`、LLM 调用入口、上游网关或补救函数，样例见 `apps/api/tests/test_model_gateway.py`、`apps/api/tests/test_messages_stream.py`。

**What NOT to Mock:**
- 前端 store 纯状态转移测试直接使用真实 store 实例，样例见 `apps/web/src/test/workspace-store.test.ts`。
- 后端 repository/service 组合测试通常使用真实 SQLite 内存库与真实 FastAPI app，不 mock 数据库层，样例见 `apps/api/tests/conftest.py`、`apps/api/tests/test_auth.py`。

## Fixtures and Factories

**Test Data:**
```python
@pytest.fixture
def auth_client(client: TestClient) -> TestClient:
    response = client.post(
        "/api/auth/register",
        json={"email": "session-user@example.com", "password": "secret123"},
    )
    token = response.json()["access_token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client
```

```python
def _sample_turn_decision() -> TurnDecision:
    return TurnDecision(
        phase="problem",
        phase_goal="你的目标用户是谁？",
        suggestions=[Suggestion(...)],
        next_best_questions=["你的目标用户是谁？"],
    )
```

```typescript
function buildSnapshotWithDecisions(
  decisions?: AgentTurnDecision[],
  state?: StateSnapshotResponse,
): SessionSnapshotResponse {
  return {
    session: {
      id: "session-1",
      user_id: "user-1",
      title: "AI Co-founder",
      initial_idea: "idea",
      created_at: "2026-04-05T00:00:00Z",
      updated_at: "2026-04-05T00:00:00Z",
    },
    state: state ?? {},
    prd_snapshot: { sections: {} },
    messages: [],
    assistant_reply_groups: [],
    turn_decisions: decisions,
  };
}
```

**Location:**
- 后端通用 fixture 放在 `apps/api/tests/conftest.py`。
- 后端复杂场景的 helper/factory 多数内联在测试文件顶部，样例见 `apps/api/tests/test_messages_service.py`、`apps/api/tests/test_messages_stream.py`。
- 前端没有单独的 `fixtures/` 目录；测试数据通常内联在测试文件中，样例见 `apps/web/src/test/workspace-page.test.tsx`、`apps/web/src/test/workspace-store.test.ts`。

## Coverage

**Requirements:**
- 未检测到覆盖率阈值配置，也未发现 `coverage`、`--cov`、`c8` 或 `istanbul` 相关脚本。
- 当前仓库通过“修改行为就补对应自动化测试”的仓库约定维持质量，而不是工具级覆盖率门槛。

**Configuration:**
- 前端 Vitest 配置仅声明 `jsdom`、`setupFiles`、`globals`，见 `apps/web/vitest.config.ts`。
- 后端 `pytest` 通过 `apps/api/tests/conftest.py` 提供内存数据库和 `TestClient`，未检测到独立 coverage 插件配置。

**View Coverage:**
```bash
未配置统一覆盖率命令
```

## Test Types

**Unit Tests:**
- 前端纯逻辑和状态流转测试覆盖 helper、store、hook，样例见 `apps/web/src/test/prd-store-helpers.test.ts`、`apps/web/src/test/workspace-store.test.ts`、`apps/web/src/test/use-auth-guard.test.ts`。
- 后端单元测试覆盖网关解析、配置校验和纯服务函数，样例见 `apps/api/tests/test_model_gateway.py`、`apps/api/tests/test_config.py`。

**Integration Tests:**
- 前端组件测试把组件连同 mocked router/API/store 一起运行，样例见 `apps/web/src/test/auth-form.test.tsx`、`apps/web/src/test/workspace-page.test.tsx`。
- 后端集成测试直接通过 `TestClient` 调真实路由，并配合 SQLite 内存数据库验证持久化副作用，样例见 `apps/api/tests/test_auth.py`、`apps/api/tests/test_messages_stream.py`、`apps/api/tests/test_sessions.py`。

**E2E Tests:**
- 未检测到 Playwright、Cypress 或单独 `e2e/` 目录。
- 当前最接近端到端的是后端 SSE/消息流接口测试，样例见 `apps/api/tests/test_messages_stream.py`。

## Common Patterns

**Async Testing:**
```typescript
it("persists auth state and redirects after login succeeds", async () => {
  render(<AuthForm mode="login" />);
  fireEvent.click(screen.getByRole("button", { name: "Continue" }));

  await waitFor(() => {
    expect(pushMock).toHaveBeenCalledWith("/workspace");
  });
});
```

```python
with auth_client.stream(
    "POST",
    f"/api/sessions/{seeded_session}/messages",
    json={"content": "help me think through the target user", "model_config_id": model_config_id},
) as response:
    assert response.status_code == 200
    body = "".join(response.iter_text())
```

**Error Testing:**
```typescript
await expect(listSessions("expired-token")).rejects.toMatchObject({
  code: "AUTH_REQUIRED",
  message: "未认证",
});
```

```python
with pytest.raises(ModelGatewayError, match="上游结构化提取结果不是合法 JSON"):
    generate_structured_extraction(
        base_url="https://api.example.com/v1",
        api_key="secret-key",
        model="gpt-test",
        state={"target_user": None},
        target_section="target_user",
        user_input="独立开发者",
    )
```

**Property-Based Testing:**
```typescript
fc.assert(
  fc.property(fc.array(sessionArbitrary, { minLength: 0, maxLength: 50 }), (sessions) => {
    const grouped = groupSessionsByDate(sessions);
    expect(Object.keys(grouped)).toHaveLength(5);
  }),
  { numRuns: 100 },
);
```
- 属性测试使用 `fast-check`，当前样例见 `apps/web/src/test/workspace-left-nav-grouping-pbt.test.tsx`。

**Contract Fixtures:**
```typescript
import prdMetaCases from "../../../../docs/contracts/prd-meta-cases.json";
```

```python
PRD_META_CONTRACT_CASES = json.loads(
    Path(__file__).resolve().parents[3].joinpath("docs/contracts/prd-meta-cases.json").read_text(encoding="utf-8")
)
```
- 前后端共享 `docs/contracts/prd-meta-cases.json` 做契约一致性验证，样例见 `apps/web/src/test/workspace-store.test.ts` 与 `apps/api/tests/test_messages_service.py`。

**Snapshot Testing:**
- 未检测到 Vitest/Jest snapshot 文件或 `toMatchSnapshot` 用法。

---

*Testing analysis: 2026-04-16*
