# Workspace Mandatory ABCD Guidance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让工作台 assistant 每一轮都稳定输出动态 `A/B/C/D` 引导项与固定“自由补充”入口，并在模型失约时由后端自动重试和兜底补齐。

**Architecture:** 继续沿用现有 `pm_mentor -> TurnDecision -> session snapshot -> workspace store -> assistant-turn-card` 链路，不新增第二套协议。后端负责把“每轮固定四项”做成强契约并在失败时自动补救，前端只负责展示、预填输入框和自由补充聚焦，不自行生成语义内容。

**Tech Stack:** Python, FastAPI, pytest, TypeScript, React 19, Next.js 15, Vitest, Testing Library

---

## 文件映射

### 后端核心

- `apps/api/app/agent/pm_mentor.py`
  - 收紧 `suggestions` 输出契约为固定 4 项
  - 增加 suggestion 质量校验
  - 增加“补救生成一次 + 程序化最终兜底”链路
- `apps/api/app/agent/runtime.py`
  - 统一 `greeting` / `completed` / `fallback` 三个本地分支的 4 项选项输出
- `apps/api/app/agent/types.py`
  - 如有必要，补强 `PmMentorOutput` / `TurnDecision` 的约束说明，避免实现层散落魔法值
- `apps/api/app/services/sessions.py`
  - 确认快照 meta 始终稳定透传 suggestion options，前端可直接渲染 `A/B/C/D`

### 后端测试

- `apps/api/tests/test_pm_mentor.py`
  - 锁定 4 项 suggestions、补救请求、最终兜底
- `apps/api/tests/test_agent_runtime.py`
  - 锁定 `greeting` / `completed` / `fallback` 三个本地分支也必须返回 4 项
- `apps/api/tests/test_messages_service.py`
  - 锁定消息服务和快照透传不会丢失结构化选项
- `apps/api/tests/test_sessions.py`
  - 如有必要，锁定 `decision_sections.next_step.meta.suggestion_options` 的归一化行为

### 前端核心

- `apps/web/src/components/workspace/assistant-turn-card.tsx`
  - 固定展示 4 个 `A/B/C/D` 和“自由补充”
- `apps/web/src/components/workspace/action-options.tsx`
  - 继续承载 `A/B/C/D` 卡片，但按固定四项常态来渲染
- `apps/web/src/components/workspace/conversation-panel.tsx`
  - 连接“点击建议预填输入框”和“点击自由补充聚焦输入框”的交互
- `apps/web/src/components/workspace/composer.tsx`
  - 暴露输入框 ref 或 focus 能力给上层，支持自由补充聚焦

### 前端测试

- `apps/web/src/test/assistant-turn-card.test.tsx`
  - 锁定固定 `A/B/C/D` 与“自由补充”渲染
- `apps/web/src/test/workspace-composer.test.tsx`
  - 锁定点击建议只预填不发送、点击自由补充聚焦输入框
- `apps/web/src/test/workspace-store.test.ts`
  - 如 store 解析逻辑需要轻调，补快照归一化断言

---

### Task 1: 先写后端红灯测试，锁定“四项必有”契约

**Files:**
- Modify: `apps/api/tests/test_pm_mentor.py`
- Modify: `apps/api/tests/test_agent_runtime.py`
- Test: `apps/api/tests/test_pm_mentor.py`
- Test: `apps/api/tests/test_agent_runtime.py`

- [ ] **Step 1: 在 `test_pm_mentor.py` 新增失败测试，要求主链路最终总是返回 4 个 suggestions**

```python
def test_run_pm_mentor_always_returns_four_guided_suggestions():
    result = run_pm_mentor(state, "我有个产品想法", mock_config)
    assert result.turn_decision is not None
    assert len(result.turn_decision.suggestions) == 4
    assert all(item.content.strip() for item in result.turn_decision.suggestions)
```

- [ ] **Step 2: 新增失败测试，模拟 LLM 首轮 suggestions 不足 4 项，断言会触发一次补救请求**

```python
with patch("app.agent.pm_mentor.call_pm_mentor_llm", side_effect=[bad_payload, repaired_payload]) as mock_llm:
    result = run_pm_mentor(state, user_input, mock_config)
assert mock_llm.call_count == 2
assert len(result.turn_decision.suggestions) == 4
```

- [ ] **Step 3: 新增失败测试，模拟两次 LLM 都失约，断言程序化兜底仍补齐 4 项**

