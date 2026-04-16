---
phase: 08
verified: 2026-04-16
status: passed
scope: "Phase 4 → Phase 5"
---

# Phase 4 → Phase 5 Integration Verification

## Verdict

**passed**

`structured prd_draft/evidence → prd_snapshot panel projection → prd_review sibling → export appendix/delivery milestones → replay_timeline → workspace store → PrdPanel/ReplayPanel` 这条跨阶段链路已有直接自动化证据，不需要新增 bridging regression。

## Verification Runs

### Backend

Command:

```bash
PYTHONPATH=apps/api uv run pytest apps/api/tests/test_sessions.py -q -k "review or snapshot or replay or timeline"
```

Result:

```text
12 passed, 19 deselected in 2.63s
```

Command:

```bash
PYTHONPATH=apps/api uv run pytest apps/api/tests/test_finalize_session.py apps/api/tests/test_sessions.py -q -k "export or appendix or handoff"
```

Result:

```text
5 passed, 33 deselected in 1.39s
```

### Frontend

Command:

```bash
cd apps/web && pnpm test -- src/test/prd-panel.test.tsx src/test/replay-panel.test.tsx src/test/workspace-session-shell.test.tsx
```

Result:

```text
23 test files passed
227 tests passed
```

## Flow Under Test

1. Phase 4 将 `prd_draft/evidence` 投影成章节化 `prd_snapshot`，并保留 `missing_sections/gap_prompts/ready_for_confirmation`
2. Phase 5 在同一份 persisted truth 之上追加 `prd_review` sibling，而不污染 `prd_snapshot`
3. export 继续复用 panel projection 作为正文来源，仅在正文后追加独立 `交付附录`
4. finalize/export milestone 被编码进现有 state/output，供 `replay_timeline` 聚合使用
5. workspace store 一次 hydrate 同时接收 `prd/prdReview/replayTimeline`，`PrdPanel` 继续只消费正文 projection，`ReplayPanel` 独立展示回放

## Evidence

| Link | Evidence | Why it closes the gap |
|------|----------|-----------------------|
| panel projection → review sibling | `apps/api/tests/test_sessions.py::test_get_session_snapshot_preserves_prd_panel_contract_after_stream_refresh` 与 `apps/web/src/test/prd-panel.test.tsx::renders review summary without polluting prd sections` | 证明 Phase 5 没有把 review 数据塞回 Phase 4 的正文 contract，`prd_snapshot` 和 `prd_review` 保持分层。 |
| panel projection → export appendix | `apps/api/tests/test_sessions.py::test_export_keeps_phase4_risk_and_question_sections` 与 `::test_export_returns_draft_status_when_not_finalized` | 证明导出正文继续复用 Phase 4 章节化投影，review/handoff 仅作为 `交付附录` 追加，而不是重建另一套正文。 |
| finalize/export milestones → replay timeline | `apps/api/tests/test_sessions.py::test_get_session_snapshot_returns_replay_timeline_with_delivery_milestones` 与 `apps/web/src/test/replay-panel.test.tsx::renders replay timeline in snapshot order with finalize and export milestones` | 证明交付里程碑被 replay 聚合消费，且没有引入新的持久化层。 |
| snapshot hydrate → separated frontend consumers | `apps/web/src/test/workspace-session-shell.test.tsx::hydrates prd review and replay timeline from session snapshot` 与 `apps/web/src/test/workspace-store.test.ts::stores prd review and replay timeline separately from prd panel sections` | 证明前端把 `prdReview`、`replayTimeline` 与 `prd` 正文分开维护，跨阶段 contract 没有在 hydrate 时混层。 |

## Files Involved

- [sessions.py](/Users/zhangyanhua/AI/chat-prd2/apps/api/app/services/sessions.py)
- [exports.py](/Users/zhangyanhua/AI/chat-prd2/apps/api/app/services/exports.py)
- [session_replay.py](/Users/zhangyanhua/AI/chat-prd2/apps/api/app/services/session_replay.py)
- [workspace-store.ts](/Users/zhangyanhua/AI/chat-prd2/apps/web/src/store/workspace-store.ts)
- [prd-panel.tsx](/Users/zhangyanhua/AI/chat-prd2/apps/web/src/components/workspace/prd-panel.tsx)
- [replay-panel.tsx](/Users/zhangyanhua/AI/chat-prd2/apps/web/src/components/workspace/replay-panel.tsx)

## Remaining Boundary

- 这个 artifact 只关闭 `Phase 4 → Phase 5` integration gap。
- milestone 级“模糊想法进入系统直到 review/export/replay”的整条主线验收，单独记录在 `08-E2E.md`。

## Self-Check

PASSED
