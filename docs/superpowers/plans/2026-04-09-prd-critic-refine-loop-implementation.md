# PRD Critic Refine Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `apps/api` 的对话后端从“四字段顺序填充”升级成“假设版 PRD v1 + Critic 自动审查 + 单问题 refine loop”的最小可运行闭环。

**Architecture:** 保留现有 `messages / state_version / prd_snapshot / assistant_reply_version` 基础设施，在 `app/agent` 上层新增显式 `workflow_stage` 编排。首次输入走 `Idea Parser -> PRD Draft -> Critic` 自动流，后续输入走 `refine_loop -> critic_review`，回复只输出“当前草稿摘要 + Critic verdict + 唯一下一问”。

**Tech Stack:** FastAPI, SQLAlchemy 2, Pydantic 2, pytest, SSE, OpenAI-compatible gateway

---

## 范围说明

本计划对应 [`2026-04-08-prd-critic-refine-loop-design.md`](/Users/zhangyanhua/AI/chat-prd2/docs/superpowers/specs/2026-04-08-prd-critic-refine-loop-design.md) 的最小实现闭环，只覆盖后端。

本计划范围内必须完成：

- 新增 `workflow_stage` 和闭环所需结果对象
- 首次输入自动生成“假设版 PRD v1”
- 自动执行 Critic 并产出结构化 verdict
- 每轮只追问一个最高价值产品方案问题
- 用户补充后生成 `PRD v2` 并重新跑 Critic
- 在关键产品方案缺口未补齐前，不允许进入 finalize

本计划范围外暂不实现：

- 新数据库表
- 全面重写前端协议
- 联网搜索或外部工具接入
- 通用行业化 Critic 模板库

## 文件结构与职责

### 重点修改文件

- `apps/api/app/agent/types.py`
  定义 `WorkflowStage`、`IdeaParseResult`、`PrdDraftResult`、`CriticResult` 以及运行时结果扩展字段。
- `apps/api/app/agent/runtime.py`
  从旧的四字段 runtime 升级成工作流编排入口。
- `apps/api/app/agent/understanding.py`
  从“最小理解”扩展成 `Idea Parser`，支持领域信号、显式需求、隐式假设、开放问题提取。
- `apps/api/app/agent/decision_engine.py`
  根据 `workflow_stage` 和 `critic_result` 决定是否继续 refine、是否允许 finalize。
- `apps/api/app/agent/reply_composer.py`
  改成固定输出“草稿摘要 + Critic 结论 + 唯一下一问”。
- `apps/api/app/services/messages.py`
  将新工作流状态合并进持久化链路，并保持现有 SSE / version 语义。
- `apps/api/app/schemas/state.py`
  扩展状态快照契约。
- `apps/api/tests/test_agent_runtime.py`
  覆盖首次输入自动闭环和 refine 闭环。
- `apps/api/tests/test_messages_service.py`
  覆盖服务层持久化与状态合并。
- `apps/api/tests/test_messages_stream.py`
  覆盖 SSE 流和回复内容合同。

### 预计新增测试文件

- `apps/api/tests/test_agent_types_contract.py`
  锁定新类型和阶段契约。
- `apps/api/tests/test_agent_understanding.py`
  锁定 `Idea Parser` 提取能力。
- `apps/api/tests/test_agent_reply_composer.py`
  更新为新回复合同。

## 关键实现约束

- 不推倒现有 `state_version / prd_snapshot / assistant_reply_version` 机制。
- 第一阶段只在 `state` 中承载新工作流字段，不新增表。
- 回复层不能自由泛聊，必须由 `critic_result.question_queue[0]` 驱动。
- 每轮只能输出一个下一问。
- 所有行为改动先写失败测试，再写最小实现。
- 不要一次性删除旧四字段字段；先兼容保留，再让 `workflow_stage` 成为主驱动。

## 测试总策略

- 优先验证结构化状态和 verdict，不只验证自然语言文案。
- 首次输入主样例使用“在线 3D 图纸预览平台”。
- 先跑小范围单测，再跑消息服务和流测试，最后做 API 后端回归。

### Task 1: 定义闭环核心类型与状态契约

**Files:**
- Modify: `apps/api/app/agent/types.py`
- Modify: `apps/api/app/schemas/state.py`
- Create: `apps/api/tests/test_agent_types_contract.py`

- [ ] **Step 1: 写失败测试，锁定工作流阶段和结果对象**

