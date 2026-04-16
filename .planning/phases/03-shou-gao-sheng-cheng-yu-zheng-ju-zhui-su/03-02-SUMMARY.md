---
phase: 03-shou-gao-sheng-cheng-yu-zheng-ju-zhui-su
plan: 02
subsystem: api
tags: [fastapi, sse, snapshot, finalize, export]
requires: [03-01]
provides:
  - `draft.updated` SSE 事件
  - enriched `prd_draft/evidence` 的 snapshot 与 turn decision meta
  - finalize/export 对 entry 级首稿的兼容投影
affects: [messages, sessions, finalize, export, workspace-store]
tech-stack:
  added: []
  patterns: [single-stream draft event, finalize/export compatibility projection]
key-files:
  created: []
  modified:
    - apps/api/app/schemas/message.py
    - apps/api/app/services/messages.py
    - apps/api/app/services/sessions.py
    - apps/api/app/agent/finalize_flow.py
    - apps/api/app/services/exports.py
    - apps/api/app/schemas/state.py
    - apps/api/tests/test_messages_stream.py
    - apps/api/tests/test_sessions.py
    - apps/api/tests/test_finalize_session.py
key-decisions:
  - "`draft.updated` 与 `prd.updated` 在同一条 SSE 流里共存，但 payload 语义严格分层"
  - "turn decision 只回放本轮 draft/evidence 摘要，不承担当前首稿真源"
  - "finalize/export 通过兼容投影读取 enriched `prd_draft.sections[].entries`"
patterns-established:
  - "session snapshot 与 turn decision meta 都能恢复结构化首稿与证据来源"
requirements-completed: [INTK-01, INTK-02, INTK-03]
duration: 35min
completed: 2026-04-16
---

# Phase 03-02 Summary

**Phase 3 的首稿 contract 已经进入持久化、SSE、snapshot 和 finalize/export 主链路。**

## Accomplishments

- 新增 `draft.updated` 事件，并放在 `decision.ready` 之后、`assistant.version.started` 之前。
- `sessions` 的 turn decision meta 现在会带 `draft_updates` 和 `evidence_ref_ids`，供前端恢复“本轮新增了什么”。
- `finalize_flow` 与 `exports` 已支持从 entry 级 `prd_draft.sections[].entries` 投影出兼容的 `{title, content, status}` 结构。
- `StateSnapshot` payload 补了 legacy 下标兼容，避免 finalize/snapshot 读取断裂。

## Verification

- `PYTHONPATH=apps/api uv run pytest apps/api/tests/test_messages_service.py apps/api/tests/test_messages_stream.py apps/api/tests/test_sessions.py -q -k "draft or evidence"`
- `PYTHONPATH=apps/api uv run pytest apps/api/tests/test_finalize_session.py apps/api/tests/test_messages_stream.py -q -k "draft or finalize or prd_updated"`

## Deviations from Plan

- 无。
