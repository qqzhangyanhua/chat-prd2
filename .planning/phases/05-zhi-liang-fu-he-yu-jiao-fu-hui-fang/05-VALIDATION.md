---
phase: 5
slug: zhi-liang-fu-he-yu-jiao-fu-hui-fang
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-04-16
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Vitest + pytest |
| **Config file** | `apps/web/vitest.config.ts`, `apps/api/pyproject.toml` |
| **Quick run command** | `pnpm --filter web test -- src/test/prd-panel.test.tsx src/test/replay-panel.test.tsx src/test/workspace-session-shell.test.tsx && PYTHONPATH=apps/api uv run pytest apps/api/tests/test_prd_review.py apps/api/tests/test_finalize_session.py apps/api/tests/test_sessions.py -q -k "review or export or replay or timeline"` |
| **Full suite command** | `pnpm test:web && pnpm test:api` |
| **Estimated runtime** | ~40 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pnpm --filter web test -- src/test/prd-panel.test.tsx src/test/replay-panel.test.tsx src/test/workspace-session-shell.test.tsx && PYTHONPATH=apps/api uv run pytest apps/api/tests/test_prd_review.py apps/api/tests/test_finalize_session.py apps/api/tests/test_sessions.py -q -k "review or export or replay or timeline"`
- **After every plan wave:** Run `pnpm test:web && pnpm test:api`
- **Before `$gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 40 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 05-01-01 | 01 | 1 | RVW-01 | unit | `PYTHONPATH=apps/api uv run pytest apps/api/tests/test_prd_review.py -q` | ✅ | ⬜ pending |
| 05-01-02 | 01 | 1 | RVW-01 | integration | `PYTHONPATH=apps/api uv run pytest apps/api/tests/test_sessions.py -q -k "review or snapshot"` | ✅ | ⬜ pending |
| 05-02-01 | 02 | 2 | RVW-02 | integration | `PYTHONPATH=apps/api uv run pytest apps/api/tests/test_finalize_session.py apps/api/tests/test_sessions.py -q -k "export or appendix or handoff"` | ✅ | ⬜ pending |
| 05-02-02 | 02 | 2 | RVW-02 | integration | `PYTHONPATH=apps/api uv run pytest apps/api/tests/test_finalize_session.py -q -k "finalize or export"` | ✅ | ⬜ pending |
| 05-03-01 | 03 | 3 | RVW-03 | unit | `PYTHONPATH=apps/api uv run pytest apps/api/tests/test_sessions.py -q -k "replay or timeline or review"` | ✅ | ⬜ pending |
| 05-03-02 | 03 | 3 | RVW-03 | integration | `pnpm --filter web test -- src/test/workspace-store.test.ts src/test/prd-panel.test.tsx src/test/replay-panel.test.tsx src/test/workspace-session-shell.test.tsx` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `apps/api/tests/test_sessions.py` 需要新增 review payload 与 replay timeline 聚合断言
- [ ] `apps/api/tests/test_finalize_session.py` 需要新增导出 appendix / review summary 兼容断言
- [ ] `apps/api/tests/test_messages_stream.py` 需要新增 review/export milestone stream 回归
- [ ] `apps/web/src/test/prd-panel.test.tsx` 需要新增 review summary 渲染与 panel 边界测试
- [ ] `apps/web/src/test/replay-panel.test.tsx` 需要新增 replay timeline 主渲染测试
- [ ] `apps/web/src/test/workspace-session-shell.test.tsx` 需要新增 replay timeline / export handoff UI 测试
- [ ] `apps/web/src/test/workspace-store.test.ts` 需要新增 replay state hydrate / refresh 一致性测试

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| review 提示既能指出问题又不会把 panel 变成审查台 | RVW-01 | 信息密度和语义层级需要人工判断 | 打开带 review summary 的会话，确认右侧 panel 仍以 PRD 为主体，review 只做摘要提示 |
| 导出结果保留章节与待验证项，但不会夹带内部实现噪音 | RVW-02 | 文档可读性需要人工判断 | 导出一份含风险/待确认项的 PRD，确认正文结构清晰、appendix 不喧宾夺主 |
| replay timeline 能回答“PRD 为什么变成现在这样” | RVW-03 | narrative 质量需要人工判断 | 回放一个多轮会话，确认 timeline 能看出 guidance、diagnostics、PRD 变化和 finalize/export 里程碑 |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 40s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
