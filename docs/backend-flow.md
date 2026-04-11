# 后端消息处理全链路文档

> 记录用户输入如何一步步被引导、澄清、提炼，最终生成 PRD 的完整逻辑。

---

## 一、整体架构图

```
用户输入
  │
  ▼
[HTTP POST /api/sessions/{id}/messages]
  │
  ▼
[messages.py 路由层] ─── 鉴权、校验 session 归属
  │
  ▼
[message_preparation.py] ─── 准备阶段（核心调度）
  ├─ 1. 校验模型配置是否可用
  ├─ 2. 保存用户消息
  ├─ 3. 加载当前 state（项目状态快照）
  ├─ 4. 构建对话历史
  ├─ 5. 结构化提取（extractor → LLM 兜底）
  ├─ 6. 运行 Agent（pm_mentor）
  └─ 7. 打开回复流（local 或 gateway）
  │
  ▼
[SSE 流式输出] ─── 逐块推送给前端
  │
  ▼
[持久化] ─── state、PRD、turn_decision 落库
```

---

## 二、用户输入后的第一步：校验与准备

### 2.1 路由入口

**文件：** `apps/api/app/api/routes/messages.py`

```
POST /api/sessions/{session_id}/messages
Body: { content: str, model_config_id: str }
```

路由做两件事：
1. 验证当前用户拥有该 session
2. 调用 `stream_user_message_events()`，返回 SSE 事件流

### 2.2 准备阶段（`message_preparation.py`）

系统在真正回复之前，会依次完成以下准备工作：

| 步骤 | 做什么 | 失败时 |
|------|--------|--------|
| 1 | 获取 model_config，验证是否 enabled | 抛出 ApiError + recovery_action |
| 2 | 保存用户消息到 DB | — |
| 3 | 加载最新项目状态（state） | 初始化空 state |
| 4 | 拉取对话历史（历史 user/assistant 消息） | — |
| 5 | 结构化提取用户输入 | 回退规则提取 |
| 6 | 运行 Agent（pm_mentor） | 返回兜底回复 |
| 7 | 打开回复流（local 或 gateway） | — |

---

## 三、核心 State：系统的"记忆"

系统通过一个 `state` dict 记录整个对话进展，关键字段：

```python
state = {
    # 当前阶段
    "workflow_stage": "exploring" | "finalize" | "completed",
    "current_phase": "idea_clarification" | "refine_loop" | ...,
    "stage_hint": "target_user" | "problem" | "solution" | "mvp_scope",

    # PRD 草稿
    "prd_snapshot": {
        "sections": {
            "target_user": { "title": "目标用户", "content": "...", "status": "missing|draft|confirmed" },
            "problem":     { "title": "核心问题", "content": "...", "status": "missing" },
            "solution":    { "title": "解决方案", "content": "...", "status": "missing" },
            "mvp_scope":   { "title": "MVP 范围", "content": "...", "status": "missing" },
        }
    },

    # 对话策略
    "conversation_strategy": "clarify" | "converge" | "confirm" | "choose",
    "working_hypotheses": [...],      # 系统当前的假设
    "pm_risk_flags": [...],           # 风险提示
    "pending_confirmations": [...],   # 待用户确认的点
    "next_best_questions": [...],     # 下一步最优问题
    "iteration": 3,                   # 当前轮次
}
```

每次对话完成后，系统会生成新的 state 版本快照存入 `project_state_versions` 表。

---

## 四、如何判断用户输入的质量（结构化提取层）

**文件：** `apps/api/app/agent/extractor.py`

用户输入进来后，系统不会直接交给 LLM，而是先做一轮**结构化提取**，判断这次输入是否有价值、能写到 PRD 哪个位置。

### 4.1 两阶段提取

```
用户输入
  │
  ├─ 第一阶段：规则提取（快速、低成本）
  │    ├─ 找出当前 state 中第一个缺失的 section
  │    ├─ 判断输入是否"值得捕获"
  │    └─ 返回 StructuredExtractionResult
  │
  └─ 第二阶段：LLM 结构化提取（可选，作为增强）
       ├─ 调用 generate_structured_extraction()
       ├─ 返回 JSON: { should_update, confidence, state_patch, prd_patch }
       └─ 失败则回退第一阶段结果
```

### 4.2 判断输入是否值得捕获（`should_capture`）

