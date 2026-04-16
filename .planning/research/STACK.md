# Stack Research

**Domain:** 面向独立开发者的 AI brainstorming / PRD-copilot 增强栈
**Researched:** 2026-04-16
**Confidence:** HIGH

## Recommended Stack

先给结论：这类能力升级不该推倒现有应用壳。2026 年标准做法不是再套一层“更聪明的聊天框架”，而是在现有 `Next.js + FastAPI + PostgreSQL` 之上，补齐 5 个基础件：

1. **Typed policy engine**：明确当前在探索、澄清、比较还是收敛。
2. **Structured outputs**：所有分析结果、问题清单、PRD patch 都输出为强类型对象，不靠脆弱 JSON 字符串。
3. **Issue ledger + semantic recall**：把“矛盾、缺口、假设、已确认结论”存成一等数据，而不是只留在消息流里。
4. **Prompt / trace / eval loop**：每次 prompt 调整都能被观测、回放、打分。
5. **Option-first UI contract**：后端返回“可反应选项 + 下一步动作”，前端只负责渲染，不负责决定对话策略。

### Core Technologies

| Technology | Version | Purpose | Why Recommended | Confidence |
|------------|---------|---------|-----------------|------------|
| 现有 Web 壳：Next.js | 15.x 继续沿用；绿色田野基线可看 16.2.x | 工作台 UI、流式会话、PRD 编辑与导出 | 这次需求是能力增强，不是框架迁移。对已有产品，**先保留现有 Next.js 壳**，避免把研究重点浪费在升级成本上；如果是新模块或新项目，2026 当前基线已进入 16.x。 | HIGH |
| 现有 UI 核心：React | 19.x | 工作台交互、流式消息、增量状态更新 | React 19 仍是这类交互密集工作台的主流基础；对现有产品继续沿用即可，不值得为了 brainstorm 能力再换前端范式。 | HIGH |
| FastAPI | 0.135.3 | 后端 API、SSE/流式输出、agent/policy 服务承载 | 对 Python LLM 后端仍是最稳妥的生产选择：类型友好、Pydantic 深度集成、SSE 和 async 生态成熟，适合把“对话策略 + PRD 合成”做成显式服务层。 | HIGH |
| Pydantic | 2.13.1 | 定义 `TurnAnalysis`、`IssueLedgerItem`、`ConvergenceScore`、`PrdPatch` 等强类型对象 | 这类产品的核心不是“生成一段字”，而是稳定地产生结构化中间件。Pydantic 2 是 Python 侧 schema 和运行时校验标准件。 | HIGH |
| OpenAI Python SDK | 2.32.0 | 结构化输出、Responses API、流式响应 | 2026 的标准实现已经从“拼 JSON 提示词”转向 **SDK 原生结构化解析**。如果主模型供应商支持 schema / Pydantic 直出，应优先走这个路径。 | HIGH |
| LiteLLM | 1.83.8 | 模型路由、fallback、限额、统一 OpenAI 格式网关 | 对已有 AI 产品，最实用的做法不是在业务代码里到处写多家模型兼容，而是在网关层统一。LiteLLM 已经是 2026 常见的 provider abstraction 方案。 | HIGH |
| PostgreSQL | 18.x 新部署优先；现有生产至少保持 17.x | 会话、PRD 快照、issue ledger、结构化状态主存储 | 这类产品的“真相源”是关系数据，不是向量库。PRD 收敛依赖事务、一致性、审计历史、局部更新，Postgres 仍是最佳主库。 | HIGH |
| pgvector 扩展 | 0.8.2 | 会话内语义召回、矛盾检测前的近邻检索、历史结论复用 | 你要检索的是“同一会话/同一项目里说过什么”，不是互联网级知识库。把 embedding 跟关系数据放一起，复杂度最低，足够支撑语义回看。 | HIGH |
| SQLAlchemy | 2.0.49 | 数据访问层、typed ORM / SQL、事务边界 | 适合把消息、issue、snapshot、evidence、embedding 元数据纳入一套一致事务中，不需要再引入新的数据访问抽象。 | HIGH |
| psycopg | 3.3.3 | PostgreSQL 驱动 | 2026 Python/Postgres 主流驱动，异步/同步两侧都稳。 | HIGH |