```python
with patch("app.agent.pm_mentor.call_pm_mentor_llm", return_value={"reply": "正文", "suggestions": []}):
    result = run_pm_mentor(state, "我还没想清楚", mock_config)
assert len(result.turn_decision.suggestions) == 4
assert any("我直接补充" in item.content or "我直接补充" in item.label for item in result.turn_decision.suggestions)
```

- [ ] **Step 4: 新增失败测试，要求 suggestions 的 `content` 必须是用户可直接发送的完整句子，不允许退化成标签**

```python
assert all(len(item.content) >= 8 for item in result.turn_decision.suggestions)
assert all("先聊" in item.content or "我想" in item.content or "我先" in item.content for item in result.turn_decision.suggestions)
```

- [ ] **Step 5: 在 `test_agent_runtime.py` 新增失败测试，锁定 `greeting` / `completed` / `fallback` 也必须返回 4 项**

```python
result = run_agent({"iteration": 0}, "你好", model_config=MagicMock())
assert len(result.turn_decision.suggestions) == 4
```

- [ ] **Step 6: 运行聚焦测试，确认先失败**

Run: `PYTHONPATH=apps/api uv run pytest apps/api/tests/test_pm_mentor.py apps/api/tests/test_agent_runtime.py -q`

Expected: 至少 1 个 FAIL，失败点集中在 suggestions 数量、补救重试缺失或本地分支仍只返回 3 项。

- [ ] **Step 7: 提交测试脚手架**

```bash
git add apps/api/tests/test_pm_mentor.py apps/api/tests/test_agent_runtime.py
git commit -m "test(api): lock mandatory abcd guidance contract"
```

---

### Task 2: 实现后端强契约、补救生成与最终兜底

**Files:**
- Modify: `apps/api/app/agent/pm_mentor.py`
- Modify: `apps/api/app/agent/runtime.py`
- Modify: `apps/api/app/agent/types.py`
- Test: `apps/api/tests/test_pm_mentor.py`
- Test: `apps/api/tests/test_agent_runtime.py`

- [ ] **Step 1: 在 `pm_mentor.py` 提炼 suggestion 校验函数，明确“必须正好 4 项”的标准**

```python
def _validate_guided_suggestions(items: list[Suggestion]) -> tuple[bool, str | None]:
    if len(items) != 4:
        return False, "count"
    if any(not item.content.strip() for item in items):
        return False, "empty-content"
    if len({item.content for item in items}) != 4:
        return False, "duplicate-content"
    return True, None
```

- [ ] **Step 2: 增加“补救生成一次”的专用 prompt 生成器，只重写 suggestions，不改正文**

```python
def _build_suggestion_repair_prompt(...):
    return {
        "reply": original_reply,
        "invalid_suggestions": [...],
        "required_count": 4,
    }
```

- [ ] **Step 3: 在 `run_pm_mentor()` 中接入双阶段流程：首轮解析 -> 校验失败 -> 补救请求 -> 再校验**

```python
raw = call_pm_mentor_llm(...)
mentor_output = parse_pm_mentor_output(raw)
if suggestions_invalid:
    repaired_raw = call_pm_mentor_llm(...)
    mentor_output = merge_reply_with_repaired_suggestions(mentor_output, repaired_raw)
```

- [ ] **Step 4: 实现最终程序化兜底，确保无论模型返回什么都能得到 4 个 suggestions**

```python
if suggestions_still_invalid:
    suggestions = _build_programmatic_guided_suggestions(
        user_input=user_input,
        next_focus=mentor_output.next_focus,
        state=state,
        conversation_strategy=conversation_strategy,
    )
```

- [ ] **Step 5: 统一 `runtime.py` 三个本地分支，全部输出 4 项 suggestions**

```python
suggestions = [
    ...  # A
    ...  # B
    ...  # C
    ...  # D
]
```

- [ ] **Step 6: 保持 `next_best_questions` 与 suggestions 同步，避免前端拿到空 guidance**

```python
next_best_questions = [item.content for item in suggestions]
```

- [ ] **Step 7: 运行 Task 1 的聚焦测试，确认转绿**

Run: `PYTHONPATH=apps/api uv run pytest apps/api/tests/test_pm_mentor.py apps/api/tests/test_agent_runtime.py -q`

Expected: PASS，且本地分支和主链路都稳定返回 4 项。

- [ ] **Step 8: 提交后端契约实现**

```bash
git add apps/api/app/agent/pm_mentor.py apps/api/app/agent/runtime.py apps/api/app/agent/types.py
git commit -m "feat(api): enforce mandatory abcd guidance contract"
```

---

### Task 3: 锁定快照与会话透传，确保前端始终拿到结构化选项

