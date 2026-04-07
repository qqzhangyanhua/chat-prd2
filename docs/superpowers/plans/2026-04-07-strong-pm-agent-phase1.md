# 强推进型 AI 产品经理 Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把当前后端从“记录 action 的问答链路”升级成“PM 决策先行、回复严格受决策约束”的第一阶段系统，并让每轮回复默认包含建议。

**Architecture:** 保留现有 `sessions / messages / state_version / prd_snapshot / assistant_reply_version` 基础设施，在 `app/agent` 内增加输入理解、PM 决策、建议规划、回复编排四层。`messages.py` 退化为会话编排器，所有 PM 逻辑都通过结构化 `TurnDecision` 对象汇总并落库。

**Tech Stack:** FastAPI, SQLAlchemy 2, Pydantic 2, pytest, SSE, OpenAI-compatible gateway

---

## 范围说明

本计划只覆盖 [strong-pm-agent-design.md](/Users/zhangyanhua/AI/chat-prd2/docs/superpowers/specs/2026-04-07-strong-pm-agent-design.md) 的第一阶段：

- 引入 `TurnDecision`
- 引入 `Suggestion`
- 把最终回复绑定到决策对象
- 扩展状态模型到“阶段 + 假设 + 风险 + 确认项 + 建议方向”
- 新增回合决策审计持久化

本计划暂不覆盖：

- 联网调研或工具调用
- 完整非线性多阶段跳转
- 更完整的 PRD 文档输出
- 决策评分与离线评估平台

## 文件结构与职责

### 新增文件

- `apps/api/app/agent/understanding.py`
  输入理解层，负责把用户输入拆成 PM 可用的结构化理解。
- `apps/api/app/agent/decision_engine.py`
  PM 决策引擎，负责阶段判断、风险标记、下一步动作选择。
- `apps/api/app/agent/suggestion_planner.py`
  建议规划器，负责生成选项、推荐项与理由。
- `apps/api/app/agent/reply_composer.py`
  回复编排器，负责按回复合同输出最终文本。
- `apps/api/app/repositories/agent_turn_decisions.py`
  回合决策数据访问层。
- `apps/api/tests/test_agent_understanding.py`
  输入理解单测。
- `apps/api/tests/test_agent_decision_engine.py`
  决策引擎单测。
- `apps/api/tests/test_agent_suggestion_planner.py`
  建议规划器单测。
- `apps/api/tests/test_agent_reply_composer.py`
  回复合同单测。

### 修改文件

- `apps/api/app/agent/types.py`
  扩展为 `TurnDecision`、`Suggestion`、`UnderstandingResult` 等核心类型。
- `apps/api/app/agent/runtime.py`
  从轻量追问器改为总编排入口。
- `apps/api/app/schemas/state.py`
  扩展状态快照字段。
- `apps/api/app/schemas/message.py`
  为 SSE 或快照响应新增决策元数据字段（如需要）。
- `apps/api/app/services/messages.py`
  接入新决策链路与决策持久化。
- `apps/api/app/db/models.py`
  增加 `AgentTurnDecision` ORM 模型。
- `apps/api/alembic/versions/*.py`
  新增迁移脚本。
- `apps/api/tests/test_agent_runtime.py`
  更新 runtime 行为断言。
- `apps/api/tests/test_messages_service.py`
  更新服务层行为断言。
- `apps/api/tests/test_messages_stream.py`
  更新流式响应与持久化断言。
- `apps/api/tests/test_sessions.py`
  如需验证快照展示与历史返回，更新会话测试。

## 关键实现约束

- 回复文本不允许再直接基于“历史消息 + system prompt”自由生成。
- 每轮必须先形成 `TurnDecision`，再基于 `reply_brief + suggestions` 生成最终回复。
- 每轮回复默认都要包含：
  - 当前判断
  - 建议或备选方向
  - 推荐理由
  - 下一步确认动作
- 状态写入必须区分：
  - 已确认事实
  - 工作假设
  - 待确认项
- 重生成只影响表达层，不影响状态与决策审计。

## 测试总策略

- 先补失败测试，再做实现。
- 优先验证结构化决策，而不是只验证最终回复文本。
- 行为测试必须覆盖“默认给建议”和“先做假设再推进”。

### Task 1: 扩展核心类型与状态契约

**Files:**
- Modify: `apps/api/app/agent/types.py`
- Modify: `apps/api/app/schemas/state.py`
- Modify: `apps/api/tests/test_agent_runtime.py`
- Create: `apps/api/tests/test_agent_types_contract.py`

- [ ] **Step 1: 写失败测试，锁定新决策契约**

