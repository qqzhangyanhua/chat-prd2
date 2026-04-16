# Architecture Research

**Domain:** 面向独立开发者的 AI brainstorming / contradiction-gap detection / convergence / PRD copilot
**Researched:** 2026-04-16
**Confidence:** HIGH

## Standard Architecture

### System Overview

```text
┌──────────────────────────────────────────────────────────────────────┐
│                        Web Workspace Layer                          │
├──────────────────────────────────────────────────────────────────────┤
│  Conversation Panel   Guidance / Options UI   PRD Panel   Export UI │
│          │                    │                 │          │         │
├──────────┴────────────────────┴─────────────────┴──────────┴─────────┤
│                    Client Session / Event Store                      │
├──────────────────────────────────────────────────────────────────────┤
│  SSE Stream Applier   Draft State Cache   Decision View Model        │
│          │                    │                 │                    │
├──────────┴────────────────────┴─────────────────┴────────────────────┤
│                     API / Orchestration Layer                        │
├──────────────────────────────────────────────────────────────────────┤
│ Messages API   Session API   Finalize API   Export API               │
│          │           │            │             │                    │
├──────────┴───────────┴────────────┴─────────────┴────────────────────┤
│                    Turn Intelligence Layer                           │
├──────────────────────────────────────────────────────────────────────┤
│  Input Extractor → Gap/Contradiction Judge → Convergence Policy      │
│                  → Reply Planner → PRD Patch Builder                 │
├──────────────────────────────────────────────────────────────────────┤
│                      Domain Persistence Layer                        │
├──────────────────────────────────────────────────────────────────────┤
│  Messages   Turn Decisions   State Snapshots   PRD Snapshots         │
├──────────────────────────────────────────────────────────────────────┤
│                  Model / Tool / Observability Layer                  │
├──────────────────────────────────────────────────────────────────────┤
│  LLM Gateway   Structured Output Schema   Traces / Eval / Replay     │
└──────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| 会话工作台层 | 承接用户输入、显示 AI 回复、渲染可反应选项与 PRD 草稿 | Next.js 页面 + React 组件 + SSE 客户端 |
| 客户端事件状态层 | 把流式事件归并成单一会话真相源，避免 UI 组件直接吃原始流 | Zustand store，按 event type apply |
| API 编排层 | 验证权限、组织消息流、触发 agent 决策与持久化 | FastAPI route + service orchestration |
| 回合智能层 | 负责“本轮该判断什么、问什么、更新什么”，不负责 UI | 独立 agent/runtime + extractor + readiness + updater |
| PRD 状态层 | 保存结构化草稿、状态补丁、确认状态与版本历史 | PostgreSQL + state/prd repositories |
| 模型网关层 | 统一接第三方模型、结构化输出、重试策略与流式协议 | provider adapter / model gateway |
| 评估观测层 | 记录 turn decision、重放关键案例、评估收敛质量 | trace、decision log、offline eval pipeline |

## Recommended Project Structure

```text
apps/
├── web/src/
│   ├── app/workspace/                 # 工作台页面与入口
│   ├── components/workspace/          # 对话面板、引导卡片、PRD 面板
│   ├── store/workspace-store.ts       # SSE 事件归并后的客户端真相源
│   ├── store/prd-store-helpers.ts     # PRD 派生与合并逻辑
│   └── lib/types.ts                   # 决策、PRD、事件的共享协议类型
└── api/app/
    ├── api/routes/                    # sessions/messages/exports/finalize 路由
    ├── services/                      # 流式编排、持久化、PRD runtime
    ├── agent/                         # 回合智能：extract / judge / converge / finalize
    ├── repositories/                  # messages/state/prd/turn_decisions 数据访问
    ├── schemas/                       # message/state/prd 契约
    └── core/                          # provider、错误、配置
