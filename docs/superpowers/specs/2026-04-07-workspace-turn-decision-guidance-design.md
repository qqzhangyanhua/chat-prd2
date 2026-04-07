# Workspace 决策引导卡前端设计

## 1. 背景

`apps/api` 已经完成“强推进型 AI 产品经理”后端第一阶段增强：

- 每轮会持久化 `turn_decisions`
- 决策中包含 `conversation_strategy`、`strategy_reason`、`next_best_questions`
- 会话快照接口 `GET /api/sessions/{id}` 已可返回面向前端消费的 `turn_decisions`
- 回复正文已经升级为“判断 + 假设 + 建议 + 待确认 + 下一步动作”的协议

但 `apps/web` 目前仍主要展示：

- 助手自然语言回复
- `currentAction`
- PRD 面板
- 回复版本历史

前端还没有把“这一轮 AI 为什么这样推进、建议用户下一步怎么回答”显式展示出来。结果是：

- 用户能看到回复内容，但不容易理解 AI 当前处于什么推进阶段
- 用户不知道下一步该怎么确认，容易只回“继续”“可以”“确认”
- 后端虽然已经具备 PM 决策结构，前端仍然像普通聊天界面

本次设计要解决的问题不是重做整个工作台，而是在现有界面里把“AI 正在稳定推进决策”这件事清晰地展示出来。

## 2. 目标

本次范围内必须达成：

- 前端可消费会话快照中的 `turn_decisions`
- 用户能看到当前会话最近一轮的推进策略和推进原因
- 用户能看到 2 到 4 个推荐下一问/快捷回答
- 点击推荐项只填入输入框，不自动发送
- 交互与现有聊天流兼容，不打断消息、重生成、版本历史等能力

本次范围外暂不做：

- 独立侧边栏式“AI 驾驶舱”
- 完整决策时间线回放
- 对历史每轮 `turn_decisions` 的可视化浏览
- 根据阶段动态切换复杂视觉组件

## 3. 设计原则

### 3.1 先增强推进感，再增强信息密度

当前首要目标是让用户知道“现在应该怎么继续”，而不是一次性暴露所有审计信息。

### 3.2 复用现有结构，避免重排主界面

优先复用当前 `assistant-turn-card`、store hydrate 流程和 `setInputValue(...)` 输入填充机制，避免引入新的布局主轴。

### 3.3 只强调最新决策，不铺开全部历史

本轮只展示“最新有效推进建议”，避免历史建议同时出现造成用户分心。

### 3.4 建议必须可执行

推荐项不是泛化标签，而是用户可以直接点击并继续编辑的具体句子或问题。

## 4. 方案对比

### 方案 A：在助手回复卡中嵌入“决策引导卡”

做法：

- 在当前助手回复卡中增加一块轻量“下一步建议”区域
- 展示当前阶段、推进原因、推荐下一问按钮
- 点击按钮调用 `setInputValue(...)`

优点：

- 改动最小，最快能上线验证
- 与当前阅读路径一致，用户不需要学习新区域
- 可以直接复用现有助手卡片和选项点击填充输入框的模式

缺点：

- 决策历史感较弱
- 结构上更偏“当前推进器”，不偏“完整驾驶舱”

### 方案 B：在会话区域顶部增加固定“AI 驾驶舱”

做法：

- 在消息列表顶部增加独立卡片
- 固定显示当前策略、风险、建议和下一步动作

优点：

- 产品感更强，像持续控盘的 AI 合伙人
- 决策信息和聊天内容分区更清楚

缺点：

- 会影响现有布局和移动端阅读节奏
- 用户视线可能在驾驶舱和消息流之间来回切换

### 方案 C：为每轮消息增加完整“决策时间线”

做法：

- 每条助手消息都挂载决策面板
- 支持回看 `judgement / assumptions / options / confirm / next_step`

优点：

- 最完整，适合后续复盘与审计
- 可以充分呈现后端结构化决策价值

缺点：

- 信息量大，实现成本高
- 当前阶段容易让用户觉得系统过重

### 推荐

采用方案 A。

原因：

- 用户当前最明确的反馈是“要多给建议，不然用户不知道下一步怎么确认”
- 方案 A 最直接回应这个痛点，且不会引入额外认知负担
- 当前前端已有点击选项填入输入框的现成机制，落地成本最低
- 后续如果验证有效，可平滑升级为方案 B 或 C，而无需推翻数据结构

## 5. 目标交互

用户在当前会话中看到一条助手回复时，除正文外，还会看到一个轻量引导区：

- 阶段标签：如 `澄清中`、`取舍中`、`收敛中`、`确认中`
- 推进原因：用一句话解释“为什么现在建议这样聊”
- 推荐下一问：2 到 4 个可点击按钮

按钮点击后：

- 将推荐问题或回答模板填入输入框
- 保留用户编辑权
- 不直接触发发送

如果当前快照里没有可用 `turn_decisions` 或缺少 `next_best_questions`：

- 不展示该引导区
- 保持现有界面行为不变

## 6. 数据设计

### 6.1 前端类型扩展

在 `apps/web/src/lib/types.ts` 中新增：

- `AgentTurnDecision`
- `AgentTurnDecisionSection`