```python
from app.agent.types import NextMove


def test_next_move_only_exposes_phase1_supported_values():
    assert get_args(NextMove) == (
        "probe_for_specificity",
        "assume_and_advance",
        "challenge_and_reframe",
        "summarize_and_confirm",
        "force_rank_or_choose",
    )


def test_turn_decision_requires_suggestions_and_reply_brief():
    decision = TurnDecision(
        phase="target_user_narrowing",
        phase_goal="收敛目标用户",
        understanding={"summary": "用户想做 AI 产品经理工具"},
        assumptions=[],
        gaps=["目标用户过泛"],
        challenges=[],
        pm_risk_flags=["user_too_broad"],
        next_move="probe_for_specificity",
        suggestions=[Suggestion(...)],
        recommendation={"label": "先聚焦独立开发者"},
        reply_brief={"must_include": ["判断", "建议", "理由", "确认推进"]},
        state_patch={"current_phase": "target_user_narrowing"},
        prd_patch={},
        needs_confirmation=["是否聚焦独立开发者"],
        confidence="medium",
    )
    assert decision.next_move == "probe_for_specificity"
```

- [ ] **Step 2: 运行新测试，确认当前实现失败**

Run: `cd apps/api && uv run pytest tests/test_agent_types_contract.py tests/test_agent_runtime.py -q`
Expected: FAIL，提示 `TurnDecision` / `Suggestion` / `NextMove` 不存在或字段不完整。

- [ ] **Step 3: 在 `types.py` 中定义第一阶段所需核心类型**

```python
class SuggestionType(Literal):
    "direction" | "tradeoff" | "recommendation" | "warning"


class NextMove(Literal):
    "probe_for_specificity" | "assume_and_advance" | ...


@dataclass(slots=True)
class Suggestion:
    type: SuggestionType
    label: str
    content: str
    rationale: str
    priority: int


@dataclass(slots=True)
class TurnDecision:
    phase: str
    phase_goal: str
    understanding: dict[str, Any]
    assumptions: list[dict[str, Any]]
    gaps: list[str]
    challenges: list[str]
    pm_risk_flags: list[str]
    next_move: NextMove
    suggestions: list[Suggestion]
    recommendation: dict[str, Any] | None
    reply_brief: dict[str, Any]
    state_patch: dict[str, Any]
    prd_patch: dict[str, Any]
    needs_confirmation: list[str]
    confidence: Literal["high", "medium", "low"]
```

- [ ] **Step 4: 扩展 `StateSnapshot` 和运行时状态字段**

```python
class StateSnapshot(BaseModel):
    ...
    current_phase: str
    phase_goal: str | None
    working_hypotheses: list[dict[str, Any]]
    evidence: list[dict[str, Any]]
    decision_readiness: str | None
    pm_risk_flags: list[str]
    recommended_directions: list[dict[str, Any]]
    pending_confirmations: list[str]
    rejected_options: list[str]
    next_best_questions: list[str]
```

- [ ] **Step 5: 更新现有 runtime 测试，使其断言面向 `TurnDecision`**

Run: `cd apps/api && uv run pytest tests/test_agent_types_contract.py tests/test_agent_runtime.py -q`
Expected: PASS，旧断言中若仍使用 `action.target`，改为断言 `next_move`、`phase`、`state_patch`。

- [ ] **Step 6: 提交本任务**

```bash
git add apps/api/app/agent/types.py apps/api/app/schemas/state.py apps/api/tests/test_agent_runtime.py apps/api/tests/test_agent_types_contract.py
git commit -m "feat(api): add pm decision contracts"
```

### Task 2: 实现输入理解层

**Files:**
- Create: `apps/api/app/agent/understanding.py`
- Modify: `apps/api/app/agent/runtime.py`
- Create: `apps/api/tests/test_agent_understanding.py`

- [ ] **Step 1: 写失败测试，定义输入理解最小能力**

```python
def test_understanding_extracts_fact_guess_and_problem_signal():
    result = understand_user_input(
        state={"current_phase": "target_user_narrowing"},
        user_input="我想做一个帮创业者梳理需求的 AI，但我猜更适合独立开发者，因为他们最缺产品判断。",
    )
    assert result.summary
    assert "独立开发者" in result.candidate_updates["target_user"]
    assert result.assumption_candidates == ["更适合独立开发者"]
    assert "创业者" in result.ambiguous_points[0]


def test_understanding_marks_overly_broad_user_segment():
    result = understand_user_input(
        state={"current_phase": "target_user_narrowing"},
        user_input="目标用户就是所有创业者",
    )
    assert "user_too_broad" in result.risk_hints
```