**Files:**
- Modify: `apps/api/tests/test_messages_service.py`
- Modify: `apps/api/tests/test_sessions.py`
- Modify: `apps/api/app/services/sessions.py`
- Test: `apps/api/tests/test_messages_service.py`
- Test: `apps/api/tests/test_sessions.py`

- [ ] **Step 1: 在 `test_messages_service.py` 新增失败测试，断言消息处理后 `suggestions_json` 和 `next_best_questions` 同步保存**

```python
decision = saved_turn_decision
assert len(decision.suggestions_json) == 4
assert decision.state_patch_json["next_best_questions"] == [
    item["content"] for item in decision.suggestions_json
]
```

- [ ] **Step 2: 在 `test_sessions.py` 或对应快照测试中新增失败测试，断言 `decision_sections.next_step.meta.suggestion_options` 始终带回 4 项**

```python
snapshot = get_session(...)
options = snapshot.turn_decisions[-1].decision_sections[1].meta["suggestion_options"]
assert len(options) == 4
```

- [ ] **Step 3: 如测试暴露缺口，最小修改 `sessions.py` 的 `_normalize_suggestion_options()` 或 section 组装逻辑**

```python
suggestion_options = _normalize_suggestion_options(decision.suggestions_json or [])
suggestion_options = suggestion_options[:4]
```

- [ ] **Step 4: 运行透传相关后端测试**

Run: `PYTHONPATH=apps/api uv run pytest apps/api/tests/test_messages_service.py apps/api/tests/test_sessions.py -q`

Expected: PASS，快照层不丢四项建议。

- [ ] **Step 5: 提交透传回归修正**

```bash
git add apps/api/tests/test_messages_service.py apps/api/tests/test_sessions.py apps/api/app/services/sessions.py
git commit -m "test(api): preserve abcd guidance through session snapshots"
```

---

### Task 4: 先写前端红灯测试，锁定 A/B/C/D 与自由补充交互

**Files:**
- Modify: `apps/web/src/test/assistant-turn-card.test.tsx`
- Modify: `apps/web/src/test/workspace-composer.test.tsx`
- Modify: `apps/web/src/test/workspace-store.test.ts`
- Test: `apps/web/src/test/assistant-turn-card.test.tsx`
- Test: `apps/web/src/test/workspace-composer.test.tsx`
- Test: `apps/web/src/test/workspace-store.test.ts`

- [ ] **Step 1: 在 `assistant-turn-card.test.tsx` 新增失败测试，要求有 4 个 `方案 A/B/C/D` 和 1 个“自由补充”**

```tsx
expect(screen.getByRole("button", { name: /方案 a/i })).toBeInTheDocument();
expect(screen.getByRole("button", { name: /方案 d/i })).toBeInTheDocument();
expect(screen.getByRole("button", { name: "自由补充" })).toBeInTheDocument();
```

- [ ] **Step 2: 新增失败测试，要求点击自由补充时触发独立回调而不是写入预设文本**

```tsx
const onFreeform = vi.fn();
fireEvent.click(screen.getByRole("button", { name: "自由补充" }));
expect(onFreeform).toHaveBeenCalledTimes(1);
expect(onSelectDecisionGuidanceQuestion).not.toHaveBeenCalled();
```

- [ ] **Step 3: 在 `workspace-composer.test.tsx` 的 `ConversationPanel` 集成测试里新增失败断言**

```tsx
fireEvent.click(screen.getByRole("button", { name: /方案 a/i }));
expect(workspaceStore.getState().inputValue).toBe(option.content)

fireEvent.click(screen.getByRole("button", { name: "自由补充" }));
expect(screen.getByRole("textbox")).toHaveFocus()
```

- [ ] **Step 4: 如 store 解析需要轻微调整，在 `workspace-store.test.ts` 补一个“只有 suggestionOptions 也能稳定展示四项”的断言**

```tsx
expect(store.getState().decisionGuidance?.suggestionOptions).toHaveLength(4)
```

- [ ] **Step 5: 运行前端聚焦测试，确认先失败**

Run: `pnpm --filter web test -- src/test/assistant-turn-card.test.tsx src/test/workspace-composer.test.tsx src/test/workspace-store.test.ts`

Expected: FAIL，失败点集中在“自由补充”按钮和输入框聚焦能力尚未实现。

- [ ] **Step 6: 提交前端测试脚手架**

```bash
git add apps/web/src/test/assistant-turn-card.test.tsx apps/web/src/test/workspace-composer.test.tsx apps/web/src/test/workspace-store.test.ts
git commit -m "test(web): lock abcd guidance and freeform behavior"
```

