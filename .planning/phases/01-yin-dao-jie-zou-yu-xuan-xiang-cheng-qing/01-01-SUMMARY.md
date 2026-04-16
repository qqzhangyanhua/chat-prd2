---
phase: 01-yin-dao-jie-zou-yu-xuan-xiang-cheng-qing
plan: 01
subsystem: api
tags: [fastapi, guidance, sse, pm-mentor]
requires: []
provides:
  - 后端 guidance contract 显式输出 response_mode、guidance_mode、guidance_step、focus_dimension
  - high_uncertainty 节点强制切到 options-first 并输出 option_cards 与 freeform_affordance
  - decision.ready 事件与问候/降级路径共享同一套结构化 guidance 字段
affects: [sessions, workspace-store, assistant-turn-card]
tech-stack:
  added: []
  patterns: [后端统一 guidance contract, options-first 决策]
key-files:
  created: []
  modified:
    - apps/api/app/agent/types.py
    - apps/api/app/agent/pm_mentor.py
    - apps/api/app/agent/runtime.py
    - apps/api/app/schemas/message.py
    - apps/api/app/services/message_state.py
key-decisions:
  - "把 options-first 作为高不确定节点的后端决策，而不是前端展示推断"
  - "结构化 guidance 字段先挂到 TurnDecision，再由 SSE payload 直接透出"
patterns-established:
  - "TurnDecision 是 guidance 真源，SSE 只做序列化"
requirements-completed: [GUID-01, GUID-02, GUID-03, GUID-04]
duration: 1h
completed: 2026-04-16
---

# Phase 01-01 Summary

**后端 guidance contract 现在能显式表达节奏、推进维度、切换原因和 options-first 选项决策**

## Accomplishments

- 扩展 `TurnDecision`，补齐 response/guidance/focus/transition/option/freeform 字段。
- 在 `pm_mentor` 中加入高不确定判定，缺少足够方向信息时直接输出 `options_first`。
- 让 `decision.ready` 事件把新 guidance contract 原样透出，问候与本地 fallback 路径也保持一致。

## Verification

- `PYTHONPATH=apps/api uv run pytest apps/api/tests/test_pm_mentor.py apps/api/tests/test_agent_runtime.py apps/api/tests/test_messages_stream.py -q -k "guidance or structured"`

## Deviations from Plan

- 无。