```python
from typing import get_args

from app.agent.types import WorkflowStage, CriticResult, IdeaParseResult, PrdDraftResult


def test_workflow_stage_supports_closed_loop_values():
    assert set(get_args(WorkflowStage)) >= {
        "idea_parser",
        "prd_draft",
        "critic_review",
        "refine_loop",
        "finalize",
    }


def test_critic_result_requires_verdict_and_question_queue():
    result = CriticResult(
        overall_verdict="revise",
        strengths=["方向清楚"],
        major_gaps=["未明确文件格式"],
        minor_gaps=[],
        question_queue=["第一版要支持哪些 3D/CAD 文件格式？"],
        blocking_questions=[],
        recommended_next_focus="产品方案",
        revision_instructions=["先明确格式支持"],
    )
    assert result.overall_verdict == "revise"
    assert result.question_queue[0].startswith("第一版要支持")
```

- [ ] **Step 2: 运行测试，确认当前实现失败**

Run: `cd apps/api && uv run pytest tests/test_agent_types_contract.py -q`
Expected: FAIL，提示 `WorkflowStage` 或新结果对象不存在。

- [ ] **Step 3: 在 `types.py` 中定义新类型**

```python
WorkflowStage = Literal[
    "idea_parser",
    "prd_draft",
    "critic_review",
    "refine_loop",
    "finalize",
]


@dataclass(slots=True)
class IdeaParseResult:
    idea_summary: str
    product_type: str | None
    domain_signals: list[str]
    explicit_requirements: list[str]
    implicit_assumptions: list[str]
    open_questions: list[str]
    confidence: Literal["high", "medium", "low"]


@dataclass(slots=True)
class PrdDraftResult:
    version: int
    status: Literal["draft_hypothesis", "draft_refined", "ready_for_finalize"]
    sections: dict[str, dict[str, Any]]
    assumptions: list[str]
    missing_information: list[str]
    critic_ready: bool


@dataclass(slots=True)
class CriticResult:
    overall_verdict: Literal["pass", "revise", "block"]
    strengths: list[str]
    major_gaps: list[str]
    minor_gaps: list[str]
    question_queue: list[str]
    blocking_questions: list[str]
    recommended_next_focus: str | None
    revision_instructions: list[str]
```

- [ ] **Step 4: 扩展 `StateSnapshot` 契约**

```python
class StateSnapshot(BaseModel):
    ...
    workflow_stage: str = "idea_parser"
    idea_parse_result: dict | None = None
    prd_draft: dict | None = None
    critic_result: dict | None = None
    refine_history: list[dict] = Field(default_factory=list)
    finalization_ready: bool = False
```

- [ ] **Step 5: 运行契约测试确认通过**

Run: `cd apps/api && uv run pytest tests/test_agent_types_contract.py -q`
Expected: PASS

- [ ] **Step 6: 提交本任务**

```bash
git add apps/api/app/agent/types.py apps/api/app/schemas/state.py apps/api/tests/test_agent_types_contract.py
git commit -m "feat(api): add prd critic loop contracts"
```

### Task 2: 实现 Idea Parser 最小能力

**Files:**
- Modify: `apps/api/app/agent/understanding.py`
- Create: `apps/api/tests/test_agent_understanding.py`

- [ ] **Step 1: 写失败测试，覆盖一句话产品想法解析**

```python
from app.agent.understanding import parse_idea_input


def test_parse_idea_input_extracts_domain_signals_and_questions():
    result = parse_idea_input("我想做一个在线3D图纸预览平台")
    assert "3D图纸预览平台" in result.idea_summary
    assert result.product_type == "在线3D图纸预览平台"
    assert "3D预览" in result.domain_signals
    assert any("格式" in question for question in result.open_questions)
    assert any("权限" in question for question in result.open_questions)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd apps/api && uv run pytest tests/test_agent_understanding.py -q`
Expected: FAIL，提示 `parse_idea_input` 不存在。

- [ ] **Step 3: 在 `understanding.py` 中实现最小规则版 Idea Parser**

```python
def parse_idea_input(user_input: str) -> IdeaParseResult:
    normalized = normalize_text(user_input)
    product_type = infer_product_type(normalized)
    domain_signals = infer_domain_signals(normalized)
    explicit_requirements = infer_explicit_requirements(normalized)
    implicit_assumptions = infer_implicit_assumptions(normalized)
    open_questions = build_open_questions(product_type, domain_signals)
    return IdeaParseResult(...)
```

- [ ] **Step 4: 兼容旧 `understand_user_input` 调用**

```python
def understand_user_input(state: dict, user_input: str) -> UnderstandingResult:
    ...
    if state.get("workflow_stage") == "idea_parser":
        idea_result = parse_idea_input(user_input)
        ...
```

