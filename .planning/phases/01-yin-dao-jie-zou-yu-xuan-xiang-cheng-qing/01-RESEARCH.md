# Phase 1: 引导节奏与选项澄清 - Research

**Researched:** 2026-04-16  
**Domain:** 工作台引导状态机、结构化 decision contract、SSE 驱动的前端引导 UI  
**Confidence:** HIGH

## User Constraints

Phase 1 没有单独的 `01-CONTEXT.md`。当前有效约束来自 [`PROJECT.md`](/Users/zhangyanhua/AI/chat-prd2/.planning/PROJECT.md)、[`ROADMAP.md`](/Users/zhangyanhua/AI/chat-prd2/.planning/ROADMAP.md)、[`REQUIREMENTS.md`](/Users/zhangyanhua/AI/chat-prd2/.planning/REQUIREMENTS.md)：

### Locked Constraints

- 延续现有 `Next.js + FastAPI + PostgreSQL` 架构，不为 Phase 1 引入新前端状态机框架或新实时传输层。
- 默认引导节奏必须是“先探索、再逐步收紧”。
- 优先改善引导结构，再做更深的诊断与 PRD 沉淀。
- 面向个人开发者，交互应降低表达门槛，优先“可反应选项”而不是泛泛追问。
- 成功标准不是多聊几轮，而是更稳定地推进用户、问题、方案、边界、约束、验证路径。

### Claude's Discretion

- 最小可行引导状态机具体如何建模。
- decision contract 需要新增哪些字段才能让前端只渲染、不猜测。
- workspace 中提示卡、选项卡、模式切换提示的具体呈现方式。
- Phase 1 应拆成几个 plan / 工作包。

### Deferred Ideas (Out of Scope)

- 矛盾 / 缺口 / 假设的完整诊断台账。
- 带证据追溯的结构化首稿生成。
- PRD 章节化增量编排与 finalize readiness 的完整策略。
- 质量复核、导出、回放与评测体系。

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| GUID-01 | 默认采用“先探索、再逐步收紧”，并能在关键节点切换到聚焦澄清或确认模式 | 推荐使用显式 `guidance_mode + guidance_step + transition_reason` 状态机，而不是只看 `conversation_strategy` 字符串 |
| GUID-02 | 每轮追问都围绕用户、问题、方案、边界、约束或验证路径推进 | decision contract 中增加 `focus_dimension`、`goal_label`、`why_this_now`，前端直接展示“这一轮在推进什么” |
| GUID-03 | 高不确定节点优先给 2-4 个可反应选项，并始终保留“都不对，我补充”入口 | 后端输出 `response_mode=options_first`、`option_cards`、`freeform_affordance`，前端统一渲染 ActionOptions + 自由补充按钮 |
| GUID-04 | 系统能判断此刻应继续深挖、比较选项还是开始收敛，并把判断反映到下一轮引导动作 | 将 `next_move` 扩展为面向 UI 的 `guidance_step`、`transition_trigger`、`can_switch_mode`、`available_mode_switches` |
</phase_requirements>

## Summary

现有代码已经具备 Phase 1 所需的关键骨架：后端有 `TurnDecision -> decision.ready` 事件链路，前端有 `workspace-store` 的单一状态真源，SSE 顺序也已稳定在 `action.decided -> decision.ready -> assistant.version.started`。因此 Phase 1 不需要新增新的实时协议、也不需要引入 XState 一类新状态机框架；应该在现有 contract 上做一次“从展示型 guidance 到驱动型 guidance”的扩展。

最小可行方案不是把状态机做得很重，而是把“引导节奏”和“这一轮响应方式”显式化。建议保留当前 `conversation_strategy`，但新增更适合驱动前端的字段：`guidance_mode` 表示当前节奏（explore / narrow / compare / confirm），`guidance_step` 表示这轮想让用户做什么（answer / choose / rank / confirm / freeform），`focus_dimension` 表示本轮推进维度（user / problem / solution / boundary / constraint / validation），并补上 `transition_reason`、`option_cards`、`freeform_affordance` 等 UI 直接消费字段。这样前端不需要再从 `next_move`、`strategyLabel`、`suggestions` 之间做隐式推断。

