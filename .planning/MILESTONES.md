# Milestones

## v1.0 AI Brainstorming PRD Copilot v1 (Shipped: 2026-04-16)

**Phases completed:** 8 phases, 24 plans

**Key accomplishments:**

- 后端 guidance contract 现在能显式表达节奏、推进维度、切换原因和 options-first 选项决策
- session snapshot、turn decision meta 和 SSE guidance payload 现在共享同一份 guidance 真相
- 工作台现在能直接展示当前引导节奏、聚焦维度、options-first 选项和“都不对，我补充”入口
- 后端已经能稳定产出结构化诊断项，并把兼容字段统一降级为 diagnostics 派生结果
- diagnostics 现在已经贯通到 SSE、turn decision 持久化和 session snapshot
- 用户现在可以在会话列同时看到“本轮诊断”和“持续问题台账”
- Phase 3 的首稿 contract 已经落地到后端类型、state schema 和 pm_mentor 输出。
- Phase 3 的首稿 contract 已经进入持久化、SSE、snapshot 和 finalize/export 主链路。
- 用户现在可以在会话列直接看到结构化首稿、区分确认状态，并逐条查看来源证据。
- Phase 4 的后端 panel contract 已落地：系统现在可以把 persisted `prd_draft`、diagnostics 和 readiness 统一投影成章节化 PRD 视图。
- Phase 4 的 panel projection 已经接入消息流、snapshot、finalize 与 export，右侧 PRD 不再依赖不同路径各自拼装。
- 前端已经完整消费 Phase 4 的章节化 PRD contract，右侧 `PrdPanel` 现在是收敛视图，不再只是 preview。
- 独立 PRD review projector 与 snapshot sibling contract，稳定输出五个质量维度、缺口列表和 legacy fallback 结果
- 结构化 PRD 导出继续复用共享 projection，并附带分区明确的 review/handoff 附录与 replay-friendly 交付里程碑。
- 单会话 replay timeline 与前端 review/replay 消费已经打通，Phase 5 到此闭环。
- 已为 Phase 1 补齐可审计的 verification artifact，GUID-01~04 不再只停留在 summary 声明层。
- Phase 2 的 verification artifact 和 `Phase 1 → Phase 2` integration artifact 已经补齐。
- Phase 6 的 planning 状态已与 verification 证据对齐，并把焦点移交到 Phase 7。
- 已为 Phase 3 补齐可审计的 verification artifact，INTK-01~03 不再只停留在 summary 声明层。
- Phase 4 的 verification artifact 和 `Phase 3 → Phase 4` integration artifact 已经补齐。
- Phase 7 的 planning 状态已与 verification 证据对齐，并把焦点移交到 Phase 8。
- Phase 5 的 requirement-level verification 已补齐，RVW-01~03 不再依赖 summary/UAT 的间接声明。
- 最后两类审计证据已经补齐：`Phase 4 → Phase 5` integration artifact 和 milestone 主线 E2E artifact。
- Phase 8 的 planning 状态已与全部验证证据对齐，并把下一步焦点切换到 milestone re-audit。

---
