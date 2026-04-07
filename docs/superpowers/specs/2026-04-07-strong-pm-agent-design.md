# 强推进型 AI 产品经理后端设计

## 1. 背景

当前 `apps/api` 已经具备会话、消息流、状态快照、PRD 快照、回复版本历史、模型配置等基础设施，但“智能体”本质上仍是一个带状态的 PRD 槽位采集器：

- `agent/runtime.py` 只负责按缺失字段顺序决定下一步动作
- `messages.py` 会记录 `action`，但最终回复并不真正受该决策约束
- 当前状态核心只围绕 `target_user / problem / solution / mvp_scope`
- 系统更像“追问表单”而不是“产品判断型对话智能体”

用户的明确目标不是继续增强一个问答式助手，而是把后端升级为：

- 面向 `创业想法梳理` 场景
- 风格为 `强推进型`
- 在信息不足时 `先显式做假设，再继续推进`
- 每轮都 `给出建议、推荐方向、推动用户展开想法`

因此本次设计的重点不是再加几个字段，而是把后端改造成“先决策、后表达”的 PM 智能体架构。

## 2. 目标

本次设计只解决一个核心问题：

把当前 PRD 槽位采集式消息链路，升级成一个稳定的“强推进型 AI 产品经理决策链路”。

本次范围内必须达成：

- 每轮先产出结构化 PM 决策，再生成最终回复
- 回复必须严格受 PM 决策约束，不能自由漂移成泛聊天
- 智能体在每轮默认提供建议，而不是只提问
- 智能体支持“显式假设 + 继续推进”的默认策略
- 状态模型能表达阶段、假设、风险、确认项和建议历史
- 后端能记录“为什么这一轮这样回复”的决策审计数据

本次范围外暂不做：

- 联网搜索、外部工具调用、任务执行型 agent
- 完整自治规划执行
- 多角色协作智能体
- 自动生成商业模型、市场分析、定价方案等完整创业文档

## 3. 设计原则

### 3.1 强推进优先，不以陪聊为目标

智能体的职责是推动用户做产品判断，而不是无限延续对话。

### 3.2 先决策，后表达

每轮先做 PM 判断，再由回复生成层把该判断翻译成自然语言。

### 3.3 信息不足时允许假设，但必须显式声明

不能偷偷脑补；必须明确哪些是已确认事实，哪些是工作假设。

### 3.4 每轮都要给建议

回复不能只有问题，必须至少包含：

- 当前判断
- 建议或备选方向
- 推荐理由
- 下一步确认动作

### 3.5 单轮只推进一个核心决策

避免一轮同时推进多个阶段，导致对话发散和状态混乱。

## 4. 方案对比

### 方案 A：增强现有规则状态机

做法：

- 继续保留当前缺字段顺序推进
- 用更多规则控制回复模板
- 少量补充假设和建议模板

优点：

- 改动最小
- 行为可控
- 容易测试

缺点：

- 很难真正像产品经理
- 面对复杂输入时扩展性差
- 容易变成“更复杂的流程机”

### 方案 B：纯 LLM 决策驱动

做法：

- 当前阶段、风险、建议、下一步动作都由模型直接判断
- 后端只做 schema 校验和持久化

优点：

- 最接近真人 PM
- 复杂输入理解上限高
- 更适合非线性、多轮修正场景

缺点：

- 漂移风险高
- 需要更强的评估和回退机制
- 一步切换成本大

### 方案 C：规则外壳 + LLM 决策内核

做法：

- 外层保留阶段边界、会话持久化和约束校验
- 内层让 LLM 负责理解、判断、建议、下一步推进决策
- 最终回复由决策结果驱动

优点：

- 兼顾可控性和智能感
- 能充分复用现有 `sessions/messages/state/prd/version` 基础设施
- 支持渐进演进

缺点：

- 架构边界需要设计清楚
- 比增强规则方案更复杂

### 推荐

采用方案 C。

原因：

- 当前仓库已经有稳定的消息流、状态版本、回复版本骨架，不值得推倒
- 仅增强规则无法达到“像真人 PM”的目标
- 纯模型决策一步到位风险过高
- 混合方案最适合先把“决策真正控制回复”这件事做对

