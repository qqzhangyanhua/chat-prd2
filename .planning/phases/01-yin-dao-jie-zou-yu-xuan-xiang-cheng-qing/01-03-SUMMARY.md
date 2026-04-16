---
phase: 01-yin-dao-jie-zou-yu-xuan-xiang-cheng-qing
plan: 03
subsystem: ui
tags: [nextjs, react, zustand, guidance-ui]
requires:
  - phase: 01-02
    provides: snapshot 与 SSE 对齐的 guidance contract
provides:
  - 前端类型系统支持 guidance_mode、guidance_step、focus_dimension、option_cards、freeform_affordance
  - workspace store 统一从 SSE 与 snapshot 派生 decisionGuidance
  - 工作台卡片显示当前节奏、聚焦维度、options-first 选项与自由补充入口
affects: [conversation-panel, workspace-composer]
tech-stack:
  added: []
  patterns: [store 统一 guidance 派生, UI 优先渲染 option cards]
key-files:
  created: []
  modified:
    - apps/web/src/lib/types.ts
    - apps/web/src/store/workspace-store.ts
    - apps/web/src/components/workspace/action-options.tsx
    - apps/web/src/components/workspace/assistant-turn-card.tsx
    - apps/web/src/test/workspace-store.test.ts
    - apps/web/src/test/assistant-turn-card.test.tsx
    - apps/web/src/test/workspace-session-shell.test.tsx
    - apps/web/src/test/workspace-composer.test.tsx
key-decisions:
  - "前端只消费 guidance contract，不再从旧 strategy 字段二次猜模式"
  - "optionCards 优先于旧 suggestionOptions，但保持向后兼容"
patterns-established:
  - "DecisionGuidance 仅在字段存在时扩展，避免破坏旧测试和旧消费路径"
requirements-completed: [GUID-01, GUID-02, GUID-03, GUID-04]
duration: 1h
completed: 2026-04-16
---

# Phase 01-03 Summary

**工作台现在能直接展示当前引导节奏、聚焦维度、options-first 选项和“都不对，我补充”入口**

## Accomplishments

- 扩展前端 guidance 类型，让 SSE 与 snapshot 都能表达 guidance mode/step/focus/transition。
- 让 `workspace-store` 成为 guidance 的唯一真源，统一事件流与 hydrate 派生逻辑。
- 升级 `AssistantTurnCard` 与 `ActionOptions`，优先展示 option cards，并在有 freeform affordance 时始终保留自由补充入口。

## Verification

- `cd apps/web && pnpm test -- src/test/workspace-store.test.ts src/test/workspace-session-shell.test.tsx src/test/assistant-turn-card.test.tsx`

## Deviations from Plan

- 无。
