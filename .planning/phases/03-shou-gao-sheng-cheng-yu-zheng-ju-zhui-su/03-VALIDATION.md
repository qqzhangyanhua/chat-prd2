---
phase: 3
slug: shou-gao-sheng-cheng-yu-zheng-ju-zhui-su
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-04-16
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Vitest + pytest |
| **Config file** | `apps/web/vitest.config.ts`, `apps/api/pyproject.toml` |
| **Quick run command** | `pnpm --filter web test -- src/test/workspace-store.test.ts src/test/workspace-session-shell.test.tsx src/test/prd-panel.test.tsx && PYTHONPATH=apps/api uv run pytest apps/api/tests/test_messages_stream.py apps/api/tests/test_sessions.py apps/api/tests/test_messages_service.py -q -k "draft or evidence"` |
| **Full suite command** | `pnpm test:web && pnpm test:api` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pnpm --filter web test -- src/test/workspace-store.test.ts src/test/workspace-session-shell.test.tsx src/test/prd-panel.test.tsx && PYTHONPATH=apps/api uv run pytest apps/api/tests/test_messages_stream.py apps/api/tests/test_sessions.py apps/api/tests/test_messages_service.py -q -k "draft or evidence"`
- **After every plan wave:** Run `pnpm test:web && pnpm test:api`
- **Before `$gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 1 | INTK-02 | unit | `PYTHONPATH=apps/api uv run pytest apps/api/tests/test_agent_types_contract.py apps/api/tests/test_message_state.py -q -k "draft or evidence or assertion"` | ✅ | ⬜ pending |
| 03-01-02 | 01 | 1 | INTK-01, INTK-02, INTK-03 | unit | `PYTHONPATH=apps/api uv run pytest apps/api/tests/test_pm_mentor.py -q -k "draft or evidence"` | ✅ | ⬜ pending |
| 03-02-01 | 02 | 2 | INTK-01, INTK-02, INTK-03 | integration | `PYTHONPATH=apps/api uv run pytest apps/api/tests/test_messages_service.py apps/api/tests/test_messages_stream.py apps/api/tests/test_sessions.py -q -k "draft or evidence"` | ✅ | ⬜ pending |
| 03-02-02 | 02 | 2 | INTK-01, INTK-03 | integration | `PYTHONPATH=apps/api uv run pytest apps/api/tests/test_finalize_session.py apps/api/tests/test_messages_stream.py -q -k "draft or finalize or prd_updated"` | ✅ | ⬜ pending |
| 03-03-01 | 03 | 3 | INTK-02, INTK-03 | unit | `pnpm --filter web test -- src/test/workspace-store.test.ts -t "draft|evidence"` | ✅ | ⬜ pending |
| 03-03-02 | 03 | 3 | INTK-01, INTK-02, INTK-03 | integration | `pnpm --filter web test -- src/test/workspace-session-shell.test.tsx src/test/prd-panel.test.tsx -t "draft|evidence|panel"` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `apps/api/tests/test_messages_service.py` 需要新增 enriched `prd_draft` contract 测试，覆盖 entries/assertion_state/evidence refs
- [ ] `apps/api/tests/test_messages_stream.py` 需要新增 `draft.updated` 事件顺序与结构断言
- [ ] `apps/api/tests/test_sessions.py` 需要新增 snapshot hydrate 后 draft/evidence registry 一致性断言
- [ ] `apps/api/tests/test_message_state.py` 需要新增 completeness 与 assertion_state 分层测试
- [ ] `apps/web/src/test/workspace-store.test.ts` 需要新增 first-draft hydrate / stream merge / stale snapshot 保护测试
- [ ] `apps/web/src/test/workspace-session-shell.test.tsx` 需要新增首稿卡片与 evidence drawer 展示测试
- [ ] `apps/web/src/test/prd-panel.test.tsx` 需要新增“Phase 3 不应污染右侧 panel 语义”的回归测试

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| 条目级状态标签不会误导用户把推断当成已确认 | INTK-02 | 语义呈现需要人工判断 | 在会话列查看同一 section 下的 confirmed / inferred / to_validate entry，确认视觉层级和中文文案清晰 |
| 证据抽屉的信息密度足够支撑回溯，但不会压住会话主线 | INTK-03 | UI 可读性需要人工评估 | 连续触发多轮首稿更新，打开不同 entry 的来源抽屉，确认 excerpt 与来源类型清楚可读 |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all新增测试缺口
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
