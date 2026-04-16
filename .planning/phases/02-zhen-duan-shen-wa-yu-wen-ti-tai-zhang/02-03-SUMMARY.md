---
phase: 02-zhen-duan-shen-wa-yu-wen-ti-tai-zhang
plan: 03
subsystem: ui
tags: [nextjs, react, zustand, diagnostics-ui]
requires:
  - phase: 02-02
    provides: diagnostics SSE/snapshot contract
provides:
  - workspace store 统一维护 latest diagnostics 与 open ledger
  - AssistantTurnCard 展示本轮诊断摘要
  - 会话列新增持续问题台账卡片，且不修改 PRD 面板
affects: [conversation-panel, assistant-turn-card, workspace-session-shell]
tech-stack:
  added: []
  patterns: [store 统一 diagnostics 真源, 会话列最小诊断 UI]
key-files:
  created:
    - apps/web/src/components/workspace/diagnostics-ledger-card.tsx
  modified:
    - apps/web/src/lib/types.ts
    - apps/web/src/store/workspace-store.ts
    - apps/web/src/components/workspace/assistant-turn-card.tsx
    - apps/web/src/components/workspace/conversation-panel.tsx
    - apps/web/src/test/workspace-store.test.ts
    - apps/web/src/test/assistant-turn-card.test.tsx
    - apps/web/src/test/workspace-session-shell.test.tsx
key-decisions:
  - "open ledger 继续留在会话列，不侵入右侧 PRD 面板"
  - "decision.ready 只增量更新本轮诊断与 ledger summary，完整 ledger 由 snapshot hydrate 恢复"
patterns-established:
  - "store 统一 merge snapshot diagnostics 与 decision.ready diagnostics"
requirements-completed: [DIAG-02, DIAG-03]
duration: 55min
completed: 2026-04-16
---

# Phase 02-03 Summary

**用户现在可以在会话列同时看到“本轮诊断”和“持续问题台账”**

## Accomplishments

- 扩展前端 diagnostics 类型，并在 `workspace-store` 中统一管理 latest diagnostics 与 open ledger。
- 在 `AssistantTurnCard` 中新增本轮诊断摘要，直接展示类型、影响范围和建议动作。
- 新增 `DiagnosticsLedgerCard`，按未知项 / 风险 / 待验证三组展示持续问题台账。

## Verification

- `cd apps/web && pnpm test -- src/test/workspace-store.test.ts src/test/assistant-turn-card.test.tsx src/test/workspace-session-shell.test.tsx`

## Deviations from Plan

- 无。