```python
# 过滤无意义的继续指令
SKIP_INPUTS = {"继续", "继续吧", "好的", "好", "嗯", "ok", "继续推进"}

# 检测模糊/不确定回答
UNCERTAIN_PHRASES = ("还没想好", "不确定", "不清楚", "待定", "之后再说", "再想想")
```

- 如果是空输入、继续指令 → `should_update=False`，跳过 PRD 更新
- 如果包含不确定短语 → `should_update=False`，系统继续追问而不写入 PRD

### 4.3 第一个缺失的 section 决定写入位置

系统按固定顺序找缺口：

```
target_user → problem → solution → mvp_scope
```

用户输入会被尝试映射到当前第一个 `status="missing"` 的 section。

### 4.4 置信度判断

| 用户输入示例 | confidence | PRD status |
|-------------|-----------|------------|
| "SaaS 创始人，25-45岁，已募资的项目" | high | confirmed |
| "小企业，可能是电商或服务行业" | medium | draft |
| "我还没想好" / "各种人都能用" | low | 不写入 |

---

## 五、Agent：如何决定下一步引导方向

**文件：** `apps/api/app/agent/runtime.py` → `pm_mentor.py`

### 5.1 Agent 决策优先级

```python
def run_agent(state, user_input, model_result, model_config, conversation_history):

    # 优先级 1：流程已完成
    if state["workflow_stage"] == "completed":
        return _build_completed_result()   # reply_mode="local"

    # 优先级 2：无可用模型配置
    if model_config is None:
        return _build_fallback_result()    # reply_mode="local"

    # 默认路径：PM Mentor LLM
    return run_pm_mentor(state, user_input, model_config, conversation_history)
```

### 5.2 PM Mentor 的四个职责

PM Mentor 是一个结构化 LLM Prompt，每轮对话必须完成四步：

```
1. Observation（观察）
   ─ 识别用户输入中的关键信息
   ─ 例："用户提到了目标是创始人群体，但没有说明规模限制"

2. Challenge（挑战）
   ─ 挑战用户的一个具体假设，而不是泛泛提问
   ─ 例："你说'所有创业者都需要'，但早期 MVP 通常需要更精准的用户画像"

3. Suggestion（建议）
   ─ 给出具体的 PM 框架建议
   ─ 例："建议用 Jobs-to-be-Done 框架重新描述目标用户的核心场景"

4. Question（追问）
   ─ 只问一个最关键的问题，推动对话前进
   ─ 例："如果你只能选一类用户优先服务，你会选谁？为什么？"
```

### 5.3 LLM 的输入与输出格式

**输入给 LLM：**
```json
{
    "current_prd": {
        "sections": { "target_user": {...}, "problem": {...}, ... },
        "missing": ["problem", "solution", "mvp_scope"]
    },
    "conversation_history": [
        {"role": "user", "content": "我想做一个..."},
        {"role": "assistant", "content": "很好！那么..."}
    ],
    "turn_count": 3,
    "user_input": "目标用户是 SaaS 创始人"
}
```

**LLM 输出（JSON）：**
```json
{
    "observation": "用户明确了目标用户是 SaaS 创始人",
    "challenge": "SaaS 创始人群体很广，早期和晚期创始人需求差异很大",
    "suggestion": "建议区分 pre-PMF 和 post-PMF 两类创始人",
    "question": "你的产品主要帮助还在寻找 PMF 的创始人，还是已经找到了在做增长的？",
    "reply": "",                          // 若为空，系统自动拼接上面四项
    "prd_updates": {
        "target_user": {
            "title": "目标用户",
            "content": "SaaS 创始人",
            "status": "draft"             // draft=有信息但不够具体
        }
    },
    "confidence": "medium",
    "next_focus": "target_user"           // 下一轮继续聚焦目标用户
}
```

### 5.4 `next_focus` 如何推进流程

```python
if next_focus == "done":
    state_patch["workflow_stage"] = "completed"
else:
    state_patch["stage_hint"] = next_focus  # 告诉下一轮重点关注哪个 section
```

---

## 六、如何处理用户模糊/不明确的输入

这是系统最核心的引导能力，分为四层处理：

### 场景：用户说"我不太确定目标用户是谁"

