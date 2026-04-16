# Phase 05: 质量复核与交付回放 - Research

**Researched:** 2026-04-16
**Domain:** PRD review contract, export reuse, session replay, validation architecture
**Confidence:** HIGH

## User Constraints

No `CONTEXT.md` exists for this phase. Planning must therefore honor the explicit phase brief, current roadmap, and prior phase decisions already recorded in `.planning/STATE.md`.

- Must address `RVW-01`, `RVW-02`, `RVW-03`.
- Continue without discuss-phase context and without UI-SPEC by default.
- Research focus is existing implementation boundaries, correct layering, and the most reasonable plan split.
- Preserve Phase 3 / Phase 4 layering:
  first-draft + evidence stay in conversation column,
  right-side PRD panel stays a projection consumer,
  export/finalize/snapshot keep using the shared projection path where possible.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| RVW-01 | 系统必须对当前 PRD 给出基础质量检查，至少覆盖目标清晰度、范围边界、成功标准、风险暴露和待验证项完整度 | Use a separate `review contract` derived from persisted `prd_draft + diagnostics + readiness`, not the panel projection itself |
| RVW-02 | 用户确认后，系统可以导出可复制或可下载的结构化 PRD 文本，保留章节与待验证项 | Reuse current export pipeline and Phase 4 panel projection sections; extend export payload shape rather than mixing review into panel |
| RVW-03 | 系统需要保留引导决策、问题诊断与 PRD 变更记录，以便后续回放、调优与质量评测 | Reuse existing `messages + assistant_reply_groups + turn_decisions + prd_snapshot/state versions`; Phase 5 MVP is timeline assembly, not a new persistence system |
</phase_requirements>

## Summary

Phase 4 already settled the most important architectural question: persisted `state.prd_draft` is the content truth, and the right-side PRD panel is only a projection of that truth. `prd.updated`, session snapshot, finalize, and export already converge on the same `prd_runtime` projector. That is the correct base to preserve for Phase 5.

For Phase 5, “质量复核” should **not** be added as another panel meta hack and should **not** mutate the draft truth. It should be a separate review contract computed from the true source: structured `prd_draft.sections`, diagnostics ledger, readiness output, and finalized status. The panel may display a summary of review results, but the review itself should live in its own contract so it can be reused by snapshot, export, and replay without polluting Phase 4 projection semantics.

“交付回放” also does not need new storage for v1. The session snapshot already exposes the minimum raw materials: ordered `messages`, per-user-turn `turn_decisions`, and `assistant_reply_groups` with version history; persisted state/PRD versions already exist in the database. The smallest correct deliverable is a replay-oriented normalized timeline assembled from these existing records, showing guidance decision, diagnostics, PRD delta summary, and final export/finalize milestones.

**Primary recommendation:** Split Phase 5 into three plans: `review contract`, `export/handoff extension`, `replay timeline consumption`, in that order.

## Standard Stack

### Core

| Library / Module | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `apps/api/app/services/prd_runtime.py` | repo current | Single projector for `prd_draft -> panel payload` | Phase 4 already made it the shared projection path for SSE, snapshot, finalize, export |
| `apps/api/app/agent/readiness.py` | repo current | Readiness and gap evaluation | Already computes section completeness, `to_validate`, risk counts, and confirmation gate |
| `apps/api/app/services/sessions.py` | repo current | Snapshot aggregation boundary | Already returns `messages`, `assistant_reply_groups`, `turn_decisions`, and panel snapshot in one response |
| FastAPI | `>=0.115.0` in `apps/api/pyproject.toml` | API routes and response contracts | Existing backend boundary; no reason to introduce a second delivery stack |
| Next.js | `15.0.0` in `apps/web/package.json` | Workspace UI shell | Existing web delivery layer |
| Zustand | `5.0.0` in lock/stack docs | Workspace state truth on client | Existing session hydration and SSE consumption path |

### Supporting

