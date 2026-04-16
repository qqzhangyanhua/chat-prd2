# Phase 3: 首稿生成与证据追溯 - Research

**Researched:** 2026-04-16  
**Domain:** 首稿文档真源、内容确认状态建模、证据追溯 contract、与现有 PRD runtime 的边界划分  
**Confidence:** HIGH

## User Constraints

Phase 3 没有单独的 `03-CONTEXT.md`。当前有效约束来自 [`REQUIREMENTS.md`](/Users/zhangyanhua/AI/chat-prd2/.planning/REQUIREMENTS.md)、[`ROADMAP.md`](/Users/zhangyanhua/AI/chat-prd2/.planning/ROADMAP.md)、[`STATE.md`](/Users/zhangyanhua/AI/chat-prd2/.planning/STATE.md)、Phase 2 执行总结，以及本次研究指令：

### Locked Constraints

- 必须覆盖 `INTK-01`、`INTK-02`、`INTK-03`。
- 研究重点是“首稿生成与证据追溯”的实现事实与边界，不是提前设计完整 Phase 4 PRD panel。
- 首稿真源不能和 Phase 2 diagnostics ledger 混成同一层，也不能让前端自己从历史文本反推证据。
- 必须覆盖后端 state、SSE、session snapshot、前端类型与 UI 消费边界。
- 输出需明确 Validation Architecture，便于后续生成 `03-VALIDATION.md`。

### Claude's Discretion

- 首稿真源应该继续复用哪个现有 state 容器，哪些字段应新增。
- “已确认 / 推断 / 待验证” 的最小 contract 粒度。
- 证据 registry 与 draft content 的引用关系。
- Phase 3 应拆成几个 plan。

### Deferred Ideas (Out of Scope)

- Phase 4 的章节化 PRD 增量编排与右侧 panel 全面重做。
- Phase 5 的导出回放、质量评审、跨会话分析与审计体系。
- 通用知识库或外部文档导入增强。
- 用户可编辑的复杂证据管理工作台。

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| INTK-01 | 生成覆盖目标用户、核心问题、方案方向、范围边界、成功标准的结构化首稿 | 推荐把首稿文档真源放在持久化后端 state 的 `prd_draft` 层，扩展 section schema，而不是直接把最终文案塞进 assistant 回复或 diagnostics |
| INTK-02 | 首稿必须区分“已确认 / 推断 / 待验证” | 推荐不要复用当前 `missing` 语义，新增独立 `assertion_state`，避免把“已有内容但待验证”误当成“内容缺失” |
| INTK-03 | 用户可查看首稿来源于哪些对话轮次或证据项 | 推荐新增 session-level `evidence` registry，并让 draft entry 通过 `evidence_refs` 直接引用，不允许前端自行倒推 |
</phase_requirements>

## Summary

当前仓库已经有一条稳定的 PRD runtime 链路，但它服务的是“右侧 PRD 面板实时预览”和“finalize readiness”，不是 Phase 3 需要的“首稿内容确认状态 + 证据追溯”。现有关键事实是：`state.prd_draft` 已经是后端持久化的文档态真源，`prd.updated` 是实时预览事件，`workspaceStore.prd` 是前端投影，`prd_snapshot.sections` 是兼容与导出回退层；与此同时，`state.evidence` 已存在但当前基本未被使用，`turn_decisions` 能稳定回放每轮 guidance/diagnostics 元数据。这意味着 Phase 3 最合理的做法不是新造第三套“文档系统”，而是在现有 persisted state 上补齐更细的 draft contract，并把 evidence registry 正式用起来。

最关键的边界判断有三条。第一，首稿真源应继续放在后端持久化 state 层，优先复用并升级 `state.prd_draft`，而不是放在 diagnostics ledger、assistant 文本或前端 store。第二，“已确认 / 推断 / 待验证” 不应复用当前 `PrdSectionStatus = confirmed | inferred | missing`，因为 `missing` 表示内容缺失，而 INTK-02 关注的是“内容已写出但仍待验证”的断言状态；因此需要新增独立 `assertion_state`。第三，证据追溯不应挂在 UI 推理逻辑里，而应通过 `state.evidence` 做 session-level registry，draft 内容只保存 `evidence_ref_ids`，`turn_decisions` 记录“本轮新增了哪些 entry / evidence”，这样前端只渲染，不猜测。

