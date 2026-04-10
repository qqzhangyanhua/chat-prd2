# PM Mentor 架构重设计

**日期：** 2026-04-10  
**状态：** 待实施  
**目标：** 将当前基于规则状态机的 Agent 重构为 LLM 驱动的 PM 导师对话系统

---

## 背景与问题

当前 Agent 架构存在三个核心问题：

1. **规则状态机主导推理**：`runtime.py` 包含 10 个 if 分支的硬编码命令匹配（如 "不对，先改目标用户"），LLM 只用于生成最终回复文字，不参与任何推理。

2. **Critic 硬编码领域知识**：`decision_engine.py` 的 Critic 只检查三个固定关键词（核心文件格式、预览深度、权限边界），是为 3D 图纸预览产品写死的，无法适配任何其他领域。

3. **两条并行路径冲突**：旧的"四字段填槽"路径（target_user/problem/solution/mvp_scope）和新的 `initial_draft_flow` 并存，逻辑混乱。

**用户期望的体验：** AI 像一个 PM 导师，每轮给出"观察 + 挑战 + 建议 + 追问"，帮助用户挖掘想法、挑战假设，逐步形成高质量 PRD。

---

## 方案选择

选择 **方案 B：瘦编排层 + LLM 作为核心推理引擎**。

放弃的方案：
- 方案 A（全量 LLM）：行为不可预测，调试困难
- 方案 C（多步 Pipeline）：每轮 3 次 LLM 调用，慢且贵

---

## Section 1：整体架构变化

### 现在的数据流

```
user_input
  → 检查10种命令（硬编码字符串匹配）
  → 规则提取字段（target_user/problem/solution/mvp_scope）
  → 规则决策（decision_engine）
  → LLM 仅生成回复文本
  → reply
```

### 新的数据流

```
user_input
  → 瘦编排层（仅3个判断：已完成？网关错误？首次消息？）
  → LLM PM Mentor（输入：对话历史 + 当前PRD状态）
  → 结构化 JSON 输出（观察 + 挑战 + 建议 + 追问 + PRD增量）
  → 回复组装
  → PRD 更新（具体信息写入，模糊信息标注待补充）
```

### Agent 模块变化

**删除**（逻辑移入 LLM prompt）：
- `decision_engine.py`
- `validation_flows.py`
- `initial_draft_flow.py`
- `refine_loop_flow.py`
- `understanding.py`
- `suggestion_planner.py`
- `reply_composer.py`
- `prompts.py`

**新增**：
- `pm_mentor.py` — LLM PM 导师核心，组装上下文，调用 LLM，解析结构化输出
- `prd_updater.py` — 把 LLM 输出的 `prd_updates` 合并进当前 PRD 状态

**保留（精简）**：
- `runtime.py` — 从 760 行缩减到 ~80 行的瘦编排层
- `types.py` — 更新类型定义，新增 `PmMentorOutput` dataclass
- `extractor.py` — 只保留 `normalize_text` 等工具函数，删除规则提取逻辑

---

## Section 2：LLM 输入/输出契约

### LLM 接收的上下文

```python
{
  "conversation_history": [
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."},
    # 最近 10 轮（早期信息已沉淀在 PRD 里，无需全量历史）
  ],
  "current_prd": {
    "sections": {
      "target_user":  {"content": "...", "status": "confirmed|draft|missing"},
      "problem":      {"content": "...", "status": "..."},
      "solution":     {"content": "...", "status": "..."},
      "mvp_scope":    {"content": "...", "status": "..."},
      # LLM 可以自行决定新增 section（如 success_metrics、non_goals 等）
    },
    "missing": ["尚未明确核心价值主张", "..."],
  },
  "turn_count": 3,
}
```

### LLM 输出 JSON Schema

```json
{
  "observation":  "用户本轮输入的核心信息或隐含假设",
  "challenge":    "一个具体的挑战或反问（必须指向具体假设）",
  "suggestion":   "PM 视角的具体建议或框架",
  "question":     "本轮最关键的一个追问（只能问一个）",
  "reply":        "面向用户的完整回复（组合以上四项）",
  "prd_updates": {
    "target_user": {
      "content": "小微企业主，主要场景是...",
      "status": "draft"
    }
  },
  "confidence":   "high | medium | low",
  "next_focus":   "target_user | problem | solution | mvp_scope | validation | done"
}
```

对应的 Python dataclass（放入 `types.py`）：

```python
@dataclass
class PmMentorOutput:
    observation: str
    challenge: str
    suggestion: str
    question: str
    reply: str
    prd_updates: dict[str, dict]   # section_key -> {content, status}
    confidence: str                 # "high" | "medium" | "low"
    next_focus: str
```

---

## Section 3：瘦编排层 + PRD 更新逻辑

### 新 `runtime.py`（~80 行）

```python
def run_agent(state: dict, user_input: str) -> AgentResult:

    # 边界 1：PRD 已完成
    if state.get("workflow_stage") == "completed":
        return _build_completed_result(state)

    # 边界 2：网关不可用 -> 降级本地回复
    if not _gateway_available(state):
        return _build_fallback_result(state, user_input)

    # 其余全部 -> LLM PM Mentor
    return run_pm_mentor(state, user_input)
```

