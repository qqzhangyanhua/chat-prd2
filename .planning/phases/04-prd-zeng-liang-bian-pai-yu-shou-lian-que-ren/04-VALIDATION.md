---
phase: 4
slug: prd-zeng-liang-bian-pai-yu-shou-lian-que-ren
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-04-16
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Vitest + pytest |
| **Config file** | `apps/web/vitest.config.ts`, `apps/api/pyproject.toml` |
| **Quick run command** | `pnpm --filter web test -- src/test/prd-panel.test.tsx src/test/workspace-store.test.ts && PYTHONPATH=apps/api uv run pytest apps/api/tests/test_readiness.py apps/api/tests/test_messages_stream.py apps/api/tests/test_sessions.py apps/api/tests/test_finalize_session.py -q -k "prd or readiness or finalize"` |
| **Full suite command** | `pnpm test:web && pnpm test:api` |
| **Estimated runtime** | ~35 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pnpm --filter web test -- src/test/prd-panel.test.tsx src/test/workspace-store.test.ts && PYTHONPATH=apps/api uv run pytest apps/api/tests/test_readiness.py apps/api/tests/test_messages_stream.py apps/api/tests/test_sessions.py apps/api/tests/test_finalize_session.py -q -k "prd or readiness or finalize"`
- **After every plan wave:** Run `pnpm test:web && pnpm test:api`
- **Before `$gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 35 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 04-01-01 | 01 | 1 | PRD-01, PRD-02 | unit | `PYTHONPATH=apps/api uv run pytest apps/api/tests/test_readiness.py apps/api/tests/test_message_state.py -q -k "readiness or prd"` | ✅ | ⬜ pending |
| 04-01-02 | 01 | 1 | PRD-01, PRD-03, PRD-04 | unit | `PYTHONPATH=apps/api uv run pytest apps/api/tests/test_messages_stream.py apps/api/tests/test_sessions.py -q -k "prd_updated or missing or confirmation"` | ✅ | ⬜ pending |
| 04-02-01 | 02 | 2 | PRD-02, PRD-04 | integration | `PYTHONPATH=apps/api uv run pytest apps/api/tests/test_messages_service.py apps/api/tests/test_messages_stream.py apps/api/tests/test_sessions.py -q -k "prd_updated or finalize or snapshot"` | ✅ | ⬜ pending |
| 04-02-02 | 02 | 2 | PRD-04 | integration | `PYTHONPATH=apps/api uv run pytest apps/api/tests/test_finalize_session.py -q -k "finalize or normalized"` | ✅ | ⬜ pending |
| 04-03-01 | 03 | 3 | PRD-01, PRD-02, PRD-03 | unit | `pnpm --filter web test -- src/test/workspace-store.test.ts -t "prd panel|gap|changed"` | ✅ | ⬜ pending |
| 04-03-02 | 03 | 3 | PRD-01, PRD-02, PRD-03, PRD-04 | integration | `pnpm --filter web test -- src/test/prd-panel.test.tsx src/test/workspace-session-shell.test.tsx -t "section|incremental|confirm|gap"` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `apps/api/tests/test_readiness.py` 需要升级到 entry/completeness-aware readiness，而不是旧 `content/status` 假设
- [ ] `apps/api/tests/test_messages_stream.py` 需要新增 `prd.updated` 章节化 payload、`sections_changed`、`missing_sections` 与 `ready_for_confirmation` 断言
- [ ] `apps/api/tests/test_sessions.py` 需要新增 snapshot hydrate 的 PRD panel projection 一致性测试
- [ ] `apps/api/tests/test_finalize_session.py` 需要新增 Phase 4 panel projection 与 finalized 状态兼容测试
- [ ] `apps/web/src/test/workspace-store.test.ts` 需要新增 PRD panel hydrate / stale snapshot / changed section merge 测试
- [ ] `apps/web/src/test/prd-panel.test.tsx` 需要新增章节顺序、增量高亮、缺口提示、确认 CTA 与 finalized 退场测试

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| 用户能一眼看出“本轮更新了哪几章” | PRD-02 | 动效与视觉层级需要人工判断 | 连续推进两轮会话，确认 `PrdPanel` 只标记本轮变化章节，未变化章节不被误高亮 |
| 缺口提示不会和 diagnostics ledger 重复到显得啰嗦 | PRD-03 | 信息密度与职责边界需要人工判断 | 同时查看左侧 diagnostics ledger 和右侧 PRD panel，确认 panel 只给摘要级缺口，不复制 ledger 全量明细 |
| 可确认初稿的 CTA 时机符合直觉 | PRD-04 | 需要整体体验判断 | 构造“正文齐备但仍有待验证项”与“正文齐备且 major gaps 清空”两种场景，确认 CTA 只在后者或准后者出现 |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all新增测试缺口
- [x] No watch-mode flags
- [x] Feedback latency < 40s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
