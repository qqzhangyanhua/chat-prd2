# Phase 2: 诊断深挖与问题台账 - Research

**Researched:** 2026-04-16  
**Domain:** 结构化诊断项建模、问题台账持久化、SSE/快照一致性、工作台最小诊断 UI  
**Confidence:** HIGH

## User Constraints

Phase 2 没有单独的 `02-CONTEXT.md`。当前有效约束来自 [`REQUIREMENTS.md`](/Users/zhangyanhua/AI/chat-prd2/.planning/REQUIREMENTS.md)、[`ROADMAP.md`](/Users/zhangyanhua/AI/chat-prd2/.planning/ROADMAP.md)、[`STATE.md`](/Users/zhangyanhua/AI/chat-prd2/.planning/STATE.md) 与本次研究指令：

### Locked Constraints

- 延续现有 `Next.js + FastAPI + PostgreSQL` 架构，不新增第二套实时通道或前端状态框架。
- Phase 2 只解决“矛盾 / 缺口 / 假设识别”和“未知项 / 风险 / 待验证台账”，不要提前把 UI 做成 Phase 4 的 PRD 编排面板。
- 诊断信息必须同时覆盖后端状态、SSE、session snapshot 和前端共享类型，不能只做单次流式提示。
- 重点研究当前架构里“诊断检测放哪一层最合理”，而不是做无边界的产品探索。
- 必须覆盖 `DIAG-01`、`DIAG-02`、`DIAG-03`。

### Claude's Discretion

- 诊断项的一等契约如何建模。
- 诊断项在 `TurnDecision`、数据库、`state snapshot`、`decision.ready`、`workspace-store` 之间如何分层。
- 最小可交付诊断 UI 放在工作台哪一块，既够用又不抢 Phase 4 的职责。
- Phase 2 应拆成几个 plan。

### Deferred Ideas (Out of Scope)

- 证据追溯型 PRD 首稿正文与章节化来源展示。
- 右侧 PRD 面板的章节缺口可视化和增量更新策略。
- 质量复核、导出、回放分析的完整产品化界面。
- 用户主动全局切换引导模式的完整控制台。

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DIAG-01 | 识别用户表达中的矛盾、信息缺口和隐含假设，并以结构化问题或提示暴露 | 推荐把检测逻辑放在 `pm_mentor.py`，输出结构化 `diagnostics`，而不是让前端从 `challenge` 文案二次解析 |
| DIAG-02 | 每个问题项标明类型、影响范围、建议下一步动作 | 推荐新增 `DiagnosticItem` 契约，强制包含 `type / impact_scope / suggested_next_step / status / bucket` |
| DIAG-03 | 维护持续更新的未知项 / 风险 / 待验证清单 | 推荐“双层真源”：`turn_decisions` 保留每轮诊断快照，`state snapshot` 保留聚合后的 open ledger，SSE 只推增量 |
</phase_requirements>

## Summary

Phase 1 已经把 guidance contract 贯通到了 `TurnDecision -> decision.ready -> session snapshot -> workspace-store -> AssistantTurnCard`。Phase 2 最合理的做法不是再发明一套“诊断系统”，而是在现有 turn decision 链路上再加一层结构化诊断契约。当前仓库里其实已经有一些半成品：后端 `TurnDecision` 已有 `assumptions / gaps / challenges / pm_risk_flags`，状态里也有 `working_hypotheses / pm_risk_flags / pending_confirmations / open_questions`，`pm_mentor.py` 甚至已经有 `_has_contradictory_info()` 等启发式函数。但这些字段现在仍然分散、未用户可见、也没有统一 item id / status / impact scope，因此还不能满足“问题台账”。

最重要的规划判断有三个。第一，诊断识别应继续放在 `apps/api/app/agent/pm_mentor.py`，因为只有这里同时掌握最新用户输入、已有 PRD state、历史 guidance 和 LLM 判断；`message_state.py`、`sessions.py`、前端 store 只应负责归一化、持久化和展示，不应重复做矛盾检测。第二，Phase 2 需要一个新的 authoritative contract，例如 `DiagnosticItem`，并让它贯穿 `TurnDecision`、`agent_turn_decisions` 落库、`state snapshot` 聚合和 `decision.ready` 流式事件。第三，最小 UI 不应该进入右侧 PRD 面板，而应该继续留在会话工作台左侧，做成“本轮诊断 + 持续台账”两层展示，避免和 Phase 4 的 PRD 章节缺口 UI 重叠。

