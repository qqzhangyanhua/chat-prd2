---
phase: 1
slug: yin-dao-jie-zou-yu-xuan-xiang-cheng-qing
status: ready
nyquist_compliant: true
wave_0_complete: true
created: 2026-04-16
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Vitest 2.0.0 + pytest 8.x |
| **Config file** | `apps/web/vitest.config.ts`, `apps/api/pyproject.toml` |
| **Quick run command** | `cd apps/api && pytest tests/test_pm_mentor.py -q -k guidance && cd ../.. && pnpm --filter web test -- src/test/workspace-store.test.ts -t "decision guidance"` |
| **Full suite command** | `pnpm test:web && pnpm test:api` |
| **Estimated runtime** | ~25 seconds |

---

## Sampling Rate

- **After every task commit:** Run the task-specific smoke command from the table below
- **After every plan wave:** Run `pnpm test:web && pnpm test:api`
- **Before `$gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 1-01-01 | 01 | 1 | GUID-01, GUID-02, GUID-03, GUID-04 | unit + integration | `cd apps/api && pytest tests/test_pm_mentor.py tests/test_agent_runtime.py tests/test_messages_stream.py -q -k "guidance or structured"` | ✅ | ⬜ pending |
| 1-02-01 | 02 | 2 | GUID-01, GUID-02, GUID-04 | integration | `cd apps/api && pytest tests/test_sessions.py tests/test_messages_stream.py -q` | ✅ | ⬜ pending |
| 1-03-01 | 03 | 3 | GUID-01, GUID-02, GUID-04 | unit + component | `pnpm --filter web test -- src/test/workspace-store.test.ts src/test/workspace-session-shell.test.tsx` | ✅ | ⬜ pending |
| 1-03-02 | 03 | 3 | GUID-03, GUID-04 | component | `pnpm --filter web test -- src/test/assistant-turn-card.test.tsx src/test/workspace-session-shell.test.tsx` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| 用户能直观看到当前在探索、比较还是确认，并理解为何此刻切换 | GUID-01, GUID-04 | 自动化可验证字段与组件可见性，但无法充分判断文案是否真正可理解 | 运行工作台会话，触发 3 种以上 guidance mode，确认 guidance 区显示模式标签、推进维度和切换原因 |
| “都不对，我补充”在有选项和无选项两种场景都不会消失 | GUID-03 | 自动化覆盖组件显隐，人工更容易发现交互阻断与视觉层级问题 | 分别构造 option_cards>0 和 option_cards=0 的 session，确认 guidance 区都保留自由补充入口 |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 120s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-04-16
