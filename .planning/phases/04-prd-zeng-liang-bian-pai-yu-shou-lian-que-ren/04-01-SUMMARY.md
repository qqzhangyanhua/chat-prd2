---
phase: 04-prd-zeng-liang-bian-pai-yu-shou-lian-que-ren
plan: 01
subsystem: api
tags: [fastapi, prd-panel, readiness, sse]
requires: []
provides:
  - `prd.updated` 章节化 panel contract
  - entry/completeness aware 的 readiness 与 gap projector
  - snapshot 与 SSE 对齐的 PRD panel projection
affects: [messages, sessions, prd-panel, finalize]
tech-stack:
  added: []
  patterns: [persisted prd_draft 真源, panel projection contract, legacy snapshot fallback]
key-files:
  created: []
  modified:
    - apps/api/app/schemas/message.py
    - apps/api/app/services/prd_runtime.py
    - apps/api/app/agent/readiness.py
    - apps/api/app/services/message_state.py
    - apps/api/app/services/sessions.py
    - apps/api/tests/test_readiness.py
    - apps/api/tests/test_message_state.py
    - apps/api/tests/test_messages_stream.py
    - apps/api/tests/test_sessions.py
key-decisions:
  - "右侧 PrdPanel 的 authoritative truth 改为后端 panel projection，不再让前端拼 first-draft"
  - "`to_validate` 进入 risk/open question 摘要，但不再等同于 missing"
  - "空状态与 legacy critic-only 预览继续保留旧 meta contract，避免打破 Phase 3 既有共享契约"
patterns-established:
  - "`prd.updated`、session snapshot、readiness projector 共用同一套 `prd_draft -> panel` 投影逻辑"
requirements-completed: [PRD-01, PRD-02, PRD-03, PRD-04]
duration: 约 45min
completed: 2026-04-16
---

# Phase 04-01 Summary

**Phase 4 的后端 panel contract 已落地：系统现在可以把 persisted `prd_draft`、diagnostics 和 readiness 统一投影成章节化 PRD 视图。**

## Accomplishments

- 扩展 `PrdUpdatedEventData`，固定 `sections`、`meta`、`sections_changed`、`missing_sections`、`gap_prompts`、`ready_for_confirmation` 字段。
- 重写 `prd_runtime` 的 panel projection：优先从结构化 `prd_draft.sections[*].entries/completeness` 生成 `target_user/problem/solution/mvp_scope/constraints/success_metrics/risks_to_validate/open_questions` 八个章节，只把 diagnostics 和待验证项做摘要投影。
- 升级 `evaluate_finalize_readiness()`：支持 `drafting`、`needs_input`、`ready_for_confirmation`、`finalized` 四态，并让 `to_validate` 与 open risk 参与 gap 汇总而不误判为 missing。
- `merge_readiness_state_patch()` 现在以 `ready_for_confirmation` 作为确认门槛；`get_session_snapshot()` 改为返回与 `prd.updated` 同源的 panel projection。
- 补齐后端测试，锁定 SSE、snapshot、readiness 和 legacy meta fallback 的兼容边界。

## Verification

- `rg -n "sections_changed|missing_sections|gap_prompts|ready_for_confirmation" apps/api/app/schemas/message.py apps/api/app/services/prd_runtime.py`
- `rg -n "risks_to_validate|open_questions|target_user|success_metrics" apps/api/tests/test_messages_stream.py apps/api/tests/test_sessions.py`
- `PYTHONPATH=apps/api uv run pytest apps/api/tests/test_messages_stream.py apps/api/tests/test_sessions.py -q -k "prd_updated or missing or confirmation"`
- `PYTHONPATH=apps/api uv run pytest apps/api/tests/test_readiness.py apps/api/tests/test_message_state.py -q -k "readiness or prd"`
- `PYTHONPATH=apps/api uv run pytest apps/api/tests/test_messages_service.py apps/api/tests/test_finalize_session.py -q`

## Deviations from Plan

- 计划文件未列出 `apps/api/app/services/sessions.py` 与 `apps/api/tests/test_message_state.py`，但为满足“snapshot 与 `prd.updated` 使用同一份投影 shape”和 readiness merge 回归，实际一并修改。
