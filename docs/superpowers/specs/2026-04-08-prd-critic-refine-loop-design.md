# 假设版 PRD + Critic + Refine 闭环后端设计

## 1. 背景

当前 `apps/api` 已经具备会话、消息流、状态快照、PRD 快照、回复版本历史和结构化提取骨架，但对话链路的核心驱动力仍然是“四字段顺序填充”：

- `agent/extractor.py` 会把用户输入直接归入当前缺失字段
- `agent/decision_engine.py` 主要围绕 `target_user / problem / solution / mvp_scope` 选择下一步
- `agent/reply_composer.py` 更偏向总结和确认，不具备稳定的“持续追问”能力
- `agent/runtime.py` 在四字段补齐后会自然进入 `confirm`

这导致系统虽然能快速沉淀一个最小 PRD 骨架，但无法满足新的目标对话形态：

- 用户先抛出一个想法
- 系统先生成一个“假设版 PRD v1”
- 系统自动以 `Critic` 身份审查当前草稿
- 系统围绕关键缺口持续追问和 refine
- 直到关键信息充分后，才进入可确认的结构化文档阶段

用户明确希望的目标流程是：

```text
Step1 理解意图（Idea Parser）
Step2 生成 PRD v1
Step3 自动 Review（Critic）
Step4 输出结构化文档 + 改进建议
Step5 用户继续 refine
```

本次设计的核心不是继续增强“字段收集器”，而是把后端升级成一个显式的“阶段闭环编排器”。

## 2. 目标

本次设计只解决一个核心问题：

把当前后端消息链路升级成一个支持 `Idea Parser -> 假设版 PRD -> Critic -> refine loop -> finalize` 的对话闭环。

本次范围内必须达成：

- 支持在信息不足时先生成“假设版 PRD v1”
- PRD v1 生成后自动触发 Critic 审查，而不是直接确认
- Critic 既能协作补充，也能对关键缺口设置卡口
- refine 阶段每轮只追问一个最高价值问题
- 对话默认优先追问“产品方案细节”缺口
- 会话状态可以表达工作流阶段、假设、缺口、Critic 结论和 refine 历史
- 最终回复受阶段和 Critic 结果驱动，而不是自由泛聊

本次范围外暂不做：

- 多 agent 并行执行
- 联网研究、行业情报、竞品分析自动写入
- 自动生成完整商业计划书
- 前端协议大改或全新 UI 工作流
- 数据库新增大量新表

## 3. 设计原则

### 3.1 先产出假设版，不假装已确认

当用户信息不足时，系统可以先给出 `PRD v1`，但必须显式标注：

- 哪些内容来自用户明确表达
- 哪些内容是系统工作假设
- 哪些内容仍然缺失

### 3.2 Critic 是结构化审稿器，不是泛化评论器

Critic 必须输出稳定的结构化结果，用于驱动下一轮 refine，而不是只返回一句“还可以继续完善”。

### 3.3 每轮只推进一个最关键问题

系统必须维护问题优先级队列，但单轮只抛出一个最高价值问题，避免用户被多问题轰炸。

### 3.4 先协作，再卡口

Critic 的默认行为是：

- 先总结当前已形成的判断
- 再指出最关键缺口
- 在命中关键缺口时阻止 finalize

### 3.5 工作流阶段控制流程，对话策略控制表达

新的系统要区分：

- `workflow_stage` 决定当前流程走到哪一步
- `conversation_strategy` 决定这一轮采用什么表达策略

不能继续仅靠 `clarify / converge / confirm` 这几个策略词承担完整流程控制。

## 4. 方案对比

### 方案 A：继续增强现有四字段流

做法：

- 保留当前四字段状态机
- 补充更多规则和追问模板
- 在四字段填满后追加一个简单 review 阶段

优点：

- 改动最小
- 风险最低
- 复用现有逻辑最多

缺点：

- 底层仍是“字段填空”
- 很难稳定支持假设版 PRD 和 Critic 闭环
- 后续会继续受四字段模型限制

### 方案 B：外包一层工作流编排器

做法：

- 保留 `understanding / extraction / suggestion / reply` 等既有能力
- 在外层新增显式工作流阶段
- 由编排器驱动 `Idea Parser -> PRD Draft -> Critic -> Refine Loop`