**Primary recommendation:** 以 `TurnDecision` 为诊断真源，在后端新增统一 `DiagnosticItem` 契约和 open ledger 聚合逻辑，沿用现有 `decision.ready + snapshot + workspace-store` 通道，把诊断 UI 限定在会话列的独立“问题台账”卡片。

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Next.js | repo: `15.0.0` / latest verified: `16.2.4` | 工作台页面壳层与客户端组件 | Phase 2 只是扩展现有 workspace，不需要换框架 |
| React | repo: `19.0.0` / latest verified: `19.2.5` | 客户端诊断卡片与列表渲染 | 现有客户端组件边界足够承接诊断 UI |
| Zustand | repo: `^5.0.0` / latest verified: `5.0.12` | `workspace-store` 单一真相源 | 当前已承担 snapshot hydrate 与 SSE 增量应用，适合承接 diagnostics ledger |
| FastAPI | repo range: `>=0.115.0` / latest verified: `0.135.3` | 消息流、会话快照、诊断事件透出 | 可继续使用 `StreamingResponse` 承载 SSE，不需要新协议 |
| Pydantic | repo range: `>=2.8.0` / latest verified: `2.13.1` | 诊断事件、snapshot、session 响应模型 | Phase 2 的核心是新增结构化 contract，Pydantic 2 是直接落点 |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `sse-starlette` | repo range: `>=2.1.0` / latest verified: `3.3.4` | 维持现有 SSE 输出 | 继续沿用当前事件流，不拆第二通道 |
| Vitest | repo: `^2.0.0` | store 和 UI 诊断回归测试 | 新增 ledger 派生与组件呈现时必须补 |
| pytest | repo range: `>=8.3.0` / latest verified: `9.0.3` | agent / state / sessions / message stream 回归 | 诊断 contract 与聚合逻辑主要在后端 |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| 在现有 `decision.ready` 上扩展 diagnostics payload | 新增专用 `diagnostics.updated` SSE 事件 | 会引入第二真源，增加事件时序和 refresh 一致性风险 |
| 在 `pm_mentor` 输出结构化诊断项 | 前端从 `challenge`、`reply` 文本中解析矛盾和缺口 | 不可测、易受 prompt 漂移影响，且无法稳定落库 |
| 在会话列展示诊断台账 | 提前塞进右侧 PRD 章节面板 | 会和 Phase 4 的章节化缺口 UI 冲突，职责边界不清 |

**Installation:**

```bash
pnpm install
uv pip install -e "apps/api[dev]"
```

**Version verification:** 2026-04-16 已核对 registry / PyPI。

- `next` latest `16.2.4`
- `react` latest `19.2.5`
- `zustand` latest `5.0.12`
- `fastapi` latest `0.135.3`，发布时间 2026-04-01
- `pydantic` latest `2.13.1`，发布时间 2026-04-15
- `pytest` latest `9.0.3`，发布时间 2026-04-07
- `sse-starlette` latest `3.3.4`，发布时间 2026-03-29

结论：Phase 2 不需要版本升级；计划应完全围绕现有仓库版本与现有事件链路展开。

## Architecture Patterns

### Recommended Project Structure

