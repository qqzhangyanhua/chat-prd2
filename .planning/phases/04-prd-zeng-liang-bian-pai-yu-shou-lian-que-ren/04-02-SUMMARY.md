---
phase: 04-prd-zeng-liang-bian-pai-yu-shou-lian-que-ren
plan: 02
subsystem: api
tags: [fastapi, sse, snapshot, finalize, export]
requires: [04-01]
provides:
  - SSE 与 session snapshot 共用的 Phase 4 panel payload
  - finalize 接入 readiness projector 的收敛门槛
  - export 兼容 risks/open questions 的章节化导出
affects: [messages, sessions, finalize, exports, prd-panel]
tech-stack:
  added: []
  patterns: [single prd panel payload, finalized panel compatibility, export from projection]
key-files:
  created: []
  modified:
    - apps/api/app/services/messages.py
    - apps/api/app/services/sessions.py
    - apps/api/app/agent/finalize_flow.py
    - apps/api/app/services/exports.py
    - apps/api/tests/test_messages_service.py
    - apps/api/tests/test_messages_stream.py
    - apps/api/tests/test_sessions.py
    - apps/api/tests/test_finalize_session.py
    - apps/api/app/schemas/prd.py
    - apps/api/app/services/prd_runtime.py
    - apps/api/app/services/finalize_session.py
key-decisions:
  - "session snapshot 不再只返回 sections，而是直接返回与 `prd.updated` 同 shape 的 panel payload"
  - "finalize 以 readiness projector 为准，stored `finalization_ready` 只作为历史状态，不再单独决定是否可 finalize"
  - "export 以 Phase 4 projection 为主，并保留 summary/out_of_scope 等 draft 补充字段"
patterns-established:
  - "SSE、snapshot、finalize、export 全部通过同一条 `prd_draft -> panel payload` 路径收敛"
requirements-completed: [PRD-02, PRD-03, PRD-04]
duration: 约 55min
completed: 2026-04-16
---

# Phase 04-02 Summary

**Phase 4 的 panel projection 已经接入消息流、snapshot、finalize 与 export，右侧 PRD 不再依赖不同路径各自拼装。**

## Accomplishments

- 扩展 `PrdSnapshotResponse`，让 snapshot 返回 `meta / sections_changed / missing_sections / gap_prompts / ready_for_confirmation`，与 `prd.updated` 保持同 shape。
- 在 `prd_runtime` 增加统一 snapshot payload builder，`messages.py` 与 `sessions.py` 都只消费这套 projector contract。
- finalize 改为使用 readiness projector 判定是否允许终稿化，并在 finalized sections 中保留 `risks_to_validate` / `open_questions` 等辅助章节。
- export 现在以 Phase 4 projection 为主输出章节，同时继续兼容 `summary` / `out_of_scope` 等 draft 补充字段，不回退成整篇重写。
- 补齐 stream-refresh、snapshot hydrate、finalize gate、export 风险摘要等回归测试。

## Verification

- `rg -n "sections_changed|missing_sections|ready_for_confirmation" apps/api/app/services/messages.py apps/api/app/services/sessions.py`
- `rg -n "ready_for_confirmation|finalized|open_questions|risks_to_validate" apps/api/app/agent/finalize_flow.py apps/api/app/services/exports.py apps/api/tests/test_finalize_session.py`
- `PYTHONPATH=apps/api uv run pytest apps/api/tests/test_messages_service.py apps/api/tests/test_messages_stream.py apps/api/tests/test_sessions.py -q -k "prd_updated or snapshot or finalize"`
- `PYTHONPATH=apps/api uv run pytest apps/api/tests/test_finalize_session.py -q -k "finalize or normalized"`

## Deviations from Plan

- 额外修改了 `apps/api/app/schemas/prd.py`、`apps/api/app/services/prd_runtime.py`、`apps/api/app/services/finalize_session.py`。原因是 04-02 要把 panel contract 真正贯通到 snapshot 与 finalize 链路，这三处是必要接口层，不改无法完成计划目标。