对前端而言，正确方向是继续以 [`workspace-store.ts`](/Users/zhangyanhua/AI/chat-prd2/apps/web/src/store/workspace-store.ts) 为唯一状态入口，在现有 `decisionGuidance` 上升维，不改变 SSE 消费方式。`ConversationPanel` 与 `AssistantTurnCard` 已经有状态徽章、选项区和自由补充入口，只要 contract 足够明确，就能在不破坏现有消息流的前提下，把“现在在探索 / 正在比较 / 开始收敛 / 等你确认”表达得更稳定。

**Primary recommendation:** 不升级框架，不重做流式链路；直接扩展 `TurnDecision / decision.ready / workspace-store`，把引导节奏、选项式响应和模式切换提示做成后端决策、前端渲染。

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Next.js | repo: `15.0.0` / latest verified: `16.2.4` | 现有 workspace 路由与客户端壳层 | Phase 1 仅需沿用现有 App Router 与客户端组件边界，不需要升级才能做 SSE guidance UI |
| React | repo: `19.0.0` / latest verified: `19.2.5` | 客户端工作台状态与交互渲染 | 现有客户端状态组织已足够；保持 store 驱动即可 |
| Zustand | repo: `5.0.0` / latest verified: `5.0.12` | workspace 单一真相源 | 当前 store 已承担 hydrate、SSE 应用、decision guidance 派生，最适合承接本 phase |
| FastAPI | repo range: `>=0.115.0` / latest verified: `0.135.3` | 后端 SSE 消息流与会话接口 | 官方 `StreamingResponse` 直接支持 `text/event-stream`，适配当前消息流模式 |
| Pydantic | repo range: `>=2.8.0` / latest verified: `2.13.1` | 结构化 event / session / state contract | Phase 1 的关键就是新增 typed 字段，Pydantic 2 是正确落点 |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `sse-starlette` | repo range: `>=2.1.0` / latest verified: `3.3.4` | SSE 响应支持 | 维持现有 FastAPI 流式返回，不新增第二套流协议 |
| Vitest | repo: `2.0.0` | 前端 store / component 回归测试 | 新增 decision contract 派生与 UI 呈现时必须补前端回归 |
| pytest | repo range: `>=8.3.0` / latest verified: `9.0.3` | 后端 contract / stream 顺序测试 | 扩展 `DecisionReadyEventData` 与 session snapshot 时必须补后端回归 |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| 在 Zustand store 上扩展状态机字段 | 引入 XState / Robot 等显式状态机库 | 这会增加前端状态源与学习成本；Phase 1 当前状态规模不足以证明需要新框架 |
| 保持现有 SSE 事件流并扩展 payload | 新增独立 `/guidance` 轮询或 websocket channel | 会把同一轮 decision 与 assistant 回复拆开，增加一致性风险 |
| 后端输出结构化 option / mode contract | 前端从 assistant 文本里解析模式和选项 | 不可测试、易漂移、与 GUID-04 冲突 |

**Installation:**

```bash
pnpm install
uv pip install -e "apps/api[dev]"
```

**Version verification:**  
已于 2026-04-16 核对 registry / PyPI：

- `next`: repo `15.0.0`，该版本发布时间 2024-10-21；latest `16.2.4`
- `react`: repo `19.0.0`，该版本发布时间 2024-12-05；latest `19.2.5`
- `zustand`: repo `5.0.0`，该版本发布时间 2024-10-14；latest `5.0.12`
- `fastapi`: latest `0.135.3`，发布时间 2026-04-01
- `pydantic`: latest `2.13.1`，发布时间 2026-04-15

结论：Phase 1 不应把版本升级当成前置工作；计划应围绕当前仓库 pinned 版本设计。

## Architecture Patterns

### Recommended Project Structure