```text
apps/api/app/
├── agent/
│   ├── pm_mentor.py                 # 识别 contradiction / gap / assumption 并产出 diagnostics
│   ├── runtime.py                   # 本地 greeting / completed / finalize 分支补齐 diagnostics contract
│   └── types.py                     # 新增 DiagnosticItem / DiagnosticLedgerSummary
├── repositories/
│   └── agent_turn_decisions.py      # 持久化 diagnostics_json，并保留旧字段派生
├── schemas/
│   ├── message.py                   # decision.ready 增加 diagnostics / ledger_summary
│   ├── session.py                   # Session snapshot response 回传 open diagnostics
│   └── state.py                     # StateSnapshot 聚合字段
└── services/
    ├── message_state.py             # merge diagnostics ledger, 统一 build payload
    └── sessions.py                  # snapshot / decision_sections 回填 diagnostics meta

apps/web/src/
├── lib/types.ts                     # DecisionDiagnostic / DiagnosticLedger 类型
├── store/workspace-store.ts         # derive latest diagnostics + persisted ledger
└── components/workspace/
   ├── assistant-turn-card.tsx       # 本轮诊断摘要
   ├── diagnostics-ledger-card.tsx   # 持续台账卡片
   └── workspace-session-shell.tsx   # 组合会话卡与诊断台账
```

### Pattern 1: 检测逻辑只放在 `pm_mentor`

**What:** 诊断检测应作为 agent 决策的一部分，由 `pm_mentor.py` 输出结构化项；`message_state.py`、`sessions.py` 和前端只消费，不推断。

**Why here:** `run_pm_mentor()` 已经是当前系统唯一同时具备“用户本轮输入 + 既有 state + 建议节奏 + LLM 结果”的位置，并且现有 `_has_contradictory_info()`、`_is_jumping_around()` 等启发式函数已经证明诊断信号就放在这一层最合适。

**When to use:** 每轮 `TurnDecision` 生成时。

**Example:**

```python
# Source: repo pattern, recommended extension
@dataclass
class DiagnosticItem:
    id: str
    type: Literal["contradiction", "gap", "assumption"]
    bucket: Literal["unknown", "risk", "to_validate"]
    status: Literal["open", "resolved", "superseded"]
    title: str
    detail: str
    impact_scope: list[str]
    suggested_next_step: dict[str, str]
    evidence_refs: list[dict[str, str]]
    confidence: Literal["high", "medium", "low"]
```

### Pattern 2: `turn_decisions` 记录每轮诊断，`state snapshot` 记录 open ledger

**What:** 采用双层真源。

- `TurnDecision.diagnostics`: 每轮 agent 在当下识别出的诊断项快照，用于回放、调试、Phase 5 留痕
- `state_snapshot.diagnostics`: 当前 session 仍然 open 的诊断 ledger，用于 hydrate、刷新恢复和 UI 展示

**Why:** `turn_decisions` 负责“历史事实”，`state snapshot` 负责“当前工作台状态”；这与当前 PRD 的 `prd.updated` vs `snapshot.state` 分层完全一致。

**When to use:** 所有 `decision.ready` 事件与 `getSession()` 响应。

**Example:**

```python
# Source: repo pattern + recommended extension
state_patch.update({
    "diagnostics": open_ledger,
    "diagnostic_summary": {
        "open_count": len(open_ledger),
        "unknown_count": count_by_bucket(open_ledger, "unknown"),
        "risk_count": count_by_bucket(open_ledger, "risk"),
        "to_validate_count": count_by_bucket(open_ledger, "to_validate"),
    },
})
```

### Pattern 3: 保留现有旧字段，但把它们降级为派生字段

**What:** 当前已有 `assumptions_json`、`risk_flags_json`、`working_hypotheses`、`pm_risk_flags`、`open_questions`。Phase 2 不应直接删掉这些字段；应把它们视为 `diagnostics` 的兼容派生。

**Recommended mapping:**

- `assumptions_json`: `diagnostics` 中 `type="assumption"` 的子集
- `risk_flags_json` / `pm_risk_flags`: `bucket="risk"` 的摘要字符串
- `open_questions`: `suggested_next_step.prompt` 或 `bucket="unknown"` 的用户面问题

**Why:** 这样能减少一次性大改，也能避免把现有测试和老 UI 全部打碎。

### Pattern 4: 最小 UI 放在会话列，不放进 PRD 面板

**What:** Phase 2 最小 UI 建议拆成两层：

- `AssistantTurnCard` 里增加“本轮诊断”摘要，展示最新 turn 的 1-3 个重点问题项
- 新增独立 `DiagnosticsLedgerCard`，放在会话列里，持续显示 open 的未知项 / 风险 / 待验证清单

