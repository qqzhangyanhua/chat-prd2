---
phase: 04-prd-zeng-liang-bian-pai-yu-shou-lian-que-ren
plan: 03
subsystem: web
tags: [nextjs, zustand, prd-panel, snapshot, streaming]
requires: [04-02]
provides:
  - 前端 `prd` store 消费 Phase 4 panel contract
  - 右侧 `PrdPanel` 的章节化展示、缺口提示与确认 CTA
  - 与 Phase 3 first-draft UI 分层的前端回归覆盖
affects: [prd-panel, workspace-store, workspace-session-shell]
tech-stack:
  added: []
  patterns: [panel projection state, changed section highlight, gap prompt rendering]
key-files:
  created: []
  modified:
    - apps/web/src/lib/types.ts
    - apps/web/src/store/prd-store-helpers.ts
    - apps/web/src/store/workspace-store.ts
    - apps/web/src/components/workspace/prd-panel.tsx
    - apps/web/src/test/workspace-store.test.ts
    - apps/web/src/test/prd-panel.test.tsx
    - apps/web/src/test/workspace-session-shell.test.tsx
    - apps/web/src/test/workspace-composer.test.tsx
    - apps/web/src/test/prd-store-helpers.test.ts
    - .planning/ROADMAP.md
    - .planning/STATE.md
key-decisions:
  - "前端 `prd` state 不再拆 `extraSections`，统一按 panel projection sections + sectionOrder 消费"
  - "右侧 panel 只展示 panel projection，不把 first-draft/evidence 搬进右侧"
  - "兼容 legacy finalize 路径，同时支持 Phase 4 的 ready-for-confirmation CTA"
patterns-established:
  - "snapshot hydrate、SSE prd.updated、stale snapshot 保护共用同一套 PRD panel normalize 逻辑"
requirements-completed: [PRD-01, PRD-02, PRD-03, PRD-04]
duration: 约 45min
completed: 2026-04-16
---

# Phase 04-03 Summary

**前端已经完整消费 Phase 4 的章节化 PRD contract，右侧 `PrdPanel` 现在是收敛视图，不再只是 preview。**

## Accomplishments

- `PrdState` 升级为统一的 panel projection 结构，新增 `sectionOrder / sectionsChanged / missingSections / gapPrompts / readyForConfirmation`。
- `workspace-store` 统一用 snapshot / SSE 共用的 normalize 逻辑维护 PRD panel 状态，并保留 stale snapshot 保护。
- `PrdPanel` 改为按章节顺序展示正文与辅助章节，支持本轮更新高亮、缺口提示和“确认初稿并生成最终版 PRD”入口。
- 保持 Phase 3 的 first-draft / evidence drawer 仍在会话列，不把 raw first-draft 直接搬进右侧 panel。
- 修正并补齐前端测试，使旧 `extraSections` / 旧 finalize 文案假设迁移到 Phase 4 语义。

## Verification

- `cd apps/web && pnpm test -- src/test/prd-store-helpers.test.ts src/test/prd-panel.test.tsx src/test/workspace-composer.test.tsx src/test/workspace-session-shell.test.tsx`
- `cd apps/web && pnpm test -- src/test/workspace-store.test.ts`
- `cd apps/web && pnpm test -- src/test/workspace-store.test.ts -t "prd panel|gap|changed"`
- `cd apps/web && pnpm test -- src/test/prd-panel.test.tsx src/test/workspace-session-shell.test.tsx -t "section|incremental|confirm|gap"`

## Deviations from Plan

- 额外修改了 `apps/web/src/test/workspace-composer.test.tsx` 和 `apps/web/src/test/prd-store-helpers.test.ts`。原因是 Phase 4 前端 contract 改变后，旧测试仍按 `extraSections` 与单一 finalize 文案断言，必须同步迁移，否则无法稳定验证新边界。
