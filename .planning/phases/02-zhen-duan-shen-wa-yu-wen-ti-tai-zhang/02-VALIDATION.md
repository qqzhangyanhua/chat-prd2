---
phase: 2
slug: zhen-duan-shen-wa-yu-wen-ti-tai-zhang
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-04-16
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Vitest + pytest |
| **Config file** | `apps/web/vitest.config.ts`, `apps/api/pyproject.toml` |
| **Quick run command** | `pnpm --filter web test -- src/test/workspace-store.test.ts src/test/assistant-turn-card.test.tsx src/test/workspace-session-shell.test.tsx -t diagnostic && PYTHONPATH=apps/api uv run pytest apps/api/tests/test_agent_runtime.py apps/api/tests/test_message_state.py apps/api/tests/test_pm_mentor.py apps/api/tests/test_messages_stream.py apps/api/tests/test_sessions.py -q -k "diagnostic"` |
| **Full suite command** | `pnpm test:web && pnpm test:api` |
| **Estimated runtime** | ~25 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pnpm --filter web test -- src/test/workspace-store.test.ts src/test/assistant-turn-card.test.tsx src/test/workspace-session-shell.test.tsx -t diagnostic && PYTHONPATH=apps/api uv run pytest apps/api/tests/test_agent_runtime.py apps/api/tests/test_message_state.py apps/api/tests/test_pm_mentor.py apps/api/tests/test_messages_stream.py apps/api/tests/test_sessions.py -q -k "diagnostic"`
- **After every plan wave:** Run `pnpm test:web && pnpm test:api`
- **Before `$gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 25 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 1 | DIAG-01, DIAG-02 | unit | `PYTHONPATH=apps/api uv run pytest apps/api/tests/test_agent_runtime.py -q -k "diagnostic"` | ✅ | ⬜ pending |
| 02-01-02 | 01 | 1 | DIAG-01 | unit | `PYTHONPATH=apps/api uv run pytest apps/api/tests/test_pm_mentor.py -q -k "diagnostic"` | ✅ | ⬜ pending |
| 02-01-03 | 01 | 1 | DIAG-02 | unit | `PYTHONPATH=apps/api uv run pytest apps/api/tests/test_message_state.py -q -k "diagnostic"` | ❌ W0 | ⬜ pending |
| 02-02-01 | 02 | 2 | DIAG-02 | integration | `PYTHONPATH=apps/api uv run pytest apps/api/tests/test_messages_stream.py -q -k "diagnostic"` | ✅ | ⬜ pending |
| 02-02-02 | 02 | 2 | DIAG-02, DIAG-03 | integration | `PYTHONPATH=apps/api uv run pytest apps/api/tests/test_sessions.py -q -k "diagnostic"` | ✅ | ⬜ pending |
| 02-03-01 | 03 | 3 | DIAG-02 | unit | `cd apps/web && pnpm test -- src/test/workspace-store.test.ts -t diagnostic` | ✅ | ⬜ pending |
| 02-03-02 | 03 | 3 | DIAG-03 | unit + integration | `cd apps/web && pnpm test -- src/test/assistant-turn-card.test.tsx src/test/workspace-session-shell.test.tsx -t diagnostic` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `apps/api/tests/test_pm_mentor.py` — contradiction / gap / assumption 分类、误报控制、去重 id 测试
- [ ] `apps/api/tests/test_agent_runtime.py` — greeting / completed / fallback / 本地降级路径返回空 diagnostics contract 测试
- [ ] `apps/api/tests/test_message_state.py` — `build_decision_state_patch()` 输出 diagnostics、summary 与兼容派生字段测试
- [ ] `apps/api/tests/test_messages_stream.py` — `decision.ready` diagnostics payload 与事件顺序断言
- [ ] `apps/api/tests/test_sessions.py` — session hydrate 后 open ledger 一致性断言
- [ ] `apps/web/src/test/workspace-store.test.ts` — diagnostics hydrate / SSE merge / stale snapshot 保护测试
- [ ] `apps/web/src/test/assistant-turn-card.test.tsx` — 本轮诊断摘要与 suggested next step 渲染测试
- [ ] `apps/web/src/test/workspace-session-shell.test.tsx` — 持续台账卡片渲染与刷新恢复测试

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| 探索态输入不会被过早标成 contradiction | DIAG-01 | 误报率需要人工判断语义合理性 | 在工作台输入多个探索式表述，确认 UI 优先显示 gap/assumption 而不是直接判矛盾 |
| 持续台账的信息密度可读，不压住会话主线 | DIAG-03 | UI 信息层级需要人工评估 | 连续触发 3 轮 diagnostics，确认会话列仍然可读，台账不遮挡主要回复 |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 25s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