```text
apps/api/app/
├── agent/
│   ├── pm_mentor.py          # 生成 guidance_mode / guidance_step / option_cards
│   ├── runtime.py            # greeting / completed / finalize 的本地分支也要对齐新 contract
│   └── types.py              # TurnDecision 结构扩展
├── schemas/
│   ├── message.py            # decision.ready 事件结构扩展
│   └── state.py              # persisted guidance 状态字段
└── services/
    ├── message_state.py      # 构建 guidance payload / merge state patch
    └── sessions.py           # snapshot 中 turn_decisions 的 meta 回填

apps/web/src/
├── lib/types.ts              # DecisionGuidance / DecisionReadyData 类型扩展
├── store/workspace-store.ts  # 统一派生 guidance view model
└── components/workspace/
   ├── conversation-panel.tsx
   ├── assistant-turn-card.tsx
   └── action-options.tsx
```

### Pattern 1: 轻量显式引导状态机

**What:** 在保留现有 `conversation_strategy` 的前提下，再增加一个专门驱动前端的轻量状态机：

- `guidance_mode`: `explore | narrow | compare | confirm`
- `guidance_step`: `answer | choose | rank | confirm | freeform`
- `focus_dimension`: `target_user | problem | solution | boundary | constraint | validation`
- `transition_reason`: 为什么此刻切到这个模式
- `transition_trigger`: 触发切换的判断，如 `high_uncertainty`、`multiple_viable_options`、`enough_signal_to_confirm`

**When to use:** 用于每一轮 `decision.ready` 和 session snapshot。不要只存在于 SSE 中。

**Example:**

```typescript
// Source: repo pattern + typed event contract
type GuidanceMode = "explore" | "narrow" | "compare" | "confirm";
type GuidanceStep = "answer" | "choose" | "rank" | "confirm" | "freeform";

interface GuidanceContract {
  guidance_mode: GuidanceMode;
  guidance_step: GuidanceStep;
  focus_dimension: "target_user" | "problem" | "solution" | "boundary" | "constraint" | "validation";
  transition_reason: string;
  transition_trigger: "high_uncertainty" | "needs_specificity" | "multiple_options" | "ready_to_confirm";
}
```

### Pattern 2: options-first contract，而不是文本推断

**What:** 把“可反应选项”定义成一等字段，而不是 `suggestions` 的弱语义列表。

建议新增：

- `response_mode`: `options_first | direct_answer | confirm_reply`
- `option_cards`: 2-4 个可点击选项，包含 `id / label / content / rationale / type / recommended`
- `freeform_affordance`: `{ label, placeholder, preserve_current_input }`
- `mode_switch_prompt`: 用于提示“如果你不想继续细挖，可以切到比较/确认”

**When to use:** GUID-03 与 GUID-04 的直接实现基础。

**Example:**

```typescript
// Source: repo ActionOptions usage + Phase 1 recommended contract
interface GuidanceOptionCard {
  id: string;
  label: string;
  content: string;
  rationale: string;
  type: "direction" | "tradeoff" | "constraint" | "verification";
  recommended: boolean;
}
```

### Pattern 3: snapshot 与 SSE 共享同一 guidance 真源

**What:** `decision.ready` 和 `getSession()` 暴露同构 guidance 信息，前端只做一次归一化。

**When to use:** 避免刷新后 guidance 漂移。

**Example:**

```typescript
// Source: current workspace-store hydrate + applyEvent pattern
hydrateSession(snapshot) -> deriveDecisionGuidance(latestTurnDecision)
applyEvent(decision.ready) -> deriveGuidanceFromDecisionReady(event.data)
```

### Anti-Patterns to Avoid

- **前端猜模式：** 不要让 `AssistantTurnCard` 根据 `next_move + suggestionOptions.length + 文案关键词` 推断当前模式。
- **只在 SSE 扩字段：** 如果新字段不进 session snapshot，刷新或 regenerate 后会丢。
- **把“都不对，我补充”写死在组件里但不进 contract：** 计划阶段必须决定它何时显示、文案是什么、是否保留输入框内容。
- **把状态机建到 `workflow_stage` 里：** `workflow_stage` 是 PRD 生命周期，不是每轮 guidance 节奏；Phase 1 不要混层。
- **引导节奏和 model scene 耦合：** `collaboration_mode_label` 是模型协作模式，不等于引导模式。

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| 每轮 SSE 第二条新协议 | 单独 websocket / polling guidance 通道 | 继续使用 `decision.ready` | 现有事件顺序与 store 已稳定，新增通道会带来一致性问题 |
| 前端模式识别器 | 解析 assistant 文案中的“现在在确认/比较” | 后端直接输出 `guidance_mode` 与 `guidance_step` | 文本不可测，容易随 prompt 漂移 |
| 新状态机框架 | XState 全量重构 workspace | 扩展 Zustand store view model | 当前状态规模小，最大风险在 contract 缺失，不在状态库 |
| 自定义选项排序算法 | 组件层二次重排 suggestion 优先级 | 后端输出 `priority` + `recommended` | 决策责任应留在后端 |
| “唯一下一问”生成器 | 前端基于 option 拼接下一问文案 | 后端提供 `goal_label / why_this_now / option_cards` | 避免展示层决定产品推进逻辑 |