完全删除的逻辑（现在由 LLM 处理）：
- 硬编码命令匹配（"不对，先改目标用户" 等字符串判断）
- validation_switch / vague_validation / followup 流程
- confirm_continue 命令
- 四字段填槽路径（first_missing_section 驱动的逐步收集）

### `prd_updater.py` 合并规则

```
LLM 返回 prd_updates
  → 遍历每个 section
  → status == "confirmed" 或 "draft"  → 写入，覆盖旧内容
  → status == "missing"               → 保留旧内容，更新缺口描述
  → 无该 section 的旧记录             → 新建 section
  → prd_updates 为空 {}               → PRD 不变，不触发 prd.updated 事件
```

触发 `prd.updated` SSE 事件的条件：

```python
def should_emit_prd_updated(old_prd: dict, new_prd: dict) -> bool:
    return old_prd != new_prd
```

### 完整单轮 SSE 事件序列（不变）

```
message.accepted
  → reply_group.created
  → assistant.version.started
  → action.decided
  → assistant.delta（多次）
  → assistant.done
  → prd.updated（仅当 PRD 有实质变化时）
```

---

## Section 4：PM Mentor Prompt 设计

### System Prompt

```
你是一位经验丰富的 AI 产品联合创始人（PM 导师风格）。
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
严格返回 JSON，包含字段：
observation / challenge / suggestion / question / reply / prd_updates / confidence / next_focus
```

### User Prompt（每轮动态生成）

```
【当前 PRD 状态】
{current_prd_json}

【对话历史（最近 {N} 轮）】
{conversation_history}

【用户本轮输入】
{user_input}
```

### 关键设计决策

| 决策 | 选择 | 原因 |
|------|------|------|
| model_scene | `reasoning` | PM 导师需要推理能力，不是速度优先 |
| 对话历史保留轮数 | 最近 10 轮 | 避免超 context，早期信息已沉淀在 PRD 里 |
| 结构化输出方式 | `generate_structured_extraction`（已有） | 复用现有 model_gateway，不引入新依赖 |
| reply 由谁生成 | LLM 直接输出 | 删除 `reply_composer.py`，不再需要二次组装 |

---

## Section 5：错误处理 + 测试策略

### 错误处理

**LLM 输出 JSON 解析失败：**
```
解析失败 → 重试一次（同 prompt）→ 仍失败 → 降级：
  reply = "我现在处理不了这个输入，能换个方式描述一下吗？"
  prd_updates = {}（PRD 不变）
```

**必填字段缺失（question 或 reply 为空）：**
```
用 fallback 填充，不向用户报错
  reply fallback = observation + "\n" + challenge + "\n" + suggestion + "\n" + question 文本拼接
```

**model_gateway 超时/网络错误：**
```
沿用现有 ModelGatewayError 体系 → raise_api_error → 前端 recovery_action（不变）
```

### 测试策略

| 测试类型 | 覆盖目标 | 方式 |
|------|------|------|
| `pm_mentor.py` 单元测试 | 上下文组装正确性（历史截断、PRD 序列化） | mock LLM，验证 prompt 结构 |
| `prd_updater.py` 单元测试 | 各 status 组合的合并逻辑 | 纯 Python，无 LLM 依赖 |
| `runtime.py` 单元测试 | 三个边界条件路由 | mock pm_mentor |
| 集成测试 | 完整单轮 SSE 事件序列 | 沿用 `test_messages_stream.py` 模式 |
| LLM 输出契约测试 | JSON schema 校验（缺字段/类型错误） | Pydantic model 解析 |

**不测试：** LLM 回复质量（prompt 工程问题，非代码问题）。

---

## 迁移策略

1. 新增 `pm_mentor.py` 和 `prd_updater.py`，不删除旧文件
2. 在 `runtime.py` 加一个 feature flag：`USE_PM_MENTOR = True/False`
3. 两路并行跑测试，确认新路径 SSE 事件序列完整
4. 测试通过后删除旧文件（`decision_engine.py`、`validation_flows.py` 等）

---

## 文件变更清单

| 操作 | 文件 |
|------|------|
| 新增 | `apps/api/app/agent/pm_mentor.py` |
| 新增 | `apps/api/app/agent/prd_updater.py` |
| 重写 | `apps/api/app/agent/runtime.py`（760行 → ~80行） |
| 更新 | `apps/api/app/agent/types.py`（新增 `PmMentorOutput`） |
| 精简 | `apps/api/app/agent/extractor.py`（只保留工具函数） |
| 删除 | `apps/api/app/agent/decision_engine.py` |
| 删除 | `apps/api/app/agent/validation_flows.py` |
| 删除 | `apps/api/app/agent/initial_draft_flow.py` |
| 删除 | `apps/api/app/agent/refine_loop_flow.py` |
| 删除 | `apps/api/app/agent/understanding.py` |
| 删除 | `apps/api/app/agent/suggestion_planner.py` |
| 删除 | `apps/api/app/agent/reply_composer.py` |
| 删除 | `apps/api/app/agent/prompts.py` |
| 新增测试 | `apps/api/tests/test_pm_mentor.py` |
| 新增测试 | `apps/api/tests/test_prd_updater.py` |
