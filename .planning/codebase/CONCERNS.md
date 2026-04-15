# Codebase Concerns

**Analysis Date:** 2026-04-16

## Tech Debt

**消息编排逻辑双份实现：**
- Issue: `apps/api/app/services/messages.py` 与 `apps/api/app/services/message_preparation.py` 同时维护模型选择、会话历史构建、流式准备、异常映射与日志字段，形成并行实现。
- Files: `apps/api/app/services/messages.py`, `apps/api/app/services/message_preparation.py`
- Impact: 任一侧修复或扩展后，另一侧容易遗漏，消息发送与重生成路径会出现行为漂移，后续重构成本高。
- Fix approach: 以 `message_preparation` 或单一 orchestration service 为唯一入口，`messages.py` 仅负责事件编排与持久化，禁止再次复制准备逻辑。

**前端工作台状态机集中在单一大文件：**
- Issue: 工作台流式事件消费、PRD 合并、回复版本历史、请求生命周期和导航状态全部堆叠在 `apps/web/src/store/workspace-store.ts` 一个约 1000 行的 store 中。
- Files: `apps/web/src/store/workspace-store.ts`
- Impact: 新增一个 SSE 事件或修改 hydrate 语义时，极易影响 `startRequest`、`assistant.done`、`refreshSessionSnapshot` 等相邻分支，回归面大。
- Fix approach: 拆分为 `hydration`、`stream lifecycle`、`reply history`、`prd projection` 四个 reducer/模块，并为事件处理建立契约测试。

**管理员模型配置页承担过多职责：**
- Issue: `apps/web/src/components/admin/model-config-admin-page.tsx` 同时处理权限分支、CRUD 表单、推荐排序、恢复理由推导和预览 UI。
- Files: `apps/web/src/components/admin/model-config-admin-page.tsx`
- Impact: 任何表单字段调整都可能连带破坏推荐预览与交互状态，维护难度接近页面级应用。
- Fix approach: 把表单状态、排序逻辑、推荐解释和列表渲染拆成独立 hooks/components，并让页面只负责装配。

## Known Bugs

**流式回复中断后会留下“只有用户消息、没有助手镜像”的会话状态：**
- Symptoms: 用户消息已经写入数据库，但如果上游模型流或客户端连接在持久化助手回复前中断，快照中会出现没有对应 assistant message 的 user turn。
- Files: `apps/api/app/services/message_preparation.py`, `apps/api/app/services/messages.py`, `apps/api/app/repositories/messages.py`
- Trigger: `prepare_message_stream()` 在打开流前先 `create_message(... role=\"user\")` 并 `db.commit()`，而 `persist_assistant_reply_and_version()` 只在流正常结束后执行。
- Workaround: 重新生成该轮消息，或重新加载会话后继续对话。
- Root cause: 用户消息持久化与助手回复持久化分成两个事务，中间没有断流补偿、超时清理或 orphan repair。

**服务重启会导致既有 token 全部失效：**
- Symptoms: 已登录用户在服务重启后会被强制登出，旧 token 无法再通过鉴权。
- Files: `apps/api/app/core/security.py`, `apps/api/app/core/config.py`
- Trigger: 未设置 `AUTH_SECRET_KEY` 时，`apps/api/app/core/security.py` 会生成随机 `SECRET_KEY`。
- Workaround: 显式配置固定 `AUTH_SECRET_KEY`，然后要求用户重新登录。
- Root cause: JWT 签名密钥不是稳定配置而是进程启动时随机生成的后备值。

## Security Considerations

**仓库文档直接暴露真实连接信息与密钥样例：**
- Risk: `README.md` 明文包含 `DATABASE_URL`、`AUTH_SECRET_KEY` 和可访问主机信息，文档一旦外泄即形成真实凭据泄露事件。
- Files: `README.md`
- Current mitigation: 未检测到脱敏、占位符替换或安全说明。
- Recommendations: 立即把示例改为占位符，轮换已暴露凭据，并把真实配置迁移到 `.env.example` 的脱敏模板。

