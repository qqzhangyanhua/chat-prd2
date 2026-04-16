---
phase: 05-zhi-liang-fu-he-yu-jiao-fu-hui-fang
plan: 02
subsystem: api
tags: [fastapi, export, finalize, prd-review, replay]
requires:
  - phase: 05-01
    provides: 独立 prd_review contract 与 snapshot sibling review payload
provides:
  - review-aware export builder，继续复用 Phase 4 panel projection sections
  - finalize/export 最小交付里程碑线索，供后续 replay 聚合识别
  - 结构化 PRD markdown 附录，分离 review/handoff 摘要且保持 file_name/content 兼容
affects: [exports, finalize, replay, review]
tech-stack:
  added: []
  patterns: [export-from-projection, delivery-milestone-without-new-storage]
key-files:
  created: []
  modified:
    - apps/api/app/services/exports.py
    - apps/api/app/api/routes/exports.py
    - apps/api/app/services/finalize_session.py
    - apps/api/tests/test_sessions.py
    - apps/api/tests/test_finalize_session.py
key-decisions:
  - "导出正文继续完全来自 `build_prd_updated_event_data(...)[\"sections\"]`，review/handoff 只作为附录追加，不混入 panel projection。"
  - "replay 所需 finalize/export 线索通过现有 state 版本和 export response 推导，不新增 repository 或持久化表。"
patterns-established:
  - "导出响应可以扩展 sibling 元数据，但必须保留 `file_name` 与 `content` 作为向后兼容主契约。"
  - "交付里程碑优先落在现有 state/output 上，后续 replay 聚合从已有记录读取。"
requirements-completed: [RVW-02]
duration: 7min
completed: 2026-04-16
---

# Phase 05 Plan 02: 导出与交付链路 Summary

**结构化 PRD 导出继续复用共享 projection，并附带分区明确的 review/handoff 附录与 replay-friendly 交付里程碑。**

## Performance

- **Duration:** 7 min
- **Started:** 2026-04-16T05:30:00Z
- **Completed:** 2026-04-16T05:37:12Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- `exports.py` 继续以 Phase 4 panel projection sections 作为 PRD 正文章节来源，并保留 `risks_to_validate` / `open_questions` 等待验证内容。
- 导出结果新增独立 `appendix` 与 markdown `交付附录`，把 review summary / handoff summary 放在正文之后，避免污染共享 projection。
- `finalize_session.py` 在现有 state version 中写入最小 `delivery_milestone`，并在 export response 暴露 finalize/export milestone 线索，供 05-03 replay 复用。

## Task Commits

Each task was committed atomically:

1. **Task 1: 扩展 export builder，复用 panel projection 并保留待验证项与最小 review 摘要** - `c35213e` (feat)
2. **Task 2: 在 finalize/export 链路补齐可回放的交付里程碑，而不新增持久化表** - `e5453dc` (feat)

**Plan metadata:** pending docs commit

## Files Created/Modified

- `apps/api/app/services/exports.py` - 复用 panel projection 生成 markdown，并追加独立 appendix 与 export milestone。
- `apps/api/app/api/routes/exports.py` - 放宽导出 route 返回类型，兼容新增 sibling 元数据。
- `apps/api/app/services/finalize_session.py` - 写入 replay-friendly finalize delivery milestone。
- `apps/api/tests/test_sessions.py` - 覆盖 finalized / draft 导出、appendix 分区、handoff summary 与 export milestone。
- `apps/api/tests/test_finalize_session.py` - 覆盖 finalize 持久化 delivery milestone 字段。

## Decisions Made

- 导出附录的 summary 不直接照搬 snapshot review verdict，而是按 export 语义根据 checks 降级，避免 finalize-ready 状态掩盖开放风险。
- 缺失章节在 handoff summary 中按 PRD 章节顺序输出，保证 replay/handoff 消费稳定可读。

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- 当前工作区已有未提交的 phase 连续改动；本次仅暂存和提交 05-02 直接涉及的后端文件，未回滚或混入其他改动。

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- 05-03 可以直接复用 `delivery_milestone` 与 export response 中的 finalize/export metadata 做 replay timeline 聚合。
- 导出正文、appendix 与 finalize milestone 的边界已固定，不需要额外存储层即可继续推进。

## Self-Check

PASSED

- FOUND: `.planning/phases/05-zhi-liang-fu-he-yu-jiao-fu-hui-fang/05-02-SUMMARY.md`
- FOUND: `c35213e`
- FOUND: `e5453dc`

---
*Phase: 05-zhi-liang-fu-he-yu-jiao-fu-hui-fang*
*Completed: 2026-04-16*