- [ ] **Step 5: 运行理解层测试确认通过**

Run: `cd apps/api && uv run pytest tests/test_agent_understanding.py -q`
Expected: PASS

- [ ] **Step 6: 提交本任务**

```bash
git add apps/api/app/agent/understanding.py apps/api/tests/test_agent_understanding.py
git commit -m "feat(api): add idea parser for draft loop"
```

### Task 3: 在 runtime 中打通首次输入自动闭环

**Files:**
- Modify: `apps/api/app/agent/runtime.py`
- Modify: `apps/api/tests/test_agent_runtime.py`

- [ ] **Step 1: 写失败测试，覆盖首次输入自动生成 PRD v1 + Critic**

```python
from app.agent.runtime import run_agent


def test_run_agent_builds_draft_and_critic_on_first_idea():
    state = {
        "idea": "我想做一个在线3D图纸预览平台",
        "workflow_stage": "idea_parser",
        "prd_snapshot": {"sections": {}},
    }

    result = run_agent(state, "我想做一个在线3D图纸预览平台")

    assert result.state_patch["workflow_stage"] == "refine_loop"
    assert result.state_patch["idea_parse_result"]["product_type"] == "在线3D图纸预览平台"
    assert result.state_patch["prd_draft"]["version"] == 1
    assert result.state_patch["prd_draft"]["status"] == "draft_hypothesis"
    assert result.state_patch["critic_result"]["overall_verdict"] in {"revise", "block"}
    assert result.state_patch["critic_result"]["question_queue"]
```

- [ ] **Step 2: 运行 runtime 测试确认失败**

Run: `cd apps/api && uv run pytest tests/test_agent_runtime.py -q`
Expected: FAIL，旧 runtime 不会生成上述结构。

- [ ] **Step 3: 在 `runtime.py` 新增首次输入闭环编排函数**

```python
def _build_initial_prd_draft(idea_result: IdeaParseResult) -> PrdDraftResult:
    ...


def _review_prd_draft(prd_draft: PrdDraftResult) -> CriticResult:
    ...


def _run_initial_draft_flow(state: dict, user_input: str) -> AgentResult:
    idea_result = parse_idea_input(user_input)
    prd_draft = _build_initial_prd_draft(idea_result)
    critic_result = _review_prd_draft(prd_draft)
    state_patch = {
        "workflow_stage": "refine_loop",
        "idea_parse_result": asdict(idea_result),
        "prd_draft": asdict(prd_draft),
        "critic_result": asdict(critic_result),
        "finalization_ready": critic_result.overall_verdict == "pass",
    }
    ...
```

- [ ] **Step 4: 让首次消息绕过旧四字段“填槽即收敛”路径**

```python
if state.get("workflow_stage") in {None, "idea_parser"}:
    return _run_initial_draft_flow(state, user_input)
```

- [ ] **Step 5: 运行 runtime 测试确认通过**

Run: `cd apps/api && uv run pytest tests/test_agent_runtime.py -q`
Expected: PASS，至少首次闭环相关测试通过。

- [ ] **Step 6: 提交本任务**

```bash
git add apps/api/app/agent/runtime.py apps/api/tests/test_agent_runtime.py
git commit -m "feat(api): add initial prd draft critic flow"
```

### Task 4: 实现 Critic 卡口与单问题队列

**Files:**
- Modify: `apps/api/app/agent/decision_engine.py`
- Modify: `apps/api/app/agent/runtime.py`
- Modify: `apps/api/tests/test_agent_runtime.py`

- [ ] **Step 1: 写失败测试，覆盖产品方案优先卡口**

```python
def test_critic_blocks_finalize_when_two_key_product_gaps_missing():
    state = {
        "workflow_stage": "refine_loop",
        "prd_draft": {
            "version": 1,
            "status": "draft_hypothesis",
            "sections": {},
            "assumptions": [],
            "missing_information": [
                "未明确核心文件格式",
                "未明确预览深度",
                "未明确权限边界",
            ],
            "critic_ready": True,
        },
    }

    result = run_agent(state, "继续")
    assert result.state_patch["critic_result"]["overall_verdict"] == "block"
    assert result.state_patch["finalization_ready"] is False
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd apps/api && uv run pytest tests/test_agent_runtime.py -q`
Expected: FAIL，当前未实现产品方案卡口。

- [ ] **Step 3: 在 `decision_engine.py` 中新增 Critic 规则函数**