**模型供应商凭据明文存库并明文回显到前端：**
- Risk: `LLMModelConfig.api_key` 以明文保存，管理员接口 `ModelConfigAdminResponse` 直接返回 `api_key`，前端表单状态继续把它保存在浏览器内存中。
- Files: `apps/api/app/db/models.py`, `apps/api/app/repositories/model_configs.py`, `apps/api/app/schemas/model_config.py`, `apps/api/app/api/routes/admin_model_configs.py`, `apps/web/src/components/admin/model-config-admin-page.tsx`, `apps/web/src/lib/types.ts`
- Current mitigation: 仅 `/api/model-configs/enabled` 对普通用户隐藏 `api_key` 与 `base_url`；管理员读接口未做脱敏。
- Recommendations: 至少做服务端加密存储和回显脱敏，更新接口为“只写不读” secret 字段，前端仅展示掩码与“重新输入后覆盖”流程。

**访问令牌持久化在 localStorage：**
- Risk: `accessToken` 通过 Zustand persist 写入 `window.localStorage`，一旦页面出现 XSS，令牌可被直接窃取。
- Files: `apps/web/src/store/auth-store.ts`
- Current mitigation: 未检测到 HttpOnly cookie、token rotation 或 CSP 级别的补偿措施。
- Recommendations: 改为 HttpOnly secure cookie 会话，至少补充 CSP、短期 token + refresh 机制与登出失效策略。

**鉴权没有速率限制或登录防暴力破解：**
- Risk: 登录与注册接口对尝试频率没有限制，密码校验直接走 bcrypt，比对成本可被恶意放大为应用层 DoS。
- Files: `apps/api/app/api/routes/auth.py`, `apps/api/app/services/auth.py`
- Current mitigation: 仅有 bcrypt 哈希与 Bearer token 校验，未检测到 IP/用户维度限流、验证码或锁定策略。
- Recommendations: 为 `/api/auth/login` 和 `/api/auth/register` 增加限流、失败计数、审计日志和异常峰值告警。

## Performance Bottlenecks

**会话快照读取存在按回复组逐个加载版本的 N+1 模式：**
- Problem: `get_session_snapshot()` 先拉取所有 reply group，再在 `_list_assistant_reply_groups()` 内对每个 group 单独查询 `list_versions_for_group()`。
- Files: `apps/api/app/services/sessions.py`, `apps/api/app/repositories/assistant_reply_versions.py`
- Measurement: 仓库内未提供基准数据；从代码路径看，回复组数量越多，数据库 round-trip 数量线性上升。
- Cause: 会话聚合使用逐组查询而不是一次性批量预取。
- Improvement path: 改成单次按 `session_id` 拉取全部版本并在内存分组，或用 ORM eager loading/手写 join 返回聚合结果。

**每次消息生成都会把完整会话历史重新发送给模型：**
- Problem: `build_gateway_messages()` 与 `build_gateway_messages_for_regenerate()` 每轮都读取整个会话消息序列并拼成上游模型输入。
- Files: `apps/api/app/services/message_preparation.py`, `apps/api/app/repositories/messages.py`
- Measurement: 仓库内未提供 token 或延迟统计；从实现看，请求成本会随历史长度持续增长。
- Cause: 没有摘要压缩、窗口裁剪、分层记忆或缓存过往上下文。
- Improvement path: 增加 conversation window、历史摘要、阶段性压缩快照，并把完整历史与模型输入解耦。

## Fragile Areas

**SSE 事件契约跨前后端手工同步：**
- Files: `apps/api/app/services/messages.py`, `apps/api/app/schemas/message.py`, `apps/web/src/lib/sse.ts`, `apps/web/src/store/workspace-store.ts`
- Why fragile: 事件名、字段名和时序完全靠手工保持一致，前端 `parseSseEventBlock()` 与 `applyEvent()` 没有运行时 schema 校验。
- Safe modification: 修改任一 SSE payload 前，先同步更新后端 schema、前端解析器和 store 分支，并补充端到端事件顺序测试。
- Test coverage: 有 `apps/api/tests/test_messages_stream.py` 与 `apps/web/src/test/workspace-store.test.ts`，但没有覆盖“后端字段新增/缺失时的兼容退化”。

