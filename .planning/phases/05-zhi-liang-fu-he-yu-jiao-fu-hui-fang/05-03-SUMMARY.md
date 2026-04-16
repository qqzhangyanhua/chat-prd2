---
phase: 05-zhi-liang-fu-he-yu-jiao-fu-hui-fang
plan: 03
subsystem: api+web
tags: [replay, review, snapshot, workspace]
requires: [05-01, 05-02]
provides:
  - 单会话 replay timeline 聚合
  - 前端 `prdReview` 与 `replayTimeline` 消费
  - review summary 与 panel projection 分层的用户界面
affects: [sessions, workspace-store, prd-panel, replay-panel]
tech-stack:
  added: []
  patterns: [review as sibling contract, replay timeline aggregation, snapshot-first hydration]
key-files:
  created:
    - apps/api/app/schemas/replay.py
    - apps/api/app/services/session_replay.py
    - apps/web/src/components/workspace/replay-panel.tsx
    - apps/web/src/test/replay-panel.test.tsx
  modified:
    - apps/api/app/schemas/session.py
    - apps/api/app/services/sessions.py
    - apps/api/tests/test_sessions.py
    - apps/web/src/lib/types.ts
    - apps/web/src/store/workspace-store.ts
    - apps/web/src/components/workspace/prd-panel.tsx
    - apps/web/src/components/workspace/workspace-session-shell.tsx
    - apps/web/src/test/workspace-store.test.ts
    - apps/web/src/test/prd-panel.test.tsx
    - apps/web/src/test/workspace-session-shell.test.tsx
    - .planning/ROADMAP.md
    - .planning/STATE.md
    - .planning/REQUIREMENTS.md
key-decisions:
  - "replay 只聚合单会话 narrative-first timeline，不新增持久化层"
  - "前端独立维护 `prdReview` 与 `replayTimeline`，不污染 `prd` panel state"
  - "PrdPanel` 只展示 review summary，不把 review 逻辑并回 panel projection"
patterns-established:
  - "snapshot 一次 hydrate 即可获得 panel + review + replay 三份合同"
requirements-completed: [RVW-03]
duration: 约 20min
completed: 2026-04-16
---

# Phase 05-03 Summary

**单会话 replay timeline 与前端 review/replay 消费已经打通，Phase 5 到此闭环。**

## Accomplishments

- 新增后端 `session_replay` 聚合层和 `replay` schema，基于现有 `messages / assistant_reply_groups / turn_decisions / snapshot versions` 组装 narrative-first timeline。
- `sessions.py` 现在在 snapshot 中同时返回 `prd_review` 与 `replay_timeline`，不新增持久化层。
- 前端独立维护 `prdReview` 和 `replayTimeline`，保持与 `prd` panel projection 分离。
- `PrdPanel` 增加 review summary 展示，但正文 sections 仍只消费 panel projection。
- 新增 `ReplayPanel`，在工作台中展示 guidance、diagnostics、PRD 变化以及 finalize/export 里程碑。

## Verification

- `PYTHONPATH=apps/api uv run pytest apps/api/tests/test_sessions.py -q -k "replay or timeline or review"`
- `cd apps/web && pnpm test -- src/test/workspace-store.test.ts src/test/prd-panel.test.tsx src/test/replay-panel.test.tsx src/test/workspace-session-shell.test.tsx`

## Deviations from Plan

- 无额外架构偏离。执行仍然遵守了 Phase 5 的三条硬边界：review contract 独立、export 复用后端 projection、replay 不引入新存储层。

## Self-Check

PASSED

- Found `.planning/phases/05-zhi-liang-fu-he-yu-jiao-fu-hui-fang/05-03-SUMMARY.md`
- Found task commit `d5e0d40`
- Found task commit `a21bb90`
