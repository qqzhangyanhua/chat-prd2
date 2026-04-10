# PM Mentor Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the rule-based Agent state machine with an LLM-driven PM mentor that gives "observation + challenge + suggestion + question" per turn and updates the PRD intelligently.

**Architecture:** A thin Python orchestrator (`runtime.py`, ~80 lines) handles only three boundary conditions (PRD complete, no model config, errors). All reasoning is delegated to `pm_mentor.py`, which calls the LLM with structured context (conversation history + current PRD state) and parses a structured JSON output. A new `prd_updater.py` merges LLM-returned `prd_updates` into the PRD state.

**Tech Stack:** Python 3.12+, FastAPI, SQLAlchemy, httpx (already in use), pytest

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `apps/api/app/agent/types.py` | Add `PmMentorOutput` dataclass; update `WorkflowStage` |
| Create | `apps/api/app/agent/prd_updater.py` | Merge LLM prd_updates into PRD state |
| Modify | `apps/api/app/services/model_gateway.py` | Add `call_pm_mentor_llm()` |
| Create | `apps/api/app/agent/pm_mentor.py` | LLM PM Mentor: build context, call LLM, parse output, return AgentResult |
| Rewrite | `apps/api/app/agent/runtime.py` | Thin orchestrator: 3 boundary conditions → pm_mentor |
| Modify | `apps/api/app/services/message_preparation.py` | Pass `model_config` + `conversation_history` to `run_agent` |
| Delete | `apps/api/app/agent/decision_engine.py` | Replaced by LLM reasoning |
| Delete | `apps/api/app/agent/validation_flows.py` | Replaced by LLM reasoning |
| Delete | `apps/api/app/agent/initial_draft_flow.py` | Replaced by pm_mentor |
| Delete | `apps/api/app/agent/refine_loop_flow.py` | Replaced by pm_mentor |
| Delete | `apps/api/app/agent/understanding.py` | Replaced by pm_mentor |
| Delete | `apps/api/app/agent/suggestion_planner.py` | Replaced by pm_mentor |
| Delete | `apps/api/app/agent/reply_composer.py` | LLM now generates reply directly |
| Delete | `apps/api/app/agent/prompts.py` | Moved into pm_mentor system prompt |
| Create | `apps/api/tests/test_prd_updater.py` | Tests for prd_updater |
| Create | `apps/api/tests/test_pm_mentor.py` | Tests for pm_mentor |
| Modify | `apps/api/tests/test_agent_runtime.py` | Update for new runtime interface |

---

## Task 1: Add `PmMentorOutput` type and update `WorkflowStage`

**Files:**
- Modify: `apps/api/app/agent/types.py`

- [ ] **Step 1: Write the failing test**

```python
# apps/api/tests/test_agent_types_contract.py  (already exists — append this test)
def test_pm_mentor_output_dataclass():
    from app.agent.types import PmMentorOutput
    output = PmMentorOutput(
        observation="obs",
        challenge="ch",
        suggestion="sg",
        question="q?",
        reply="full reply",
        prd_updates={"target_user": {"content": "x", "status": "draft"}},
        confidence="medium",
        next_focus="problem",
    )
    assert output.observation == "obs"
    assert output.prd_updates["target_user"]["status"] == "draft"
    assert output.confidence == "medium"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/zhangyanhua/AI/chat-prd2 && python -m pytest apps/api/tests/test_agent_types_contract.py::test_pm_mentor_output_dataclass -v --tb=short
```
Expected: `FAILED` with `ImportError: cannot import name 'PmMentorOutput'`

- [ ] **Step 3: Add `PmMentorOutput` to `types.py`**

Open `apps/api/app/agent/types.py` and append after the `CriticResult` dataclass (after line 119):

```python
@dataclass(slots=True)
class PmMentorOutput:
    observation: str
    challenge: str
    suggestion: str
    question: str
    reply: str
    prd_updates: dict[str, dict[str, Any]]
    confidence: Literal["high", "medium", "low"]
    next_focus: str
```

Also update `WorkflowStage` (replace lines 21-27) to add `"completed"`:

```python
WorkflowStage = Literal[
    "idea_parser",
    "prd_draft",
    "critic_review",
    "refine_loop",
    "finalize",
    "completed",
]
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /Users/zhangyanhua/AI/chat-prd2 && python -m pytest apps/api/tests/test_agent_types_contract.py::test_pm_mentor_output_dataclass -v
```
Expected: `PASSED`

- [ ] **Step 5: Commit**

```bash
cd /Users/zhangyanhua/AI/chat-prd2 && git add apps/api/app/agent/types.py apps/api/tests/test_agent_types_contract.py && git commit -m "feat(agent): add PmMentorOutput type and completed WorkflowStage"
```

---

## Task 2: Create `prd_updater.py`

**Files:**
- Create: `apps/api/app/agent/prd_updater.py`
- Create: `apps/api/tests/test_prd_updater.py`

- [ ] **Step 1: Write the failing tests**

Create `apps/api/tests/test_prd_updater.py`:

```python
import pytest
from app.agent.prd_updater import merge_prd_updates, should_emit_prd_updated


def test_merge_creates_new_draft_section():
    current = {"sections": {}}
    updates = {"target_user": {"content": "小微企业主", "status": "draft"}}
    result = merge_prd_updates(current, updates)
    assert result["sections"]["target_user"]["content"] == "小微企业主"
    assert result["sections"]["target_user"]["status"] == "draft"


def test_merge_overwrites_existing_section():
    current = {"sections": {"target_user": {"content": "旧内容", "status": "draft"}}}
    updates = {"target_user": {"content": "新内容", "status": "confirmed"}}
    result = merge_prd_updates(current, updates)
    assert result["sections"]["target_user"]["content"] == "新内容"
    assert result["sections"]["target_user"]["status"] == "confirmed"


def test_merge_missing_status_preserves_old_content():
    current = {"sections": {"target_user": {"content": "已有内容", "status": "draft"}}}
    updates = {"target_user": {"content": "需要补充场景", "status": "missing"}}
    result = merge_prd_updates(current, updates)
    # 保留旧 content，只更新 status
    assert result["sections"]["target_user"]["content"] == "已有内容"
    assert result["sections"]["target_user"]["status"] == "missing"
    assert result["sections"]["target_user"]["missing_reason"] == "需要补充场景"


def test_merge_missing_status_no_old_section():
    current = {"sections": {}}
    updates = {"problem": {"content": "需要明确问题", "status": "missing"}}
    result = merge_prd_updates(current, updates)
    assert result["sections"]["problem"]["status"] == "missing"
    assert result["sections"]["problem"]["missing_reason"] == "需要明确问题"


def test_merge_empty_updates_returns_copy():
    current = {"sections": {"target_user": {"content": "x", "status": "draft"}}}
    result = merge_prd_updates(current, {})
    assert result == current
    assert result is not current  # deep copy


def test_merge_ignores_non_dict_update_values():
    current = {"sections": {}}
    updates = {"target_user": "invalid"}
    result = merge_prd_updates(current, updates)
    assert "target_user" not in result["sections"]


def test_should_emit_prd_updated_when_changed():
    old = {"sections": {}}
    new = {"sections": {"target_user": {"content": "x", "status": "draft"}}}
    assert should_emit_prd_updated(old, new) is True


def test_should_emit_prd_updated_when_unchanged():
    prd = {"sections": {"target_user": {"content": "x", "status": "draft"}}}
    assert should_emit_prd_updated(prd, prd) is False


def test_should_emit_prd_updated_equal_dicts():
    old = {"sections": {"x": {"content": "a"}}}
    new = {"sections": {"x": {"content": "a"}}}
    assert should_emit_prd_updated(old, new) is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/zhangyanhua/AI/chat-prd2 && python -m pytest apps/api/tests/test_prd_updater.py -v --tb=short
```
Expected: `ERROR` collecting (module not found)

- [ ] **Step 3: Create `prd_updater.py`**

Create `apps/api/app/agent/prd_updater.py`:

```python
from __future__ import annotations

from copy import deepcopy
from typing import Any


def merge_prd_updates(
    current_prd: dict[str, Any],
    prd_updates: dict[str, Any],
) -> dict[str, Any]:
    """把 LLM 返回的 prd_updates 合并进当前 PRD 状态。

    规则：
    - status confirmed/draft → 写入，覆盖旧内容
    - status missing → 保留旧 content，更新 status 和缺口描述
    - 无旧记录 → 新建 section
    - prd_updates 为空 {} → 返回原 PRD 的深拷贝，不触发变更
    - 非 dict 的 update value → 忽略
    """
    if not prd_updates:
        return deepcopy(current_prd)

    result = deepcopy(current_prd)
    sections = result.setdefault("sections", {})

    for key, update in prd_updates.items():
        if not isinstance(update, dict):
            continue

        status = update.get("status", "draft")
        content = update.get("content", "")

        if status == "missing":
            old = sections.get(key) or {}
            sections[key] = {
                **old,
                "status": "missing",
                "missing_reason": content,
            }
        else:
            sections[key] = {
                "content": content,
                "status": status,
                "title": update.get("title", key),
            }

    return result


def should_emit_prd_updated(old_prd: dict[str, Any], new_prd: dict[str, Any]) -> bool:
    """只要有任何 section 的 content 或 status 发生变化就返回 True。"""
    return old_prd != new_prd
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/zhangyanhua/AI/chat-prd2 && python -m pytest apps/api/tests/test_prd_updater.py -v
```
Expected: 9 tests `PASSED`

- [ ] **Step 5: Commit**

```bash
cd /Users/zhangyanhua/AI/chat-prd2 && git add apps/api/app/agent/prd_updater.py apps/api/tests/test_prd_updater.py && git commit -m "feat(agent): add prd_updater with merge and emit-check logic"
```

---

## Task 3: Add `call_pm_mentor_llm` to `model_gateway.py`

