# Coding Conventions

**Analysis Date:** 2026-04-16

## Naming Patterns

**Files:**
- 前端源码文件使用 kebab-case，路径样例见 `apps/web/src/hooks/use-auth-guard.ts`、`apps/web/src/lib/recovery-action.ts`、`apps/web/src/components/workspace/workspace-session-shell.tsx`。
- Next.js App Router 页面文件固定使用 `page.tsx` 与 `layout.tsx`，路径样例见 `apps/web/src/app/page.tsx`、`apps/web/src/app/login/page.tsx`、`apps/web/src/app/layout.tsx`。
- 前端测试文件集中放在 `apps/web/src/test`，命名使用 `*.test.ts` 或 `*.test.tsx`，样例见 `apps/web/src/test/api.test.ts`、`apps/web/src/test/auth-form.test.tsx`。
- 后端模块文件使用 `snake_case`，路径样例见 `apps/api/app/core/api_error.py`、`apps/api/app/services/model_gateway.py`、`apps/api/app/api/routes/auth.py`。
- 后端测试文件放在 `apps/api/tests`，命名使用 `test_*.py`，样例见 `apps/api/tests/test_auth.py`、`apps/api/tests/test_messages_service.py`。

**Functions:**
- 前端函数、hook、store action 使用 `camelCase`，样例见 `apps/web/src/lib/api.ts` 中的 `requestJson`、`throwApiError`，`apps/web/src/store/workspace-store.ts` 中的 `normalizeSuggestionOptions`、`pickLatestDecision`。
- React 事件处理函数使用 `handleXxx` 命名，样例见 `apps/web/src/components/auth/auth-form.tsx` 中的 `handleSubmit`、`handleSchemaRetry`。
- React hook 使用 `useXxx` 命名，样例见 `apps/web/src/hooks/use-auth-guard.ts`、`apps/web/src/hooks/use-schema-gate.ts`。
- 后端函数使用 `snake_case`，内部辅助函数常以前导下划线标记，样例见 `apps/api/app/services/messages.py` 中的 `_build_assistant_error_event`、`_prepare_message_stream`，`apps/api/app/services/model_gateway.py` 中的 `_extract_json_object_content`。

**Variables:**
- 前端局部变量与状态字段使用 `camelCase`，样例见 `apps/web/src/components/auth/auth-form.tsx` 中的 `schemaRecoveryAction`、`errorRecoveryAction`。
- 前端常量使用 `UPPER_SNAKE_CASE`，样例见 `apps/web/src/lib/api.ts` 中的 `API_BASE_URL`、`SCHEMA_OUTDATED_DETAIL`，`apps/web/src/components/workspace/assistant-turn-card.tsx` 中的 `DECISION_GUIDANCE_REASON_LABEL`。
- 后端模块级常量使用 `UPPER_SNAKE_CASE`，样例见 `apps/api/app/services/messages.py` 中的 `SYSTEM_PROMPT`、`apps/api/tests/test_messages_service.py` 中的 `PRD_META_CONTRACT_CASES`。
- 后端临时对象与 fixture 名称保持 `snake_case`，样例见 `apps/api/tests/conftest.py` 中的 `testing_session_local`、`seeded_session`。

**Types:**
- 前端 TypeScript `interface`、`type`、组件 props 名称使用 `PascalCase`，不加 `I` 前缀，样例见 `apps/web/src/lib/types.ts` 中的 `SessionSnapshotResponse`、`PrdState`，`apps/web/src/components/auth/auth-form.tsx` 中的 `AuthFormProps`。
- 前端联合字面量类型多用于状态枚举，样例见 `apps/web/src/store/workspace-store.ts` 中的 `type StreamPhase = "idle" | "waiting" | "streaming"`。
- 后端异常类型和类名使用 `PascalCase`，样例见 `apps/api/app/core/api_error.py` 中的 `ApiError`、`apps/api/app/services/model_gateway.py` 中的 `ModelGatewayError`。

## Code Style

**Formatting:**
- 未检测到独立的 Prettier、ESLint 或 Biome 配置文件；`/Users/zhangyanhua/AI/chat-prd2` 与 `apps/web` 下均未发现 `.prettierrc`、`.eslintrc*`、`eslint.config.*`、`biome.json`。
- 前端代码以 TypeScript 严格模式为准，`apps/web/tsconfig.json` 开启 `strict: true`、`noEmit: true`、`moduleResolution: "bundler"`。
- 前端文件现状以 2 空格缩进、双引号、保留分号为主，样例见 `apps/web/src/lib/api.ts`、`apps/web/src/components/auth/auth-form.tsx`、`apps/web/vitest.config.ts`。
- 后端文件遵循 4 空格缩进、PEP 8 风格、显式类型标注优先，样例见 `apps/api/app/core/api_error.py`、`apps/api/app/services/auth.py`、`apps/api/app/services/model_gateway.py`。

