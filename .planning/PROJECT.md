# AI Brainstorming PRD Copilot

## What This Is

这是一个面向个人开发者的想法压实产品。用户带着一句模糊、零散、半成形的产品念头进入系统，系统通过持续追问、识别矛盾与缺口、提供可反应选项、在合适时机推动确认，逐步把想法收敛成结构化 PRD 初稿，并给出可回放、可导出的交付结果。

当前代码库已经交付了完整的 v1.0 工作流：引导澄清、问题诊断、首稿沉淀、章节化 PRD 收敛、质量复核、导出与回放。下一轮工作不再是把主链路补齐，而是提升控制能力、上下文 grounding 和从 PRD 到执行工件的桥接能力。

## Core Value

把个人开发者脑中模糊的产品想法持续压实成可确认、可执行的 PRD，而不是停留在泛泛陪聊。

## Requirements

### Validated

- ✓ 用户可以创建和加载工作台会话，并在前后端之间持久化会话上下文 — existing
- ✓ 用户可以与 AI 进行流式多轮对话，并接收增量回复事件 — existing
- ✓ 系统可以维护 PRD 快照、状态快照与回复版本历史，支撑持续收敛 — existing
- ✓ 用户可以完成会话、导出结果，并通过认证体系访问受保护工作台 — existing
- ✓ 系统默认采用“先探索、再逐步收紧”的引导节奏，并能在高不确定节点优先给出可反应选项 — v1.0
- ✓ 系统能识别矛盾、信息缺口与隐含假设，并持续维护未知项 / 风险 / 待验证台账 — v1.0
- ✓ 系统能把对话沉淀为带证据来源与断言状态的结构化首稿 — v1.0
- ✓ 系统能以章节化、增量更新的方式收敛 PRD，并在信息充分时给出可确认初稿 — v1.0
- ✓ 系统能提供独立的质量复核、结构化导出与单会话回放能力 — v1.0

### Active

- [ ] 支持用户主动切换引导模式，而不只是让系统在卡片中提示当前模式
- [ ] 支持导入外部上下文材料，为需求澄清提供 grounding
- [ ] 在 PRD 稳定后生成 build brief、MVP scope 或 AI coding prompt
- [ ] 基于 review / replay 数据形成可持续优化的质量评估闭环

### Out of Scope

- 通用闲聊助手体验优化 — 当前目标是高质量需求澄清与 PRD 收敛，不是提升陪聊自然度
- 为模式切换做花哨展示层 — 模式只是手段，优先验证它是否真的提升收敛质量
- 多端产品矩阵扩展（如移动端原生 App） — 当前聚焦在已有 Web 工作台内把核心引导链路做深
- 面向大型团队的复杂协同流程 — 当前主要用户是个人开发者，不先引入重型协作能力
- 重型任务管理或项目管理套件 — 当前更适合先把 PRD 到执行工件的轻桥接做好

## Context

- 代码库是 `pnpm` monorepo，前端位于 `apps/web`，使用 Next.js 15、React 19、Zustand；后端位于 `apps/api`，使用 FastAPI、SQLAlchemy、PostgreSQL。
- 现有产品主线已经围绕工作台会话形成：用户可以进入工作台，发送想法，接收流式 AI 回复，并逐步形成首稿、PRD panel、review、导出与 replay snapshot。
- 后端已经有独立的 agent 决策层，位于 `apps/api/app/agent`；前端有工作台状态与事件应用层，位于 `apps/web/src/store/workspace-store.ts`。
- v1.0 已完成 8 个 phase、24 个 plan，并通过 milestone audit；当前没有活动中的 roadmap phase。
- 主要目标用户是个人开发者：他们往往只有模糊想法，不知道如何把想法具象化，也不知道需求边界和隐含矛盾在哪里。
- 当前已知产品缺口主要在“用户主动控制模式”“外部上下文导入”“PRD 到执行工件桥接”三条线上。

## Constraints

- **Tech stack**: 延续现有 Next.js + FastAPI + PostgreSQL 架构 — 当前产品已具备可运行工作台与后端能力，不适合为新目标推倒重来
- **Product focus**: 继续保持“引导结构 > 追问深度 > PRD 沉淀”的优先级，但下一轮要把控制权和 grounding 补强
- **Default interaction**: 默认模式仍应先探索再逐步收紧 — 需要在保持用户可表达空间的同时推进收敛
- **User segment**: 主要面向个人开发者 — 决定了交互、术语和产出物要偏“帮助想清楚”，而不是面向企业流程管理
- **Outcome quality**: 成功标准仍然是可确认、可执行的 PRD；下游执行桥接只能建立在已确认内容之上

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| 现阶段聚焦“引导式需求澄清与 PRD 收敛”而不是通用聊天体验 | 用户真正痛点是不会把模糊想法压实，不是缺一个聊天窗口 | ✓ Good |
| 引导能力优先级为“引导结构 > 追问深度 > PRD 沉淀” | 先解决节奏控制和推进机制，才能让追问和文档沉淀稳定发挥作用 | ✓ Good |
| 产品需要支持可切换的引导模式 | 不同用户状态需要不同推进强度，但模式切换必须服务于 PRD 收敛 | ⚠️ Revisit |
| 默认模式采用“先探索，再逐步收紧” | 既保留用户表达空间，又能逐步把对话收束到可确认结果 | ✓ Good |
| 当前优先增强矛盾识别、收敛判断和选项式引导 | 这三项最直接影响用户能否从模糊想法走到清晰 PRD | ✓ Good |

## Current State

- 已交付版本：`v1.0`
- 里程碑状态：已归档，milestone audit `17/17` requirements satisfied
- 已完成范围：引导澄清、诊断台账、首稿与证据追溯、PRD 增量编排、质量复核、导出、回放，以及 phase/milestone 级验证闭环
- 已知后续议题：前端主动 mode switch、外部上下文导入、执行桥接工件、质量评估闭环

## Next Milestone Goals

1. 让用户可以主动切换引导模式，并观察这对收敛效率的真实影响。
2. 支持导入外部上下文材料，减少模型在高不确定输入下的盲猜。
3. 在 PRD 确认后生成更可执行的下游工件，如 build brief、MVP scope 或 AI coding prompt。

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `$gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `$gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-16 after v1.0 milestone*
