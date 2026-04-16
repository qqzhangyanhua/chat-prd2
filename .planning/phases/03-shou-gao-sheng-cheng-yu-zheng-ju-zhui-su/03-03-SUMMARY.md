---
phase: 03-shou-gao-sheng-cheng-yu-zheng-ju-zhui-su
plan: 03
subsystem: web
tags: [react, zustand, workspace, first-draft]
requires: [03-02]
provides:
  - first-draft 前端类型与独立 store
  - 会话列首稿卡片与来源抽屉
  - `PrdPanel` 不消费 `draft.updated` 的边界回归
affects: [conversation-panel, workspace-store, prd-panel]
tech-stack:
  added: []
  patterns: [independent firstDraft view model, conversation-column draft UI]
key-files:
  created:
    - apps/web/src/components/workspace/first-draft-card.tsx
    - apps/web/src/components/workspace/draft-evidence-drawer.tsx
  modified:
    - apps/web/src/lib/types.ts
    - apps/web/src/store/workspace-store.ts
    - apps/web/src/components/workspace/conversation-panel.tsx
    - apps/web/src/test/workspace-store.test.ts
    - apps/web/src/test/workspace-session-shell.test.tsx
    - apps/web/src/test/prd-panel.test.tsx
key-decisions:
  - "firstDraft 在 store 中独立于 `prd` 和 diagnostics ledger 维护"
  - "首稿 UI 放在会话列，右侧 `PrdPanel` 继续只展示 runtime preview"
  - "来源查看采用轻量 drawer，不引入额外状态管理或重型浮层"
patterns-established:
  - "snapshot hydrate 与 `draft.updated` merge 都走同一套 firstDraft normalization"
requirements-completed: [INTK-01, INTK-02, INTK-03]
duration: 40min
completed: 2026-04-16
---

# Phase 03-03 Summary

**用户现在可以在会话列直接看到结构化首稿、区分确认状态，并逐条查看来源证据。**

## Accomplishments

- 增加 `firstDraft` 独立 store，支持 snapshot hydrate、`draft.updated` merge 和 stale snapshot 保护。
- 新建 `FirstDraftCard` 与 `DraftEvidenceDrawer`，在会话列展示首稿 section、条目状态和来源追溯。
- 保持 `PrdPanel` 不变，只增加回归测试确保 `draft.updated` 不会污染右侧预览列。

## Verification

- `cd apps/web && pnpm test -- src/test/workspace-store.test.ts src/test/workspace-session-shell.test.tsx src/test/prd-panel.test.tsx`

## Deviations from Plan

- 无。