**Why:** 这样既满足“持续可见”，又不会把右侧 PRD 面板提前做成缺口编排系统。

**Minimum scope:**

- 支持按 `bucket` 分组
- 支持展示 `type / impact_scope / suggested_next_step`
- 只显示 `open` 项
- 本 phase 不做手动 resolve，不做 PRD section inline badge

### Anti-Patterns to Avoid

- **前端做矛盾识别：** 不要在 `workspace-store` 或组件里根据用户/AI 文本做字符串判断。
- **只有字符串数组，没有 item id/status：** 这会让去重、回放、更新和 future audit 全部变脆。
- **只把 diagnostics 放进 SSE，不进 snapshot：** 刷新会丢台账。
- **把 diagnostics 直接塞进 PRD section content：** 这会抢走 Phase 4 的职责。
- **把 `currentAction.challenge` 当成完整诊断系统：** 它只能表达本轮 challenge，不是可维护 ledger。

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| 诊断识别 | 前端文本解析器或正则规则引擎 | `pm_mentor` 输出结构化 `DiagnosticItem` | 当前 agent 层已掌握上下文，展示层不应承担推理 |
| 台账真源 | 第二套 diagnostics SSE 通道 | 继续沿用 `decision.ready + snapshot.state` | 避免事件顺序和刷新恢复漂移 |
| 历史留痕 | 只保留最新台账，不保留每轮记录 | `agent_turn_decisions` 保存 per-turn diagnostics | Phase 5 回放和误报分析会依赖历史 |
| 状态更新 | 每轮全量重建无 id 的列表 | 稳定 `diagnostic_id` + status 更新 | 否则无法可靠去重、关闭、替换 |
| UI 承载 | 右侧 PRD 缺口面板 | 会话列独立 ledger card | 保持 Phase 2 与 Phase 4 解耦 |

**Key insight:** Phase 2 真正要补的不是“再多写一点 challenge 文案”，而是把诊断从零散字符串升级成系统级 contract。

## Common Pitfalls

### Pitfall 1: 把探索态误判为矛盾

**What goes wrong:** 用户前后是在探索不同方向，但系统过早认定为 contradiction。  
**Why it happens:** 只看表面转折词，没有结合 `workflow_stage`、当前 focus 和已确认程度。  
**How to avoid:** contradiction 需要同时满足“新输入反向覆盖已有较高置信内容”与“影响已存在的关键 section”；探索期默认降到 `gap` 或 `assumption`。  
**Warning signs:** 用户刚开始发散举例，就频繁出现“你前后矛盾”的高强度提示。

### Pitfall 2: 诊断项没有稳定身份，导致每轮重复刷屏

**What goes wrong:** 同一个缺口在每轮都被当成新项，列表越滚越长。  
**Why it happens:** 只有文本，没有稳定 id 或 dedupe key。  
**How to avoid:** 用 `type + normalized_scope + normalized_claim` 生成 deterministic id；重复项更新 `last_seen_at` 与 evidence，不新增。  
**Warning signs:** 同一会话里出现多条只差一两个字的“目标用户不清晰”。

### Pitfall 3: 只存“问题是什么”，不存“下一步怎么澄清”

**What goes wrong:** UI 能展示问题，但用户不知道下一步该回答什么。  
**Why it happens:** 只把 diagnostics 当风控标签，而不是产品推进工具。  
**How to avoid:** `suggested_next_step` 成为必填字段，至少包含 `label / prompt / action_kind`。  
**Warning signs:** 组件只能渲染红黄标签，无法生成可点击澄清动作。

### Pitfall 4: `state snapshot` 和 `turn_decisions` 内容漂移

**What goes wrong:** SSE 显示 open diagnostics，刷新后 snapshot 又少一半。  
**Why it happens:** 只更新了 event payload，没有同步 state 聚合。  
**How to avoid:** 所有 diagnostics 先进入 `TurnDecision`，再统一由 `merge_state_patch_with_decision()` 生成 open ledger。  
**Warning signs:** 前端 store 开始维护“页面级临时 diagnostics”。