**Key insight:** Phase 1 的真正缺口不是“前端不会展示卡片”，而是“后端没有把引导节奏作为第一等契约输出”。计划必须先补 contract，再补 UI。

## Common Pitfalls

### Pitfall 1: 把 `conversation_strategy` 当成完整状态机

**What goes wrong:** 目前只有 `greet / clarify / choose / converge / confirm`，但这不足以表达“这一轮是让用户回答、选择、排序还是确认”。  
**Why it happens:** `conversation_strategy` 更像标签，不是完整 UI contract。  
**How to avoid:** 保留现有字段兼容旧逻辑，同时新增 `guidance_mode + guidance_step + focus_dimension`。  
**Warning signs:** 前端开始出现 `if strategy === "choose" && options.length === 0` 之类的补丁逻辑。

### Pitfall 2: 快照和流式 guidance 不一致

**What goes wrong:** SSE 展示了“比较中”，刷新后 session snapshot 又退回“继续澄清”。  
**Why it happens:** 新字段只加在 `decision.ready`，没进入 `turn_decisions` 或 `state_snapshot`。  
**How to avoid:** `DecisionReadyEventData`、`AgentTurnDecisionResponse`、`StateSnapshot` 同步扩展。  
**Warning signs:** `workspace-store` 开始维护“仅当前页面有效”的临时 guidance 字段。

### Pitfall 3: 选项式引导绑架用户

**What goes wrong:** 用户只能点系统给的选项，无法表达“都不对，但方向接近”。  
**Why it happens:** 计划只考虑按钮，不考虑自由补充入口。  
**How to avoid:** contract 中显式定义 `freeform_affordance`，UI 始终提供该入口。  
**Warning signs:** 测试只验证按钮数量，不验证自由输入仍可用。

### Pitfall 4: 把 `workflow_stage` 和 `guidance_mode` 混在一起

**What goes wrong:** `refine_loop` 被当成“探索中”，`finalize` 被当成“确认中”，导致产品生命周期和单轮引导节奏互相污染。  
**Why it happens:** 现有 `workflow_stage` 恰好有阶段语义，容易被误用。  
**How to avoid:** 明确 `workflow_stage` 管 PRD 生命周期，`guidance_mode` 管单轮推进方式。  
**Warning signs:** state patch 同时试图用一个字段表示“PRD 是否 ready”和“这一轮是否要求用户确认”。

### Pitfall 5: 让 `pm_mentor` 与 `runtime` 分支 contract 漂移

**What goes wrong:** greeting / completed / finalize 的本地回复分支没有新字段，导致进入特殊路径时 UI 退化。  
**Why it happens:** 只改了 `pm_mentor.py`。  
**How to avoid:** `runtime.py` 中 `_build_greeting_result`、`_build_completed_result`、`_build_finalize_action_result` 同步对齐新结构。  
**Warning signs:** 只有常规对话能看到模式切换提示，问候态和完成态没有。

## Code Examples

Verified patterns from official sources and current repo:

### FastAPI 继续使用 `StreamingResponse` 承载 SSE

```python
# Source: https://github.com/fastapi/fastapi/blob/0.128.0/docs/en/docs/advanced/custom-response.md
from fastapi.responses import StreamingResponse

@app.get("/stream")
async def stream_response():
    async def generate():
        yield "event: decision.ready\ndata: {...}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
```

### 前端继续在客户端组件消费事件流并落入 store

```typescript
// Source: current repo pattern
for await (const event of parseEventStream(stream)) {
  workspaceStore.getState().applyEvent(event);
}
```