优点：

- 最贴近目标流程
- 可复用现有持久化和 SSE 能力
- 改造边界清晰，适合渐进落地

缺点：

- 需要调整 `runtime.py`、`types.py`、状态 patch 结构
- 要补充新的测试合同

### 方案 C：重做为多代理流水线

做法：

- 独立实现 `Idea Parser`、`PRD Writer`、`Critic`、`Refiner`
- 每个代理单独输出结构化结果

优点：

- 概念最清晰
- 扩展潜力最高

缺点：

- 与当前代码差距太大
- 测试成本和维护成本最高
- 一次改造风险过高

### 推荐

采用方案 B。

原因：

- 当前仓库已经有可靠的状态版本、PRD 快照、回复版本、消息流骨架
- 方案 B 能在不推倒重来的前提下建立完整闭环
- 它最适合先把“自动出草稿 + 自动自审 + 持续 refine”做对

## 5. 目标工作流

新的后端主流程调整为：

```text
用户输入
  -> Idea Parser
  -> PRD Draft Builder
  -> Critic Review
  -> Reply Composer
  -> State / PRD / Decision Persistence
  -> SSE Assistant Reply
```

当用户继续回复后：

```text
用户补充信息
  -> Refine Integrator
  -> PRD Draft Update
  -> Critic Review
  -> Next Best Question
```

### 5.1 新的业务阶段

新增 `workflow_stage`，取值如下：

- `idea_parser`
- `prd_draft`
- `critic_review`
- `refine_loop`
- `finalize`

### 5.2 保留对话策略

保留 `conversation_strategy`，但其职责收窄为表达层策略，例如：

- `probe`
- `synthesize`
- `challenge`
- `confirm`

如果需要兼容当前实现，也可以在第一阶段继续沿用 `clarify / converge / confirm / choose`，但不能再让它承担业务阶段控制。

## 6. 数据结构设计

本次优先使用会话 `state` 承载新结构，先不引入新表。

### 6.1 IdeaParseResult

新增结构化对象：

```python
IdeaParseResult
- idea_summary: str
- product_type: str | None
- domain_signals: list[str]
- explicit_requirements: list[str]
- implicit_assumptions: list[str]
- open_questions: list[str]
- confidence: "high" | "medium" | "low"
```

用途：

- 从用户一句话输入中提取初始方向
- 支持后续 PRD Draft 生成
- 明确哪些是已知信息，哪些是推断

### 6.2 PrdDraftResult

新增结构化对象：

```python
PrdDraftResult
- version: int
- status: "draft_hypothesis" | "draft_refined" | "ready_for_finalize"
- sections: dict[str, dict[str, Any]]
- assumptions: list[str]
- missing_information: list[str]
- critic_ready: bool
```

关键约束：

- `version` 从 1 开始递增
- `status=draft_hypothesis` 表示当前仍是基于假设的草稿
- `sections` 必须支持“内容 + 来源 + 置信度”类信息

### 6.3 CriticResult

新增结构化对象：

```python
CriticResult
- overall_verdict: "pass" | "revise" | "block"
- strengths: list[str]
- major_gaps: list[str]
- minor_gaps: list[str]
- question_queue: list[str]
- blocking_questions: list[str]
- recommended_next_focus: str | None
- revision_instructions: list[str]
```

用途：

- 驱动下一轮问什么
- 判断是否允许进入 finalize
- 为回复层提供“结论 + 追问”来源

### 6.4 State 扩展字段

建议新增：

- `workflow_stage: str`
- `idea_parse_result: dict | None`
- `prd_draft: dict | None`
- `critic_result: dict | None`
- `refine_history: list[dict]`
- `finalization_ready: bool`

兼容已有字段：

- 当前 `target_user / problem / solution / mvp_scope` 可以继续保留
- 但它们转为 PRD 草稿的兼容快照，不再作为唯一流程驱动

## 7. 各阶段职责

### 7.1 Idea Parser

职责：

- 理解用户抛出的产品想法
- 判断产品类型和领域信号
- 抽取显式需求
- 推导工作假设
- 生成待补充问题