- [ ] **Step 2: 运行理解层测试，确认失败**

Run: `cd apps/api && uv run pytest tests/test_agent_understanding.py -q`
Expected: FAIL，提示 `understand_user_input` 或 `UnderstandingResult` 不存在。

- [ ] **Step 3: 实现 `UnderstandingResult` 与最小规则 + 模型兼容输入理解**

```python
def understand_user_input(state: dict, user_input: str) -> UnderstandingResult:
    normalized = normalize_text(user_input)
    summary = summarize_input_locally(normalized)
    candidate_updates = extract_candidate_updates(state, normalized)
    assumption_candidates = detect_assumption_candidates(normalized)
    ambiguous_points = detect_ambiguous_points(state, normalized)
    risk_hints = detect_risk_hints(state, normalized, candidate_updates)
    return UnderstandingResult(...)
```

- [ ] **Step 4: 让 runtime 改为先调用理解层，而不是直接按缺字段归类**

Run: `cd apps/api && uv run pytest tests/test_agent_understanding.py tests/test_agent_runtime.py -q`
Expected: PASS，runtime 至少能拿到理解结果并继续执行。

- [ ] **Step 5: 提交本任务**

```bash
git add apps/api/app/agent/understanding.py apps/api/app/agent/runtime.py apps/api/tests/test_agent_understanding.py
git commit -m "feat(api): add agent understanding layer"
```

### Task 3: 实现 PM 决策引擎

**Files:**
- Create: `apps/api/app/agent/decision_engine.py`
- Modify: `apps/api/app/agent/runtime.py`
- Create: `apps/api/tests/test_agent_decision_engine.py`

- [ ] **Step 1: 写失败测试，定义阶段 1 的决策规则**

```python
def test_decision_engine_uses_assume_and_advance_when_input_is_directional_but_incomplete():
    understanding = UnderstandingResult(
        summary="用户倾向服务独立开发者，但未说明具体触发场景",
        candidate_updates={"target_user": "独立开发者"},
        assumption_candidates=["服务刚开始找 PMF 的独立开发者"],
        ambiguous_points=["缺少触发场景"],
        risk_hints=[],
    )
    decision = build_turn_decision(state=state, understanding=understanding)
    assert decision.next_move == "assume_and_advance"
    assert decision.assumptions
    assert decision.needs_confirmation


def test_decision_engine_chooses_force_rank_when_scope_remains_broad():
    understanding = UnderstandingResult(...)
    decision = build_turn_decision(state=state, understanding=understanding)
    assert decision.next_move == "force_rank_or_choose"
    assert "user_too_broad" in decision.pm_risk_flags
```

- [ ] **Step 2: 运行决策引擎测试，确认失败**

Run: `cd apps/api && uv run pytest tests/test_agent_decision_engine.py -q`
Expected: FAIL，提示 `build_turn_decision` 不存在。

- [ ] **Step 3: 在 `decision_engine.py` 中实现最小可用决策器**

```python
def build_turn_decision(state: dict, understanding: UnderstandingResult) -> TurnDecision:
    phase = resolve_phase(state)
    phase_goal = resolve_phase_goal(phase)
    gaps = compute_gaps(phase, understanding, state)
    risk_flags = merge_risk_hints(understanding.risk_hints, state)
    next_move = choose_next_move(phase, gaps, risk_flags, understanding)
    state_patch = build_state_patch(...)
    prd_patch = build_prd_patch(...)
    return TurnDecision(...)
```

- [ ] **Step 4: 明确第一阶段的决策策略白名单**

实现要求：
- 若用户输入过泛且未收敛，优先 `force_rank_or_choose`
- 若方向有价值但细节不足，优先 `assume_and_advance`
- 若用户先聊方案再聊问题，优先 `challenge_and_reframe`
- 若已形成局部共识，优先 `summarize_and_confirm`

- [ ] **Step 5: 让 runtime 改为调用决策引擎生成 `TurnDecision`**

Run: `cd apps/api && uv run pytest tests/test_agent_decision_engine.py tests/test_agent_runtime.py -q`
Expected: PASS，runtime 不再直接手写 action。

- [ ] **Step 6: 提交本任务**

```bash
git add apps/api/app/agent/decision_engine.py apps/api/app/agent/runtime.py apps/api/tests/test_agent_decision_engine.py apps/api/tests/test_agent_runtime.py
git commit -m "feat(api): add pm decision engine"
```

### Task 4: 实现建议规划与回复编排