## 5. 目标架构

新的后端消息链路调整为：

```text
用户输入
  -> Input Understanding
  -> PM Decision Engine
  -> Suggestion Planner
  -> Reply Composer
  -> State / Decision Persistence
  -> SSE / Assistant Reply
```

各层职责如下。

### 5.1 Input Understanding

负责把用户输入转换成 PM 可用的结构化理解，而不是简单填槽位。

输出至少包含：

- 新增事实
- 用户显式表达的目标/问题/方案
- 模糊表述
- 可疑前提
- 信息来源类型（事实 / 猜测 / 愿景）

### 5.2 PM Decision Engine

负责判断：

- 当前处于哪个产品阶段
- 本轮要推进哪个唯一目标
- 当前输入是否足够支持阶段推进
- 这轮需要挑战什么
- 是否先立假设
- 应采用哪类下一步动作

### 5.3 Suggestion Planner

负责根据阶段和决策结果给出建议包。

建议包必须支持：

- 给出 2 到 3 个可选方向
- 推荐其中一个方向
- 解释推荐理由
- 告诉用户需要确认什么

### 5.4 Reply Composer

负责把决策层和建议层产出的结构翻译成最终回复。

它不负责思考，只负责表达，必须受“回复合同”约束。

### 5.5 State & Audit Persistence

负责把本轮输入理解、PM 决策、建议、状态补丁、确认项、版本信息全部落库，支持调试与评估。

## 6. 阶段模型

当前 4 槽位顺序不再作为唯一驱动逻辑，改为 6 个产品决策阶段。

### 6.1 Idea Clarification

要回答：

- 这是一个什么产品方向
- 想解决什么机会
- 明确不做什么

关键产物：

- `idea_summary`
- `opportunity_hypothesis`
- `out_of_scope`

### 6.2 Target User Narrowing

要回答：

- 第一优先服务谁
- 这个人群为什么值得优先切入
- 使用触发场景是什么

关键产物：

- `primary_user_segment`
- `triggering_context`
- `why_now`

### 6.3 Problem Validation

要回答：

- 用户最痛的核心问题是什么
- 当前替代方案是什么
- 问题频率和迫切性如何

关键产物：

- `top_problem`
- `current_alternatives`
- `urgency_frequency`
- `evidence_vs_assumption`

### 6.4 Value Proposition & Solution Shape

要回答：

- 为什么这条解决路径值得先做
- 与替代方案相比的关键差异是什么

关键产物：

- `value_proposition`
- `solution_thesis`
- `differentiators`
- `tradeoffs`

### 6.5 MVP Compression

要回答：

- 首版必须包含什么
- 明确不做什么
- 最小闭环是什么

关键产物：

- `must_have_capabilities`
- `excluded_features`
- `mvp_loop`
- `launch_risks`

### 6.6 Decision Summary

要回答：

- 已确认了什么
- 哪些仍是工作假设
- 后续该验证什么

关键产物：

- `confirmed_decisions`
- `working_hypotheses`
- `open_questions`
- `next_validation_steps`

### 6.7 阶段切换规则

阶段切换不能只靠“字段有值”，而要同时满足：

- `completeness`: 当前阶段信息是否基本完整
- `decision_readiness`: 当前阶段信息是否足以支持继续推进

如果答案仍然过泛、不可执行、缺乏证据，智能体应停留在当前阶段继续压缩，而不是机械进入下一阶段。

## 7. 单轮决策对象

新增统一的 `TurnDecision` 结构，取代当前只有 `action` 的轻量对象。

建议字段如下：

```python
TurnDecision
- phase: str
- phase_goal: str
- understanding: dict
- assumptions: list[dict]
- gaps: list[str]
- challenges: list[str]
- pm_risk_flags: list[str]
- next_move: str
- suggestions: list[dict]
- recommendation: dict | None
- reply_brief: dict
- state_patch: dict
- prd_patch: dict
- needs_confirmation: list[str]
- confidence: "high" | "medium" | "low"
```

### 7.1 `next_move` 白名单

仅允许以下几类：

