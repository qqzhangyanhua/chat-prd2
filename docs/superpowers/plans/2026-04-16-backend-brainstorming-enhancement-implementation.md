# Backend Brainstorming Enhancement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 `apps/api` 的消息主链路把“头脑风暴”升级为一等后端能力，做到实时可见、按 phase 递进、可被测试约束。

**Architecture:** 保留现有 `run_agent -> turn_decision -> state/session snapshot` 架构，不推翻现有 PM Mentor 流程。改造重点放在三层：流式协议显式暴露结构化 guidance；`pm_mentor` 基于 phase/subfocus 生成更贴上下文的 suggestions；质量校验器阻止 suggestions 退化为通用模板。

**Tech Stack:** FastAPI SSE、SQLAlchemy、dataclass agent types、pytest

---

## File Map

- Modify: `apps/api/app/schemas/message.py`
  负责定义 SSE 事件载荷，补充结构化脑暴事件 schema。
- Modify: `apps/api/app/services/messages.py`
  负责流式消息事件顺序与数据组装，新增实时 guidance 事件。
- Modify: `apps/api/app/services/message_preparation.py`
  负责准备 `PreparedMessageStream` / `PreparedRegenerateStream`，补充 guidance 载荷透传。
- Modify: `apps/api/app/services/message_models.py`
  负责 Prepared stream 数据结构，新增结构化 guidance 字段。
- Modify: `apps/api/app/agent/types.py`
  负责 `TurnDecision` / phase 建模，补充 subfocus 或 phase detail 字段。
- Modify: `apps/api/app/agent/pm_mentor.py`
  负责 prompt、repair、fallback、quality guard，改成按 phase 递进生成 suggestions。
- Modify: `apps/api/app/services/message_state.py`
  负责把新增脑暴字段写入 state patch，保证快照侧一致。
- Modify: `apps/api/app/services/sessions.py`
  负责 session snapshot 输出，保证流式 guidance 与快照 guidance 一致。
- Test: `apps/api/tests/test_messages_stream.py`
  验证主链路 SSE 直接返回结构化脑暴载荷。
- Test: `apps/api/tests/test_pm_mentor.py`
  验证 phase-aware suggestions、repair、fallback 与质量校验。
- Test: `apps/api/tests/test_messages_service.py`
  验证持久化与 state patch 一致性。
- Test: `apps/api/tests/test_sessions.py`
  验证 snapshot 暴露的 guidance 与流式事件对齐。

### Task 1: 暴露实时头脑风暴事件

**Files:**
- Modify: `apps/api/app/schemas/message.py`
- Modify: `apps/api/app/services/message_models.py`
- Modify: `apps/api/app/services/message_preparation.py`
- Modify: `apps/api/app/services/messages.py`
- Test: `apps/api/tests/test_messages_stream.py`

- [ ] **Step 1: 写失败测试，要求 SSE 主链路直接返回结构化 guidance**

```python
def test_message_stream_emits_decision_ready_with_structured_guidance(...):
    parsed_events = _parse_sse_events(body)
    guidance_payload = next(payload for name, payload in parsed_events if name == "decision.ready")

    assert guidance_payload["phase"] == "target_user"
    assert len(guidance_payload["suggestions"]) == 4
    assert guidance_payload["recommendation"]["label"]
    assert guidance_payload["next_best_questions"] == [
        item["content"] for item in guidance_payload["suggestions"]
    ]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `PYTHONPATH=apps/api uv run pytest apps/api/tests/test_messages_stream.py -q -k decision_ready`
Expected: FAIL，提示不存在 `decision.ready` 事件或缺少 guidance 字段。

- [ ] **Step 3: 新增 guidance schema 与 prepared stream 字段**

```python
class DecisionReadyEventData(BaseModel):
    session_id: str
    user_message_id: str
    phase: str
    conversation_strategy: str
    next_move: str
    suggestions: list[dict[str, Any]]
    recommendation: dict[str, Any] | None
    next_best_questions: list[str]
```

```python
@dataclass
class PreparedMessageStream:
    ...
    guidance: dict[str, Any]