**Files:**
- Create: `apps/api/app/agent/suggestion_planner.py`
- Create: `apps/api/app/agent/reply_composer.py`
- Modify: `apps/api/app/agent/runtime.py`
- Create: `apps/api/tests/test_agent_suggestion_planner.py`
- Create: `apps/api/tests/test_agent_reply_composer.py`

- [ ] **Step 1: 写失败测试，锁定“默认给建议”的行为**

```python
def test_suggestion_planner_returns_options_and_recommendation():
    decision = TurnDecision(next_move="force_rank_or_choose", ...)
    suggestions = build_suggestions(decision)
    assert len(suggestions) >= 2
    assert any(item.type == "recommendation" for item in suggestions)


def test_reply_composer_always_contains_judgment_suggestion_reason_and_confirmation():
    reply = compose_reply(decision)
    assert "我现在的判断是" in reply
    assert "我建议" in reply
    assert "原因是" in reply
    assert "你确认一下" in reply
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `cd apps/api && uv run pytest tests/test_agent_suggestion_planner.py tests/test_agent_reply_composer.py -q`
Expected: FAIL，提示 `build_suggestions` / `compose_reply` 不存在。

- [ ] **Step 3: 实现建议规划器**

```python
def build_suggestions(decision: TurnDecision) -> list[Suggestion]:
    if decision.next_move == "force_rank_or_choose":
        return [
            Suggestion(type="direction", ...),
            Suggestion(type="direction", ...),
            Suggestion(type="recommendation", ...),
        ]
    if decision.next_move == "assume_and_advance":
        return [...]
```

- [ ] **Step 4: 实现回复编排器，按回复合同输出**

```python
def compose_reply(decision: TurnDecision) -> str:
    parts = [
        render_judgment_block(decision),
        render_suggestion_block(decision.suggestions, decision.recommendation),
        render_reason_block(decision),
        render_confirmation_block(decision),
    ]
    return "\n\n".join(part for part in parts if part)
```

- [ ] **Step 5: 让 runtime 使用 `build_suggestions` 与 `compose_reply` 完成最终 `AgentResult`**

Run: `cd apps/api && uv run pytest tests/test_agent_suggestion_planner.py tests/test_agent_reply_composer.py tests/test_agent_runtime.py -q`
Expected: PASS，runtime 返回的 `reply` 已体现建议驱动。

- [ ] **Step 6: 提交本任务**

```bash
git add apps/api/app/agent/suggestion_planner.py apps/api/app/agent/reply_composer.py apps/api/app/agent/runtime.py apps/api/tests/test_agent_suggestion_planner.py apps/api/tests/test_agent_reply_composer.py apps/api/tests/test_agent_runtime.py
git commit -m "feat(api): bind reply generation to pm decisions"
```

### Task 5: 新增回合决策审计持久化

**Files:**
- Modify: `apps/api/app/db/models.py`
- Create: `apps/api/app/repositories/agent_turn_decisions.py`
- Modify: `apps/api/app/services/messages.py`
- Modify: `apps/api/alembic/versions/<new_revision>_add_agent_turn_decisions.py`
- Modify: `apps/api/tests/test_messages_service.py`
- Modify: `apps/api/tests/test_messages_stream.py`

- [ ] **Step 1: 写失败测试，定义新消息必须落库决策审计**

```python
def test_handle_user_message_persists_turn_decision(db_session, monkeypatch):
    monkeypatch.setattr("app.services.messages.generate_reply", lambda **_: "placeholder")
    result = handle_user_message(...)
    saved = agent_turn_decisions_repository.get_latest_for_user_message(db_session, result.user_message_id)
    assert saved is not None
    assert saved.next_move == "assume_and_advance"
    assert saved.suggestions_json
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `cd apps/api && uv run pytest tests/test_messages_service.py::test_handle_user_message_persists_turn_decision -q`
Expected: FAIL，提示表或 repository 不存在。

- [ ] **Step 3: 增加 ORM 模型与 Alembic 迁移**

```python
class AgentTurnDecision(Base):
    __tablename__ = "agent_turn_decisions"
    id = mapped_column(String, primary_key=True)
    session_id = mapped_column(ForeignKey("project_sessions.id"), index=True)
    user_message_id = mapped_column(ForeignKey("conversation_messages.id"), index=True, unique=True)
    phase = mapped_column(String)
    phase_goal = mapped_column(String)
    understanding_summary = mapped_column(Text)
    assumptions_json = mapped_column(JSON, default=list)
    risk_flags_json = mapped_column(JSON, default=list)
    next_move = mapped_column(String)
    suggestions_json = mapped_column(JSON, default=list)
    recommendation_json = mapped_column(JSON, default=dict)
    needs_confirmation_json = mapped_column(JSON, default=list)
    confidence = mapped_column(String)
    state_patch_json = mapped_column(JSON, default=dict)
    prd_patch_json = mapped_column(JSON, default=dict)
```