### Pitfall 5: 诊断 UI 提前侵入 PRD 编排

**What goes wrong:** 本 phase 花时间在右侧章节缺口、内联 badge、章节状态交互，导致范围失控。  
**Why it happens:** “impact_scope” 很容易让人直接想到 PRD section UI。  
**How to avoid:** 本 phase 只在会话列展示 `impact_scope` 标签，不做 PRD panel 交互。  
**Warning signs:** 计划开始出现“修改 PRD side panel 章节卡片”的大规模任务。

## Code Examples

Verified patterns from current repo and official sources:

### 后端继续用 `StreamingResponse` 承载增量事件

```python
# Source: Context7 /fastapi/fastapi/0.128.0
from fastapi.responses import StreamingResponse

@app.get("/stream")
def stream():
    def generate():
        yield "event: decision.ready\\ndata: {...}\\n\\n"
    return StreamingResponse(generate(), media_type="text/event-stream")
```

### 推荐的 diagnostics 合并伪代码

```python
# Source: repo merge_state_patch_with_decision pattern, recommended extension
new_items = detect_diagnostics(user_input, current_state, mentor_output)
history_items = current_state.get("diagnostics", [])
open_ledger = merge_diagnostics(history_items, new_items)

turn_decision = TurnDecision(
    ...,
    diagnostics=new_items,
    diagnostic_summary=summarize_diagnostics(open_ledger),
)

state_patch.update({
    "diagnostics": open_ledger,
    "diagnostic_summary": summarize_diagnostics(open_ledger),
})
```

### 前端继续只做归一化和渲染