```

### Structure Rationale

- **`web/src/store/`**：前端必须以“事件归并后的会话状态”为核心，而不是让组件各自推断对话阶段，否则引导节奏会失真。
- **`api/app/agent/`**：brainstorming、矛盾识别、收敛决策、最终草稿生成要留在独立决策层，避免混进 route/service 后变成难测的提示词泥团。
- **`api/app/services/`**：只做流式编排、事务边界、持久化顺序，不直接承载产品判断。
- **`api/app/repositories/`**：把 message、decision、state、prd 分开存，后续才能做回放、评估、版本比较。

## Architectural Patterns

### Pattern 1: Turn-Based Decision Envelope

**What:** 每次用户输入先产出结构化 `TurnDecision`，再生成自然语言回复与 PRD/state patch。  
**When to use:** 需要解释“为什么现在追问/收敛/确认”，并且后续要做评估与可视化时。  
**Trade-offs:** 比“直接 prompt 一次回复”更复杂，但可测试、可回放、可插入规则保护。

**Example:**
```typescript
type TurnDecision = {
  understanding: {...}
  gaps: string[]
  challenges: string[]
  conversationStrategy: "clarify" | "choose" | "converge" | "confirm"
  nextMove: "probe_for_specificity" | "force_rank_or_choose" | "summarize_and_confirm"
  prdPatch: Record<string, unknown>
  statePatch: Record<string, unknown>
}
```

### Pattern 2: Dual Track State

**What:** 把“对话运行状态”和“PRD 结构化草稿”拆成两条状态轨。  
**When to use:** brainstorming 产品需要既记住对话节奏，又沉淀长期可编辑文档时。  
**Trade-offs:** 要维护两个版本面，但比把所有信息塞进消息历史里稳定得多。

**Example:**
```typescript
type RuntimeState = {
  workflowStage: "idea_parser" | "refine_loop" | "finalize" | "completed"
  conversationStrategy: string
  nextBestQuestions: string[]
}

type PrdDraft = {
  sections: Record<string, { content: string; status: "draft" | "confirmed" | "missing" }>
  version: number
}
```

### Pattern 3: Interruptible Convergence Gate

**What:** 在“是否进入 finalize / 是否接受某个收敛结论”处设置显式闸门，而不是让模型默默切阶段。  
**When to use:** 用户需要对目标用户、核心问题、方案边界进行确认，或导出前需要补洞时。  
**Trade-offs:** 会多一次确认摩擦，但能显著降低错误收敛和错误导出的代价。

## Data Flow

### Request Flow

```text
[用户输入]
    ↓
[web Composer]
    ↓
[workspace-store.startRequest]
    ↓
[POST /api/sessions/{id}/messages]
    ↓
[messages service]
    ↓
[run_agent / turn intelligence]
    ↓
[decision + state_patch + prd_patch + reply]
    ↓
[persist messages / decisions / snapshots]
    ↓
[SSE events: accepted → decision.ready → assistant.delta/done → prd.updated]
    ↓
[workspace-store.applyEvent]
    ↓
[Conversation Panel / Guidance UI / PRD Panel 同步刷新]
```

### State Management

```text
[Workspace Store]
    ↓ subscribe
[Conversation UI] [Guidance UI] [PRD UI]
    ↑                ↑            ↑
    └────── applyEvent / hydrateSession / refreshSnapshot ──────┘
