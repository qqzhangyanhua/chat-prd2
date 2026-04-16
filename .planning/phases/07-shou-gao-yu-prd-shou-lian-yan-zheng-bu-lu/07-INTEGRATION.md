---
phase: 07
verified: 2026-04-16
status: passed
scope: "Phase 3 → Phase 4"
---

# Phase 3 → Phase 4 Integration Verification

## Verdict

**passed**

`structured prd_draft/evidence → prd.updated → session snapshot → workspace store → PrdPanel` 这条跨阶段链路已有直接自动化证据，不需要新增 bridging regression。

## Verification Runs

### Backend

Command:

```bash
PYTHONPATH=apps/api uv run pytest apps/api/tests/test_messages_stream.py apps/api/tests/test_sessions.py apps/api/tests/test_messages_service.py apps/api/tests/test_finalize_session.py -q -k "draft or prd_updated or snapshot or finalize"
```

Result:

```text
40 passed, 46 deselected in 13.03s
```

### Frontend

Command:

```bash
cd apps/web && pnpm test -- src/test/workspace-store.test.ts src/test/prd-panel.test.tsx src/test/workspace-session-shell.test.tsx
```

Result:

```text
23 test files passed
227 tests passed
```

## Flow Under Test

1. Phase 3 持久化 `prd_draft` 与 `evidence` 真源  
2. Phase 4 从 persisted truth 投影出 `prd.updated` / `prd_snapshot`  
3. readiness projector 基于同一 truth 产生 `missing_sections/gap_prompts/ready_for_confirmation`  
4. workspace store hydrate / merge 时保持 first-draft 与 panel projection 分层  
5. 右侧 `PrdPanel` 只消费 panel projection，会话列继续承载 first draft / evidence

## Evidence

| Link | Evidence | Why it closes the gap |
|------|----------|-----------------------|
| persisted draft → panel projection | `apps/api/tests/test_messages_stream.py::test_message_stream_emits_draft_updated_without_polluting_prd_updated` 断言 `draft.updated` 与 `prd.updated` 分层共存 | 证明首稿真源和 panel projection 不是同一层语义，Phase 4 没有回退成 raw draft 直出。 |
| stream → snapshot consistency | `apps/api/tests/test_sessions.py::test_get_session_snapshot_returns_panel_projection_shape_from_structured_draft` 以及第 624-627 行断言 snapshot 与 `prd.updated` 的 `sections_changed/missing_sections/gap_prompts/ready_for_confirmation` 一致 | 证明跨阶段信息不是前端重算，而是后端在 stream/snapshot 间保持同一份投影真相。 |
| readiness/finalize reuse | `apps/api/tests/test_readiness.py` 的 ready/finalized 场景，以及 `apps/api/tests/test_sessions.py::test_finalize_route_moves_ready_session_to_completed` | 证明 persisted draft 真源继续被 readiness/finalize 复用，而不是另一条分叉状态机。 |
| hydrate → panel layering | `apps/web/src/test/workspace-session-shell.test.tsx::keeps first draft in conversation column while prd panel renders gap and confirm state` 与 `apps/web/src/test/prd-panel.test.tsx` 的 changed sections / gap 渲染 | 证明 first draft/evidence 继续留在会话列，右侧 panel 只消费 panel projection。 |

## Files Involved

- [prd_runtime.py](/Users/zhangyanhua/AI/chat-prd2/apps/api/app/services/prd_runtime.py)
- [sessions.py](/Users/zhangyanhua/AI/chat-prd2/apps/api/app/services/sessions.py)
- [workspace-store.ts](/Users/zhangyanhua/AI/chat-prd2/apps/web/src/store/workspace-store.ts)
- [prd-panel.tsx](/Users/zhangyanhua/AI/chat-prd2/apps/web/src/components/workspace/prd-panel.tsx)
- [workspace-session-shell.tsx](/Users/zhangyanhua/AI/chat-prd2/apps/web/src/components/workspace/workspace-session-shell.tsx)

## Remaining Boundary

- 这个 artifact 只关闭 `Phase 3 → Phase 4` integration gap。
- 后续 `Phase 4 → Phase 5` 和 milestone 级 E2E 验证仍需要在 Phase 8 收口。

## Self-Check

PASSED