**Linting:**
- 未检测到可执行的前端 lint 脚本；根 `package.json` 仅定义 `dev:web`、`dev:api`、`test:web`、`test:api`，`apps/web/package.json` 仅定义 `dev`、`build`、`start`、`test`。
- 当前仓库的实际约束来自现有文件风格与 TypeScript/Python 编译或运行时校验，而不是独立 lint 配置。

## Import Organization

**Order:**
1. 标准库或框架依赖先放顶部，样例见 `apps/web/src/components/auth/auth-form.tsx` 中的 `next/*`、`react` 导入，`apps/api/app/services/model_gateway.py` 中的 `json`、`logging`、`httpx` 导入。
2. 前端内部模块优先使用 `../`、`../../` 相对路径；样例见 `apps/web/src/components/auth/auth-form.tsx`。
3. 前端 type-only 导入使用 `import type` 单独声明，通常放在普通导入之后、内部依赖之前或之间，样例见 `apps/web/src/lib/api.ts`、`apps/web/src/test/workspace-store.test.ts`。
4. 后端内部模块统一走 `app.*` 绝对导入，样例见 `apps/api/app/api/routes/auth.py`、`apps/api/app/services/messages.py`、`apps/api/tests/test_model_gateway.py`。

**Grouping:**
- 前端导入组之间通常留一个空行；样例见 `apps/web/src/components/auth/auth-form.tsx`、`apps/web/src/test/workspace-page.test.tsx`。
- 后端导入通常按“标准库 / 第三方 / 本地 app 模块”分组，组间留空行；样例见 `apps/api/tests/conftest.py`、`apps/api/app/services/messages.py`。
- 后端多个同源导入通常拆成逐行 `from ... import ...`，而不是一行导入多个名字，样例见 `apps/api/app/services/messages.py`、`apps/api/tests/test_messages_stream.py`。

**Path Aliases:**
- `apps/web/tsconfig.json` 定义了 `@/* -> ./src/*`，`apps/web/vitest.config.ts` 也同步配置了 `@` 别名。
- 现有前端源码大多仍使用相对路径；新增代码应优先延续所在目录现有风格，不要强行混用别名与相对路径。

## Error Handling

**Patterns:**
- 前端 API 层统一把非 2xx 响应转换为 `ApiError`，样例见 `apps/web/src/lib/api.ts` 中的 `throwApiError`、`requestJson`、`requestVoid`。
- 前端组件或 hook 在边界层 `try/catch`，把异常落为 UI 状态或恢复动作，样例见 `apps/web/src/components/auth/auth-form.tsx` 中的 `handleSubmit`、`handleSchemaRetry`，`apps/web/src/lib/stream-error.ts`。
- 后端业务层对可预期业务错误优先使用 `raise_api_error(...)` 返回结构化错误，样例见 `apps/api/app/core/api_error.py`、`apps/api/app/services/auth.py`、`apps/api/app/services/message_preparation.py`。
- 后端对数据库或网关调用常用 `try/except` 包裹，并在失败时 `rollback`、记录日志或转译异常，样例见 `apps/api/app/services/auth.py`、`apps/api/app/services/model_gateway.py`、`apps/api/app/services/messages.py`。

**Error Types:**
- 前端对需要登录的请求在 401 时清理状态并重定向，样例见 `apps/web/src/lib/api.ts` 中的 `redirectToLogin`。
- 后端对认证失效返回带 `code`、`message`、`recovery_action` 的统一错误对象，样例见 `apps/api/app/services/auth.py` 与 `apps/api/tests/test_auth.py`。
- 需要兼容 FastAPI 默认行为的地方仍直接抛 `HTTPException`，样例见 `apps/api/app/services/auth.py` 的重复注册/密码错误，`apps/api/app/api/routes/admin_model_configs.py` 的 403/404。

## Logging

**Framework:**
- 后端使用标准库 `logging`，通过 `logging.getLogger(__name__)` 创建模块 logger，样例见 `apps/api/app/services/model_gateway.py`、`apps/api/app/services/messages.py`、`apps/api/app/services/legacy_session_backfill.py`。
- 前端没有统一日志封装；少量组件直接使用 `console.error` 记录边界失败，样例见 `apps/web/src/components/workspace/conversation-panel.tsx`、`apps/web/src/components/workspace/prd-panel.tsx`、`apps/web/src/components/workspace/composer.tsx`。