```

### Key Data Flows

1. **Brainstorming flow：** 用户自由输入进入 `messages`，agent 先做抽取与初步理解，再产出可反应选项和下一步提问方向。
2. **Contradiction / gap detection flow：** agent 从当前输入 + 历史 `state/prd` 中比对缺口、冲突、假设，把结果写入 `TurnDecision`，必要时更新 section 状态为 `missing` 而不是强行补全。
3. **Convergence flow：** 当核心 section 已具备基本内容时，收敛策略从 `clarify` 切到 `choose/converge/confirm`，前端据 `decisionGuidance` 渲染取舍卡或确认卡。
4. **PRD drafting flow：** `prd_patch` 不直接覆盖全文，而是按 section merge，形成版本化 PRD snapshot，供右侧面板实时展示和导出。
5. **Finalize / export flow：** `readiness` 检查必填 section 与缺口，只有满足门槛才允许 finalize；导出层只读已确认的最新 PRD snapshot。

## Component Boundaries

### What Talks to What

| Boundary | Communication | Notes |
|----------|---------------|-------|
| `web/components/workspace` ↔ `web/store/workspace-store` | 直接状态订阅 + action 调用 | UI 不应自行推断策略，统一读 store |
| `workspace-store` ↔ `api/routes/messages` | HTTP + SSE | 只传用户输入与模型配置，流中回传结构化事件 |
| `api/routes/messages` ↔ `services/messages.py` | 函数调用 | route 只做鉴权和会话存在性校验 |
| `services/messages.py` ↔ `agent/runtime.py` | 纯 Python 调用 | service 持有事务边界，agent 只负责决策结果 |
| `agent/runtime.py` ↔ `extractor/readiness/prd_updater` | 内部组合 | 把抽取、判断、补丁生成拆开，便于替换策略 |
| `services/*` ↔ `repositories/*` | repository API | 防止 agent 直接触库 |
| `services/model_gateway.py` ↔ 外部 LLM | provider adapter | 统一结构化输出、流式协议、错误语义 |

### Internal Boundary Rules

| Boundary | Rule | Why |
|----------|------|-----|
| UI ↔ Agent | UI 不直接依赖提示词或模型返回原文，只依赖结构化 decision/event | 保持前端可重构、可测试 |
| Service ↔ Agent | agent 不开事务、不直接持久化 | 避免业务判断与持久化顺序耦合 |
| Message History ↔ PRD Draft | 消息历史是证据，不是最终文档 | 防止 PRD 质量被聊天噪声污染 |
| Contradiction Detection ↔ Final Reply | 先产出 machine-readable judgement，再渲染人类可读回复 | 方便后续评估与策略升级 |

## Suggested Build Order

### Dependency Order

```text
结构化状态契约
  → 回合决策记录
    → 缺口/矛盾检测
      → 收敛策略切换
        → PRD section merge 与 finalize gate
          → 前端引导卡与确认卡
            → 评估/观测/回放
```

### Recommended Incremental Build

1. **先固化协议层**  
   明确 `TurnDecision`、`DecisionReadyEventData`、`PrdPatch`、`StatePatch` 的 schema。没有稳定协议，前后端会反复返工。

2. **再加决策持久化与回放**  
   先把每轮决策结果存下来，再优化 prompt。没有 replay，后续无法判断“为什么这轮追问失败”。

3. **然后做 gap / contradiction detector**  
   这是 guided brainstorming 与普通聊天的分水岭，优先级高于“更会写 PRD”。

4. **再做 convergence policy**  
   包括 `clarify → choose → converge → confirm` 的切换规则、finalize readiness、确认点设计。

5. **再增强 PRD drafting**  
   把 section merge、缺口标记、confirmed/draft/missing 状态做稳定，再谈整文润色。

6. **最后补 UI 呈现与评估系统**  
   引导卡、取舍卡、确认卡、版本对比、trace/eval。它们非常重要，但依赖前面的结构化边界已经成立。

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 0-1k 用户 | 保持单体前后端即可，重点放在结构化事件、决策日志、PRD 快照正确性 |
| 1k-100k 用户 | 优先优化流式连接、snapshot 查询、长会话压缩/摘要、LLM 成本与超时控制 |
| 100k+ 用户 | 再考虑把事件流、离线评估、导出任务拆到异步作业；不要过早微服务化 |

### Scaling Priorities

1. **First bottleneck:** 长会话上下文膨胀。先做会话摘要、结构化 state 回灌，而不是把完整聊天历史永远喂给模型。
2. **Second bottleneck:** 决策质量不可观测。需要 trace、失败案例集合、对比评估，否则只能靠主观感觉调 prompt。

## Anti-Patterns

### Anti-Pattern 1: 把 brainstorming 当成单轮聊天增强

**What people do:** 只在系统提示词里加“你要更会追问、更会写 PRD”。  
**Why it's wrong:** 没有显式 gap、contradiction、strategy state，模型无法稳定切换“探索”和“收敛”。  
**Do this instead:** 先生成结构化 turn decision，再用该 decision 驱动回复和 UI。

### Anti-Pattern 2: 把 PRD 直接等同于聊天记录总结

**What people do:** 每轮都让模型“重写整份 PRD”。  
**Why it's wrong:** 容易漂移、难以版本比较，也无法标记哪些 section 已确认、哪些仍缺失。  
**Do this instead:** 按 section patch + merge + status 管理 PRD，导出时再组装整文。

### Anti-Pattern 3: 让前端自己猜当前阶段

**What people do:** 前端根据消息文案里有没有“请确认”来判断是否进入 finalize。  
**Why it's wrong:** 文案一改就失效，状态不可测试。  
**Do this instead:** 后端显式发出 `workflowStage`、`conversationStrategy`、`isFinalizeReady`。

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| LLM provider | 统一 model gateway + structured output schema | 回合决策与 PRD patch 应优先走结构化输出 |
| Export / storage | 只读 PRD snapshot | 导出不应重新调用模型生成最终文档 |
| Observability | trace / replay / eval | 至少保存输入、decision、reply、patch、最终状态 |

### Existing-App Integration Boundaries

| Existing Piece | Additions | Boundary |
|----------------|-----------|----------|
| `apps/web/src/components/workspace/*` | 新增 guidance card、取舍卡、确认卡、矛盾提示 | 组件只消费 store 中的 `decisionGuidance` 和 `prd` |
| `apps/web/src/store/workspace-store.ts` | 扩展 decision/event 归并 | 维持前端唯一真相源，不在组件内散落判断逻辑 |
| `apps/api/app/api/routes/messages.py` | 保持现有流式入口 | 不新增第二套“brainstorming 专用 API” |
| `apps/api/app/agent/*` | 扩成 extractor / contradiction judge / convergence policy / finalize gate | 智能逻辑集中，不让 service 膨胀 |
| `apps/api/app/services/messages.py` | 继续做 event stream 编排与持久化顺序 | 服务层不承载产品策略 |
| `apps/api/app/repositories/state.py` + `prd.py` + `agent_turn_decisions.py` | 增强版本、状态、评估回放所需字段 | 数据层支撑后续调优闭环 |

## Sources

- LangChain Docs, “Workflows and agents” — 说明 workflow 与 agent 的区别，以及 evaluator-optimizer 循环适合迭代收敛场景。https://docs.langchain.com/oss/python/langgraph/workflows-agents
- LangChain Docs, “Human-in-the-Loop” — 明确 interrupt/pause/resume 模式适合关键确认闸门。https://docs.langchain.com/oss/python/langchain/frontend/human-in-the-loop
- LangChain Docs, “What’s new in LangGraph v1” — 持久化、streaming、HITL、durable execution 仍是一等能力。https://docs.langchain.com/oss/python/releases/langgraph-v1
- LangChain Docs, “Deep Agents overview” — 强调长期上下文管理、子代理、持久 memory、summarization、permissions 的分层价值。https://docs.langchain.com/oss/python/deepagents/overview
- OpenAI API model docs, “GPT-5.1” — 官方模型文档将 Structured Outputs 列为一等特性，适合 decision / patch 这类 machine-readable 契约。https://developers.openai.com/api/docs/models/gpt-5.1
- OpenAI Developers, “Docs MCP” — 官方文档 MCP 体现“宿主聚合上下文、工具只做专责能力”的集成边界思路。https://developers.openai.com/learn/docs-mcp
- Model Context Protocol Spec, “Architecture” — host/client/server 边界强调状态会话、能力隔离、宿主掌控上下文聚合。https://modelcontextprotocol.io/specification/draft/architecture
- Local codebase inspection: `apps/api/app/services/messages.py`, `apps/api/app/agent/runtime.py`, `apps/api/app/agent/readiness.py`, `apps/api/app/agent/extractor.py`, `apps/api/app/agent/prd_updater.py`, `apps/web/src/store/workspace-store.ts`, `apps/api/app/api/routes/messages.py`

---
*Architecture research for: AI brainstorming to PRD copilot added onto an existing chat workspace*
*Researched: 2026-04-16*
