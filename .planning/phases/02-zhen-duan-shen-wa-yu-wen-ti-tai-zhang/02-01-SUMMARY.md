---
phase: 02-zhen-duan-shen-wa-yu-wen-ti-tai-zhang
plan: 01
subsystem: api
tags: [fastapi, diagnostics, pm-mentor, state]
requires: []
provides:
  - TurnDecision 显式输出 diagnostics 与 diagnostic_summary
  - pm_mentor 能识别 contradiction/gap/assumption 并控制探索态误报
  - message_state 从 diagnostics 派生 working_hypotheses、pm_risk_flags、open_questions
affects: [messages, sessions, workspace-store]
tech-stack:
  added: []
  patterns: [agent 层诊断真源, diagnostics 驱动兼容字段]
key-files:
  created:
    - apps/api/tests/test_message_state.py
  modified:
    - apps/api/app/agent/types.py
    - apps/api/app/agent/pm_mentor.py
    - apps/api/app/services/message_state.py
    - apps/api/app/repositories/agent_turn_decisions.py
    - apps/api/tests/test_agent_runtime.py
    - apps/api/tests/test_pm_mentor.py
key-decisions:
  - "诊断识别固定在 pm_mentor，state/session/frontend 只消费结构化结果"
  - "旧字段 assumptions/gaps/pm_risk_flags 继续保留，但统一从 diagnostics 派生"
patterns-established:
  - "DiagnosticItem + DiagnosticSummary 成为 Phase 2 后端真源"
requirements-completed: [DIAG-01, DIAG-02]
duration: 50min
completed: 2026-04-16
---

# Phase 02-01 Summary

**后端已经能稳定产出结构化诊断项，并把兼容字段统一降级为 diagnostics 派生结果**

## Accomplishments

- 扩展 `TurnDecision`，新增 `diagnostics` 与 `diagnostic_summary` 契约。
- 在 `pm_mentor` 中落地 contradiction / gap / assumption 识别，并避免把探索态文本误报成矛盾。
- 在 `message_state` 中统一派生 `working_hypotheses`、`pm_risk_flags`、`open_questions`。

## Verification

- `PYTHONPATH=apps/api uv run pytest apps/api/tests/test_agent_runtime.py apps/api/tests/test_message_state.py apps/api/tests/test_pm_mentor.py -q`

## Deviations from Plan

- 无。