示例输入：

> 我想做一个在线 3D 图纸预览平台

示例输出方向：

- `product_type`: 在线 3D 图纸预览平台
- `domain_signals`: CAD、3D 预览、文件加载、浏览器渲染、协作分享
- `implicit_assumptions`: 可能涉及工程、制造、建筑或供应链协作
- `open_questions`: 格式支持、预览深度、权限模型、协作能力、性能要求

### 7.2 PRD Draft Builder

职责：

- 把 `IdeaParseResult` 组织成第一版 PRD 草稿
- 即使信息不充分，也输出可讨论的结构化文档
- 同时显式列出假设和缺口

关键要求：

- 用户一句话输入时也允许生成 `PRD v1`
- 必须明确“这是一版假设稿，不是确认稿”
- 不允许把推断伪装成已确认事实

### 7.3 Critic Review

职责：

- 审查当前草稿是否存在关键缺口
- 优先聚焦“产品方案细节”
- 产出可执行的追问队列

默认优先追问的问题类型：

- 支持哪些 3D / CAD 文件格式
- 只是预览，还是需要测量、剖切、标注、批注
- 用户是内部工程团队、外部客户还是供应链协作方
- 大文件加载和首屏速度要求
- 权限模型与分享边界
- 是否需要版本对比、审图流程、快照导出

### 7.4 Refine Loop

职责：

- 把用户新补充的信息合并回当前草稿
- 刷新 Critic 结论
- 再次输出唯一最高价值问题

关键要求：

- 每次只消费当前一个高优先级问题
- 每轮补充后 PRD 草稿版本递增
- 每轮都重新执行 Critic，而不是只在第一次执行

## 8. Critic 策略与卡口规则

### 8.1 默认风格

采用“双层模式”：

- 第一层：协作顾问型
- 第二层：关键缺口卡口型

### 8.2 Verdict 语义

- `pass`
  当前草稿足以进入 finalize 或确认
- `revise`
  当前草稿可以继续 refine，但不阻断整体推进
- `block`
  当前草稿命中关键缺口，不能 finalize

### 8.3 产品方案优先卡口

由于当前目标优先追“产品方案细节”，建议以下缺口视为关键项：

- 未明确核心文件格式
- 未明确核心使用者
- 未明确预览深度
- 未明确权限 / 协作边界

当上述 4 类中缺失 2 类及以上时：

- `overall_verdict = block`
- 不允许进入 `finalize`
- 必须生成对应 `blocking_questions`

## 9. 回复生成策略

`reply_composer.py` 不再只输出总结式模板，而是固定按以下结构组织：

1. 当前假设版 PRD 摘要
2. Critic 当前结论
3. 当前最关键缺口
4. 唯一下一问

回复原则：

- 不一次问多个问题
- 不输出泛化鼓励语
- 要明确说明“这轮为什么问这个”
- 问题必须来自 `critic_result.question_queue[0]`

示例表达：

```text
我先把当前理解整理成一版假设稿：这是一个面向需要在线查看 3D 图纸的团队协作平台，核心价值可能是免安装预览、跨角色共享和更快对齐图纸理解。

当前 Critic 判断是：这版草稿可以继续 refine，但产品方案层还有关键空洞。

我现在最缺的是你要支持到什么预览深度，因为“只看模型”和“需要测量、剖切、标注”会直接决定技术路线和 MVP 范围。

请你先回答一个问题：第一版只需要基础预览，还是必须支持测量、剖切、标注中的一部分？
```

## 10. 后端改造边界

### 10.1 `app/agent/types.py`

新增：

- `IdeaParseResult`
- `PrdDraftResult`
- `CriticResult`
- `WorkflowStage`

### 10.2 `app/agent/runtime.py`

从“单层规则运行时”升级为“工作流编排器”：

- 根据 `workflow_stage` 决定本轮执行哪个阶段函数
- 允许自动流转 `idea_parser -> prd_draft -> critic_review`
- 用户补充后走 `refine_loop -> critic_review`

### 10.3 `app/agent/understanding.py`

从“最小理解层”升级为 `Idea Parser`：

- 支持领域信号识别
- 支持显式需求 / 隐式假设 / 开放问题提取