- `probe_for_specificity`
- `assume_and_advance`
- `challenge_and_reframe`
- `summarize_and_confirm`
- `force_rank_or_choose`

### 7.2 `pm_risk_flags` 白名单

至少支持以下风险标签：

- `user_too_broad`
- `problem_not_painful_enough`
- `solution_before_problem`
- `mvp_scope_bloated`
- `evidence_missing`
- `false_consensus`

### 7.3 建议对象

建议包结构建议为：

```python
Suggestion
- type: "direction" | "tradeoff" | "recommendation" | "warning"
- label: str
- content: str
- rationale: str
- priority: int
```

至少要支持：

- 给用户 2 到 3 个互斥方向
- 推荐其中一个
- 说明为什么推荐
- 告知用户如何确认或反驳

## 8. 回复合同

最终用户可见回复不能再由“自由聊天提示词”直接生成，而要受单轮决策约束。

默认每轮回复都要覆盖 4 个逻辑块：

1. `判断`
   当前对用户输入的 PM 视角理解
2. `建议`
   给出建议、选项或推荐方向
3. `理由`
   说明为什么这样建议
4. `确认推进`
   让用户确认、选择、补充或反驳

### 8.1 各动作的回复约束

#### `probe_for_specificity`

必须：

- 明确指出当前信息哪里太泛
- 解释为什么这会阻碍产品决策
- 只追一个最关键的问题
- 尽量带一个建议性参考方向

#### `assume_and_advance`

必须：

- 明说“我先做以下假设”
- 区分假设与事实
- 基于假设继续推进一个更关键决策
- 给用户一个确认或反驳入口

#### `challenge_and_reframe`

必须：

- 直接指出当前表述的问题
- 给出更合适的产品判断框架
- 把讨论拉回当前阶段目标

#### `summarize_and_confirm`

必须：

- 总结已确认内容
- 标注仍未确认项
- 要求用户确认总结是否成立

#### `force_rank_or_choose`

必须：

- 给 2 到 3 个互斥选项
- 明确推荐一个
- 解释推荐逻辑
- 要求用户做选择或反驳

## 9. 状态模型升级

当前 `state_json` 需要从 PRD 槽位集合升级为 PM 决策状态。

建议保留现有字段并新增：

- `current_phase`
- `phase_goal`
- `working_hypotheses`
- `evidence`
- `decision_readiness`
- `pm_risk_flags`
- `recommended_directions`
- `pending_confirmations`
- `rejected_options`
- `next_best_questions`

状态字段语义：

- `working_hypotheses`
  当前为了推进对话而采用的假设
- `evidence`
  支持或反驳假设的用户表达、历史共识
- `decision_readiness`
  当前阶段是否足够支持进入下一阶段
- `pending_confirmations`
  必须等待用户明确确认的点
- `rejected_options`
  已被用户否定的方向，避免反复建议

## 10. 决策审计持久化

仅存消息和状态版本不足以解释智能体行为，因此新增一类“回合决策记录”。

建议新增表：`agent_turn_decisions`

字段建议：

- `id`
- `session_id`
- `user_message_id`
- `phase`
- `phase_goal`
- `understanding_summary`
- `assumptions_json`
- `risk_flags_json`
- `next_move`
- `suggestions_json`
- `recommendation_json`
- `needs_confirmation_json`
- `confidence`
- `state_patch_json`
- `prd_patch_json`
- `created_at`

作用：

- 复盘为什么系统会给出当前建议
- 评估“像 PM 的程度”
- 调试漂移问题
- 为后续自动评分和离线评估提供样本

## 11. 与当前代码的模块映射

建议按以下边界重构：

### 11.1 新增文件

- `apps/api/app/agent/understanding.py`
  输入理解与结构化抽取
- `apps/api/app/agent/decision_engine.py`
  阶段判断、风险判断、下一步动作选择
- `apps/api/app/agent/suggestion_planner.py`
  生成建议包、推荐项、理由
- `apps/api/app/agent/reply_composer.py`
  根据决策合同生成最终回复

### 11.2 调整现有文件