| Library / Module | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `apps/api/app/services/exports.py` | repo current | Markdown export builder | Reuse for RVW-02; extend payload shape, not storage model |
| `apps/api/app/services/finalize_session.py` | repo current | Finalization transition | Reuse as the terminal “delivery milestone” in replay |
| `apps/web/src/store/prd-store-helpers.ts` | repo current | Panel snapshot normalization | Keep panel-specific normalization here; do not move review scoring logic into this helper |
| Vitest | `^2.0.0` | Frontend state/component validation | Panel/replay presentation tests |
| pytest | `>=8.3.0` | Backend service/route validation | Review/export/snapshot regression tests |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Separate review contract | Stuff review fields into `prd.updated.meta` | Faster short term, but mixes convergence projection with review semantics and makes replay/export coupling worse |
| Reuse existing snapshot materials for replay | New `review_events` or `timeline_events` table | Better long-term query ergonomics, but unnecessary for Phase 5 MVP because current session snapshot already exposes enough material |
| Reuse `build_prd_updated_event_data()` for export inputs | Rebuild export directly from `prd_draft` only | Would drift from panel/finalize semantics and recreate the Phase 4 inconsistency risk |

**Installation:**

```bash
pnpm install
uv pip install -e "apps/api[dev]"
```

**Version verification:** Existing repo pins or minimums were verified from `package.json` and `apps/api/pyproject.toml`. This phase does not require introducing a new external library.

## Architecture Patterns

### Recommended Project Structure

```text
apps/api/app/
├── services/
│   ├── prd_runtime.py          # panel projection only
│   ├── prd_review.py           # new: review contract projector
│   ├── exports.py              # export assembly using panel + review data
│   └── sessions.py             # snapshot/replay aggregation boundary
├── schemas/
│   ├── prd.py                  # snapshot payload shape
│   ├── session.py              # session snapshot + replay response
│   └── message.py              # SSE event contracts if replay milestones stream later
apps/web/src/
├── store/
│   ├── workspace-store.ts      # session hydration + replay state
│   └── prd-store-helpers.ts    # panel normalization only
└── components/workspace/
    ├── prd-panel.tsx           # panel projection consumer
    └── replay-panel.tsx        # new: replay timeline consumer
```

### Pattern 1: Source Truth vs Projection vs Review Contract

**What:** Keep three layers explicit:

- `state.prd_draft` + diagnostics ledger = source truth
- `prd_runtime` panel payload = presentation projection for right-side PRD
- `prd_review` payload = review verdicts/checks derived from truth, reusable across snapshot/export/replay

**When to use:** Any feature that answers “is this PRD good enough?” instead of “what does the PRD currently say?”

**Example:**

```python
# Source: repo pattern inferred from prd_runtime.py + readiness.py
state = latest_state()
panel = build_prd_updated_event_data(state, {}, {})
review = build_prd_review_payload(state)

return {
    "prd_snapshot": panel,
    "prd_review": review,
}
```

### Pattern 2: Export from Shared Projection, Not from UI State

**What:** Export must keep using backend-owned payload assembly. The web app should trigger export, not compose export content.

**When to use:** RVW-02 markdown/copy/download output

**Example:**

```python
# Source: repo pattern from exports.py
panel_sections = build_prd_updated_event_data(state, {}, {}).get("sections", {})
review = build_prd_review_payload(state)

markdown = build_markdown_export(
    sections=merge_export_sections(panel_sections, raw_draft_sections),
    review=review,
    is_final=is_final,
)
```

### Pattern 3: Replay as Aggregation, Not New Persistence

**What:** Assemble replay from existing snapshot materials first:

- ordered `messages`
- `turn_decisions` with guidance/diagnostic metadata
- `assistant_reply_groups` for regenerate history
- finalized/export milestones inferred from state and route actions

**When to use:** Phase 5 MVP for RVW-03

**Example:**

```typescript
// Source: repo pattern from SessionSnapshotResponse and workspace-store hydration
const replayTimeline = buildReplayTimeline({
  messages: snapshot.messages,
  turnDecisions: snapshot.turn_decisions ?? [],
  replyGroups: snapshot.assistant_reply_groups ?? [],
  prdSnapshot: snapshot.prd_snapshot,
  state: snapshot.state,
});
```

### Pattern 4: Review Checks are Deterministic and Explainable

**What:** Quality checks should be rule-based off explicit section/draft/diagnostic facts, not opaque LLM-only scoring.