### 10.4 `app/agent/extractor.py`

职责调整：

- 不再只负责当前缺失字段填充
- 支持把用户补充合并到 `prd_draft`
- 保留对已有四字段 patch 的兼容更新

### 10.5 `app/agent/decision_engine.py`

职责调整：

- 根据 `workflow_stage` 和 `critic_result` 选择下一步
- 不再只围绕四字段缺口做判断

### 10.6 `app/agent/reply_composer.py`

职责调整：

- 只负责按新合同输出结构化回复
- 回复必须受 `CriticResult` 驱动

### 10.7 `app/services/messages.py`

职责调整：

- 持久化新的 `workflow_stage`
- 合并 `idea_parse_result / prd_draft / critic_result`
- 保留现有 `state_version / prd_snapshot / assistant version` 持久化链路

## 11. 最小实现顺序

推荐按以下顺序落地：

### 第一步：补类型与状态字段

先新增：

- `workflow_stage`
- `idea_parse_result`
- `prd_draft`
- `critic_result`
- `refine_history`
- `finalization_ready`

目标：

- 先把状态空间建出来
- 不急着一次完成所有智能逻辑

### 第二步：打通最小闭环

让首次输入支持：

- `Idea Parser`
- `PRD v1`
- `Critic`
- 返回唯一下一问

目标：

- 用户一条输入后能看到完整闭环雏形

### 第三步：接入 refine 迭代

用户回答 Critic 问题后：

- 合并补充信息
- 生成 `PRD v2`
- 重新运行 Critic
- 再输出唯一下一问

### 第四步：加入 finalize 卡口

在关键缺口未补齐前：

- 不允许进入最终确认
- `overall_verdict=block`

## 12. 测试策略

### 12.1 运行时测试

新增覆盖：

- 用户一句话输入会生成 `IdeaParseResult`
- 用户一句话输入会生成 `PRD v1`
- `PRD v1` 后自动触发 `CriticResult`
- Critic 会产出 `question_queue`
- 回复只取 `question_queue[0]`

### 12.2 refine 测试

新增覆盖：

- 用户补充产品方案细节后，PRD 版本递增
- Critic 根据补充内容刷新 major gaps / blocking questions
- 同一轮不会同时追问多个问题

### 12.3 卡口测试

新增覆盖：

- 缺少关键产品方案信息时 `overall_verdict = block`
- 命中 block 时 `finalization_ready = false`
- 补齐关键方案信息后 verdict 可从 `block` 变为 `revise` 或 `pass`

### 12.4 消息服务测试

新增覆盖：

- 新状态字段被正确持久化
- `prd_snapshot` 能反映当前草稿内容
- 回复版本历史不被新工作流破坏

## 13. 验收标准

以如下输入作为主验收样例：

> 我想做一个在线 3D 图纸预览平台

系统必须做到：

1. 不直接停在四字段收集
2. 自动生成“假设版 PRD v1”
3. 自动产出 Critic 结论
4. 明确指出当前最关键产品方案缺口
5. 每轮只追问一个最高价值问题
6. 用户补充后可更新到 `PRD v2`
7. 每次更新后都重新执行 Critic
8. 在关键方案缺口未补齐前不能 finalize

## 14. 风险与后续演进

### 风险 1：旧四字段逻辑与新工作流并存导致状态冲突

缓解：

- 第一阶段保留兼容字段，但明确 `workflow_stage` 为主驱动
- 测试覆盖旧字段与新草稿的同步关系

### 风险 2：Critic 问题质量不稳定

缓解：

- 第一阶段先以规则优先，聚焦产品方案问题模板
- 后续再逐步引入更强的模型驱动

### 风险 3：回复过长、过像总结，不够像真实追问

缓解：

- 回复合同固定为“摘要 + verdict + 唯一问题”
- 明确限制只允许输出一个下一问

### 后续演进

本设计落地后，可以继续扩展：

- 行业特定产品模板
- 更细的 Critic 维度，例如商业可行性、需求真实性、技术约束
- 更完整的结构化 PRD schema
- 前端显示“假设 / 已确认 / 缺口 / 卡口”四类状态标签