**Files:**
- Modify: `apps/api/app/services/model_gateway.py`
- Modify: `apps/api/tests/test_model_gateway.py`

- [ ] **Step 1: Write the failing test**

Append to `apps/api/tests/test_model_gateway.py`:

```python
def test_call_pm_mentor_llm_returns_parsed_dict(monkeypatch):
    import json
    import httpx
    from app.services.model_gateway import call_pm_mentor_llm

    fake_response_body = {
        "choices": [{
            "message": {
                "content": json.dumps({
                    "observation": "obs",
                    "challenge": "ch",
                    "suggestion": "sg",
                    "question": "q?",
                    "reply": "full reply",
                    "prd_updates": {},
                    "confidence": "medium",
                    "next_focus": "problem",
                })
            }
        }]
    }

    class FakeResponse:
        status_code = 200
        headers = {"content-type": "application/json"}
        def raise_for_status(self): pass
        def json(self): return fake_response_body

    monkeypatch.setattr(httpx, "post", lambda *a, **kw: FakeResponse())

    result = call_pm_mentor_llm(
        base_url="http://fake-api",
        api_key="test-key",
        model="gpt-4",
        system_prompt="你是PM导师",
        user_prompt='{"user_input": "我想做个工具"}',
    )
    assert result["observation"] == "obs"
    assert result["confidence"] == "medium"


def test_call_pm_mentor_llm_raises_on_timeout(monkeypatch):
    import httpx
    from app.services.model_gateway import call_pm_mentor_llm, ModelGatewayError

    def fake_post(*args, **kwargs):
        raise httpx.TimeoutException("timeout")

    monkeypatch.setattr(httpx, "post", fake_post)

    with pytest.raises(ModelGatewayError, match="超时"):
        call_pm_mentor_llm(
            base_url="http://fake-api",
            api_key="key",
            model="gpt-4",
            system_prompt="sys",
            user_prompt="usr",
        )
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/zhangyanhua/AI/chat-prd2 && python -m pytest apps/api/tests/test_model_gateway.py::test_call_pm_mentor_llm_returns_parsed_dict apps/api/tests/test_model_gateway.py::test_call_pm_mentor_llm_raises_on_timeout -v --tb=short
```
Expected: `FAILED` with `ImportError: cannot import name 'call_pm_mentor_llm'`

- [ ] **Step 3: Add `call_pm_mentor_llm` to `model_gateway.py`**

Append to the end of `apps/api/app/services/model_gateway.py`:

```python
def call_pm_mentor_llm(
    base_url: str,
    api_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
) -> dict[str, Any]:
    """调用 LLM 获取 PM Mentor 结构化 JSON 输出。使用 response_format json_object。"""
    url = _build_chat_completions_url(base_url)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "response_format": {"type": "json_object"},
    }

    try:
        response = httpx.post(url, headers=headers, json=payload, timeout=60.0)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        _raise_for_gateway_http_error(exc, url)
    except httpx.TimeoutException as exc:
        logger.warning("PM Mentor LLM 调用超时: url=%s error=%s", url, exc)
        raise ModelGatewayError("PM Mentor LLM 调用超时") from exc
    except httpx.RequestError as exc:
        logger.warning("PM Mentor LLM 网络异常: url=%s error=%s", url, exc)
        raise ModelGatewayError("PM Mentor LLM 网络异常") from exc

    try:
        body = response.json()
    except ValueError as exc:
        _raise_for_non_json_response(response, url, exc)

    return _extract_json_object_content(body)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/zhangyanhua/AI/chat-prd2 && python -m pytest apps/api/tests/test_model_gateway.py::test_call_pm_mentor_llm_returns_parsed_dict apps/api/tests/test_model_gateway.py::test_call_pm_mentor_llm_raises_on_timeout -v
```
Expected: 2 tests `PASSED`

- [ ] **Step 5: Commit**

```bash
cd /Users/zhangyanhua/AI/chat-prd2 && git add apps/api/app/services/model_gateway.py apps/api/tests/test_model_gateway.py && git commit -m "feat(gateway): add call_pm_mentor_llm for structured JSON output"
```

---

## Task 4: Create `pm_mentor.py`

**Files:**
- Create: `apps/api/app/agent/pm_mentor.py`
- Create: `apps/api/tests/test_pm_mentor.py`

- [ ] **Step 1: Write the failing tests**

Create `apps/api/tests/test_pm_mentor.py`:

```python
import json
import pytest
from unittest.mock import MagicMock, patch


def test_parse_pm_mentor_output_full():
    from app.agent.pm_mentor import parse_pm_mentor_output
    raw = {
        "observation": "用户想做B2B SaaS",
        "challenge": "决策者还是执行者？",
        "suggestion": "先定义购买决策链",
        "question": "谁最终付费：HR总监还是员工？",
        "reply": "完整回复文本",
        "prd_updates": {"target_user": {"content": "HR总监", "status": "draft"}},
        "confidence": "medium",
        "next_focus": "target_user",
    }
    result = parse_pm_mentor_output(raw)
    assert result.observation == "用户想做B2B SaaS"
    assert result.prd_updates["target_user"]["status"] == "draft"
    assert result.confidence == "medium"
    assert result.reply == "完整回复文本"


def test_parse_pm_mentor_output_missing_reply_uses_fallback():
    from app.agent.pm_mentor import parse_pm_mentor_output
    raw = {
        "observation": "obs",
        "challenge": "ch",
        "suggestion": "sg",
        "question": "q?",
        "prd_updates": {},
        "confidence": "low",
        "next_focus": "problem",
        # "reply" is intentionally missing
    }
    result = parse_pm_mentor_output(raw)
    assert "obs" in result.reply
    assert "q?" in result.reply


def test_parse_pm_mentor_output_invalid_confidence_defaults_to_medium():
    from app.agent.pm_mentor import parse_pm_mentor_output
    raw = {
        "observation": "x", "challenge": "y", "suggestion": "z",
        "question": "q?", "reply": "r",
        "prd_updates": {}, "confidence": "unknown_value", "next_focus": "problem",
    }
    result = parse_pm_mentor_output(raw)
    assert result.confidence == "medium"


def test_build_user_prompt_includes_prd_sections():
    from app.agent.pm_mentor import _build_user_prompt
    state = {
        "prd_snapshot": {
            "sections": {"target_user": {"content": "HR总监", "status": "draft"}}
        },
        "iteration": 3,
    }
    prompt = _build_user_prompt(state, "我想加一个功能")
    data = json.loads(prompt)
    assert data["turn_count"] == 3
    assert "target_user" in data["current_prd"]["sections"]
    assert data["user_input"] == "我想加一个功能"


def test_build_user_prompt_missing_prd_snapshot():
    from app.agent.pm_mentor import _build_user_prompt
    state = {}
    prompt = _build_user_prompt(state, "测试")
    data = json.loads(prompt)
    assert data["current_prd"]["sections"] == {}
    assert data["turn_count"] == 0


def test_run_pm_mentor_calls_llm_and_returns_agent_result():
    from app.agent.pm_mentor import run_pm_mentor
    from app.agent.types import AgentResult

    fake_llm_output = {
        "observation": "用户想做任务管理工具",
        "challenge": "目标用户是个人还是团队？",
        "suggestion": "先锁定个人用户再扩展",
        "question": "你最想先服务的是个人用户还是小团队？",
        "reply": "你的想法很有意思。目标用户是个人还是团队？",
        "prd_updates": {"target_user": {"content": "待确认", "status": "missing"}},
        "confidence": "medium",
        "next_focus": "target_user",
    }

    mock_config = MagicMock()
    mock_config.base_url = "http://fake"
    mock_config.api_key = "key"
    mock_config.model = "gpt-4"

    with patch("app.agent.pm_mentor.call_pm_mentor_llm", return_value=fake_llm_output):
        result = run_pm_mentor({}, "我想做个任务管理工具", mock_config)

    assert isinstance(result, AgentResult)
    assert result.reply_mode == "local"
    assert "任务管理工具" in result.reply or "target_user" in result.reply or result.reply
    assert result.turn_decision is not None
    assert result.state_patch.get("iteration") == 1


def test_run_pm_mentor_llm_failure_returns_fallback():
    from app.agent.pm_mentor import run_pm_mentor
    from app.services.model_gateway import ModelGatewayError

    mock_config = MagicMock()
    mock_config.base_url = "http://fake"
    mock_config.api_key = "key"
    mock_config.model = "gpt-4"

    with patch("app.agent.pm_mentor.call_pm_mentor_llm", side_effect=ModelGatewayError("timeout")):
        result = run_pm_mentor({}, "测试", mock_config)

    assert result.reply_mode == "local"
    assert result.reply  # fallback reply is non-empty
    assert result.turn_decision is not None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/zhangyanhua/AI/chat-prd2 && python -m pytest apps/api/tests/test_pm_mentor.py -v --tb=short
```
Expected: `ERROR` collecting (module not found)

- [ ] **Step 3: Create `pm_mentor.py`**

Create `apps/api/app/agent/pm_mentor.py`:

```python
from __future__ import annotations

import json
import logging
from typing import Any

from app.agent.prd_updater import merge_prd_updates
from app.agent.types import AgentResult, NextAction, PmMentorOutput, TurnDecision
from app.services.model_gateway import ModelGatewayError, call_pm_mentor_llm

logger = logging.getLogger(__name__)

MAX_HISTORY_TURNS = 10

PM_MENTOR_SYSTEM_PROMPT = """你是一位经验丰富的 AI 产品联合创始人（PM 导师风格）。
你的职责是帮助用户把一个模糊的想法，逐步打磨成一份清晰可执行的 PRD。

【你的工作方式】
每轮对话，你必须做四件事：
1. Observation  — 指出用户本轮输入中最关键的信息或隐含假设
2. Challenge    — 挑战一个具体的假设或盲点（不能泛泛追问）
3. Suggestion   — 给出一个具体的 PM 视角建议或框架
4. Question     — 只问一个最关键的问题，推动对话向前

【PRD 更新规则】
- 信息具体（有场景、有角色、有边界）→ 写入对应 section，status: "draft"
- 用户明确确认 → status: "confirmed"
- 信息模糊、矛盾或不完整 → status: "missing"，content 写明缺什么
- 本轮没有新信息 → prd_updates 返回空对象 {}

【禁止行为】
- question 里不能同时问多个问题
- observation 不能重复上轮已知信息
- challenge 必须指向具体假设，不能泛泛质疑
- 信息不足时不能强行推进到下一个 section

【输出格式】
严格返回 JSON，包含以下字段：
observation, challenge, suggestion, question, reply, prd_updates, confidence, next_focus"""


def _build_conversation_history(conversation_history: list[dict[str, str]] | None) -> list[dict[str, str]]:
    if not conversation_history:
        return []
    filtered = [m for m in conversation_history if m.get("role") in {"user", "assistant"}]
    return filtered[-(MAX_HISTORY_TURNS * 2):]


def _build_current_prd(state: dict[str, Any]) -> dict[str, Any]:
    prd_snapshot = state.get("prd_snapshot") or {}
    sections = prd_snapshot.get("sections") or {}
    missing = [
        key for key, value in sections.items()
        if isinstance(value, dict) and value.get("status") == "missing"
    ]
    return {"sections": sections, "missing": missing}


def _build_user_prompt(
    state: dict[str, Any],
    user_input: str,
    conversation_history: list[dict[str, str]] | None = None,
) -> str:
    history = _build_conversation_history(conversation_history)
    current_prd = _build_current_prd(state)
    turn_count = int(state.get("iteration") or 0)
    return json.dumps(
        {
            "current_prd": current_prd,
            "conversation_history": history,
            "turn_count": turn_count,
            "user_input": user_input,
        },
        ensure_ascii=False,
    )


def parse_pm_mentor_output(raw: dict[str, Any]) -> PmMentorOutput:
    observation = raw.get("observation") or ""
    challenge = raw.get("challenge") or ""
    suggestion = raw.get("suggestion") or ""
    question = raw.get("question") or ""
    prd_updates = raw.get("prd_updates") or {}
    confidence_raw = raw.get("confidence") or "medium"
    confidence = confidence_raw if confidence_raw in {"high", "medium", "low"} else "medium"
    next_focus = raw.get("next_focus") or "problem"

    reply = raw.get("reply") or ""
    if not reply.strip():
        parts = [p for p in [observation, challenge, suggestion, question] if p.strip()]
        reply = "\n\n".join(parts) or "我需要更多信息才能继续推进。"

    return PmMentorOutput(
        observation=observation,
        challenge=challenge,
        suggestion=suggestion,
        question=question,
        reply=reply,
        prd_updates=prd_updates if isinstance(prd_updates, dict) else {},
        confidence=confidence,
        next_focus=next_focus,
    )


def run_pm_mentor(
    state: dict[str, Any],
    user_input: str,
    model_config: Any,
    *,
    conversation_history: list[dict[str, str]] | None = None,
) -> AgentResult:
    """调用 LLM PM Mentor，返回 AgentResult（reply_mode="local"）。"""
    user_prompt = _build_user_prompt(state, user_input, conversation_history)

    raw: dict[str, Any] = {}
    try:
        raw = call_pm_mentor_llm(
            base_url=model_config.base_url,
            api_key=model_config.api_key,
            model=model_config.model,
            system_prompt=PM_MENTOR_SYSTEM_PROMPT,
            user_prompt=user_prompt,
        )
    except ModelGatewayError:
        logger.warning("PM Mentor LLM 调用失败，使用降级回复")

    mentor_output = parse_pm_mentor_output(raw)

    prd_patch = mentor_output.prd_updates

    state_patch: dict[str, Any] = {
        "iteration": int(state.get("iteration") or 0) + 1,
        "stage_hint": mentor_output.next_focus,
        "conversation_strategy": "clarify",
    }
    if mentor_output.next_focus == "done":
        state_patch["workflow_stage"] = "completed"

    turn_decision = TurnDecision(
        phase=mentor_output.next_focus,
        phase_goal=mentor_output.question or None,
        understanding={
            "summary": mentor_output.observation,
            "candidate_updates": prd_patch,
            "ambiguous_points": [],
        },
        assumptions=[],
        gaps=[],
        challenges=[mentor_output.challenge] if mentor_output.challenge else [],
        pm_risk_flags=[],
        next_move="probe_for_specificity",
        suggestions=[],
        recommendation=None,
        reply_brief={"focus": mentor_output.next_focus, "must_include": []},
        state_patch=state_patch,
        prd_patch=prd_patch,
        needs_confirmation=[],
        confidence=mentor_output.confidence,
        strategy_reason=mentor_output.suggestion or None,
        next_best_questions=[mentor_output.question] if mentor_output.question else [],
        conversation_strategy="clarify",
    )

    return AgentResult(
        reply=mentor_output.reply,
        action=NextAction(
            action="probe_deeper",
            target=None,
            reason=mentor_output.question or "继续推进 PRD 补充",
        ),
        reply_mode="local",
        state_patch=state_patch,
        prd_patch=prd_patch,
        decision_log=[],
        understanding=None,
        turn_decision=turn_decision,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/zhangyanhua/AI/chat-prd2 && python -m pytest apps/api/tests/test_pm_mentor.py -v
```
Expected: 7 tests `PASSED`