**Primary recommendation:** 继续以 `state.prd_draft` 作为首稿内容真源、以 `state.evidence` 作为证据真源、以 `turn_decisions` 作为每轮增量回放真源；前端 `workspaceStore` 只派生 `draft view model`，不要让 `workspaceStore.prd` 或 diagnostics ledger 承担首稿事实层。

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Next.js | repo `15.0.0` | 工作台页面与客户端壳层 | Phase 3 继续在现有 workspace 内扩展首稿视图，不需要新框架 |
| React | repo `19.0.0` | 首稿卡片、证据抽屉、状态徽章渲染 | 当前客户端组件边界足够承载 |
| Zustand | repo `^5.0.0` | `workspace-store` 状态真源 | 已承担 snapshot hydrate、SSE merge、diagnostics merge，适合继续承接 first-draft view model |
| FastAPI | repo range `>=0.115.0` | 消息流、session snapshot、导出接口 | 现有消息流和快照模型已足够扩展首稿 contract |
| Pydantic | repo range `>=2.8.0` | 首稿 section / evidence / event schema | 本 phase 的核心是结构化 contract，Pydantic 2 是直接落点 |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `sse-starlette` | repo range `>=2.1.0` | 继续沿用现有 SSE 事件流 | 可新增 event type，但不新增新传输通道 |
| Vitest | repo `^2.0.0` | 前端 store / draft UI 回归 | 首稿 hydrate、evidence 展示、增量更新都需要 |
| pytest | repo range `>=8.3.0` | 后端 draft/evidence/session/message 回归 | contract 与 persistence 主要在后端 |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| 复用并升级 `state.prd_draft` | 新增独立 `first_draft` 顶层 state | 会增加重复真源和后续 Phase 4 映射成本；当前 `prd_draft` 已是 persisted doc layer，更适合增强而非平行复制 |
| 新增独立 `assertion_state` | 继续复用 `status=confirmed/inferred/missing` | 会把“待验证”错误挤压成“缺失”，不满足 INTK-02 |
| `state.evidence` 做 session-level registry | 把证据全文直接内联进每个 section | 去重困难、刷新 payload 膨胀、同一证据无法复用到多处内容 |
| 在同一 SSE 流里新增 `draft.updated` 或扩展 payload | 让前端从 `assistant`/`turn_decision` 文本反推首稿 | 证据链不可测、难回放、与 INTK-03 冲突 |

**Installation:**

```bash
pnpm install
uv pip install -e "apps/api[dev]"
```

**Version verification:** Phase 3 不需要新增库；计划应围绕当前仓库固定版本与现有 PRD runtime 链路设计。

## Architecture Patterns

### Recommended Project Structure

```text
apps/api/app/
├── agent/
│   ├── pm_mentor.py                # 每轮产出 draft section updates + evidence refs
│   ├── types.py                    # DraftEntry / EvidenceItem / AssertionState
│   └── finalize_flow.py            # 后续 finalize 从 enriched prd_draft 读取，而不是降级成纯字符串
├── schemas/
│   ├── state.py                    # persisted prd_draft/evidence schema
│   ├── message.py                  # draft.updated 或扩展后的 payload schema
│   └── session.py                  # snapshot 返回 draft + evidence registry
└── services/
    ├── message_state.py            # merge prd_draft updates、evidence registry、compat projections
    ├── prd_runtime.py              # 仅保留 PRD panel preview，不承载 evidence 推理
    └── sessions.py                 # 回放 turn decisions 时回填 draft/evidence meta

apps/web/src/
├── lib/types.ts                    # DraftSection / DraftEntry / EvidenceRef / EvidenceItem
├── store/workspace-store.ts        # 独立 firstDraft view model，避免混进现有 prd panel 投影
└── components/workspace/
   ├── first-draft-card.tsx         # 左侧/会话列最小首稿视图
   ├── draft-evidence-drawer.tsx    # 查看 entry 对应 evidence refs
   └── prd-panel.tsx                # 继续只消费 `workspaceStore.prd`
```