```python
def build_critic_result(prd_draft: dict) -> CriticResult:
    major_gaps = collect_major_product_gaps(prd_draft)
    blocking_questions = build_blocking_questions(major_gaps)
    verdict = "block" if len(major_gaps) >= 2 else "revise"
    question_queue = blocking_questions or build_refine_questions(prd_draft)
    return CriticResult(...)
```

- [ ] **Step 4: 保证 `question_queue` 每次只取一个最高优先项输出**

```python
next_question = critic_result.question_queue[:1]
state_patch["critic_result"]["question_queue"] = critic_result.question_queue
```

- [ ] **Step 5: 运行 runtime 测试确认通过**

Run: `cd apps/api && uv run pytest tests/test_agent_runtime.py -q`
Expected: PASS

- [ ] **Step 6: 提交本任务**

```bash
git add apps/api/app/agent/decision_engine.py apps/api/app/agent/runtime.py apps/api/tests/test_agent_runtime.py
git commit -m "feat(api): add critic blocking rules"
```

### Task 5: 重写回复合同为“摘要 + verdict + 唯一下一问”

**Files:**
- Modify: `apps/api/app/agent/reply_composer.py`
- Modify: `apps/api/tests/test_agent_reply_composer.py`

- [ ] **Step 1: 写失败测试，锁定新回复合同**

```python
from app.agent.reply_composer import compose_reply


def test_compose_reply_outputs_single_question_from_critic_queue():
    decision = DummyDecision(
        prd_draft={"status": "draft_hypothesis"},
        critic_result={
            "overall_verdict": "block",
            "major_gaps": ["未明确文件格式"],
            "question_queue": ["第一版要支持哪些 3D/CAD 文件格式？", "是否需要标注？"],
        },
    )
    reply = compose_reply(decision)
    assert "当前 Critic 判断是" in reply
    assert "第一版要支持哪些 3D/CAD 文件格式？" in reply
    assert "是否需要标注？" not in reply
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd apps/api && uv run pytest tests/test_agent_reply_composer.py -q`
Expected: FAIL，当前回复仍是旧的判断/建议/确认模板。

- [ ] **Step 3: 用最小模板重写 `compose_reply`**

```python
def compose_reply(decision: TurnDecision) -> str:
    draft_summary = build_draft_summary(decision)
    critic_summary = build_critic_summary(decision)
    next_question = first_question(decision)
    return "\n\n".join([draft_summary, critic_summary, next_question])
```

- [ ] **Step 4: 移除旧模板对多建议、多确认项的强依赖**

```python
if critic_result.question_queue:
    question = critic_result.question_queue[0]
```

- [ ] **Step 5: 运行回复合同测试确认通过**

Run: `cd apps/api && uv run pytest tests/test_agent_reply_composer.py -q`
Expected: PASS

- [ ] **Step 6: 提交本任务**

```bash
git add apps/api/app/agent/reply_composer.py apps/api/tests/test_agent_reply_composer.py
git commit -m "feat(api): update reply contract for critic refine loop"
```

### Task 6: 接入消息服务持久化并保持 SSE 语义稳定

**Files:**
- Modify: `apps/api/app/services/messages.py`
- Modify: `apps/api/tests/test_messages_service.py`
- Modify: `apps/api/tests/test_messages_stream.py`

- [ ] **Step 1: 写失败测试，覆盖新状态字段持久化**

```python
def test_handle_user_message_persists_workflow_stage_and_critic_result(...):
    result = handle_user_message(...)
    latest_state = state_repository.get_latest_state(db, session_id)
    assert latest_state["workflow_stage"] == "refine_loop"
    assert latest_state["prd_draft"]["version"] == 1
    assert latest_state["critic_result"]["question_queue"]
```

- [ ] **Step 2: 写失败流测试，覆盖 assistant 回复包含唯一下一问**

```python
def test_message_stream_emits_reply_with_single_critic_question(...):
    ...
    assert "当前 Critic 判断是" in assistant_message.content
    assert assistant_message.content.count("？") == 1
```

- [ ] **Step 3: 运行消息服务与流测试确认失败**

Run: `cd apps/api && uv run pytest tests/test_messages_service.py tests/test_messages_stream.py -q`
Expected: FAIL，当前状态未持久化新字段，回复也未遵循新合同。

- [ ] **Step 4: 在 `messages.py` 合并新状态字段**