### Phase 1 推荐的 guidance 归一化入口

```typescript
// Source: current repo pattern + recommended extension
function deriveGuidanceFromDecisionReady(data: DecisionReadyData): DecisionGuidance {
  return {
    guidanceMode: data.guidance_mode,
    guidanceStep: data.guidance_step,
    focusDimension: data.focus_dimension,
    strategyLabel: data.strategy_label,
    strategyReason: data.transition_reason,
    optionCards: normalizeOptionCards(data.option_cards),
    freeformAffordance: data.freeform_affordance,
    availableModeSwitches: data.available_mode_switches ?? [],
  };
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| 用自由文本追问推进澄清 | 用结构化 option / mode contract 驱动下一轮响应 | 近两年主流 agent UI/structured output 实践持续强化 | 更可测、更稳定，也更适合 UI 自动化与回放 |
| 只把策略留在 prompt 或回复文本里 | 决策结构显式持久化到 `turn_decisions` / snapshot | 当前 repo 已走到一半 | Phase 1 应继续把 UI 关键字段补齐 |
| 把“阶段”当成单一状态 | 生命周期状态与单轮引导状态分层 | 当前 repo 已有 `workflow_stage` 与 `conversation_strategy` 分离雏形 | 继续扩成双层状态机即可，无需重做 |

**Deprecated/outdated:**

- 让前端从文案推断引导节奏：对当前产品目标来说已经不够可靠。
- 为 options-first 另起前端本地规则引擎：会与后端策略漂移。

## Open Questions

1. **`guidance_mode` 是否需要持久化到 `state_snapshot`，还是只保存在 `turn_decisions` 即可？**
   - What we know: 当前前端 hydrate 主要依赖最新 `turn_decision`，但 `state_snapshot` 也在存 `conversation_strategy`。
   - What's unclear: planner 是否希望刷新后无需 latest decision 也能恢复 guidance badge。
   - Recommendation: Phase 1 计划里优先双写到 `turn_decisions` 和 `state_snapshot`；避免后续再补迁移。

2. **`option_cards` 是否需要稳定 ID？**
   - What we know: 当前 `suggestions` 只有 `label/content/priority/type`。
   - What's unclear: Phase 2/5 是否会按 option 做点击回放或评测。
   - Recommendation: Phase 1 先加 `id`，哪怕只是 deterministic slug；后续日志与评测会更稳。

3. **模式切换是否允许用户主动触发？**
   - What we know: 需求要求“可切换”，但没有规定必须是用户主动切换还是系统提示切换。
   - What's unclear: 是否需要真正的手动 toggle UI。
   - Recommendation: Phase 1 先做“系统提示可切换 + 一键切换建议”，不要上全局 mode switcher。

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | Vitest `2.0.0` + pytest `>=8.3.0` |
| Config file | [`apps/web/vitest.config.ts`](/Users/zhangyanhua/AI/chat-prd2/apps/web/vitest.config.ts), [`apps/api/pyproject.toml`](/Users/zhangyanhua/AI/chat-prd2/apps/api/pyproject.toml) |
| Quick run command | `pnpm --filter web test -- src/test/workspace-store.test.ts src/test/workspace-session-shell.test.tsx && pytest apps/api/tests/test_messages_stream.py apps/api/tests/test_sessions.py -q` |
| Full suite command | `pnpm test:web && pnpm test:api` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| GUID-01 | 最新 decision 能驱动 explore / narrow / compare / confirm 节奏显示 | unit | `pnpm --filter web test -- src/test/workspace-store.test.ts -t "decision guidance"` | ✅ |
| GUID-02 | 后端 snapshot / SSE 暴露结构化 focus 与 reason | integration | `pytest apps/api/tests/test_sessions.py -q -k turn_decision` | ✅ |
| GUID-03 | 高不确定节点返回 2-4 个 options 且保留自由补充入口 | integration | `pytest apps/api/tests/test_messages_stream.py -q -k structured_guidance && pnpm --filter web test -- src/test/workspace-session-shell.test.tsx -t "suggestion"` | ✅ |
| GUID-04 | 系统能在 deep dive / compare / converge / confirm 间切换，并体现在下一轮 guidance | unit + integration | `pytest apps/api/tests/test_pm_mentor.py apps/api/tests/test_agent_runtime.py -q && pnpm --filter web test -- src/test/workspace-store.test.ts -t "strategy"` | ✅ |

### Sampling Rate

- **Per task commit:** `pnpm --filter web test -- src/test/workspace-store.test.ts src/test/workspace-session-shell.test.tsx && pytest apps/api/tests/test_messages_stream.py apps/api/tests/test_sessions.py -q`
- **Per wave merge:** `pnpm test:web && pnpm test:api`
- **Phase gate:** 全量前后端测试通过后再进入 `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `apps/api/tests/test_messages_stream.py` 需要新增对 `guidance_mode / guidance_step / option_cards / freeform_affordance` 的严格断言
- [ ] `apps/api/tests/test_sessions.py` 需要新增 snapshot hydrate 后 guidance contract 一致性断言
- [ ] `apps/web/src/test/workspace-store.test.ts` 需要新增新 contract 派生测试，覆盖刷新与 `decision.ready` 双入口
- [ ] `apps/web/src/test/workspace-session-shell.test.tsx` 需要新增“都不对，我补充”始终可见与模式切换提示渲染测试