```typescript
// Source: workspace-store.ts pattern, recommended extension
function deriveDiagnosticsFromDecisionReady(data: DecisionReadyData): DiagnosticLedger {
  return {
    items: normalizeDiagnosticItems(data.diagnostics),
    summary: normalizeDiagnosticSummary(data.diagnostic_summary),
  };
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| 用 `challenge` 这类自由文本表达风险 | 用 typed issue ledger 表达 contradiction / gap / assumption | 近两年结构化 agent output 持续强化 | 更可测，可回放，可做增量更新 |
| 只在最终文档里一次性列风险 | 会话进行中持续维护 open ledger | 当前 PRD 协作产品普遍强调过程可见性 | 更符合 DIAG-03，也能减少错误假设持续扩散 |
| 诊断和引导分离成两套系统 | 诊断作为 turn decision 的一部分，与 guidance 共用通道 | 本仓库当前架构天然支持 | 降低实现复杂度和一致性风险 |

**Deprecated/outdated:**

- 仅用 `currentAction.challenge` 表达“本轮有问题”：不能满足台账要求。
- 将诊断结果只放在最终 PRD 风险章节：不满足会话过程中的持续可见。

## Likely Plan Breakdown

1. **02-01 后端诊断契约与识别规则**
   明确定义 `DiagnosticItem`、补齐 `pm_mentor` 识别与去重策略、让 greeting / fallback / finalize 路径返回空或兼容 diagnostics。
2. **02-02 持久化、SSE、snapshot 台账贯通**
   扩展 `TurnDecision`、仓储落库、`decision.ready` payload、`StateSnapshot` 聚合字段、`sessions.py` 回放结构，以及必要迁移与后端测试。
3. **02-03 工作台最小诊断 UI**
   扩展前端类型与 store，新增会话列 `DiagnosticsLedgerCard`，在 `AssistantTurnCard` 显示本轮诊断摘要，并补齐 Vitest 回归。

## Open Questions

1. **诊断项 id 是否需要跨会话稳定，还是只需 session 内稳定？**
   - What we know: 本 phase 至少需要 session 内去重和更新。
   - What's unclear: Phase 5 是否要做跨会话评测聚合。
   - Recommendation: 先做 session 内 deterministic id，跨会话分析后续再补。

2. **本 phase 是否需要“已解决”视图？**
   - What we know: DIAG-03 只要求持续维护 open lists，没有要求完整生命周期 UI。
   - What's unclear: 用户是否需要在当前 milestone 里回看 resolved 项。
   - Recommendation: Phase 2 先只显示 open 项，保留 `status` 字段但不暴露 resolved 过滤器。

3. **是否一定要数据库迁移？**
   - What we know: 现有 `state_patch_json` 已可承载额外 JSON，最小实现可以先不改表。
   - What's unclear: Phase 5 回放、误报分析、数据查询是否需要一等列。
   - Recommendation: 计划优先评估增加 `diagnostics_json` 列；如果为了节奏暂缓，也至少要把 diagnostics 一等放入 `state_patch_json` 和 snapshot，并把迁移列为后续风险。

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | Vitest `2.0.0` + pytest `>=8.3.0` |
| Config file | [`apps/web/vitest.config.ts`](/Users/zhangyanhua/AI/chat-prd2/apps/web/vitest.config.ts), [`apps/api/pyproject.toml`](/Users/zhangyanhua/AI/chat-prd2/apps/api/pyproject.toml) |
| Quick run command | `pnpm --filter web test -- src/test/workspace-store.test.ts src/test/assistant-turn-card.test.tsx src/test/workspace-session-shell.test.tsx && pytest apps/api/tests/test_pm_mentor.py apps/api/tests/test_messages_stream.py apps/api/tests/test_sessions.py -q -k "diagnostic or guidance"` |
| Full suite command | `pnpm test:web && pnpm test:api` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DIAG-01 | agent 能识别 contradiction / gap / assumption 并结构化输出 | unit | `pytest apps/api/tests/test_pm_mentor.py -q -k diagnostic` | ❌ Wave 0 |
| DIAG-02 | 每个 diagnostics item 暴露 type / impact_scope / suggested_next_step | integration | `pytest apps/api/tests/test_messages_stream.py apps/api/tests/test_sessions.py -q -k diagnostic` | ❌ Wave 0 |
| DIAG-03 | open ledger 在 SSE、snapshot、store 与 UI 中持续更新 | unit + integration | `pnpm --filter web test -- src/test/workspace-store.test.ts src/test/workspace-session-shell.test.tsx src/test/assistant-turn-card.test.tsx -t diagnostic` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `pnpm --filter web test -- src/test/workspace-store.test.ts src/test/assistant-turn-card.test.tsx src/test/workspace-session-shell.test.tsx && pytest apps/api/tests/test_pm_mentor.py apps/api/tests/test_messages_stream.py apps/api/tests/test_sessions.py -q -k "diagnostic or guidance"`
- **Per wave merge:** `pnpm test:web && pnpm test:api`
- **Phase gate:** 全量前后端测试通过后再进入 `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `apps/api/tests/test_pm_mentor.py` 需要新增 contradiction / gap / assumption 分类、误报控制、去重 id 测试
- [ ] `apps/api/tests/test_messages_stream.py` 需要新增 `decision.ready` diagnostics payload 与事件顺序断言
- [ ] `apps/api/tests/test_sessions.py` 需要新增 session hydrate 后 open ledger 一致性断言
- [ ] `apps/web/src/test/workspace-store.test.ts` 需要新增 diagnostics hydrate / SSE merge / stale snapshot 保护测试
- [ ] `apps/web/src/test/assistant-turn-card.test.tsx` 需要新增“本轮诊断摘要”与 suggested next step 渲染测试
- [ ] `apps/web/src/test/workspace-session-shell.test.tsx` 需要新增持续台账卡片渲染与刷新恢复测试

## Sources

### Primary (HIGH confidence)