- [ ] **Step 5: Commit**

```bash
cd /Users/zhangyanhua/AI/chat-prd2 && git add apps/api/app/agent/pm_mentor.py apps/api/tests/test_pm_mentor.py && git commit -m "feat(agent): add pm_mentor LLM-driven PM mentor core"
```

---

## Task 5: Rewrite `runtime.py` as thin orchestrator

**Files:**
- Rewrite: `apps/api/app/agent/runtime.py`
- Modify: `apps/api/tests/test_agent_runtime.py`

- [ ] **Step 1: Write the failing tests**

Append to `apps/api/tests/test_agent_runtime.py`:

```python
def test_run_agent_completed_stage_returns_local_reply():
    from app.agent.runtime import run_agent
    state = {"workflow_stage": "completed"}
    result = run_agent(state, "继续")
    assert result.reply_mode == "local"
    assert result.turn_decision is not None
    assert result.turn_decision.phase == "completed"


def test_run_agent_no_model_config_returns_fallback():
    from app.agent.runtime import run_agent
    state = {}
    result = run_agent(state, "我想做一个应用", model_config=None)
    assert result.reply_mode == "local"
    assert result.turn_decision is not None
    assert result.reply  # non-empty fallback message


def test_run_agent_delegates_to_pm_mentor_when_model_config_given():
    from unittest.mock import MagicMock, patch
    from app.agent.runtime import run_agent
    from app.agent.types import AgentResult, NextAction, TurnDecision

    mock_config = MagicMock()
    mock_td = TurnDecision(
        phase="problem", phase_goal="q?",
        understanding={"summary": "x", "candidate_updates": {}, "ambiguous_points": []},
        assumptions=[], gaps=[], challenges=[], pm_risk_flags=[],
        next_move="probe_for_specificity", suggestions=[], recommendation=None,
        reply_brief={}, state_patch={}, prd_patch={}, needs_confirmation=[],
        confidence="medium", conversation_strategy="clarify",
    )
    mock_result = AgentResult(
        reply="mentor reply",
        action=NextAction(action="probe_deeper", target=None, reason="test"),
        reply_mode="local",
        turn_decision=mock_td,
    )

    with patch("app.agent.pm_mentor.run_pm_mentor", return_value=mock_result) as mock_pm:
        result = run_agent({}, "hello", model_config=mock_config)
        mock_pm.assert_called_once()

    assert result.reply == "mentor reply"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/zhangyanhua/AI/chat-prd2 && python -m pytest apps/api/tests/test_agent_runtime.py::test_run_agent_completed_stage_returns_local_reply apps/api/tests/test_agent_runtime.py::test_run_agent_no_model_config_returns_fallback apps/api/tests/test_agent_runtime.py::test_run_agent_delegates_to_pm_mentor_when_model_config_given -v --tb=short
```
Expected: `FAILED` (signature mismatch or import errors)

- [ ] **Step 3: Rewrite `runtime.py`**

Replace the entire content of `apps/api/app/agent/runtime.py` with:

```python
from __future__ import annotations

from typing import Any

from app.agent.types import AgentResult, NextAction, TurnDecision


def _build_completed_result(state: dict[str, Any]) -> AgentResult:
    turn_decision = TurnDecision(
        phase="completed",
        phase_goal=None,
        understanding={
            "summary": "PRD 已完成，可以导出或继续修改。",
            "candidate_updates": {},
            "ambiguous_points": [],
        },
        assumptions=[],
        gaps=[],
        challenges=[],
        pm_risk_flags=[],
        next_move="summarize_and_confirm",
        suggestions=[],
        recommendation=None,
        reply_brief={"focus": "completed", "must_include": []},
        state_patch={},
        prd_patch={},
        needs_confirmation=[],
        confidence="high",
        strategy_reason=None,
        next_best_questions=[],
        conversation_strategy="confirm",
    )
    return AgentResult(
        reply="PRD 已完成。你可以导出 PRD，或者继续告诉我需要修改的地方。",
        action=NextAction(action="summarize_understanding", target=None, reason="PRD 已完成"),
        reply_mode="local",
        state_patch={},
        prd_patch={},
        decision_log=[],
        understanding=None,
        turn_decision=turn_decision,
    )


def _build_fallback_result(state: dict[str, Any], user_input: str) -> AgentResult:
    turn_decision = TurnDecision(
        phase="error",
        phase_goal=None,
        understanding={
            "summary": "模型配置不可用，使用降级回复。",
            "candidate_updates": {},
            "ambiguous_points": [],
        },
        assumptions=[],
        gaps=[],
        challenges=[],
        pm_risk_flags=[],
        next_move="probe_for_specificity",
        suggestions=[],
        recommendation=None,
        reply_brief={"focus": "fallback", "must_include": []},
        state_patch={},
        prd_patch={},
        needs_confirmation=[],
        confidence="low",
        strategy_reason=None,
        next_best_questions=[],
        conversation_strategy="clarify",
    )
    return AgentResult(
        reply="我现在暂时无法访问模型，请稍后重试或检查模型配置。",
        action=NextAction(action="probe_deeper", target=None, reason="模型不可用"),
        reply_mode="local",
        state_patch={},
        prd_patch={},
        decision_log=[],
        understanding=None,
        turn_decision=turn_decision,
    )


def run_agent(
    state: dict[str, Any],
    user_input: str,
    model_result: Any = None,
    *,
    model_config: Any = None,
    conversation_history: list[dict[str, str]] | None = None,
) -> AgentResult:
    """Agent 主入口（瘦编排层）。

    处理三个边界条件，其余全部交给 PM Mentor LLM：
    1. workflow_stage == "completed" → 直接返回完成回复
    2. model_config is None → 降级本地回复
    3. 其余 → run_pm_mentor
    """
    if state.get("workflow_stage") == "completed":
        return _build_completed_result(state)

    if model_config is None:
        return _build_fallback_result(state, user_input)

    from app.agent.pm_mentor import run_pm_mentor
    return run_pm_mentor(
        state,
        user_input,
        model_config,
        conversation_history=conversation_history,
    )
```

- [ ] **Step 4: Run the new tests**

```bash
cd /Users/zhangyanhua/AI/chat-prd2 && python -m pytest apps/api/tests/test_agent_runtime.py::test_run_agent_completed_stage_returns_local_reply apps/api/tests/test_agent_runtime.py::test_run_agent_no_model_config_returns_fallback apps/api/tests/test_agent_runtime.py::test_run_agent_delegates_to_pm_mentor_when_model_config_given -v
```
Expected: 3 tests `PASSED`

- [ ] **Step 5: Run full test suite to check for regressions**

```bash
cd /Users/zhangyanhua/AI/chat-prd2 && python -m pytest apps/api/tests/ -v --tb=short -q 2>&1 | tail -30
```
Expected: most tests pass. Tests that mock the old agent paths (validation_flows, decision_engine etc.) may fail — those will be cleaned up in Task 7.

- [ ] **Step 6: Commit**

```bash
cd /Users/zhangyanhua/AI/chat-prd2 && git add apps/api/app/agent/runtime.py apps/api/tests/test_agent_runtime.py && git commit -m "feat(agent): replace runtime state machine with thin pm_mentor orchestrator"
```

---

## Task 6: Update `message_preparation.py` to pass `model_config` and `conversation_history`

**Files:**
- Modify: `apps/api/app/services/message_preparation.py`

- [ ] **Step 1: Update `prepare_message_stream`**

In `apps/api/app/services/message_preparation.py`, find the `prepare_message_stream` function and replace the section from `state = state_repository.get_latest_state(...)` through `db.commit()` with:

```python
        state = state_repository.get_latest_state(db, session_id)

        # 在保存用户消息之前构建对话历史（不含当前用户输入）
        gateway_messages = build_gateway_messages(db, session_id)
        conversation_history = [m for m in gateway_messages if m.get("role") != "system"]

        model_extraction_result = resolve_model_extraction_result_fn(state, content, model_config)
        agent_result = run_agent_fn(
            state,
            content,
            model_result=model_extraction_result,
            model_config=model_config,
            conversation_history=conversation_history,
        )
        turn_decision = require_turn_decision_fn(agent_result)
        if agent_result.reply_mode == "local":
            reply_stream = LocalReplyStream(agent_result.reply)
        else:
            reply_stream = open_reply_stream_fn(
                base_url=model_config.base_url,
                api_key=model_config.api_key,
                model=model_config.model,
                messages=gateway_messages,
            )
        db.commit()
```

Note: The call to `build_gateway_messages` is now before `db.commit()` (inside the try block), and `gateway_messages` is reused both for `conversation_history` and the fallback `open_reply_stream` call.

- [ ] **Step 2: Update `prepare_regenerate_stream`**

In the same file, find `prepare_regenerate_stream` and replace the section from `state = state_repository.get_latest_state(...)` through `reply_stream = open_reply_stream_fn(...)` with:

```python
    try:
        state = state_repository.get_latest_state(db, session_id)
        gateway_messages = build_gateway_messages_for_regenerate(db, session_id, user_message_id)
        conversation_history = [m for m in gateway_messages if m.get("role") != "system"]

        agent_result = run_agent_fn(
            state,
            user_message.content,
            model_config=model_config,
            conversation_history=conversation_history,
        )
        turn_decision = require_turn_decision_fn(agent_result)
        reply_stream = open_reply_stream_fn(
            base_url=model_config.base_url,
            api_key=model_config.api_key,
            model=model_config.model,
            messages=gateway_messages,
        )
```