```
Layer 1 - 规则提取（extractor.py）：
  "不确定" 命中 UNCERTAIN_PHRASES
  → should_update=False
  → 不写入 PRD，不改变 state

Layer 2 - LLM 结构化提取：
  调用 generate_structured_extraction()
  可能返回 { should_update: false, confidence: "low" }
  → 同样不写入 PRD

Layer 3 - PM Mentor（pm_mentor.py）：
  observation: "用户表示对目标用户还不确定"
  challenge:   "不确定通常意味着需要先做市场调研或用户访谈"
  suggestion:  "可以从你自己的痛点出发，你本人就是第一个目标用户吗？"
  question:    "你有没有亲眼见过某人遇到这个问题？那个人是谁？"
  prd_updates: {}   ← 空，不更新 PRD

Layer 4 - 回复给用户：
  以 PM 顾问视角输出引导性回复
  PRD 面板不变化（section 状态仍为 missing）
```

### 场景：用户给出模糊的宽泛描述

```
用户说："目标用户是各种人，任何人都可以用"

PM Mentor 的处理：
  challenge: "产品如果面向所有人，通常意味着没有真正面向任何人"
  suggestion: "大多数成功产品都从一个非常垂直的用户群体起步"
  question:   "你见过的第一个愿意为这个产品付钱的人，他/她是谁？"

prd_updates: {}   ← 不写入，等用户给出更具体描述
```

### 引导策略（`conversation_strategy`）

系统会根据当前状态选择引导策略：

| 策略 | 触发条件 | 行为 |
|------|---------|------|
| `clarify` | section 缺失 | 追问，填补空白 |
| `converge` | 大部分 section 有草稿 | 收敛，确认细节 |
| `confirm` | 信息基本完整 | 逐项确认，转为 confirmed |
| `choose` | 用户提出多个方向 | 帮助权衡，引导做决策 |

---

## 七、PRD 的生成与演进

### 7.1 PRD section 状态机

```
missing → draft → confirmed
   ↑         ↑         ↑
用户还没    有信息     用户明确
回答此项    但模糊     确认过了
```

**状态转换规则（`prd_updater.py`）：**

```python
# 写入规则
if new_status in ("draft", "confirmed"):
    直接覆盖写入

elif new_status == "missing":
    保留原 content，仅更新状态和 gap 描述

# 空 prd_updates={} 时
    不做任何修改，返回原 PRD 副本
```

### 7.2 PRD 阶段标签

系统根据整体进度计算当前阶段：

```python
if workflow_stage == "completed":
    stage_label = "已生成终稿"
    stage_tone  = "final"

elif workflow_stage == "finalize" or overall_verdict == "pass":
    stage_label = "可整理终稿"
    stage_tone  = "ready"

else:
    stage_label = "探索中"
    stage_tone  = "draft"
```

### 7.3 PRD 最终完成的条件

PM Mentor 在 LLM 输出中返回 `"next_focus": "done"` 时，系统将 `workflow_stage` 设为 `"completed"`，此后：

1. Agent 进入 `_build_completed_result()` 分支
2. 回复固定文案（local 模式，不再调用 LLM）
3. PRD 所有 section 应已达到 `confirmed` 状态
4. 前端触发 PRD 导出按钮激活

---

## 八、SSE 流式事件序列

用户发送一条消息后，前端会收到以下事件序列：

```
1. message.accepted
   { message_id, session_id }

2. reply_group.created
   { reply_group_id, user_message_id, session_id, is_regeneration }

3. action.decided
   { action: "probe_deeper", target: "target_user", reason: "..." }
   ← 前端可据此展示"正在分析目标用户..."

4. assistant.version.started
   { assistant_version_id, version_no: 1, model_config_id, ... }

5. assistant.delta（多次，每次一个文本块）
   { delta: "你好，", ... }
   { delta: "我注意到...", ... }
   ← 前端逐字拼接展示

6. prd.updated
   {
     sections: {
       target_user: { title, content, status },
       problem:     { title, content, status },
       ...
     },
     meta: {
       stageLabel: "探索中",
       stageTone: "draft",
       criticGaps: ["缺少核心问题描述"],
       nextQuestion: "你的产品解决了什么具体问题？"
     }
   }
   ← 前端 PRD 面板实时刷新

7. assistant.done
   { assistant_message_id, prd_snapshot_version, is_latest: true }
```

---

## 九、回复模式：Local vs Gateway

| 模式 | 触发条件 | 行为 |
|------|---------|------|
| `local` | workflow 已完成 / 无模型配置 | 使用预设文案，不调用 LLM |
| `gateway` | 正常对话路径 | 调用 LLM API，流式返回 |

