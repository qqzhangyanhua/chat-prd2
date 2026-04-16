---
phase: 05-zhi-liang-fu-he-yu-jiao-fu-hui-fang
plan: 01
subsystem: api
tags: [fastapi, pydantic, prd-review, snapshot, pytest]
requires:
  - phase: 04-prd-zeng-liang-bian-pai-yu-shou-lian-que-ren
    provides: Phase 4 的 panel projection、readiness projector 与 snapshot 聚合边界
provides:
  - 独立 prd_review contract
  - session snapshot 暴露 prd_review sibling 字段
  - legacy/structured review 回归测试
affects: [phase-05-export, phase-05-replay, api-snapshot, frontend-review-consumers]
tech-stack:
  added: []
  patterns: [review-contract-as-sibling, deterministic-review-from-truth]
key-files:
  created:
    - apps/api/app/schemas/review.py
    - apps/api/app/services/prd_review.py
    - apps/api/tests/test_prd_review.py
  modified:
    - apps/api/app/schemas/session.py
    - apps/api/app/services/sessions.py
    - apps/api/tests/test_sessions.py
key-decisions:
  - "质量复核继续独立于 panel projection，通过 prd_review sibling 字段暴露，避免污染 prd_snapshot contract。"
  - "review verdict 与五个维度只基于 persisted prd_draft、diagnostics 与 evaluate_finalize_readiness 推导，不从 panel payload 反推。"
patterns-established:
  - "Pattern 1: snapshot 同时返回内容投影 prd_snapshot 与质量判断 prd_review，边界清楚。"
  - "Pattern 2: legacy session 即使没有结构化草稿，也通过 fallback snapshot 返回稳定 review payload。"
requirements-completed: [RVW-01]
duration: 4min
completed: 2026-04-16
---

# Phase 05 Plan 01: Review Contract Summary

**独立 PRD review projector 与 snapshot sibling contract，稳定输出五个质量维度、缺口列表和 legacy fallback 结果**

## Performance

- **Duration:** 4 min
- **Started:** 2026-04-16T05:24:29Z
- **Completed:** 2026-04-16T05:28:43Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- 新增 `apps/api/app/schemas/review.py` 与 `apps/api/app/services/prd_review.py`，把质量判断从 panel projection 中彻底拆开。
- `SessionCreateResponse` / `get_session_snapshot()` 现在稳定返回 `prd_review` sibling 字段，structured 与 legacy 会话都可消费。
- 用 pytest 锁定五个 review 维度、缺失章节、待验证项和 legacy fallback 语义，避免后续 contract 漂移。

## Task Commits

Each task was committed atomically:

1. **Task 1: 定义独立 review schema 和 projector，按五个质量维度输出 verdict/checklist** - `a43c14a` (test), `1ca9635` (feat)
2. **Task 2: 通过 session snapshot 暴露 `prd_review`，保持 review contract 与 panel contract 解耦** - `0353e68` (test), `e12664e` (feat)

Plan metadata: captured in the final `docs(05-01)` metadata commit after state updates

## Files Created/Modified
- `apps/api/app/schemas/review.py` - 定义 review payload 与逐维度 check schema。
- `apps/api/app/services/prd_review.py` - 基于 `prd_draft`、`diagnostics`、`evaluate_finalize_readiness()` 生成 verdict/checks/gaps。
- `apps/api/tests/test_prd_review.py` - 覆盖充分、缺失、待验证、legacy fallback 四类 review 场景。
- `apps/api/app/schemas/session.py` - 为 session snapshot 新增 `prd_review` sibling 字段。
- `apps/api/app/services/sessions.py` - 在 create/get snapshot 流程中挂接 review projector。
- `apps/api/tests/test_sessions.py` - 回归 snapshot 同时返回 `prd_snapshot` 与 `prd_review`，且 legacy contract 稳定。

## Decisions Made
- review contract 不进入 `PrdUpdatedEventData`，保持 `prd_snapshot` 继续只承载 Phase 4 的 panel projection。
- 总体 verdict 继续把“缺失章节”视为 `revise`，同时允许逐维度单独暴露 `needs_input`，避免把缺失信息误判成纯待验证。

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Task 2 的初始断言把同时存在“缺失章节”和“开放风险”的 snapshot 总体 verdict 设成了 `needs_input`。实现阶段收敛为 `revise` + 维度级 `needs_input`，并用回归测试锁定该语义。

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 05-02 可以直接复用 `prd_review` 与 `prd_snapshot` 双合同扩展导出链路。
- 前端与 replay 后续只需要消费 snapshot sibling 字段，不必再从 panel payload 推断质量结论。

## Self-Check

PASSED

- Found summary and review contract files on disk.
- Verified task commits `a43c14a`, `1ca9635`, `0353e68`, `e12664e` exist in git history.

---
*Phase: 05-zhi-liang-fu-he-yu-jiao-fu-hui-fang*
*Completed: 2026-04-16*