- `apps/api/app/agent/types.py`
  从 `NextAction` / `AgentResult` 升级为 `TurnDecision`、`Suggestion` 等结构
- `apps/api/app/agent/runtime.py`
  由“缺字段追问器”调整为总编排入口，串起 understanding / decision / suggestion / reply
- `apps/api/app/services/messages.py`
  简化为消息编排与持久化，不再承载大量 PM 逻辑
- `apps/api/app/schemas/state.py`
  同步扩展状态字段
- `apps/api/app/services/exports.py`
  后续按新增状态字段扩展导出内容

## 12. 新消息与重生成语义

### 12.1 新消息

新消息链路改为：

1. 持久化用户消息
2. 基于当前 `state` 执行输入理解
3. 生成 `TurnDecision`
4. 生成建议包和最终回复
5. 落库：
   - state version
   - prd snapshot
   - assistant message
   - assistant reply version
   - turn decision record
6. 推送 SSE：
   - `message.accepted`
   - `decision.created`（新增，可选）
   - `assistant.delta`
   - `prd.updated`
   - `assistant.done`

### 12.2 重生成

重生成继续只影响“表达层”，不影响“决策层”和“状态层”：

- 不新建 `state_version`
- 不新建 `prd_snapshot`
- 不新建新的 `turn_decision`
- 只替换建议表达方式和 assistant 文本版本

这样可保证：

- 决策是稳定的
- 表达可以多版本比较

## 13. 错误处理与降级

### 13.1 决策生成失败

若 LLM 决策失败：

- 允许回退到“轻量规则推进模式”
- 但必须显式标记低置信
- 回复要收缩成更保守的追问式输出

### 13.2 流式中断

当前流式中断会留下用户消息但没有完整 assistant 镜像的问题，后续应修复为：

- 明确发送错误事件
- 保证数据库中不会留下不可恢复的半成品状态
- 若用户消息已提交但 assistant 未完成，需有可识别的失败标记

### 13.3 结构脏数据保护

所有模型输出都必须过 schema 校验与白名单清洗，不能直接进入主状态。

## 14. 测试策略

### 14.1 单元测试

覆盖：

- 单轮复杂输入拆解
- 风险标签判断
- `next_move` 选择
- 假设生成与确认项识别
- 建议包生成是否符合当前阶段
- 回复合同是否满足“判断 + 建议 + 理由 + 确认推进”

### 14.2 服务测试

覆盖：

- 新消息是否正确写入 turn decision record
- 新状态字段是否按预期演进
- 回复是否真正受 `TurnDecision` 约束
- 重生成是否不影响状态与决策

### 14.3 行为测试

新增行为维度断言：

- 回复中是否有明确建议
- 是否存在推荐项
- 是否有显式假设
- 是否推进了唯一核心问题
- 是否避免退化成泛泛聊天

## 15. 渐进式落地路线

### 阶段 1：决策真正控制回复

目标：

- 引入 `TurnDecision`
- 引入建议包
- 让回复严格受决策合同约束
- 扩展状态到“阶段 + 假设 + 风险 + 确认项”

这是当前最优先迭代，能直接解决“智能体不像 PM”的核心问题。

### 阶段 2：决策稳定化与评估

目标：

- 新增 `agent_turn_decisions`
- 建立阶段完成判定和一致性校验
- 对建议质量、推进力度、收敛程度做行为评估

### 阶段 3：升级为产品共创智能体

目标：

- 支持非线性阶段跳转
- 支持多字段同时更新
- 支持更完整的产品判断文档输出

## 16. 结论

要把当前后端升级成“像 AI 产品经理 / AI 合伙人”的系统，关键不是继续增加提示词，而是完成一次明确的架构转换：

- 从“记录 action 的聊天系统”
- 升级为“以 PM 决策为中心的对话系统”

本次设计推荐的实现方向是：

- 保留现有会话、状态版本、回复版本基础设施
- 新增输入理解、PM 决策、建议规划、回复合同四层
- 先完成“决策真正控制回复”，再做更强自治能力

这样可以在不推翻现有后端的前提下，逐步把系统演进成一个真正会判断、会建议、会强推进的创业想法梳理智能体。