并扩展 `SessionSnapshotResponse`：

- 增加 `turn_decisions?: AgentTurnDecision[]`

类型至少要覆盖以下字段：

- 决策 ID、会话 ID、消息 ID、创建时间
- `conversation_strategy`
- `decision_sections`
- 每个 section 的 `key`、`title`、`content`
- `meta` 中的 `strategy_label`、`strategy_reason`、`next_best_questions`

### 6.2 Store 派生模型

在 `apps/web/src/store/workspace-store.ts` 中新增面向 UI 的轻量结构，例如：

- `latestTurnDecision`
- 或 `decisionGuidance`

它不需要完整复制后端审计数据，只保留当前展示所需字段：

- `conversationStrategy`
- `strategyLabel`
- `strategyReason`
- `nextBestQuestions`

派生规则：

- 优先使用最新一条 `turn_decisions`
- 如果缺失，返回 `null`
- 如果 `nextBestQuestions` 为空数组，也视为“不展示引导卡”

### 6.3 Hydrate 规则

`hydrateSession(snapshot)` 需要同时处理：

- `messages`
- `assistant_reply_groups`
- `prd_snapshot`
- `turn_decisions`

其中 `turn_decisions` 只需落成 UI 可直接消费的派生数据，不要求前端完整保留所有原始审计字段。

## 7. 组件设计

### 7.1 推荐挂载点

优先放在 `apps/web/src/components/workspace/assistant-turn-card.tsx` 中，原因是：

- 当前助手回复、重生成、版本历史都集中在这里
- 用户看完回复后，最自然的下一步就是看“建议怎么继续”
- 可避免在 `conversation-panel` 中引入额外跨组件编排

### 7.2 卡片结构

建议在现有“展开 AI 深度分析及推理”区域之前或其中增加一块轻量区：

- 上方一行阶段标签
- 中间一段推进原因
- 下方 2 到 4 个按钮式建议

视觉要求：

- 延续当前 `stone / amber` 视觉体系
- 比主回复弱一级，但要明显可点击
- 不做过重的面板堆叠，避免卡片显得过高

### 7.3 阶段文案映射

前端对 `conversation_strategy` 做稳定映射：

- `clarify` -> `澄清中`
- `choose` -> `取舍中`
- `converge` -> `收敛中`
- `confirm` -> `确认中`

如果后端已提供 `strategy_label`，优先使用后端值；前端映射作为兜底。

## 8. 交互与状态流

### 8.1 初始化加载

会话快照加载完成后：

- store 解析 `turn_decisions`
- 生成 `decisionGuidance`
- 助手卡读取并展示

### 8.2 点击推荐项

按钮点击时：

- 调用 `workspaceStore.getState().setInputValue(question)`
- 仅写入输入框
- 不改变当前流式状态
- 不自动提交请求

### 8.3 多轮更新

用户发送新消息并收到新会话快照后：

- 旧 guidance 被最新 guidance 覆盖
- 不保留多个“当前建议卡”
- 让界面始终只表达“现在最建议你做什么”

## 9. 异常与降级

需要考虑以下情况：

- `turn_decisions` 缺失：完全降级为当前界面
- `decision_sections` 结构不完整：尝试从顶层字段派生，否则隐藏
- `strategy_reason` 缺失：允许只展示阶段标签和推荐项
- `next_best_questions` 为空：不展示按钮区，必要时整个引导卡隐藏

原则是：

- 不因为决策数据缺失而影响主聊天流
- 不展示半残缺、会误导用户的建议区

## 10. 测试策略

本次至少补齐三类测试。

### 10.1 类型与 Store 测试

验证 `hydrateSession()` 能正确：

- 读取 `turn_decisions`
- 生成最新 guidance
- 在无数据时返回空态

### 10.2 组件测试

验证助手卡在存在 guidance 时会展示：

- 阶段标签
- 推进原因
- 推荐按钮

并验证按钮点击会把内容写入输入框。

### 10.3 回归测试

验证以下能力不受影响：

- 无 `turn_decisions` 时页面仍正常渲染
- 重生成和版本历史仍可使用
- 输入框已有内容时，点击推荐项会按当前既有逻辑覆盖写入

## 11. 实施边界

本次实现应控制在以下文件范围内：

- `apps/web/src/lib/types.ts`
- `apps/web/src/store/workspace-store.ts`
- `apps/web/src/components/workspace/assistant-turn-card.tsx`
- 视需要小幅调整 `apps/web/src/components/workspace/conversation-panel.tsx`
- 对应测试文件

不在本次范围内：

- 新建复杂全局布局
- 改造消息列表渲染模型
- 为决策结构新增动画流程图或多层折叠树

## 12. 后续演进建议

如果这一版验证用户确实更愿意沿着推荐项继续表达，下一阶段建议按顺序增强：

1. 在顶部增加“当前阶段 + 当前目标”固定提示
2. 支持展示最近 2 到 3 轮决策摘要，而不是只看最新一轮
3. 将“当前判断 / 关键假设 / 建议方案 / 待确认项 / 下一步动作”映射为更完整的可视区块

这样可以保持当前版本足够轻，同时为后续“AI 驾驶舱”升级预留清晰路径。
