# AI Brainstorming PRD Copilot

## What This Is

这是一个面向个人开发者的想法压实产品。用户带着一句模糊、零散、半成形的产品念头进入系统，系统通过持续追问、识别矛盾与缺口、提供可反应选项、在合适时机推动确认，逐步把想法收敛成结构化 PRD 初稿。

当前代码库已经具备会话式工作台、AI 消息流、PRD 快照与导出能力；本项目当前阶段的重点不是从零搭建聊天产品，而是把现有工作台升级成更强的引导式需求澄清与 PRD 收敛系统。

## Core Value

把个人开发者脑中模糊的产品想法持续压实成可确认、可执行的 PRD，而不是停留在泛泛陪聊。

## Requirements

### Validated

- ✓ 用户可以创建和加载工作台会话，并在前后端之间持久化会话上下文 — existing
- ✓ 用户可以与 AI 进行流式多轮对话，并接收增量回复事件 — existing
- ✓ 系统可以维护 PRD 快照、状态快照与回复版本历史，支撑持续收敛 — existing
- ✓ 用户可以完成会话、导出结果，并通过认证体系访问受保护工作台 — existing

### Active

- [ ] 系统能识别用户回答里的矛盾、信息缺口和隐含假设，并据此推进澄清
- [ ] 系统能判断当前应该继续深挖还是开始收敛，而不是始终停留在同一种对话节奏
- [ ] 系统能优先给出可反应的选项，降低用户“脑中有想法但不会表达”的阻力
- [ ] 系统默认采用“先探索、再逐步收紧”的引导模式，并支持按用户状态切换推进强度
- [ ] 系统最终输出的 PRD 初稿应明确核心用户、问题、方案、边界，以及已发现的矛盾点

### Out of Scope

- 通用闲聊助手体验优化 — 当前目标是高质量需求澄清与 PRD 收敛，不是提升陪聊自然度
- 为模式切换做花哨展示层 — 模式只是手段，优先验证它是否真的提升收敛质量
- 多端产品矩阵扩展（如移动端原生 App） — 当前聚焦在已有 Web 工作台内把核心引导链路做深
- 面向大型团队的复杂协同流程 — 当前主要用户是个人开发者，不先引入重型协作能力

## Context

- 代码库是 `pnpm` monorepo，前端位于 `apps/web`，使用 Next.js 15、React 19、Zustand；后端位于 `apps/api`，使用 FastAPI、SQLAlchemy、PostgreSQL。
- 现有产品主线已经围绕工作台会话形成：用户可以进入工作台，发送想法，接收流式 AI 回复，并逐步形成 PRD/状态快照。
- 后端已经有独立的 agent 决策层，位于 `apps/api/app/agent`；前端有工作台状态与事件应用层，位于 `apps/web/src/store/workspace-store.ts`。
- 当前这轮产品优化重点不是“补一个聊天入口”，而是增强引导结构、深挖能力和 PRD 沉淀质量。
- 主要目标用户是个人开发者：他们往往只有模糊想法，不知道如何把想法具象化，也不知道需求边界和隐含矛盾在哪里。

## Constraints

- **Tech stack**: 延续现有 Next.js + FastAPI + PostgreSQL 架构 — 当前产品已具备可运行工作台与后端能力，不适合为本轮目标推倒重来
- **Product focus**: 优先改善引导结构，其次追问深度，再到 PRD 沉淀 — 这是当前已确认的能力优先级
- **Default interaction**: 默认模式必须先探索再逐步收紧 — 需要在保持用户可表达空间的同时推进收敛
- **User segment**: 主要面向个人开发者 — 决定了交互、术语和产出物要偏“帮助想清楚”，而不是面向企业流程管理
- **Outcome quality**: 最终产物必须能落到结构化 PRD 初稿 — 成功标准不是聊得多，而是能明确用户、问题、方案和边界

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| 现阶段聚焦“引导式需求澄清与 PRD 收敛”而不是通用聊天体验 | 用户真正痛点是不会把模糊想法压实，不是缺一个聊天窗口 | — Pending |
| 引导能力优先级为“引导结构 > 追问深度 > PRD 沉淀” | 先解决节奏控制和推进机制，才能让追问和文档沉淀稳定发挥作用 | — Pending |
| 产品需要支持可切换的引导模式 | 不同用户状态需要不同推进强度，但模式切换必须服务于 PRD 收敛 | — Pending |
| 默认模式采用“先探索，再逐步收紧” | 既保留用户表达空间，又能逐步把对话收束到可确认结果 | — Pending |
| 当前优先增强矛盾识别、收敛判断和选项式引导 | 这三项最直接影响用户能否从模糊想法走到清晰 PRD | — Pending |

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
*Last updated: 2026-04-16 after initialization*