**迁移检测、旧会话回填和快照加载耦合在同一读取路径：**
- Files: `apps/api/app/main.py`, `apps/api/app/services/sessions.py`, `apps/api/app/services/legacy_session_backfill.py`, `apps/web/src/components/workspace/workspace-session-shell.tsx`
- Why fragile: 健康检查、schema 过旧提示、legacy backfill 和会话 hydrate 形成串联链路，任何一段异常都会让工作台直接进入错误态。
- Safe modification: 变更数据库结构时，先补 migration 测试、健康检查断言和旧会话回填测试，再调整前端错误恢复动作。
- Test coverage: 有 `apps/api/tests/test_health.py`、`apps/api/tests/test_sessions.py`、`apps/web/src/test/workspace-session-shell.test.tsx`，但没有覆盖“部分表存在、部分旧数据字段缺失、并发读取回填”的组合场景。

## Scaling Limits

**单会话上下文长度与快照体积会持续线性增长：**
- Current capacity: 代码中未设置消息条数、PRD 版本数、回复版本数或导出长度上限。
- Files: `apps/api/app/repositories/messages.py`, `apps/api/app/services/message_preparation.py`, `apps/api/app/services/sessions.py`, `apps/api/app/services/exports.py`
- Limit: 会话历史越长，数据库读取、SSE hydrate、导出体积和上游模型 token 成本一起增长。
- Scaling path: 为消息历史、PRD 快照和回复版本引入归档/摘要策略，给导出与会话读取增加分页或截断能力。

## Dependencies at Risk

**OpenAI 兼容接口假设过强：**
- Risk: 模型网关默认把任意 `base_url` 规范到 `/chat/completions` 并假设返回 OpenAI 风格 JSON/SSE；供应商稍有差异就会抛 `ModelGatewayError`。
- Files: `apps/api/app/services/model_gateway.py`
- Impact: 新模型供应商接入成本高，兼容性问题会直接暴露为消息流失败。
- Migration plan: 为不同 provider 建立 adapter 层，按供应商定义请求/响应协议，而不是把所有供应商压成单一 OpenAI 兼容假设。

## Missing Critical Features

**缺少 secret 生命周期管理：**
- Problem: 模型 API Key、JWT 密钥和数据库连接信息没有统一的 secret 管理方案，代码与文档里都存在明文入口。
- Files: `README.md`, `apps/api/app/core/config.py`, `apps/api/app/schemas/model_config.py`, `apps/api/app/db/models.py`
- Blocks: 无法安全地把仓库直接开放协作，也无法满足最基本的生产环境凭据治理要求。

**缺少断流补偿与后台重试机制：**
- Problem: 流式生成失败时只向前端发 `assistant.error`，没有后台恢复、重放或 orphan message 清理。
- Files: `apps/api/app/services/message_preparation.py`, `apps/api/app/services/messages.py`
- Blocks: 网络抖动或上游模型不稳定时，用户会话容易留下半完成状态，客服与运维难以修复。

## Test Coverage Gaps

**导出服务缺少独立单元测试：**
- What's not tested: `build_export_sections()`、`build_markdown_export()` 对草稿/终稿/缺失字段的格式化分支只通过 `apps/api/tests/test_sessions.py` 间接覆盖。
- Files: `apps/api/app/services/exports.py`, `apps/api/tests/test_sessions.py`
- Risk: 导出格式轻微调整就可能破坏 markdown 结构，却很难从失败用例快速定位到导出层。
- Priority: Medium

**SSE 解析器缺少独立边界测试：**
- What's not tested: `parseSseEventBlock()` 与 `parseEventStream()` 没有看到独立测试，尤其是多 `data:` 行、半包、非法 JSON 和未知事件类型分支。
- Files: `apps/web/src/lib/sse.ts`
- Risk: 一旦后端事件格式稍有变化，前端可能静默丢事件或直接抛解析异常。
- Priority: High

**断连/取消后的后端一致性没有自动化验证：**
- What's not tested: 现有测试覆盖了 `assistant.error` 事件，但没有覆盖“客户端中途取消连接后数据库是否留下 orphan user message / reply group”的一致性检查。
- Files: `apps/api/app/services/message_preparation.py`, `apps/api/app/services/messages.py`, `apps/api/tests/test_messages_stream.py`, `apps/api/tests/test_messages_service.py`
- Risk: 真实网络环境中的半完成会话问题会长期潜伏，直到用户历史数据积累后才暴露。
- Priority: High

---

*Concerns audit: 2026-04-16*