### Supporting Libraries

| Library | Version | Purpose | When to Use | Confidence |
|---------|---------|---------|-------------|------------|
| Zod | 4.3.6 | 前端校验后端返回的结构化动作，如 `assistant_action`、`option_set`、`prd_patch_preview` | 只要前端要根据后端返回的结构对象渲染不同 UI，就应该加；不要信任后端 JSON 直接进 store。 | HIGH |
| Langfuse Python | 4.2.0 | LLM traces、prompt versioning、datasets、评测实验 | 只要你准备迭代 prompt 和 judge 规则，就应该上；这是把“感觉更好了”变成“能比较、能回归”的最短路径。 | HIGH |
| `@langfuse/client` / `@langfuse/openai` | 5.1.0 | 前后端链路关联、前端事件到后端 trace 关联、prompt 版本关联 | 当你要把用户点击选项、确认 PRD、回滚快照与具体 LLM 输出关联起来时使用。 | HIGH |
| OpenTelemetry SDK | 1.41.0 | API 请求、数据库、下游 LLM 调用 tracing | 如果 Langfuse 解决的是 LLM 可观测性，OpenTelemetry 解决的是系统可观测性；二者要并存，不互斥。 | HIGH |
| Promptfoo | 4.3.6 | 离线回归评测，验证矛盾识别、缺口识别、收敛判断、PRD 合成质量 | 当你开始改 prompt / policy 时就应引入；没有 regression eval，这个方向会很快退化成“调一次坏一次”。 | MEDIUM |
| LangGraph | 1.1.6 | 仅在多节点、可中断、需 durable execution 的复杂工作流时使用 | **不是默认推荐**。当你的现有 agent 层已经演变成显式图流程、存在人工确认节点、后台长任务恢复需求时再上。 | MEDIUM |
| PydanticAI | 1.82.0 | 仅在你希望进一步强化 typed agent 封装时作为备选 | 适合偏 Python-only 的 typed agent 开发，但对已有 FastAPI agent 层不是必须新增依赖。 | MEDIUM |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| Langfuse | 观察 prompt、模型、输出、用户反馈、实验对比 | 把“矛盾识别命中率”“PRD 合成稳定性”做成可比实验，不要只看日志。 |
| Promptfoo | 建立回归数据集与 judge 规则 | 最少准备四类数据集：矛盾检测、缺口检测、收敛判断、PRD consolidation。 |
| OpenTelemetry + OTLP collector | 追踪 FastAPI 请求、SQL、LLM 延迟、错误链路 | 前端事件 ID、会话 ID、trace ID 要贯通；否则很难定位“是模型问题还是策略问题”。 |

## Installation

