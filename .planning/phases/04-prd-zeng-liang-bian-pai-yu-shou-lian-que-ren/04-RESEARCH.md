---
phase: 4
slug: prd-zeng-liang-bian-pai-yu-shou-lian-que-ren
status: completed
researched: 2026-04-16
---

# Phase 4 — Research

## Scope

Phase 4 只解决右侧 `PrdPanel` 的章节化增量编排、缺口提示和收敛确认，不重做 Phase 3 已完成的首稿与证据追溯路径。

对应需求：

- `PRD-01`：PRD 视图按章节结构化展示
- `PRD-02`：每轮只增量更新受影响章节
- `PRD-03`：明确提示关键章节缺口
- `PRD-04`：信息充分时输出可确认初稿，而不是无限追问

## Current Facts

基于当前代码，Phase 4 的关键事实已经足够明确：

1. `state.prd_draft` 是内容真源，且已经是 entry 级 persisted contract。
2. `state.evidence` 是来源真源，负责支撑回溯，不适合直接拿来渲染右侧 panel。
3. `diagnostics` / `diagnostic_summary` 已经在会话列形成独立 ledger，不能直接把这些条目抄进 PRD 正文。
4. `apps/api/app/services/prd_runtime.py` 当前只会把 `prd_patch + state_patch` 投影成扁平 `sections/meta`，还不具备章节缺口、增量变更和确认前状态建模能力。
5. `apps/web/src/components/workspace/prd-panel.tsx` 当前仍是“preview + finalize button”结构，展示能力只够支撑 Phase 0-3 的简化 preview，不够承载 Phase 4 的章节化编排。
6. `apps/api/app/agent/readiness.py` 仍然按旧式 section `content/status` 评估可 finalize 状态，需要升级到 entry/completeness-aware 的收敛判断。

## Recommended Architecture

### 1. Truth / Projection Boundary

Phase 4 最合理的边界是两层：

- **内容真源层**：继续使用 `state.prd_draft` + `state.evidence`
- **面板投影层**：升级 `prd.updated` / session snapshot 中的 panel payload，作为右侧 `PrdPanel` 的唯一消费 contract

原因：

- Phase 3 已经把 `prd_draft` 做成 entry 级 persisted truth，现在回头让 `PrdPanel` 直接消费 raw first-draft，会把 panel、首稿、导出三层职责重新缠在一起。
- 右侧 panel 需要的是“按章节收敛后的当前 PRD 视图”，不是“所有 entry 与证据原子”的裸数据。
- 这层投影正好应该由后端统一生成，避免前端自行推断哪些章节缺失、哪些内容可确认、哪些改动属于本轮增量。

### 2. Phase 4 Panel Contract

推荐把 `prd.updated` 升级成“章节化 PRD 投影 contract”，至少包含：

- `sections`: 按固定顺序输出章节化 section
- `meta`: 当前收敛状态、版本、确认提示、critic 摘要
- `sections_changed`: 本轮被影响的章节 key
- `missing_sections`: 当前仍缺信息的关键章节 key
- `gap_prompts`: 每个缺口的中文提示
- `ready_for_confirmation`: 是否达到“可确认初稿”状态

建议的 section key：

- `target_user`
- `problem`
- `solution`
- `mvp_scope`
- `constraints`
- `success_metrics`
- `risks_to_validate`
- `open_questions`

其中：

- 前六个是正文主章节
- `risks_to_validate` 与 `open_questions` 是辅助章节，不直接复制 diagnostics ledger 原文，而是做面板层摘要投影

### 3. Gap / Readiness Model

Phase 4 不应该再靠旧的 `status == missing` 判断是否能收敛，而应该引入更贴近当前 persisted truth 的规则：

- 优先读取 `prd_draft.sections[*].completeness`
- 如果 section 没有 entry，或所有 entry 都是空内容，则判定为缺口
- `to_validate` 不等于缺失，但会降低 readiness，并应进入“待验证 / 风险”章节
- readiness 需要同时看：
  - 必要正文章节是否齐备
  - diagnostics 是否仍存在高优先级 open risk
  - critic 是否还在给出 major gaps

推荐状态机：

- `drafting`：正文章节还不齐
- `needs_input`：主体已成型，但仍有关键缺口或高风险待补
- `ready_for_confirmation`：可给用户确认初稿
- `finalized`：终稿已生成

### 4. Incremental Update Strategy

`PRD-02` 的关键不是“字段变化了”，而是“用户能看懂本轮具体改了哪几章”。

因此后端投影层应明确产出：

- `sections_changed`
- 每个 changed section 的最新版本内容
- 缺口列表是否因本轮变化而减少/新增

前端不应自行 diff 全量文档。理由很直接：

- session refresh、SSE、finalize 后回放都需要使用同一份变更判定
- diff 逻辑放前端会导致 hydrate 后无法稳定重现“本轮改了什么”

### 5. UI Boundary

右侧 `PrdPanel` 在 Phase 4 负责：

- 展示当前章节化 PRD
- 明示缺口和待验证项
- 标记本轮变化
- 当 readiness 达标时给出确认/终稿入口

右侧 `PrdPanel` 不负责：

- 展示 evidence registry 明细
- 替代会话列里的 first-draft card
- 替代 diagnostics ledger 的逐项明细浏览

## Anti-Patterns To Avoid

1. **让 `PrdPanel` 直接消费 `firstDraft.sections`**
   这会把首稿原子层和面板投影层重新耦合，后续 export / finalize / replay 也会失去稳定边界。

2. **把 diagnostics ledger item 原封不动塞进 PRD section**
   diagnostics 是“问题台账”，PRD 是“当前收敛结果”。两者可以关联，但不能混成一层。

3. **每轮整篇重算前端全文 diff**
   这会让 snapshot hydrate、SSE replay 和 finalize 后一致性失控。

4. **继续用旧 `content/status` 规则判断 readiness**
   当前 persisted truth 已经升级成 entry/completeness 结构，再用旧规则会误判“待验证”和“缺失”。

## Plan Decomposition

最合理拆成 3 份 plan：

1. **04-01**：后端 PRD panel contract、章节投影与 readiness/gap projector
2. **04-02**：把投影 contract 接入 SSE、session snapshot、finalize/export 兼容层
3. **04-03**：前端 store 与 `PrdPanel` 升级，完成章节化、增量高亮、缺口提示和确认入口

依赖顺序必须是：

`04-01 -> 04-02 -> 04-03`

## Validation Architecture

验证应分三层：

1. **后端 contract / projector 单测**
   - 锁定 section composition
   - 锁定 missing section / ready_for_confirmation 判定
   - 锁定 changed sections 语义

2. **后端集成测试**
   - 锁定 `prd.updated` SSE payload
   - 锁定 session snapshot hydrate 与 finalize/export 一致性

3. **前端 store / UI 测试**
   - 锁定 panel hydrate
   - 锁定增量高亮
   - 锁定缺口提示与确认 CTA
   - 锁定不污染 Phase 3 first-draft UI

## Recommendation

Phase 4 应以“后端统一投影、前端只消费 panel contract”为主线推进。这样可以同时满足章节化展示、增量更新、缺口提示和收敛确认四个 requirement，而且不会破坏 Phase 3 已经稳定下来的 `prd_draft` / `evidence` 真源边界。
