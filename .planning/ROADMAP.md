# Roadmap: AI Brainstorming PRD Copilot

## Overview

本路线图围绕“把模糊产品想法持续压实成可确认、可执行的 PRD”展开，按能力依赖与产品优先级拆成五个阶段：先把引导节奏和选项式交互做对，再补足矛盾/缺口诊断深度，然后把澄清结果沉淀成带证据的首稿，接着完成按章节增量收敛的 PRD 编排，最后补质量复核、导出与回放能力。

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: 引导节奏与选项澄清** - 建立先探索后收紧的默认引导结构与选项式推进机制。
- [x] **Phase 2: 诊断深挖与问题台账** - 识别矛盾、缺口和假设，并把问题持续维护成可行动清单。
- [x] **Phase 3: 首稿生成与证据追溯** - 把澄清结果沉淀为可区分确认状态、可回溯来源的结构化首稿。
- [ ] **Phase 4: PRD 增量编排与收敛确认** - 以章节化、增量更新的方式把会话收束成可确认 PRD 初稿。
- [ ] **Phase 5: 质量复核与交付回放** - 对 PRD 做基础质量检查，并支持导出与回放分析。

## Phase Details

### Phase 1: 引导节奏与选项澄清
**Goal**: 用户在工作台里获得稳定、可切换的引导节奏，系统能优先用可反应选项推动澄清而不是泛泛追问。
**Depends on**: Nothing (first phase)
**Requirements**: GUID-01, GUID-02, GUID-03, GUID-04
**Success Criteria** (what must be TRUE):
  1. 用户输入模糊想法后，系统默认先进行开放探索，再在关键节点切换到聚焦澄清或确认模式。
  2. 每一轮系统追问都明显围绕用户、问题、方案、边界、约束或验证路径推进，而不是闲聊式延展。
  3. 在高不确定节点，用户能直接从 2-4 个候选选项中反应，并始终看到“都不对，我补充”的入口。
  4. 用户能感知系统会根据当前上下文在“继续深挖 / 比较选项 / 开始收敛”之间切换下一步动作。
**Plans**: 3 plans

Plans:
- [x] 01-01-PLAN.md — 扩展后端 guidance contract 与 decision.ready 结构化字段
- [x] 01-02-PLAN.md — 让 snapshot / session / SSE guidance 保持同一份真相
- [x] 01-03-PLAN.md — 消费 guidance contract 并完成工作台引导 UI 渲染

### Phase 2: 诊断深挖与问题台账
**Goal**: 用户可以看到系统主动指出当前想法中的矛盾、信息缺口和隐含假设，并给出下一步澄清方向。
**Depends on**: Phase 1
**Requirements**: DIAG-01, DIAG-02, DIAG-03
**Success Criteria** (what must be TRUE):
  1. 当用户前后表达冲突、信息缺失或带有隐含前提时，系统会把这些问题明确暴露出来，而不是继续顺着错误假设生成内容。
  2. 每个问题项都能让用户看到其类型、影响范围以及建议的下一步澄清动作。
  3. 用户在对话过程中随时都能看到持续更新的未知项、风险和待验证清单，而不是只在结束时一次性总结。
**Plans**: 3 plans

Plans:
- [x] 02-01-PLAN.md — 后端诊断契约与 contradiction/gap/assumption 检测规则
- [x] 02-02-PLAN.md — 持久化、SSE 与 session snapshot 问题台账贯通
- [x] 02-03-PLAN.md — 会话列最小诊断 UI 与前端台账消费

### Phase 3: 首稿生成与证据追溯
**Goal**: 系统把已澄清的内容快速沉淀为结构化首稿，并明确哪些内容已确认、哪些仍是推断或待验证。
**Depends on**: Phase 2
**Requirements**: INTK-01, INTK-02, INTK-03
**Success Criteria** (what must be TRUE):
  1. 用户输入初始想法并经历基础澄清后，系统能生成覆盖目标用户、核心问题、方案方向、范围边界和成功标准的结构化首稿。
  2. 用户在首稿中能清楚区分“已确认”“推断”“待验证”内容，不会把未确认信息误看成既定事实。
  3. 用户查看首稿任一关键内容时，能够回溯到对应的对话轮次或证据项来源。
**Plans**: 3 plans

Plans:
- [x] 03-01-PLAN.md — 首稿与 evidence contract：entry 级 assertion_state + 证据 registry
- [x] 03-02-PLAN.md — enriched prd_draft 持久化、draft.updated 与 snapshot/导出兼容
- [x] 03-03-PLAN.md — 会话列首稿卡片与证据抽屉，保持 PrdPanel 边界不变

### Phase 4: PRD 增量编排与收敛确认
**Goal**: 用户可以在对话进行中持续看到按章节增量更新的 PRD，并在信息充分时获得可确认的结构化初稿。
**Depends on**: Phase 3
**Requirements**: PRD-01, PRD-02, PRD-03, PRD-04
**Success Criteria** (what must be TRUE):
  1. PRD 视图按目标用户、问题、方案、范围边界、成功标准、风险/待验证项等章节结构化展示，而不是杂乱长文。
  2. 用户在每轮推进后只会看到受影响章节被增量更新，能够直观看出哪些部分发生了变化。
  3. 当某些关键章节信息不足时，PRD 视图会明确提示缺口，并引导继续澄清。
  4. 当系统判断信息已经足够时，用户能收到可确认的结构化 PRD 初稿，而不是被无限追问。
**Plans**: 3 plans

Plans:
- [x] 04-01-PLAN.md — 后端 panel contract、章节投影与 readiness/gap projector
- [x] 04-02-PLAN.md — SSE / snapshot / finalize / export 接入统一 PRD projection
- [x] 04-03-PLAN.md — 前端 store 与 PrdPanel 升级，完成增量高亮、缺口提示和确认 CTA

### Phase 5: 质量复核与交付回放
**Goal**: 用户在确认 PRD 前后都能获得基础质量反馈、结构化导出结果，以及完整的引导与变更留痕。
**Depends on**: Phase 4
**Requirements**: RVW-01, RVW-02, RVW-03
**Success Criteria** (what must be TRUE):
  1. 用户查看当前 PRD 时，系统会从目标清晰度、范围边界、成功标准、风险暴露和待验证项完整度等维度给出基础质量检查结果。
  2. 用户确认后，可以导出保留章节结构和待验证项的结构化 PRD 文本，用于复制或下载。
  3. 用户或系统后续回放时，能够看到引导决策、问题诊断和 PRD 变更记录，而不是只剩最终文档。
**Plans**: 3 plans

Plans:
- [x] 05-01-PLAN.md — 后端 review contract 与 snapshot expose，保持 review/panel contract 分离
- [ ] 05-02-PLAN.md — 导出与交付链路复用后端 projection，保留章节与待验证项
- [ ] 05-03-PLAN.md — 单会话 replay timeline 聚合与前端 review/replay 消费

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. 引导节奏与选项澄清 | 3/3 | Completed | 2026-04-16 |
| 2. 诊断深挖与问题台账 | 3/3 | Completed | 2026-04-16 |
| 3. 首稿生成与证据追溯 | 3/3 | Completed | 2026-04-16 |
| 4. PRD 增量编排与收敛确认 | 3/3 | Completed | 2026-04-16 |
| 5. 质量复核与交付回放 | 0/3 | Ready to execute | - |