```bash
# apps/web
pnpm add zod @langfuse/client @langfuse/openai
pnpm add -D promptfoo

# apps/api
pip install \
  fastapi==0.135.3 \
  pydantic==2.13.1 \
  openai==2.32.0 \
  litellm==1.83.8 \
  sqlalchemy==2.0.49 \
  "psycopg[binary]==3.3.3" \
  langfuse==4.2.0 \
  opentelemetry-sdk==1.41.0 \
  pgvector==0.4.2

# optional only when workflow complexity justifies it
pip install langgraph==1.1.6 pydantic-ai==1.82.0
```

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| **自建 typed policy engine（挂在现有 FastAPI agent 层）** | LangGraph 1.1.6 | 当流程已经明显是图结构：需要中断恢复、人工确认节点、后台长任务、分支编排时。对当前“增强收敛能力”阶段，先不要引入第二套编排抽象。 |
| **PostgreSQL + pgvector** | Pinecone / Weaviate / Milvus | 只有在你把检索范围扩到大规模跨项目知识库、向量规模明显超出单库承载时再考虑。对会话级 PRD 收敛，不值得先拆出去。 |
| **LiteLLM 网关** | 直接调用单一模型供应商 SDK | 如果你已经确定 12 个月内只用单一供应商，而且没有预算控制、fallback、AB provider 对比需求，可以先直连。否则建议从一开始就统一入口。 |
| **Langfuse + Promptfoo** | 自建日志表 + 脚本对比 | 只有在团队极度克制、评测需求很轻时才勉强成立。只要要频繁改 prompt / policy，就不要自己发明一套评测平台。 |
| **OpenAI SDK 原生 structured outputs / Pydantic parse** | 手写“输出 JSON，失败就重试”的 prompt 模式 | 仅在供应商不支持 schema 约束时退而求其次；否则这是 2026 已经不该继续依赖的旧做法。 |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| 通用“自动代理”式对话循环 | 对 brainstorm / PRD 收敛场景太不稳定，容易失控追问、跳题、重复确认，且很难评测 | 显式 `policy engine + typed state + deterministic transitions` |
| LangChain 式厚封装作为默认中间层 | 这类能力重点在状态、评测、可控性，不在“多工具炫技”；过厚抽象会让诊断更难 | 直接使用 FastAPI 服务层 + Pydantic schema，必要时再局部引入 LangGraph |
| 独立向量数据库作为第一步 | 过早拆分数据面，增加同步、部署、运维成本；会话级 recall 完全没必要 | PostgreSQL + pgvector |
| 把“矛盾/缺口/假设”只存在消息文本里 | 之后无法可靠检索、打分、回放，也无法驱动 UI | 建立 `issue_ledger`、`evidence_link`、`convergence_state` 表 |
| 把提示词硬编码在前端组件里 | 无法版本化、回滚、实验比较，也会让前后端职责混乱 | 后端集中管理 prompt，Langfuse 做版本与实验 |
| 让前端决定下一轮该问什么 | 策略会分散到 UI 层，导致产品行为不可控 | 后端返回 `assistant_action`，前端只渲染和回传用户选择 |
| 依赖“原始自由文本 PRD 总结”作为唯一产物 | 不利于局部修补、冲突定位和逐步确认 | PRD 使用结构化 section + patch 合成，再导出文本 |

## Stack Patterns by Variant

**If 你现在只是给现有产品加更强收敛能力（本项目当前情况）：**
- 使用 **现有 Next.js 工作台 + 现有 FastAPI agent 层 + Postgres 主库**
- 后端新增 `policy engine`、`turn analyzer`、`issue ledger`、`prd consolidator`
- 不要在这个阶段引入 LangGraph、独立向量库、复杂消息总线
- 因为你的主要风险是“策略不稳”，不是“系统扛不住”

**If 你后续要支持复杂多阶段编排、人工确认、恢复执行：**
- 在现有 agent 层后面引入 **LangGraph 1.1.6**
- 只让它负责编排与 checkpoint，不要把业务数据模型和 UI contract 绑死在框架里
- 因为 LangGraph 适合“显式图 + 可恢复状态”，不适合替代你的领域模型

**If 你短期内只用单一模型供应商：**
- 可先跳过 LiteLLM，直接用供应商 SDK 的 structured outputs
- 但 prompt/version/eval 仍然要用 Langfuse 或等价平台
- 因为省掉 provider abstraction 可以减小首轮改造面，但不能省掉观测和评测

**If 你要做更强的跨会话知识复用：**
- 先在 Postgres 中扩展 `project_memory`, `pattern_library`, `validated_assumptions`
- 只有在规模或查询性能明显超标时才拆独立 retrieval service
- 因为当前最重要的是“统一真相源”，不是提早做基础设施分层

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| `fastapi==0.135.3` | `pydantic==2.13.1` | 当前 FastAPI 已深度建立在 Pydantic v2 生态上，新的 typed response / request 建议统一走 v2 模型。 |
| `sqlalchemy==2.0.49` | `psycopg==3.3.3` | Python/Postgres 主流生产组合。 |
| `postgresql 17/18` | `pgvector extension 0.8.2` | pgvector 官方说明支持 Postgres 13+；新部署优先 18，现有生产保持 17/18 都合理。 |
| `openai==2.32.0` | `pydantic==2.13.1` | 适合直接用 Pydantic schema 做 structured outputs / parse。 |
| `@langfuse/client==5.1.0` | `langfuse==4.2.0` | 前后端分别埋点，没有强耦合版本绑定，但建议同一时期升级，避免 trace 字段语义漂移。 |
| `litellm==1.83.8` | OpenAI-compatible clients / provider SDKs | 适合作为统一入口；若已接入 LiteLLM，就尽量避免业务层同时直连多家模型 API。 |