**Local 模式示例：**
- PRD 完成后："感谢你的分享！PRD 已经生成，你可以点击右侧导出按钮下载 Markdown 文档。"
- 无模型配置时："当前没有可用的 AI 模型，请联系管理员配置模型后重试。"

**Gateway 模式：**
- 支持 OpenAI 兼容 API（任何 `base_url` 格式）
- 优先解析 SSE 流（`text/event-stream`），否则回退 JSON 解析
- 超时 30 秒，失败时抛出 `ModelGatewayError`

---

## 十、Turn Decision：每轮对话的决策记录

每轮对话结束后，系统会将完整决策过程落库到 `agent_turn_decisions` 表：

```python
TurnDecision {
    phase: "idea_clarification",     # 当前对话阶段
    phase_goal: "明确目标用户",        # 本阶段目标
    understanding: { ... },           # 系统对用户意图的理解
    assumptions: [                    # 当前工作假设
        { content: "用户面向 SaaS 创始人", confidence: "medium" }
    ],
    gaps: ["核心问题还未明确"],        # 信息缺口
    challenges: ["市场定位模糊"],      # 风险因素
    pm_risk_flags: ["没有竞品分析"],   # PM 视角风险
    next_move: "probe_deeper",        # 下一步动作
    conversation_strategy: "clarify", # 对话策略
    needs_confirmation: ["目标用户"],  # 待确认事项
    confidence: "medium"             # 整体置信度
}
```

这个记录用于：
- 前端展示 AI 的"思考过程"
- 后续轮次的上下文参考
- 产品分析与调优

---

## 十一、完整流程时序图

```
用户           前端              后端路由          准备层           Agent          LLM Gateway
 │               │                  │                │               │                │
 │──发送消息────▶│                  │                │               │                │
 │               │──POST /messages─▶│                │               │                │
 │               │                  │──校验 session──│               │                │
 │               │                  │──stream_events─▶               │                │
 │               │                  │                │──校验模型──────│               │
 │               │                  │                │──保存用户消息──│               │
 │               │                  │                │──加载 state───│               │
 │               │                  │                │──结构化提取────│──call LLM────▶│
 │               │                  │                │               │◀─JSON 结果────│
 │               │◀─message.accepted│                │──run_agent────▶               │
 │               │◀─reply_group────▶│                │               │──pm_mentor────▶│
 │               │◀─action.decided──│                │               │◀─JSON reply───│
 │               │◀─version.started─│                │──open_stream──│               │
 │               │◀─delta(chunk1)───│◀────────────────────────────────────stream─────│
 │               │◀─delta(chunk2)───│                │               │                │
 │               │      ...         │                │               │                │
 │               │◀─prd.updated─────│──persist all──▶│               │                │
 │               │◀─assistant.done──│                │               │                │
 │◀─展示回复──────│                  │                │               │                │
 │◀─PRD 面板刷新──│                  │                │               │                │
```

---

## 十二、错误处理与恢复

| 错误类型 | 触发条件 | recovery_action |
|---------|---------|-----------------|
| 模型不可用 | model_config disabled | `goto:/admin/models` |
| Schema 过期 | DB 迁移未完成 | `run:alembic upgrade head` |
| LLM 超时 | 30 秒无响应 | 提示重试 |
| LLM 返回非 JSON | 结构化提取失败 | 自动回退规则提取 |
| 结构化提取失败 | LLM 异常 | 回退 rule-based 结果 |

---

## 十三、关键文件索引

| 文件 | 职责 |
|------|------|
| `app/api/routes/messages.py` | HTTP 路由，SSE 事件发射 |
| `app/services/message_preparation.py` | 准备阶段调度器 |
| `app/services/messages.py` | stream_user_message_events 主函数 |
| `app/services/message_persistence.py` | 消息/state/PRD 落库 |
| `app/services/model_gateway.py` | LLM API 调用封装 |
| `app/agent/runtime.py` | Agent 入口，决策优先级路由 |
| `app/agent/pm_mentor.py` | PM Mentor LLM 调用 + 输出解析 |
| `app/agent/extractor.py` | 结构化提取（规则 + LLM） |
| `app/agent/prd_updater.py` | PRD section 合并规则 |
| `app/agent/prd_runtime.py` | PRD 阶段标签计算 |
| `app/agent/types.py` | AgentResult / TurnDecision 类型定义 |