### Pattern 1: `state.prd_draft` 继续做首稿内容真源，但 contract 要升维

**What:** 不新造第二份文档 state；继续把 `state.prd_draft` 作为 persisted doc truth，但从“section -> content/status/title”升成“section -> entries/assertion_state/evidence_refs/meta”。

**Why:** 当前 `exports.py`、`finalize_flow.py`、`prd-store-helpers.ts` 已经把 `prd_draft` 视为文档态来源。把首稿真源放回 assistant 文本或 diagnostics ledger 都会破坏现有分层。

**Recommended shape:**

```typescript
type AssertionState = "confirmed" | "inferred" | "to_validate";

interface DraftEntry {
  id: string;
  text: string;
  assertionState: AssertionState;
  evidenceRefIds: string[];
  derivedFromDiagnostics?: string[];
}

interface DraftSection {
  title: string;
  entries: DraftEntry[];
  summary?: string;
  completeness: "complete" | "partial" | "missing";
}
```

**Key rule:** `workspaceStore.prd` 仍是右侧 panel 的 projection；Phase 3 不要让它成为首稿 source of truth。

### Pattern 2: `assertion_state` 与 `section completeness` 分层，不能混用

**What:** 需要把“内容有没有”与“内容是否已确认”分成两个维度。

- `completeness`: `complete | partial | missing`
- `assertion_state`: `confirmed | inferred | to_validate`

**Why:** 当前 `missing` 语义用于 readiness 和 panel 占位；如果把“待验证内容”也塞成 `missing`，就会丢失已写出的首稿内容，且不满足 INTK-02。

**When to use:** 至少 entry 级别使用 `assertion_state`；section 级别用 `completeness` 和聚合状态。

**Recommended compatibility mapping:**

- Phase 3 的 `DraftEntry.assertionState` 不直接等于 `PrdSectionStatus`
- Phase 4 panel 若要消费，可再投影成：
  - 全部 `confirmed` -> `confirmed`
  - 存在 `inferred` / `to_validate` -> `inferred`
  - 无 entry -> `missing`

### Pattern 3: `state.evidence` 做 registry，draft entry 只存 refs

**What:** 证据追溯最小可交付建议采用两层：

- `state.evidence[]`: session-level evidence registry
- `DraftEntry.evidenceRefIds[]`: 只引用 registry id

**Evidence item minimum shape:**

```typescript
interface EvidenceItem {
  id: string;
  kind: "user_message" | "assistant_decision" | "diagnostic" | "system_inference";
  messageId?: string;
  turnDecisionId?: string;
  excerpt: string;
  sectionKeys: string[];
  createdAt?: string;
}
```

**Why:** 同一条用户输入可能同时支撑 `target_user` 和 `problem`；如果证据直接复制到多个 section，会造成同步和去重问题。

### Pattern 4: `turn_decisions` 记录“本轮新增了什么”，不是最终 draft 真源

**What:** `turn_decisions` 应保留 per-turn 增量回放信息，例如：

- `draft_updates`
- `draft_summary`
- `evidence_refs`

但不要把“完整首稿”只挂在 `turn_decisions` 里。

**Why:** `turn_decisions` 适合回放和调试；刷新后的当前文档态仍应来自最新 snapshot state。

### Pattern 5: 首稿流式更新与 PRD panel 更新分开事件语义，但共用同一 SSE 通道

**What:** 建议在现有同一条 SSE 流上新增 `draft.updated` 事件，或在 `prd.updated` 外增加明确 draft payload；不要再额外建 websocket/polling。

**Why:** 当前 `prd.updated` 在文档里已经被明确绑定为 PRD panel preview contract。若把 evidence-heavy 首稿 payload 强塞进去，会污染 Phase 4 语义。