```

- [ ] **Step 4: 在消息流里发出 `decision.ready` 事件**

```python
yield MessageStreamEvent(
    type="decision.ready",
    data=prepared.guidance,
)
```

位置要求：
- 放在 `action.decided` 之后
- 放在 `assistant.version.started` 之前
- regenerate 链路也要保持同样顺序

- [ ] **Step 5: 运行测试确认通过**

Run: `PYTHONPATH=apps/api uv run pytest apps/api/tests/test_messages_stream.py -q -k decision_ready`
Expected: PASS

- [ ] **Step 6: 补回归测试**

Run: `PYTHONPATH=apps/api uv run pytest apps/api/tests/test_messages_stream.py -q`
Expected: PASS

### Task 2: 引入 phase-aware 头脑风暴细分

**Files:**
- Modify: `apps/api/app/agent/types.py`
- Modify: `apps/api/app/agent/pm_mentor.py`
- Modify: `apps/api/app/services/message_state.py`
- Test: `apps/api/tests/test_pm_mentor.py`

- [ ] **Step 1: 写失败测试，要求已选主相位后不能退回顶层通用四选项**

```python
def test_run_pm_mentor_target_user_focus_generates_second_level_suggestions():
    state = {
        "stage_hint": "target_user",
        "current_phase": "target_user",
        "prd_snapshot": {"sections": {}},
    }

    result = run_pm_mentor(
        state,
        "我想先明确这个产品主要给谁用",
        _build_mock_model_config(),
    )

    labels = [item.label for item in result.turn_decision.suggestions]
    assert "先聊核心问题" not in labels
    assert any("角色" in item.content or "场景" in item.content or "决策" in item.content for item in result.turn_decision.suggestions)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `PYTHONPATH=apps/api uv run pytest apps/api/tests/test_pm_mentor.py -q -k second_level`
Expected: FAIL，当前 suggestions 仍可能退回通用模板。

- [ ] **Step 3: 扩展 `TurnDecision` / state，增加子焦点字段**

```python
@dataclass
class TurnDecision:
    ...
    phase_subfocus: str | None = None
```

建议子焦点：
- `target_user.segment`
- `target_user.role`
- `target_user.scenario`
- `problem.frequency`
- `problem.severity`
- `problem.workaround`
- `solution.core_loop`
- `solution.differentiation`
- `mvp_scope.must_have`
- `mvp_scope.boundary`

- [ ] **Step 4: 让 `pm_mentor` 按主相位 + 子焦点生成 fallback suggestions**

```python
if current_phase == "target_user":
    return [
        "我想先区分是个人用户还是团队角色。",
        "我想先拆清楚谁是使用者、谁是决策者。",
        "我想先讲一个最典型的使用场景，你帮我反推用户。",
        "我直接补充我观察到的用户共性。",
    ]
```

要求：
- 不能只看 `user_input`，要综合 `state.stage_hint/current_phase`
- repair 失败后的程序化 fallback 也必须按当前 phase 定制

- [ ] **Step 5: 把 `phase_subfocus` 与 phase-aware guidance 写入 state patch**

```python
return {
    ...
    "current_phase": turn_decision.phase,
    "current_phase_subfocus": turn_decision.phase_subfocus,
}
```

- [ ] **Step 6: 运行测试确认通过**

Run: `PYTHONPATH=apps/api uv run pytest apps/api/tests/test_pm_mentor.py -q -k second_level`
Expected: PASS

- [ ] **Step 7: 跑 PM Mentor 全量相关测试**

Run: `PYTHONPATH=apps/api uv run pytest apps/api/tests/test_pm_mentor.py -q`
Expected: PASS

### Task 3: 增加头脑风暴质量守门

**Files:**
- Modify: `apps/api/app/agent/pm_mentor.py`
- Test: `apps/api/tests/test_pm_mentor.py`

- [ ] **Step 1: 写失败测试，要求 suggestions 必须与当前 phase 语义一致**

```python
def test_run_pm_mentor_rejects_generic_menu_when_phase_already_target_user():
    first_output = _make_pm_output(
        suggestions=[
            _make_suggestion("先聊目标用户", "我想先明确，这个产品主要给谁用。", priority=1),
            _make_suggestion("先聊核心问题", "我想先讲清楚，这个产品到底想解决什么问题。", priority=2),
            _make_suggestion("先聊核心功能", "我想先列一下这个产品的核心功能。", priority=3),
            _make_suggestion("我直接补充", "我直接补充我现在对这个产品的想法。", priority=4),
        ]
    )
    ...
    assert repaired_or_fallback_labels != ["先聊目标用户", "先聊核心问题", "先聊核心功能", "我直接补充"]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `PYTHONPATH=apps/api uv run pytest apps/api/tests/test_pm_mentor.py -q -k generic_menu`
Expected: FAIL

- [ ] **Step 3: 实现 quality guard**

```python
def _validate_guidance_quality(...):
    return GuidanceQuality(
        phase_aligned=...,
        sufficiently_distinct=...,
        references_current_context=...,
    )