- [ ] **Step 3: Run the messages-related tests**

```bash
cd /Users/zhangyanhua/AI/chat-prd2 && python -m pytest apps/api/tests/test_messages_stream.py apps/api/tests/test_messages_service.py apps/api/tests/test_message_pipeline_modules.py apps/api/tests/test_message_service_modules.py -v --tb=short -q 2>&1 | tail -30
```
Expected: pass (these tests mock `run_agent_fn`, so they're unaffected by the new kwargs)

- [ ] **Step 4: Commit**

```bash
cd /Users/zhangyanhua/AI/chat-prd2 && git add apps/api/app/services/message_preparation.py && git commit -m "feat(services): pass model_config and conversation_history to run_agent"
```

---

## Task 7: Delete old agent files and clean up tests

**Files:**
- Delete: 8 old agent files
- Modify: test files that import deleted modules

- [ ] **Step 1: Check which test files import the modules being deleted**

```bash
cd /Users/zhangyanhua/AI/chat-prd2 && grep -rl "decision_engine\|validation_flows\|initial_draft_flow\|refine_loop_flow\|understanding\|suggestion_planner\|reply_composer\|from app.agent.prompts" apps/api/tests/
```

- [ ] **Step 2: Run the full test suite and capture failing tests**

```bash
cd /Users/zhangyanhua/AI/chat-prd2 && python -m pytest apps/api/tests/ -q --tb=line 2>&1 | grep -E "FAILED|ERROR" | head -40
```

Note the failing tests. These are tests for modules being deleted — they should be removed along with the source files.

- [ ] **Step 3: Delete old agent source files**

```bash
cd /Users/zhangyanhua/AI/chat-prd2 && rm \
  apps/api/app/agent/decision_engine.py \
  apps/api/app/agent/validation_flows.py \
  apps/api/app/agent/initial_draft_flow.py \
  apps/api/app/agent/refine_loop_flow.py \
  apps/api/app/agent/understanding.py \
  apps/api/app/agent/suggestion_planner.py \
  apps/api/app/agent/reply_composer.py \
  apps/api/app/agent/prompts.py
```

- [ ] **Step 4: Delete the corresponding old test files**

```bash
cd /Users/zhangyanhua/AI/chat-prd2 && rm -f \
  apps/api/tests/test_agent_decision_engine.py \
  apps/api/tests/test_agent_reply_composer.py \
  apps/api/tests/test_agent_understanding.py \
  apps/api/tests/test_agent_suggestion_planner.py \
  apps/api/tests/test_agent_initial_draft_flow.py \
  apps/api/tests/test_agent_refine_loop_flow.py \
  apps/api/tests/test_agent_finalize_flow.py
```

- [ ] **Step 5: Remove dead imports from `extractor.py`**

Open `apps/api/app/agent/extractor.py`. Remove any imports or functions that are only used by the deleted modules (check with grep first):

```bash
cd /Users/zhangyanhua/AI/chat-prd2 && grep -n "first_missing_section\|build_rule_extraction_result\|choose_extraction_result\|merge_refine_input\|normalize_model_extraction_result\|should_capture\|is_missing\|SECTION_TITLES\|NEXT_STAGE_HINTS" apps/api/app/agent/extractor.py
```

Keep functions still used by `message_preparation.py` (`normalize_model_extraction_result`, `first_missing_section`). Remove unused ones. Run `grep` on `apps/api/` to confirm before removing each.

- [ ] **Step 6: Run full test suite**

```bash
cd /Users/zhangyanhua/AI/chat-prd2 && python -m pytest apps/api/tests/ -v --tb=short -q 2>&1 | tail -20
```
Expected: all tests pass. If any import errors remain, trace and fix the import.

- [ ] **Step 7: Final commit**

```bash
cd /Users/zhangyanhua/AI/chat-prd2 && git add -A && git commit -m "refactor(agent): remove rule-based modules replaced by pm_mentor"
```

---

## Self-Review Checklist

- [x] **Spec coverage:** All 5 spec sections covered:
  - Section 1 (Architecture change) → Tasks 5, 7
  - Section 2 (LLM I/O contract) → Tasks 1, 3, 4
  - Section 3 (Thin orchestrator + PRD update) → Tasks 2, 5, 6
  - Section 4 (PM Mentor prompt) → Task 4 (`PM_MENTOR_SYSTEM_PROMPT`)
  - Section 5 (Error handling + testing) → Tasks 2-5 (tests), Task 4 (LLM failure fallback)
- [x] **No placeholders:** All code blocks are complete
- [x] **Type consistency:** `PmMentorOutput` defined in Task 1, used in Task 4. `run_agent` new kwargs used consistently in Tasks 5 and 6. `conversation_history` parameter passes `list[dict[str, str]] | None` throughout.
- [x] **Migration safety:** Old `runtime.py` code replaced in Task 5; callers updated in Task 6; old files deleted only in Task 7 after tests pass.