```python
def _build_decision_state_patch(turn_decision: object) -> dict:
    patch = ...
    patch["workflow_stage"] = getattr(turn_decision, "workflow_stage", "refine_loop")
    patch["idea_parse_result"] = getattr(turn_decision, "idea_parse_result", None)
    patch["prd_draft"] = getattr(turn_decision, "prd_draft", None)
    patch["critic_result"] = getattr(turn_decision, "critic_result", None)
    patch["finalization_ready"] = getattr(turn_decision, "finalization_ready", False)
    return patch
```

- [ ] **Step 5: 保持 reply version / regenerate 语义不变**

```python
# regenerate 仍然不推进 state_version / prd_snapshot
# 只新增 assistant reply version
```

- [ ] **Step 6: 运行消息服务与流测试确认通过**

Run: `cd apps/api && uv run pytest tests/test_messages_service.py tests/test_messages_stream.py -q`
Expected: PASS

- [ ] **Step 7: 提交本任务**

```bash
git add apps/api/app/services/messages.py apps/api/tests/test_messages_service.py apps/api/tests/test_messages_stream.py
git commit -m "feat(api): persist prd critic loop state"
```

### Task 7: 实现 refine 更新到 PRD v2

**Files:**
- Modify: `apps/api/app/agent/extractor.py`
- Modify: `apps/api/app/agent/runtime.py`
- Modify: `apps/api/tests/test_agent_runtime.py`
- Modify: `apps/api/tests/test_messages_service.py`

- [ ] **Step 1: 写失败测试，覆盖用户补充后版本递增**

```python
def test_run_agent_updates_prd_draft_to_v2_after_refine_answer():
    state = {
        "workflow_stage": "refine_loop",
        "prd_draft": {
            "version": 1,
            "status": "draft_hypothesis",
            "sections": {"positioning": {"content": "在线3D图纸预览平台"}},
            "assumptions": [],
            "missing_information": ["未明确核心文件格式"],
            "critic_ready": True,
        },
        "critic_result": {
            "overall_verdict": "block",
            "question_queue": ["第一版要支持哪些 3D/CAD 文件格式？"],
        },
    }

    result = run_agent(state, "第一版先支持 STEP 和 OBJ")
    assert result.state_patch["prd_draft"]["version"] == 2
    assert "STEP" in str(result.state_patch["prd_draft"]["sections"])
    assert result.state_patch["critic_result"]["question_queue"]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd apps/api && uv run pytest tests/test_agent_runtime.py tests/test_messages_service.py -q`
Expected: FAIL，当前 refine 不会更新草稿版本。

- [ ] **Step 3: 在 `extractor.py` 增加 refine 输入合并函数**

```python
def merge_refine_input_into_prd_draft(prd_draft: dict, critic_result: dict, user_input: str) -> dict:
    next_draft = deepcopy(prd_draft)
    next_draft["version"] += 1
    next_draft["status"] = "draft_refined"
    apply_answer_to_target_gap(next_draft, critic_result, user_input)
    return next_draft
```

- [ ] **Step 4: 在 `runtime.py` 中接入 `refine_loop -> critic_review`**

```python
if state.get("workflow_stage") == "refine_loop":
    next_draft = merge_refine_input_into_prd_draft(...)
    critic_result = build_critic_result(next_draft)
```

- [ ] **Step 5: 运行 refine 测试确认通过**

Run: `cd apps/api && uv run pytest tests/test_agent_runtime.py tests/test_messages_service.py -q`
Expected: PASS

- [ ] **Step 6: 提交本任务**

```bash
git add apps/api/app/agent/extractor.py apps/api/app/agent/runtime.py apps/api/tests/test_agent_runtime.py apps/api/tests/test_messages_service.py
git commit -m "feat(api): support refine draft iteration"
```

### Task 8: 做后端回归验证

**Files:**
- Test: `apps/api/tests`

- [ ] **Step 1: 运行核心闭环相关测试**

Run: `cd apps/api && uv run pytest tests/test_agent_types_contract.py tests/test_agent_understanding.py tests/test_agent_reply_composer.py tests/test_agent_runtime.py tests/test_messages_service.py tests/test_messages_stream.py -q`
Expected: PASS

- [ ] **Step 2: 运行后端回归测试**

Run: `cd apps/api && uv run pytest tests -q`
Expected: PASS

- [ ] **Step 3: 复查主验收样例**

验证输入：

```text
我想做一个在线 3D 图纸预览平台
```

检查点：

- 自动生成 `PRD v1`
- 自动执行 Critic
- 只追问一个问题
- 用户补充后能生成 `PRD v2`
- 缺口未补齐前 `finalization_ready = false`

- [ ] **Step 4: 提交回归与收尾**

```bash
git add apps/api
git commit -m "test(api): verify prd critic refine loop"
```