```

最低规则：
- 当 `current_phase in {"target_user", "problem", "solution", "mvp_scope"}` 时，suggestions 不能回到总菜单
- 四个 suggestions 至少 3 个语义类别不同
- recommendation 必须是最终 suggestions 中最贴当前 phase 的一项

- [ ] **Step 4: 接到主链路**

顺序要求：
- 先解析原始输出
- 再做数量/句子/推荐项契约校验
- 再做 phase-aware 质量校验
- 不通过时先 repair，一次 repair 后仍失败再进入 phase-aware fallback

- [ ] **Step 5: 运行测试确认通过**

Run: `PYTHONPATH=apps/api uv run pytest apps/api/tests/test_pm_mentor.py -q -k generic_menu`
Expected: PASS

- [ ] **Step 6: 跑相关回归**

Run: `PYTHONPATH=apps/api uv run pytest apps/api/tests/test_pm_mentor.py -q`
Expected: PASS

### Task 4: 对齐持久化、快照和流式协议

**Files:**
- Modify: `apps/api/app/services/message_state.py`
- Modify: `apps/api/app/services/sessions.py`
- Test: `apps/api/tests/test_messages_service.py`
- Test: `apps/api/tests/test_sessions.py`
- Test: `apps/api/tests/test_messages_stream.py`

- [ ] **Step 1: 写失败测试，要求 `decision.ready` 与 session snapshot guidance 一致**

```python
def test_stream_guidance_matches_snapshot_guidance(...):
    stream_payload = ...
    snapshot = auth_client.get(f"/api/sessions/{seeded_session}").json()
    next_step = next(section for section in snapshot["turn_decisions"][-1]["decision_sections"] if section["key"] == "next_step")

    assert stream_payload["suggestions"] == next_step["meta"]["suggestion_options"]
    assert stream_payload["next_best_questions"] == next_step["meta"]["next_best_questions"]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `PYTHONPATH=apps/api uv run pytest apps/api/tests/test_sessions.py apps/api/tests/test_messages_stream.py -q -k guidance_matches`
Expected: FAIL

- [ ] **Step 3: 统一 guidance 序列化函数**

```python
def build_guidance_payload(turn_decision: object) -> dict[str, Any]:
    ...
```

放在共享 service 模块，供：
- `messages.py` 流式事件使用
- `sessions.py` snapshot section meta 使用
- `message_state.py` state patch 使用

- [ ] **Step 4: 确保持久化后 state / snapshot / stream 三端字段一致**

至少统一这些字段：
- `phase`
- `conversation_strategy`
- `next_move`
- `suggestions`
- `recommendation`
- `next_best_questions`
- `phase_subfocus`

- [ ] **Step 5: 运行定向测试确认通过**

Run: `PYTHONPATH=apps/api uv run pytest apps/api/tests/test_messages_service.py apps/api/tests/test_sessions.py apps/api/tests/test_messages_stream.py -q`
Expected: PASS

### Task 5: 全量回归与文档更新

**Files:**
- Modify: `apps/api/CLAUDE.md`
- Optional Modify: `docs/superpowers/specs/2026-04-10-pm-mentor-architecture-design.md`

- [ ] **Step 1: 更新后端行为说明**

补充：
- 新增 `decision.ready` 事件
- `phase_subfocus` 字段语义
- guidance 质量守门规则

- [ ] **Step 2: 跑后端回归**

Run: `PYTHONPATH=apps/api uv run pytest apps/api/tests/test_pm_mentor.py apps/api/tests/test_messages_service.py apps/api/tests/test_messages_stream.py apps/api/tests/test_sessions.py -q`
Expected: PASS

- [ ] **Step 3: 记录风险与后续项**

至少记录：
- 仍未解决的 LLM 质量漂移风险
- 是否需要把 `phase_subfocus` 扩展到前端 store 类型
- 是否把 `decision.ready` 推广到 regenerate 之外的其他交互面板

- [ ] **Step 4: Commit**

```bash
git add apps/api/app apps/api/tests apps/api/CLAUDE.md docs/superpowers/plans/2026-04-16-backend-brainstorming-enhancement-implementation.md
git commit -m "feat(api): strengthen structured brainstorming guidance"
```

## Priority / Scope

### P0
- Task 1: 暴露实时头脑风暴事件
- Task 2: 引入 phase-aware 头脑风暴细分

### P1
- Task 3: 增加头脑风暴质量守门
- Task 4: 对齐持久化、快照和流式协议

### P2
- Task 5: 文档更新、扩展更多 subfocus、考虑前端类型同步

## Acceptance Criteria

- `/api/sessions/{session_id}/messages` 流式链路可直接返回结构化脑暴 guidance
- 用户进入某个主相位后，下一轮 suggestions 会进入二级细化，不再退回通用四选项
- repair / fallback 都遵守当前 phase 语义
- session snapshot、state、stream 三端 guidance 字段一致
- 相关 pytest 全部通过