**Recommended boundary:**

- `draft.updated`: 首稿内容、assertion states、evidence refs
- `prd.updated`: 右侧 panel 预览与 meta

同一 SSE 通道，但不同 event type。

### Anti-Patterns to Avoid

- **把首稿真源放在前端 store：** 刷新和 regenerate 都会漂。
- **继续复用 `missing` 表达“待验证”：** 会把“已写出但未确认”的内容丢成缺失。
- **证据只挂在 assistant 回复文本里：** 前端无法稳定回放，也无法做后续导出。
- **把 diagnostics item 直接当 evidence item：** diagnostics 是问题项，不等于支撑首稿结论的证据本身。
- **把 `prd.updated` 当万能文档事件：** 会把 Phase 3/4 contract 搅在一起。

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| 首稿真源 | 前端拼装文档或缓存上一轮文本 | persisted `state.prd_draft` | 刷新、regenerate、导出都依赖后端 persisted truth |
| 内容确认态 | 继续复用 `missing` | 独立 `assertion_state` | `missing` 是缺失，不是待验证 |
| 证据追溯 | 前端根据 message timeline 反推来源 | `state.evidence` registry + `evidenceRefIds` | 满足 INTK-03 且可测试 |
| 历史回放 | 只看最新 snapshot | `turn_decisions` 记录 per-turn draft/evidence updates | 便于后续回放和评测 |
| 实时更新 | 新 transport channel | 现有 SSE 流中新 event type | 保持单通道一致性 |

**Key insight:** Phase 3 最重要的不是“把字符串写进 PRD”，而是把“内容断言”和“证据来源”都变成可持久化、可回放、可投影的 contract。

## Common Pitfalls

### Pitfall 1: 让 `prd_draft` 继续只保存一段字符串

**What goes wrong:** 首稿看起来能显示，但无法标注哪句是 confirmed / inferred / to_validate，也无法挂 evidence refs。  
**Why it happens:** 想最小改动，继续沿用 `{ title, content, status }`。  
**How to avoid:** 至少升级为 `entries[] + assertion_state + evidenceRefIds`。  
**Warning signs:** UI 只能给整段 section 打一个统一标签。

### Pitfall 2: 把 diagnostics ledger 直接渲染成首稿

**What goes wrong:** “未知项 / 风险 / 待验证”和“草稿正文”混在一起，用户看不到已沉淀的内容。  
**Why it happens:** Phase 2 已有 ledger，很容易偷懒复用。  
**How to avoid:** diagnostics 只作为 draft 生成的输入和交叉引用，不是首稿正文层。  
**Warning signs:** 首稿卡片主要展示的还是问题清单而不是内容骨架。

### Pitfall 3: 用 section-level 证据而不是 entry-level 证据

**What goes wrong:** 一个 section 同时包含 confirmed 和 inferred 内容时，追溯粒度太粗。  
**Why it happens:** section-level 看起来实现更快。  
**How to avoid:** 最小可交付也要做到 entry-level evidence refs。  
**Warning signs:** 点击“查看来源”时只能看到整段 section 来源，而不是具体句子来源。

### Pitfall 4: 只在 snapshot 存 evidence，不在 turn decisions 留增量

**What goes wrong:** 当前态能看，历史回放却不知道哪一轮新增了哪条内容。  
**Why it happens:** 只考虑当前展示，没有考虑后续 RVW-03。  
**How to avoid:** `turn_decisions` 保留本轮 `draft_updates` 与 `evidence_refs`。  
**Warning signs:** session snapshot 很完整，但 `turn_decisions.decision_sections.meta` 完全没有首稿增量信息。

### Pitfall 5: 首稿 UI 直接侵入右侧 `PrdPanel`

**What goes wrong:** 还没到 Phase 4，就开始重做 panel、section card、stage meta，范围快速失控。  
**Why it happens:** 当前仓库已有现成 PRD 面板，最容易直接往里塞新字段。  
**How to avoid:** Phase 3 最小 UI 先在会话列提供“结构化首稿 + 查看来源”视图；右侧 panel 继续只显示 runtime PRD preview。  
**Warning signs:** 计划开始出现大量 `prd-panel.tsx`、`prd-section-card.tsx` 深改任务。

