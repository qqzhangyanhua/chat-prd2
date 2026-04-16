---
phase: 03-shou-gao-sheng-cheng-yu-zheng-ju-zhui-su
plan: 01
subsystem: api
tags: [fastapi, draft, evidence, pm-mentor]
requires: []
provides:
  - 首稿条目 contract：AssertionState、DraftEntry、DraftSection、EvidenceItem
  - StateSnapshot 支持结构化 prd_draft 与 evidence registry
  - pm_mentor 能把 prd_updates 投影成 entry 级 prd_draft 与 evidence refs
affects: [messages, sessions, workspace-store, finalize]
tech-stack:
  added: []
  patterns: [persisted prd_draft 真源, evidence registry, entry 级 assertion_state]
key-files:
  created: []
  modified:
    - apps/api/app/agent/types.py
    - apps/api/app/agent/pm_mentor.py
    - apps/api/app/schemas/state.py
    - apps/api/app/services/message_state.py
    - apps/api/tests/test_agent_types_contract.py
    - apps/api/tests/test_message_state.py
    - apps/api/tests/test_pm_mentor.py
key-decisions:
  - "Phase 3 继续复用 persisted prd_draft 作为首稿真源，但升级为 entry 级结构"
  - "待验证状态独立成 assertion_state=to_validate，不再复用 missing 语义"
  - "证据通过 evidence registry + evidence_ref_ids 连接，不让前端反推来源"
patterns-established:
  - "pm_mentor 先保留旧 prd_updates，再同步生成结构化 prd_draft/evidence"
requirements-completed: [INTK-01, INTK-02, INTK-03]
duration: 25min
completed: 2026-04-16
---

# Phase 03-01 Summary

**Phase 3 的首稿 contract 已经落地到后端类型、state schema 和 pm_mentor 输出。**

## Accomplishments

- 新增 `AssertionState`、`DraftEntry`、`DraftSection`、`EvidenceItem` 和 `DraftUpdateSummary`，固定 entry 级首稿与证据追溯 contract。
- `StateSnapshot` 现在接受结构化 `prd_draft` 与 `evidence` registry，而不是完全自由形状的字典。
- `pm_mentor` 会把旧 `prd_updates` 同步投影成结构化 `prd_draft/evidence`，并为每条 entry 生成 `evidence_ref_ids`。
- `build_decision_state_patch()` 会保留结构化 `prd_draft` 和 `evidence`，供后续 snapshot/SSE 贯通。

## Verification

- `PYTHONPATH=apps/api uv run pytest apps/api/tests/test_agent_types_contract.py apps/api/tests/test_message_state.py -q -k "draft or evidence or assertion"`
- `PYTHONPATH=apps/api uv run pytest apps/api/tests/test_pm_mentor.py -q -k "draft or evidence"`

## Deviations from Plan

- 无。