- [ ] **Step 4: 在 `messages.py` 中把 `TurnDecision` 持久化到新表**

实现要求：
- 新消息成功时写入一条决策记录
- 重生成不写新决策记录
- 若消息链路整体失败，决策记录一并回滚

- [ ] **Step 5: 更新服务与流式测试**

Run: `cd apps/api && uv run pytest tests/test_messages_service.py tests/test_messages_stream.py -q`
Expected: PASS，新增断言包括：
- 新消息会落 `agent_turn_decisions`
- 重生成不会创建新记录
- 流式成功后 assistant 回复与决策记录一致

- [ ] **Step 6: 提交本任务**

```bash
git add apps/api/app/db/models.py apps/api/app/repositories/agent_turn_decisions.py apps/api/app/services/messages.py apps/api/alembic/versions/*.py apps/api/tests/test_messages_service.py apps/api/tests/test_messages_stream.py
git commit -m "feat(api): persist agent turn decisions"
```

### Task 6: 集成新状态字段并完成端到端回归

**Files:**
- Modify: `apps/api/app/services/sessions.py`
- Modify: `apps/api/app/services/messages.py`
- Modify: `apps/api/tests/test_sessions.py`
- Modify: `apps/api/tests/test_messages_service.py`
- Modify: `apps/api/tests/test_messages_stream.py`

- [ ] **Step 1: 写失败测试，确认初始 state 与消息后 state 的新字段行为**

```python
def test_create_session_returns_phase1_default_state(auth_client):
    response = auth_client.post("/api/sessions", json={...})
    data = response.json()
    assert data["state"]["current_phase"] == "idea_clarification"
    assert data["state"]["working_hypotheses"] == []
    assert data["state"]["pending_confirmations"] == []


def test_message_updates_recommended_directions_and_pending_confirmations(...):
    ...
    latest_state = state_repository.get_latest_state(db_session, session.id)
    assert latest_state["recommended_directions"]
    assert latest_state["pending_confirmations"]
```

- [ ] **Step 2: 运行相关测试，确认失败**

Run: `cd apps/api && uv run pytest tests/test_sessions.py tests/test_messages_service.py tests/test_messages_stream.py -q`
Expected: FAIL，提示新状态字段缺失或链路未更新。

- [ ] **Step 3: 更新 `build_initial_state` 与状态补丁合并逻辑**

实现要求：
- `create_session` 初始化新状态字段
- `messages.py` 应把 `TurnDecision.state_patch` 合并到主状态
- `pending_confirmations`、`recommended_directions` 这类列表字段要采用确定性合并规则

- [ ] **Step 4: 运行 API 相关测试，完成端到端回归**

Run: `cd apps/api && uv run pytest tests/test_sessions.py tests/test_messages_service.py tests/test_messages_stream.py tests/test_agent_runtime.py tests/test_agent_understanding.py tests/test_agent_decision_engine.py tests/test_agent_suggestion_planner.py tests/test_agent_reply_composer.py -q`
Expected: PASS

- [ ] **Step 5: 运行完整后端测试集**

Run: `cd apps/api && uv run pytest -q`
Expected: PASS，全部通过。

- [ ] **Step 6: 提交本任务**

```bash
git add apps/api/app/services/sessions.py apps/api/app/services/messages.py apps/api/tests/test_sessions.py apps/api/tests/test_messages_service.py apps/api/tests/test_messages_stream.py
git commit -m "feat(api): complete phase1 strong pm agent flow"
```

## 实施备注

- 第一步只做第一阶段能力，不要顺手把后续“全自动阶段跳转”“更完整导出”“联网调研”一起做掉。
- 如果在实现中发现 `messages.py` 继续膨胀，应优先把纯 PM 逻辑下沉到 `app/agent/*`，不要把复杂判断留在 service 层。
- 如果 `TurnDecision` 过于庞大，优先拆 `understanding`、`recommendation` 为独立 dataclass，而不是往一个 `dict` 里继续塞字段。

## 完成定义

当以下条件同时满足时，本计划可视为完成：

- 新消息链路每轮都先形成 `TurnDecision`
- 回复默认包含判断、建议、理由、确认推进
- 信息不足时能够显式假设后继续推进
- 系统能记录回合决策审计
- 重生成只影响表达，不影响状态与决策
- `cd apps/api && uv run pytest -q` 全量通过