## Sources

### Primary (HIGH confidence)

- Context7 `/fastapi/fastapi/0.128.0` - 核验 `StreamingResponse` 可直接承载 `text/event-stream`  
  Source: https://github.com/fastapi/fastapi/blob/0.128.0/docs/en/docs/advanced/custom-response.md
- Context7 `/vercel/next.js/v16.1.6` - 核验 App Router 下客户端组件消费流式数据的边界  
  Source: https://github.com/vercel/next.js/blob/v16.1.6/docs/01-app/01-getting-started/07-fetching-data.mdx
- [`apps/api/app/agent/types.py`](/Users/zhangyanhua/AI/chat-prd2/apps/api/app/agent/types.py) - 当前 `TurnDecision` / `ConversationStrategy` 结构
- [`apps/api/app/services/message_state.py`](/Users/zhangyanhua/AI/chat-prd2/apps/api/app/services/message_state.py) - 当前 guidance payload 与 state patch 合并逻辑
- [`apps/api/app/services/sessions.py`](/Users/zhangyanhua/AI/chat-prd2/apps/api/app/services/sessions.py) - snapshot 中 decision sections 与 guidance meta 回填逻辑
- [`apps/web/src/store/workspace-store.ts`](/Users/zhangyanhua/AI/chat-prd2/apps/web/src/store/workspace-store.ts) - 前端 guidance 派生与 SSE 事件应用单点
- [`apps/web/src/components/workspace/assistant-turn-card.tsx`](/Users/zhangyanhua/AI/chat-prd2/apps/web/src/components/workspace/assistant-turn-card.tsx) - 现有选项式 guidance UI 入口

### Secondary (MEDIUM confidence)

- [`docs/contracts/prd-runtime-contract.md`](/Users/zhangyanhua/AI/chat-prd2/docs/contracts/prd-runtime-contract.md) - 验证当前“快照与 SSE 共享真源”的既有约束
- [`apps/api/tests/test_messages_stream.py`](/Users/zhangyanhua/AI/chat-prd2/apps/api/tests/test_messages_stream.py) - 验证现有 SSE 顺序与 `decision.ready` 已纳入回归
- [`apps/web/src/test/workspace-store.test.ts`](/Users/zhangyanhua/AI/chat-prd2/apps/web/src/test/workspace-store.test.ts) - 验证前端已覆盖 guidance 派生基础能力

### Tertiary (LOW confidence)

- “是否需要真正的用户可见全局 mode switcher” 当前缺少真实用户验证，建议在 Phase 1 只做系统提示式切换。

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH - 现有仓库边界清晰，且 FastAPI / Next.js 官方文档已核验关键能力
- Architecture: HIGH - 代码库已有完整 `TurnDecision -> SSE -> store -> UI` 主链路，扩展面明确
- Pitfalls: MEDIUM - 大部分风险来自当前结构缺口与经验判断，仍需真实会话回归验证

**Research date:** 2026-04-16  
**Valid until:** 2026-05-16

