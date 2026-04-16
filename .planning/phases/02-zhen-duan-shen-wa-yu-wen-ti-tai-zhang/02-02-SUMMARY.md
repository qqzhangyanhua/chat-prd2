---
phase: 02-zhen-duan-shen-wa-yu-wen-ti-tai-zhang
plan: 02
subsystem: api
tags: [fastapi, sse, snapshot, diagnostics-ledger]
requires:
  - phase: 02-01
    provides: diagnostics contract 与检测规则
provides:
  - decision.ready 暴露 diagnostics、diagnostic_summary、ledger_summary
  - state snapshot 持久化 open diagnostics ledger
  - turn decision 回放与 session hydrate 共享 diagnostics 数据源
affects: [workspace-store, workspace-session-shell]
tech-stack:
  added: []
  patterns: [per-turn snapshot + open ledger 双层真源]
key-files:
  created: []
  modified:
    - apps/api/app/schemas/message.py
    - apps/api/app/schemas/state.py
    - apps/api/app/services/message_preparation.py
    - apps/api/app/services/message_state.py
    - apps/api/app/services/sessions.py
    - apps/api/tests/test_messages_stream.py
    - apps/api/tests/test_sessions.py
key-decisions:
  - "decision.ready 只做 diagnostics 序列化，ledger 仍由 state snapshot 承担刷新恢复"
  - "session decision_sections.meta 直接回填 diagnostics，前端不再从历史文本重算"
patterns-established:
  - "turn decision 记录本轮诊断，state snapshot 记录当前 open ledger"
requirements-completed: [DIAG-02, DIAG-03]
duration: 45min
completed: 2026-04-16
---

# Phase 02-02 Summary

**diagnostics 现在已经贯通到 SSE、turn decision 持久化和 session snapshot**

## Accomplishments

- 扩展 `DecisionReadyEventData` 与 `StateSnapshot`，补上 diagnostics 相关结构化字段。
- 让 `message_preparation` 在构造 `decision.ready` 时同时输出本轮 diagnostics 和 ledger summary。
- 让 `sessions.py` 回放 `decision_sections.meta` 时直接携带 diagnostics 与统计摘要。

## Verification

- `PYTHONPATH=apps/api uv run pytest apps/api/tests/test_messages_stream.py apps/api/tests/test_sessions.py -q`

## Deviations from Plan

- 无。