## Code Examples

Verified patterns from current repo and recommended extensions:

### 推荐的 draft/evidence persisted shape

```json
{
  "prd_draft": {
    "version": 3,
    "status": "draft_structured",
    "sections": {
      "target_user": {
        "title": "目标用户",
        "entries": [
          {
            "id": "target-user-1",
            "text": "首版优先面向独立开发者。",
            "assertion_state": "confirmed",
            "evidence_ref_ids": ["ev-msg-12"]
          },
          {
            "id": "target-user-2",
            "text": "他们主要通过浏览器完成需求梳理。",
            "assertion_state": "to_validate",
            "evidence_ref_ids": ["ev-inf-3"]
          }
        ],
        "completeness": "partial"
      }
    }
  },
  "evidence": [
    {
      "id": "ev-msg-12",
      "kind": "user_message",
      "message_id": "msg-12",
      "excerpt": "我更想先服务独立开发者。",
      "section_keys": ["target_user"]
    }
  ]
}
```

### 推荐的 per-turn draft update

```python
# Source: repo turn_decision pattern, recommended extension
turn_decision.state_patch["draft_updates"] = {
    "sections_changed": ["target_user", "problem"],
    "entry_ids": ["target-user-1", "problem-2"],
    "evidence_ref_ids": ["ev-msg-12", "ev-diagnostic-4"],
}
```

### 前端只做归一化，不自己推断 evidence