---

### Task 5: 实现前端展示、预填与自由补充聚焦

**Files:**
- Modify: `apps/web/src/components/workspace/assistant-turn-card.tsx`
- Modify: `apps/web/src/components/workspace/action-options.tsx`
- Modify: `apps/web/src/components/workspace/conversation-panel.tsx`
- Modify: `apps/web/src/components/workspace/composer.tsx`
- Test: `apps/web/src/test/assistant-turn-card.test.tsx`
- Test: `apps/web/src/test/workspace-composer.test.tsx`
- Test: `apps/web/src/test/workspace-store.test.ts`

- [ ] **Step 1: 在 `assistant-turn-card.tsx` 增加“自由补充”按钮与对应回调**

```tsx
<button type="button" onClick={onSelectFreeformGuidance}>
  自由补充
</button>
```

- [ ] **Step 2: 保持 `action-options.tsx` 以 `A/B/C/D` 常态渲染，避免四项外的布局分支膨胀**

```tsx
{options.slice(0, 4).map((option, index) => (
  <span>方案 {String.fromCharCode(65 + index)}</span>
))}
```

- [ ] **Step 3: 在 `composer.tsx` 暴露 textarea ref 或 focus 方法，让上层能主动聚焦输入框**

```tsx
const textareaRef = useRef<HTMLTextAreaElement | null>(null)
useImperativeHandle(forwardedRef, () => ({
  focusInput: () => textareaRef.current?.focus(),
}))
```

- [ ] **Step 4: 在 `conversation-panel.tsx` 连接两类动作**

```tsx
onSelectDecisionGuidanceQuestion={(question) => {
  workspaceStore.getState().setInputValue(question)
  composerRef.current?.focusInput()
}}
onSelectFreeformGuidance={() => {
  composerRef.current?.focusInput()
}}
```

- [ ] **Step 5: 保证点击“自由补充”时不清空已有输入，点击 A/B/C/D 时只覆盖为该候选草稿，不自动发送**

```tsx
expect(sendMessage).not.toHaveBeenCalled()
```

- [ ] **Step 6: 运行 Task 4 的聚焦测试，确认转绿**

Run: `pnpm --filter web test -- src/test/assistant-turn-card.test.tsx src/test/workspace-composer.test.tsx src/test/workspace-store.test.ts`

Expected: PASS，且点击建议后输入框内容变化、点击自由补充后输入框获得焦点。

- [ ] **Step 7: 提交前端交互实现**

```bash
git add apps/web/src/components/workspace/assistant-turn-card.tsx apps/web/src/components/workspace/action-options.tsx apps/web/src/components/workspace/conversation-panel.tsx apps/web/src/components/workspace/composer.tsx
git commit -m "feat(web): add mandatory abcd guidance interactions"
```

---

### Task 6: 做端到端回归验证并收尾

**Files:**
- Modify: `apps/api/tests/test_messages_service.py`
- Modify: `apps/web/src/test/workspace-composer.test.tsx`
- Test: `apps/api/tests/test_pm_mentor.py`
- Test: `apps/api/tests/test_agent_runtime.py`
- Test: `apps/api/tests/test_messages_service.py`
- Test: `apps/api/tests/test_sessions.py`
- Test: `apps/web/src/test/assistant-turn-card.test.tsx`
- Test: `apps/web/src/test/workspace-composer.test.tsx`
- Test: `apps/web/src/test/workspace-store.test.ts`

- [ ] **Step 1: 跑后端完整聚焦回归**

Run: `PYTHONPATH=apps/api uv run pytest apps/api/tests/test_pm_mentor.py apps/api/tests/test_agent_runtime.py apps/api/tests/test_messages_service.py apps/api/tests/test_sessions.py -q`

Expected: PASS

- [ ] **Step 2: 跑前端完整聚焦回归**

Run: `pnpm --filter web test -- src/test/assistant-turn-card.test.tsx src/test/workspace-composer.test.tsx src/test/workspace-store.test.ts`

Expected: PASS

- [ ] **Step 3: 如有失败，只修最小必要代码，不顺手重构无关 UI 或 agent 逻辑**

- [ ] **Step 4: 检查最终行为与 spec 对齐**

```text
- 每轮都有四项 suggestions
- 每轮都有自由补充
- 点建议只预填不发送
- 点自由补充只聚焦不清空
- 模型失约时后端仍补齐四项
```

- [ ] **Step 5: 提交最终回归修正**

```bash
git add apps/api apps/web
git commit -m "feat(api,web): enforce mandatory abcd guidance in workspace"
```