**Patterns:**
- 后端日志主要记录上游请求失败、非 JSON 响应、流式解析异常和回退路径，样例见 `apps/api/app/services/model_gateway.py`、`apps/api/app/agent/pm_mentor.py`。
- 日志消息倾向附带上下文信息，如 `url`、`status`、`content_type`、`body_preview`，样例见 `apps/api/app/services/model_gateway.py`。
- 新增前端代码不要扩散 `console.log`；若必须记录客户端异常，保持在边界组件并沿用 `console.error("中文说明", error)` 这种格式。

## Comments

**When to Comment:**
- 前端仅在非显然 API 约束或组件尺寸约束处使用简短注释，样例见 `apps/web/src/components/workspace/spinner.tsx`、`apps/web/src/components/workspace/brand-icon.tsx`、`apps/web/src/lib/stream-error.ts`。
- 后端在规则判断、兼容逻辑和复杂编排处使用中文注释或 docstring 解释“为什么”，样例见 `apps/api/app/agent/runtime.py`、`apps/api/app/services/message_preparation.py`、`apps/api/app/agent/prd_updater.py`。
- 测试里允许用注释标注需求映射或特殊约束，样例见 `apps/web/src/test/workspace-left-nav-grouping-pbt.test.tsx`、`apps/api/tests/test_prd_updater.py`。

**JSDoc/TSDoc:**
- 前端不是普遍使用 JSDoc/TSDoc；仅在少数 props 或辅助结构上使用块注释，样例见 `apps/web/src/store/auth-store.ts`、`apps/web/src/lib/stream-error.ts`。
- 后端更常用 Python docstring，尤其在 agent 或服务辅助函数上，样例见 `apps/api/app/services/model_gateway.py`、`apps/api/app/agent/runtime.py`。

**TODO Comments:**
- 未检测到活跃的 TODO 约定在前端或后端主代码中大规模使用；新增 TODO 时应附明确上下文，避免无指向的占位备注。

## Function Design

**Size:**
- 前端简单工具函数保持小而纯，复杂状态逻辑会拆到 helper 函数，样例见 `apps/web/src/store/prd-store-helpers.ts`、`apps/web/src/lib/recovery-action.ts`。
- 后端复杂服务文件允许较大体量，但通过 `_helper` 函数拆分流程，样例见 `apps/api/app/services/messages.py`、`apps/api/app/services/model_gateway.py`。

**Parameters:**
- 前端组件 props 使用对象参数并显式定义 `Props` 接口，样例见 `apps/web/src/components/auth/auth-form.tsx`、`apps/web/src/components/workspace/workspace-entry.tsx`。
- 前端 API/工具函数在参数较少时保留位置参数，样例见 `apps/web/src/lib/api.ts` 中的 `login(email, password)`、`sendMessage(sessionId, content, accessToken?, signal?, modelConfigId?)`。
- 后端服务函数常把依赖资源放在前面，例如 `db: Session`、`session_id: str`，样例见 `apps/api/app/services/auth.py`、`apps/api/app/services/messages.py`。

**Return Values:**
- 前端大量使用早返回和显式 `null`/空数组保护，样例见 `apps/web/src/store/workspace-store.ts` 中的 `normalizeBestQuestions`、`normalizeSuggestionOptions`。
- 后端返回类型尽量显式声明，辅助函数常返回 `str | None`、`dict[str, Any]`、具名 schema 或 ORM 模型，样例见 `apps/api/app/services/model_gateway.py`、`apps/api/app/api/routes/auth.py`。

## Module Design

**Exports:**
- 前端普通模块优先命名导出，样例见 `apps/web/src/lib/api.ts`、`apps/web/src/store/workspace-store.ts`、`apps/web/src/components/workspace/workspace-entry.tsx`。
- Next.js 路由文件使用默认导出页面组件，样例见 `apps/web/src/app/page.tsx`、`apps/web/src/app/workspace/page.tsx`、`apps/web/src/app/admin/models/page.tsx`。
- 后端模块通过显式函数和类暴露能力，不依赖 barrel file，样例见 `apps/api/app/core/api_error.py`、`apps/api/app/services/auth.py`。

**Barrel Files:**
- 前端 `apps/web/src` 下未检测到 `index.ts`/`index.tsx` barrel file。
- 后端按包目录组织，但导入时直接引用具体模块路径 `app.services.messages`、`app.repositories.sessions`，不要新增含糊的聚合出口。

---

*Convention analysis: 2026-04-16*