**When to use:** `RVW-01` baseline quality review

**Recommended dimensions:**

- 目标清晰度: `target_user`, `problem`, `solution` completeness + specificity
- 范围边界: `mvp_scope`, `constraints`, `out_of_scope`
- 成功标准: `success_metrics`
- 风险暴露: diagnostics risk/to_validate + `risks_to_validate`
- 待验证完整度: `open_questions` plus `to_validate` entries

### Anti-Patterns to Avoid

- **Review logic inside `PrdPanel`:** panel is a consumer, not the place to decide quality truth.
- **Mutating `prd_draft` with review-only fields:** review is derived analysis, not authoring content.
- **Export from client-side store:** creates drift with snapshot/finalize/export semantics.
- **Replay from raw messages only:** loses diagnostics, recommendation, and regenerate history already preserved elsewhere.
- **Using `critic_result` as the only review source:** Phase 4 readiness is broader and entry-aware; review must use actual structured sections and diagnostics.

## Don’t Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Review storage | New `review_history` persistence for v1 | Deterministic projector from current state | Existing state already has enough inputs; avoid write-path complexity |
| Export content assembly | Frontend markdown/string builder | `apps/api/app/services/exports.py` | Backend already owns normalized export shape and final/draft status |
| Replay persistence | New event-sourcing subsystem | Session snapshot aggregation over existing tables | `messages`, `turn_decisions`, `assistant_reply_groups`, `state_versions`, `prd_snapshots` already cover the needed history |
| Panel review rendering | Another overloaded `prd.meta` object | Dedicated `prd_review` contract | Prevents Phase 4 panel contract creep |

**Key insight:** Phase 5 is primarily a projection-and-aggregation phase, not a new persistence phase.

## Common Pitfalls

### Pitfall 1: Treating Panel Projection as the Review Truth

**What goes wrong:** Review verdicts get encoded into `prd.updated.meta` or inferred from panel copy alone.
**Why it happens:** The panel is visible and already normalized, so it feels convenient.
**How to avoid:** Build review from `prd_draft.sections`, diagnostics ledger, and readiness output first; let panel consume only a summary if needed.
**Warning signs:** `PrdPanel` starts containing scoring rules or section-by-section completeness heuristics.

### Pitfall 2: Mixing Phase 3 First-Draft Evidence into Phase 4 Panel State

**What goes wrong:** evidence registry and entry-level assertions leak into the right-side panel or export path in raw form.
**Why it happens:** replay/export needs provenance, and developers reuse the nearest UI surface.
**How to avoid:** Keep evidence and first-draft provenance in replay/conversation surfaces; panel remains section-level projection.
**Warning signs:** `draft.updated` data begins changing right-side PRD rendering beyond intended summaries.

### Pitfall 3: Rebuilding Export Directly from Legacy Snapshot

**What goes wrong:** export loses Phase 4 sections like `risks_to_validate` or diverges from finalized output.
**Why it happens:** legacy snapshot path looks simpler.
**How to avoid:** Keep export rooted in shared panel projection plus explicit draft-only supplemental fields.
**Warning signs:** export tests stop asserting `gap_prompts`, `ready_for_confirmation`, risk sections, or finalized preference paths.

### Pitfall 4: Over-scoping Replay into Full Audit/Analytics

**What goes wrong:** Phase 5 stalls on perfect diffing, visual timeline polish, or data warehousing.
**Why it happens:** “回放” sounds like full observability.
**How to avoid:** Define MVP as one normalized session replay view showing guidance, diagnostics, PRD changes, and delivery milestones.
**Warning signs:** plan introduces new tables, background jobs, or cross-session analytics before a single-session replay exists.

### Pitfall 5: Using Only Current Snapshot for Change History

**What goes wrong:** replay shows final state but not what changed when.
**Why it happens:** current API returns latest truth cheaply.
**How to avoid:** derive timeline items from `turn_decisions` summaries plus reply version history first; if version-by-version PRD diff is needed later, make that a follow-up plan.
**Warning signs:** replay screen cannot answer “why did the PRD move in this direction?”

## Code Examples

Verified patterns from current repo:

### Shared Panel Projection

