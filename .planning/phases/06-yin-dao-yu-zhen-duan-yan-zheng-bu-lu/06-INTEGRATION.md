---
phase: 06
verified: 2026-04-16
status: passed
scope: "Phase 1 → Phase 2"
---

# Phase 1 → Phase 2 Integration Verification

## Verdict

**passed**

`guidance contract → decision.ready → session snapshot → workspace store → diagnostics ledger UI` 这条跨阶段链路已有直接自动化证据，不需要新增 bridging regression。

## Verification Runs

### Backend

Command:

```bash
PYTHONPATH=apps/api uv run pytest apps/api/tests/test_sessions.py apps/api/tests/test_messages_stream.py -q -k "guidance or diagnostic or snapshot"
```

Result:

```text
13 passed, 27 deselected in 5.44s
```

### Frontend

Command:

```bash
cd apps/web && pnpm test -- src/test/workspace-store.test.ts src/test/workspace-session-shell.test.tsx
```

Result:

```text
23 test files passed
227 tests passed
```

## Flow Under Test

1. Phase 1 产生结构化 guidance contract  
2. `decision.ready` 事件同时携带 guidance 与 diagnostics 元数据  
3. session snapshot / turn decision 持久化保持 guidance 和 diagnostics 同源  
4. workspace store hydrate / merge 时同时保留 decision guidance 与 open ledger  
5. UI 在会话列展示 diagnostics，不污染右侧 PRD 面板

## Evidence

| Link | Evidence | Why it closes the gap |
|------|----------|-----------------------|
| `decision.ready` guidance + diagnostics | `apps/api/tests/test_messages_stream.py::test_message_stream_emits_decision_ready_with_structured_guidance` 断言同一 payload 同时包含 `guidance_mode/guidance_step/focus_dimension` 与 `diagnostics/diagnostic_summary/ledger_summary` | 证明 guidance 真源和 diagnostics 真源在流式事件里并存，不互相覆盖。 |
| stream → snapshot consistency | `apps/api/tests/test_sessions.py::test_stream_guidance_matches_session_snapshot_guidance` 断言 `decision.ready` 中的 guidance 和 diagnostics 与 session snapshot / turn decision meta 一致 | 证明跨阶段信息不是前端重算，而是后端在 stream/snapshot 之间保持同一份真相。 |
| event merge → open ledger | `apps/web/src/test/workspace-store.test.ts::merges diagnostics from decision.ready into the open ledger` 与 `...keeps the fresher diagnostic ledger when a stale snapshot hydrates` | 证明 store 同时消费 guidance 与 diagnostics，并对 stale snapshot 做保护。 |
| hydrate → conversation column | `apps/web/src/test/workspace-session-shell.test.tsx::hydrates structured guidance from the session snapshot` 与 `...renders diagnostics only in the conversation column after hydrate` | 证明 guidance 仍作为引导状态存在，而 diagnostics 只进入会话列，不污染 PRD panel。 |

## Files Involved

- [message_preparation.py](/Users/zhangyanhua/AI/chat-prd2/apps/api/app/services/message_preparation.py)
- [sessions.py](/Users/zhangyanhua/AI/chat-prd2/apps/api/app/services/sessions.py)
- [workspace-store.ts](/Users/zhangyanhua/AI/chat-prd2/apps/web/src/store/workspace-store.ts)
- [workspace-session-shell.tsx](/Users/zhangyanhua/AI/chat-prd2/apps/web/src/components/workspace/workspace-session-shell.tsx)

## Remaining Boundary

- 这个 artifact 只关闭 `Phase 1 → Phase 2` integration gap。
- 后续 `Phase 3 → Phase 4` 与 `Phase 4 → Phase 5` 仍需要各自的 integration verification artifact，在 Phase 7 / 8 处理。

## Self-Check

PASSED