- Context7 `/fastapi/fastapi/0.128.0` - 核验 `StreamingResponse` 可继续用于 `text/event-stream`
- [`apps/api/app/agent/pm_mentor.py`](/Users/zhangyanhua/AI/chat-prd2/apps/api/app/agent/pm_mentor.py) - 当前 guidance 决策、启发式函数与 `TurnDecision` 构造位置
- [`apps/api/app/agent/types.py`](/Users/zhangyanhua/AI/chat-prd2/apps/api/app/agent/types.py) - 当前 `TurnDecision`、guidance 相关 dataclass 定义
- [`apps/api/app/services/message_state.py`](/Users/zhangyanhua/AI/chat-prd2/apps/api/app/services/message_state.py) - `build_guidance_payload()`、`merge_state_patch_with_decision()` 与 state patch 真源
- [`apps/api/app/services/sessions.py`](/Users/zhangyanhua/AI/chat-prd2/apps/api/app/services/sessions.py) - `turn_decisions` 回放与 session snapshot 结构
- [`apps/api/app/repositories/agent_turn_decisions.py`](/Users/zhangyanhua/AI/chat-prd2/apps/api/app/repositories/agent_turn_decisions.py) - 当前 turn decision 落库逻辑
- [`apps/api/app/schemas/message.py`](/Users/zhangyanhua/AI/chat-prd2/apps/api/app/schemas/message.py) - `DecisionReadyEventData` 与 `AgentTurnDecisionResponse`
- [`apps/api/app/schemas/state.py`](/Users/zhangyanhua/AI/chat-prd2/apps/api/app/schemas/state.py) - `StateSnapshot` 当前聚合字段
- [`apps/web/src/lib/types.ts`](/Users/zhangyanhua/AI/chat-prd2/apps/web/src/lib/types.ts) - 前端 guidance / session 类型边界
- [`apps/web/src/store/workspace-store.ts`](/Users/zhangyanhua/AI/chat-prd2/apps/web/src/store/workspace-store.ts) - snapshot 与 SSE 到 store 的统一归一化入口
- [`apps/web/src/components/workspace/assistant-turn-card.tsx`](/Users/zhangyanhua/AI/chat-prd2/apps/web/src/components/workspace/assistant-turn-card.tsx) - 当前最接近承载“本轮诊断”的 UI 区域

### Secondary (MEDIUM confidence)

- [`docs/contracts/prd-runtime-contract.md`](/Users/zhangyanhua/AI/chat-prd2/docs/contracts/prd-runtime-contract.md) - 佐证“事件流 + 快照双层真源”的既有设计原则
- [`apps/api/tests/test_message_service_modules.py`](/Users/zhangyanhua/AI/chat-prd2/apps/api/tests/test_message_service_modules.py) - 佐证当前 state 已有 `assumptions / risks / open_questions` 等分散字段
- [`apps/web/src/test/workspace-store.test.ts`](/Users/zhangyanhua/AI/chat-prd2/apps/web/src/test/workspace-store.test.ts) - 佐证 store 已覆盖 guidance hydrate / event apply 主路径
- [`apps/web/src/test/workspace-session-shell.test.tsx`](/Users/zhangyanhua/AI/chat-prd2/apps/web/src/test/workspace-session-shell.test.tsx) - 佐证 snapshot guidance 已在工作台中被集成测试覆盖
- [`01-01-SUMMARY.md`](/Users/zhangyanhua/AI/chat-prd2/.planning/phases/01-yin-dao-jie-zou-yu-xuan-xiang-cheng-qing/01-01-SUMMARY.md), [`01-02-SUMMARY.md`](/Users/zhangyanhua/AI/chat-prd2/.planning/phases/01-yin-dao-jie-zou-yu-xuan-xiang-cheng-qing/01-02-SUMMARY.md), [`01-03-SUMMARY.md`](/Users/zhangyanhua/AI/chat-prd2/.planning/phases/01-yin-dao-jie-zou-yu-xuan-xiang-cheng-qing/01-03-SUMMARY.md) - 佐证 Phase 1 已建立 guidance contract、snapshot 对齐与前端消费模式

### Tertiary (LOW confidence)

- “是否必须在本 phase 就做数据库一等列 `diagnostics_json`” 当前没有产品侧硬约束，属于工程质量推荐，需在 plan 阶段结合节奏确认

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH - 当前 phase 无需新库，版本已在 registry / PyPI 验证
- Architecture: HIGH - 关键事实均来自现有代码链路，且与 Phase 1 已建立模式一致
- Pitfalls: MEDIUM - 主要基于当前代码形态和该类产品常见失败模式推导，虽有强证据，但误报阈值仍需实现后校准

**Research date:** 2026-04-16  
**Valid until:** 2026-05-16