```python
# Source: apps/api/app/services/prd_runtime.py
def build_prd_snapshot_payload(state, *, snapshot_id, session_id, version):
    panel_payload = build_prd_updated_event_data(state, {}, {})
    return {
        "id": snapshot_id,
        "session_id": session_id,
        "version": version,
        "sections": panel_payload["sections"],
        "meta": panel_payload.get("meta"),
        "sections_changed": list(panel_payload.get("sections_changed", [])),
        "missing_sections": list(panel_payload.get("missing_sections", [])),
        "gap_prompts": list(panel_payload.get("gap_prompts", [])),
        "ready_for_confirmation": bool(panel_payload.get("ready_for_confirmation")),
    }
```

### Finalize Uses Readiness Projector

```python
# Source: apps/api/app/services/finalize_session.py
readiness = evaluate_finalize_readiness(current_state)
if current_state.get("workflow_stage") != "finalize" or not readiness.get("ready_for_confirmation"):
    raise FINALIZE_NOT_READY
```

### Session Snapshot Already Exposes Replay Materials

```python
# Source: apps/api/app/services/sessions.py
assistant_reply_groups = _list_assistant_reply_groups(db, session_id)
messages = _build_timeline_messages(raw_messages, assistant_reply_groups)
turn_decisions = _list_turn_decisions(db, session_id)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Panel derived ad hoc / legacy meta fallback | Shared `prd_draft -> panel payload` projector across SSE, snapshot, finalize, export | Phase 4 on 2026-04-16 | Phase 5 should extend shared projectors, not fork them |
| Finalize gate via stale `finalization_ready` flag | Readiness projector decides confirmation/finalize | Phase 4 on 2026-04-16 | Review must trust entry-aware readiness, not stale booleans |
| Frontend store splitting extra sections separately | Unified section order + missing/gap/ready metadata | Phase 4 on 2026-04-16 | Review summary can attach cleanly without reviving old split logic |

**Deprecated/outdated:**

- `critic_result` as the sole quality signal: outdated for Phase 5 because Phase 4 readiness now evaluates structured draft completeness and to-validate state.
- Legacy `prd_snapshot.sections` as primary authoring truth: outdated; it is now a compatibility/export persistence layer, not the main authoring truth.

## Open Questions

1. **Does replay need version-by-version PRD diffs in Phase 5?**
   - What we know: current API exposes latest snapshot plus per-turn decision summaries and reply versions.
   - What's unclear: whether user needs exact structural PRD delta per persisted state version, or only per-turn narrative/change summary.
   - Recommendation: make MVP narrative-first using `turn_decisions`; defer precise persisted diff viewer unless user explicitly asks.

2. **Should review verdicts stream live over SSE or only arrive in snapshot?**
   - What we know: current SSE already carries `prd.updated`; review could be computed on the same write path.
   - What's unclear: whether Phase 5 UX needs real-time review updates every turn.
   - Recommendation: backend should compute review in the same service path, but streaming it can be optional if snapshot hydration is enough for v1.

3. **Should export include review results or only PRD content?**
   - What we know: current export returns markdown PRD content only.
   - What's unclear: whether users want a “review appendix” in exported output.
   - Recommendation: keep RVW-02 focused on structured PRD export first; append review summary only if it does not blur the core deliverable.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest `>=8.3.0`, Vitest `^2.0.0` |
| Config file | `apps/web/vitest.config.ts`; pytest via repo conventions in `apps/api/tests` |
| Quick run command | `PYTHONPATH=apps/api uv run pytest apps/api/tests/test_sessions.py apps/api/tests/test_finalize_session.py -q -k "export or finalize or turn_decisions"` |
| Full suite command | `pnpm test:web && pnpm test:api` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| RVW-01 | Review payload evaluates PRD completeness, boundaries, success metrics, risks, open validation | unit/service | `PYTHONPATH=apps/api uv run pytest apps/api/tests/test_prd_review.py -q` | ❌ Wave 0 |
| RVW-02 | Export reuses shared projection and preserves sections plus validation items | service/route | `PYTHONPATH=apps/api uv run pytest apps/api/tests/test_sessions.py -q -k "export"` | ✅ |
| RVW-03 | Session snapshot/replay surface exposes guidance, diagnostics, and PRD change history coherently | service/frontend | `PYTHONPATH=apps/api uv run pytest apps/api/tests/test_sessions.py -q -k "turn_decisions or snapshot"` and `pnpm --filter web test -- src/test/replay-panel.test.tsx` | API ✅ / Web ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `PYTHONPATH=apps/api uv run pytest apps/api/tests/test_sessions.py apps/api/tests/test_finalize_session.py -q -k "export or finalize or turn_decisions"` and `pnpm --filter web test -- src/test/prd-panel.test.tsx`
- **Per wave merge:** `pnpm --filter web test -- src/test/prd-panel.test.tsx src/test/workspace-store.test.ts src/test/workspace-session-shell.test.tsx`
- **Phase gate:** `pnpm test:web && pnpm test:api`

### Wave 0 Gaps

- [ ] `apps/api/tests/test_prd_review.py` — covers deterministic review contract for `RVW-01`
- [ ] `apps/web/src/test/replay-panel.test.tsx` — covers replay timeline rendering and anti-mixing boundaries for `RVW-03`
- [ ] `apps/web/src/test/workspace-store.test.ts` additions — covers replay timeline normalization on snapshot hydrate

## Recommended Plan Split

### Plan 05-01: 后端 review contract 与 snapshot/expose 边界

**Scope:** Implement backend-only review projector and expose it through session snapshot and optionally dedicated route.

**Why first:** This decides the contract and prevents front-end review logic from drifting.

**Outputs:**

- `prd_review` payload computed from `prd_draft + diagnostics + readiness`
- API schema additions
- deterministic tests for review dimensions

### Plan 05-02: 导出与交付复用 Phase 4 contract

**Scope:** Extend export/handoff to reuse existing panel projection and incorporate the minimum review-aware delivery metadata without altering source truth.

**Why second:** Export must consume the stable review/panel contracts defined in 05-01.

**Outputs:**

- export payload/markdown updates
- finalize/export regression coverage
- clear boundary between PRD content and review appendix or summary

### Plan 05-03: 回放聚合与前端消费

**Scope:** Build replay timeline from existing snapshot materials and add the minimal UI/state consumption path.

**Why third:** Replay depends on stable backend contracts from 05-01 and any export/finalize milestones from 05-02.

**Outputs:**

- normalized replay timeline in API snapshot or dedicated response
- workspace store hydration support
- replay panel/component tests

## Sources

### Primary (HIGH confidence)

- Local source: `apps/api/app/services/prd_runtime.py` - shared panel projection, snapshot payload
- Local source: `apps/api/app/agent/readiness.py` - readiness and gap evaluation rules
- Local source: `apps/api/app/services/exports.py` - export assembly and section reuse
- Local source: `apps/api/app/services/finalize_session.py` - finalize gate and finalized draft transition
- Local source: `apps/api/app/services/sessions.py` - snapshot aggregation, turn decisions, reply groups
- Local source: `apps/web/src/components/workspace/prd-panel.tsx` - current panel consumer boundary
- Local source: `apps/web/src/store/workspace-store.ts` - session hydration and event consumption
- Local source: `.planning/phases/04-prd-zeng-liang-bian-pai-yu-shou-lian-que-ren/04-01-SUMMARY.md`
- Local source: `.planning/phases/04-prd-zeng-liang-bian-pai-yu-shou-lian-que-ren/04-02-SUMMARY.md`
- Local source: `.planning/phases/04-prd-zeng-liang-bian-pai-yu-shou-lian-que-ren/04-03-SUMMARY.md`

### Secondary (MEDIUM confidence)

- `docs/contracts/prd-runtime-contract.md` - useful architectural intent, but partially outdated in wording (`extraSections`) versus current Phase 4 implementation

### Tertiary (LOW confidence)

- None

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH - derived from repository package/config files and current code paths
- Architecture: HIGH - grounded in Phase 4 summaries and current service/store boundaries
- Pitfalls: HIGH - inferred directly from existing layering decisions and current contract seams

**Research date:** 2026-04-16
**Valid until:** 2026-05-16