```typescript
// Source: workspace-store.ts pattern, recommended extension
function deriveFirstDraftFromSnapshot(snapshot: SessionSnapshotResponse): FirstDraftState {
  return {
    sections: normalizeDraftSections(snapshot.state.prd_draft),
    evidenceRegistry: normalizeEvidenceRegistry(snapshot.state.evidence),
    latestUpdates: deriveLatestDraftUpdates(snapshot.turn_decisions),
  };
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| 用 section-level 单字符串表示草稿 | 用 structured entries + assertion state + evidence refs | 近两年带 provenance 的 agent/document workflows 普遍如此 | 更适合追溯、比较与后续增量编排 |
| 只给最终文档，不给来源 | 内容层直接带 evidence refs | 当前 agent 文档系统主流做法 | 满足 INTK-03，前端无需倒推 |
| “缺失”与“待验证”混为一谈 | completeness 与 assertion state 分层 | 当前仓库尚未做到 | 可以同时表达“已有内容但未确认”和“内容仍缺失” |

**Deprecated/outdated:**

- 继续让 `content + status` 承担所有首稿语义。
- 只依赖 `assistant reply + turn decision summary` 做来源展示。

## Open Questions

1. **首稿最小 UI 是否放在会话列，还是允许轻量进入右侧 panel？**
   - What we know: 当前 `PrdPanel` 明确是 runtime PRD preview。
   - What's unclear: 产品是否希望 Phase 3 就让首稿与 panel 部分重合。
   - Recommendation: Phase 3 先放会话列；右侧 panel 保持 Phase 4 边界。

2. **`draft.updated` 是否必须新增 event type？**
   - What we know: 现有 SSE 通道稳定，新增 event type 成本可控。
   - What's unclear: 是否允许在短期内扩展 `prd.updated` 而不混乱。
   - Recommendation: 优先新增 `draft.updated`；如果计划阶段要求最小改动，也至少要在 schema 名称上明确它是 draft payload，而不是继续复用 panel 语义。

3. **证据 registry 是否需要保存 assistant/diagnostic 类型证据？**
   - What we know: 用户消息是最基础来源，但推断和诊断也可能是草稿内容来源之一。
   - What's unclear: 产品是否接受“AI 推断”作为可见 evidence source。
   - Recommendation: 最小可交付允许 `user_message` 和 `system_inference` 两类；diagnostic 可作为辅助来源但不替代正文证据。

## Likely Plan Breakdown

1. **03-01 首稿与证据 contract（backend）**
   定义 `assertion_state`、`DraftEntry`、`EvidenceItem`、`draft_updates`，升级 `prd_draft`/`state.evidence`/`turn_decision` 契约，并明确与现有 `missing`、`diagnostics` 的边界。

2. **03-02 持久化、SSE、snapshot 贯通（backend integration）**
   让消息流在持久化 state 时写入 enriched `prd_draft` 和 `evidence`，新增 `draft.updated` 或等价 payload，扩展 `session snapshot` 与回放 meta，保证 refresh / regenerate 一致。

3. **03-03 工作台最小首稿与来源 UI（frontend）**
   扩展前端类型和 `workspace-store`，新增会话列首稿卡片与 evidence drawer，展示“已确认 / 推断 / 待验证”与来源，不侵入右侧 `PrdPanel`。

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | Vitest `2.0.0` + pytest `>=8.3.0` |
| Config file | [`apps/web/vitest.config.ts`](/Users/zhangyanhua/AI/chat-prd2/apps/web/vitest.config.ts), [`apps/api/pyproject.toml`](/Users/zhangyanhua/AI/chat-prd2/apps/api/pyproject.toml) |
| Quick run command | `pnpm --filter web test -- src/test/workspace-store.test.ts src/test/workspace-session-shell.test.tsx src/test/prd-panel.test.tsx && pytest apps/api/tests/test_messages_stream.py apps/api/tests/test_sessions.py apps/api/tests/test_messages_service.py -q -k "draft or evidence"` |
| Full suite command | `pnpm test:web && pnpm test:api` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INTK-01 | 生成覆盖目标用户、问题、方案、范围边界、成功标准的结构化首稿 sections | integration | `pytest apps/api/tests/test_messages_service.py apps/api/tests/test_messages_stream.py -q -k draft_sections` | ❌ Wave 0 |
| INTK-02 | 每条 draft entry 暴露 confirmed / inferred / to_validate，不复用 missing | unit + integration | `pytest apps/api/tests/test_message_state.py -q -k assertion_state && pnpm --filter web test -- src/test/workspace-store.test.ts -t draft` | ❌ Wave 0 |
| INTK-03 | draft entry 直接携带 evidence refs，snapshot hydrate 后前端可查看来源 | integration | `pytest apps/api/tests/test_sessions.py -q -k evidence && pnpm --filter web test -- src/test/workspace-session-shell.test.tsx -t evidence` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `pnpm --filter web test -- src/test/workspace-store.test.ts src/test/workspace-session-shell.test.tsx && pytest apps/api/tests/test_messages_stream.py apps/api/tests/test_sessions.py apps/api/tests/test_messages_service.py -q -k "draft or evidence"`
- **Per wave merge:** `pnpm test:web && pnpm test:api`
- **Phase gate:** 全量前后端测试通过后再进入 `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `apps/api/tests/test_messages_service.py` 需要新增 `prd_draft` enriched contract 测试，覆盖 entries/assertion_state/evidence refs
- [ ] `apps/api/tests/test_messages_stream.py` 需要新增 `draft.updated` 或等价 payload 顺序与结构断言
- [ ] `apps/api/tests/test_sessions.py` 需要新增 snapshot hydrate 后 draft/evidence registry 一致性断言
- [ ] `apps/web/src/test/workspace-store.test.ts` 需要新增 first-draft hydrate / stream merge / stale snapshot 保护测试
- [ ] `apps/web/src/test/workspace-session-shell.test.tsx` 需要新增首稿卡片与 evidence drawer 展示测试
- [ ] `apps/web/src/test/prd-panel.test.tsx` 需要新增“Phase 3 不应污染右侧 panel 语义”的回归测试

## Sources

### Primary (HIGH confidence)