## Recommended Implementation Approach

标准实现不是“让模型自己想下一步”，而是后端按以下流水线执行：

1. **Turn Analysis**
   - 输入：用户新消息 + 当前会话结构化状态 + 最近 PRD snapshot + issue ledger
   - 输出：`TurnAnalysis`
   - 字段至少包括：`facts`, `goals`, `constraints`, `assumptions`, `contradictions`, `gaps`, `confidence`, `candidate_axes`

2. **Issue Ledger Update**
   - 把每个矛盾、缺口、假设写入结构化表
   - 每条 issue 要有状态：`open`, `tentatively_resolved`, `confirmed`, `discarded`
   - issue 要能链接到证据消息和 PRD section

3. **Semantic Recall**
   - 对“当前用户说法”和“现有开放 issue”做 embedding
   - 用 pgvector 召回同一会话或同一项目中相关 statement / issue / PRD section
   - 召回后再做规则过滤，不要只靠向量相似度直接下判断

4. **Convergence Policy**
   - 输出一个显式枚举：`explore`, `clarify`, `compare_options`, `converge`, `confirm_prd`
   - 判断依据至少包含：开放 issue 数、近几轮新增信息量、用户确认信号、关键字段完整度
   - 这一步要 deterministic first，LLM 只辅助打分，不负责最终随意选模式

5. **Assistant Action Generation**
   - 后端返回一个强类型 `assistant_action`
   - 结构建议包含：`mode`, `question`, `option_set`, `why_this_next`, `issue_refs`, `prd_patch_preview`
   - UI 必须优先渲染选项，支持“一键选择 + 补充说明”

6. **PRD Consolidation**
   - 不要每轮重写整份 PRD
   - 用 section-based patch：`target_section`, `before`, `after`, `confidence`, `depends_on_issue_ids`
   - 这样才方便做回滚、差异展示、用户确认和最终导出

## Sources

- `/vercel/next.js` — 通过 Context7 确认 Next.js 当前文档版本轨迹，16.x 已可见；对本项目建议保持现有壳不在本轮升级
- `/reactjs/react.dev`、`/facebook/react` — 通过 Context7 确认 React 19.x 仍是当前主流稳定线
- `/fastapi/fastapi` + PyPI `fastapi 0.135.3` — 确认 FastAPI 当前版本与生产适配性
- `/pydantic/pydantic` + PyPI `pydantic 2.13.1` — 确认 Pydantic v2 作为强类型 schema 基线
- `/openai/openai-python` + PyPI `openai 2.32.0` — 确认 Responses API、structured outputs、Pydantic parse 能力
- `/berriai/litellm` + PyPI `litellm 1.83.8` — 确认统一 OpenAI 格式、fallback、budget、proxy 能力
- `/pgvector/pgvector` + GitHub 官方仓库 README — 确认 pgvector 0.8.2、HNSW、iterative scan、Postgres 13+ 支持
- `/websites/postgresql_18` + PostgreSQL 官方文档 — 确认 PostgreSQL 18 为 current，18.3 / 17.9 等版本在 2026-02-26 发布
- `/langfuse/langfuse-docs` + PyPI / npm registry — 确认 prompt management、datasets、experiments、SDK 当前版本
- `/open-telemetry/opentelemetry-python` + PyPI `opentelemetry-sdk 1.41.0` — 确认 FastAPI / requests / SQL instrumentation 能力
- PyPI `langgraph 1.1.6`, `pydantic-ai 1.82.0`; npm `zod 4.3.6`, `promptfoo 4.3.6` — 用于版本校验

---
*Stack research for: AI brainstorming / PRD convergence enhancement*
*Researched: 2026-04-16*