- [`apps/api/app/services/sessions.py`](/Users/zhangyanhua/AI/chat-prd2/apps/api/app/services/sessions.py) - `build_initial_state()`、session snapshot 组装与 turn decision 回放边界
- [`apps/api/app/services/message_state.py`](/Users/zhangyanhua/AI/chat-prd2/apps/api/app/services/message_state.py) - 当前 state patch merge、readiness merge 与 diagnostics 兼容派生逻辑
- [`apps/api/app/services/message_persistence.py`](/Users/zhangyanhua/AI/chat-prd2/apps/api/app/services/message_persistence.py) - state/prd snapshot/turn decision 持久化顺序
- [`apps/api/app/services/prd_runtime.py`](/Users/zhangyanhua/AI/chat-prd2/apps/api/app/services/prd_runtime.py) - 当前 `prd.updated` 明确服务于 PRD preview/meta
- [`apps/api/app/services/exports.py`](/Users/zhangyanhua/AI/chat-prd2/apps/api/app/services/exports.py) - 当前导出优先使用 `prd_draft`
- [`apps/api/app/agent/types.py`](/Users/zhangyanhua/AI/chat-prd2/apps/api/app/agent/types.py) - `TurnDecision`、`DiagnosticItem` 现有 contract
- [`apps/api/app/agent/pm_mentor.py`](/Users/zhangyanhua/AI/chat-prd2/apps/api/app/agent/pm_mentor.py) - 当前 `prd_updates` 与 status 语义（`confirmed/draft/missing`）
- [`apps/web/src/store/prd-store-helpers.ts`](/Users/zhangyanhua/AI/chat-prd2/apps/web/src/store/prd-store-helpers.ts) - 当前 panel 对 `confirmed/inferred/missing` 的投影逻辑
- [`apps/web/src/store/workspace-store.ts`](/Users/zhangyanhua/AI/chat-prd2/apps/web/src/store/workspace-store.ts) - snapshot / SSE -> store 的统一真源入口
- [`apps/web/src/components/workspace/prd-panel.tsx`](/Users/zhangyanhua/AI/chat-prd2/apps/web/src/components/workspace/prd-panel.tsx) - 当前右侧 panel 的明确消费边界
- [`docs/contracts/prd-runtime-contract.md`](/Users/zhangyanhua/AI/chat-prd2/docs/contracts/prd-runtime-contract.md) - 现有 PRD runtime 真源与不变量

### Secondary (MEDIUM confidence)

- [`02-01-SUMMARY.md`](/Users/zhangyanhua/AI/chat-prd2/.planning/phases/02-zhen-duan-shen-wa-yu-wen-ti-tai-zhang/02-01-SUMMARY.md), [`02-02-SUMMARY.md`](/Users/zhangyanhua/AI/chat-prd2/.planning/phases/02-zhen-duan-shen-wa-yu-wen-ti-tai-zhang/02-02-SUMMARY.md), [`02-03-SUMMARY.md`](/Users/zhangyanhua/AI/chat-prd2/.planning/phases/02-zhen-duan-shen-wa-yu-wen-ti-tai-zhang/02-03-SUMMARY.md) - 佐证 diagnostics 已形成独立双层真源，不能与首稿混层
- [`apps/api/tests/test_messages_stream.py`](/Users/zhangyanhua/AI/chat-prd2/apps/api/tests/test_messages_stream.py) - 佐证当前 SSE 顺序与 finalize 语义
- [`apps/api/tests/test_sessions.py`](/Users/zhangyanhua/AI/chat-prd2/apps/api/tests/test_sessions.py) - 佐证当前 snapshot/backfill/export 行为

### Tertiary (LOW confidence)

- “Phase 3 是否需要独立 `draft.updated` event type” 当前是架构建议，虽有充分代码依据，但仍需在计划阶段与范围控制一起确认

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH - 完全基于仓库现有技术栈
- Architecture: HIGH - 关键判断均来自当前 runtime、store、snapshot、export 代码
- Pitfalls: HIGH - 直接源于当前 `missing` 语义、`prd.updated` 边界和 Phase 2/4 已明确职责

**Research date:** 2026-04-16  
**Valid until:** 2026-05-16
