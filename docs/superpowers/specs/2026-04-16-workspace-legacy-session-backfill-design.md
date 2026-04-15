# Workspace 旧会话按需补算设计

## 1. 背景

截至当前版本，`workspace` 新会话已经具备完整 PRD 对话闭环：

- `idea_parser -> refine_loop -> finalize -> completed`
- `finalization_ready / prd_draft / critic_result / workflow_stage` 已成为显式真相源
- `completed` 后继续输入可自动 reopen
- 导出会跟随草稿 / 终稿状态切换

但这套闭环当前只保证新会话成立。旧会话仍然停留在兼容模式：

- 可以继续聊天
- 可以继续导出
- 但不保证存在 `workflow_stage / prd_draft / critic_result / finalization_ready`

这带来两个问题：

1. 前端虽然已经全面切到显式状态消费，但旧会话打开时仍可能缺失关键字段。
2. 同一条旧会话如果继续使用新工作台逻辑，会出现“新前端消费旧状态”的语义断层。

因此，下一阶段需要在不扩大改造范围的前提下，为旧会话补上最小必要的显式闭环状态。

## 2. 目标

本次设计只解决一个问题：

为旧会话提供“打开时按需补算”的兼容升级能力，让旧会话第一次进入工作台时，就能被补成可被当前前后端稳定消费的显式闭环状态。

本次范围内必须达成：

- 旧会话在打开单个 session 时，若缺失显式闭环字段，自动触发补算
- 补算结果写回数据库，而不是只在本次读取临时计算
- 补算后旧会话至少拥有：
  - `workflow_stage`
  - `prd_draft`
  - `critic_result`
  - `finalization_ready`
- 旧会话补算后，最多只能进入 `finalize`
- 旧会话绝不能被直接补算成 `completed`
- 补算失败不阻断继续聊天和导出

本次范围外暂不做：

- 后台批量迁移历史 session
- 打开列表页时批量扫描并补算
- 基于历史消息重放整条 agent 链
- 自动把旧会话补成 `completed`
- 额外新增数据库表

## 3. 关键业务约束

### 3.1 触发时机限定在单会话读取

旧会话补算只在读取单个 session snapshot 时触发。

不在以下位置触发：

- session 列表
- workspace 首页
- 后台批量任务

这样可以把写操作控制在最小范围内，避免把“兼容修复”扩散成全局迁移任务。

### 3.2 旧会话不能被直接补成 completed

即使旧会话当前内容已经足够完整，也最多只能补算到：

- `workflow_stage = "finalize"`
- `finalization_ready = True`

不能直接补成：

- `workflow_stage = "completed"`

原因是 `completed` 在现有业务定义里必须满足：

1. 已存在实际终稿输出
2. 用户做过明确确认

旧会话的历史数据里通常缺少这条“明确确认”的可靠证据，因此不允许通过推断直接进入完成态。

### 3.3 补算必须落库

旧会话补算结果必须写回数据库，而不是每次读取时临时重算。

原因：

- 前端后续行为依赖稳定真相源
- 同一会话重复读取不应得到不一致结果
- 后续 reopen / finalize / 导出都需要基于同一份补算后 state 持续推进

### 3.4 不能依赖历史消息重放

本次补算不重放历史消息，也不重新调用 `pm_mentor`。

补算只基于已有静态快照推导，包括：

- 旧 state 中已有的 `prd_draft`
- 旧 state 中已有的 `prd_snapshot`
- 最新 `prd_snapshot` 持久化结果

这样可以避免：

- 引入额外模型依赖
- 让旧会话升级结果受模型漂移影响
- 把兼容问题扩展成完整再生成任务

## 4. 方案对比

### 方案 A：读取时临时补算，不落库

做法：

- `get_session_snapshot()` 检测到旧会话缺显式字段时，临时构造兼容状态返回给前端
- 不写入新的 `state_version`

优点：

- 改动最小
- 实现最快

缺点：

- 每次读取都重复推断
- 同一会话的行为状态不稳定
- reopen / finalize / 导出后续仍会遇到状态断层

### 方案 B：`get_session_snapshot()` 按需调用独立 backfill service，并写回数据库

做法：

- 读取 snapshot 时检查是否缺显式闭环字段
- 若缺失，则调用独立的 `legacy session backfill service`
- service 负责推导状态并写入新的 `state_version / prd_snapshot`
- 然后返回补算后的最新 snapshot

优点：

- 前端无感接入
- 职责清晰，易于测试
- 后续可平滑扩展成后台批量修复或管理端修复工具

缺点：

- 比直接塞进 `sessions.py` 多一层编排

### 方案 C：前端检测旧会话后，主动调用“升级会话”接口

做法：

- `GET /sessions/{id}` 先返回旧结构
- 前端发现字段缺失，再调用一个显式升级接口

优点：

- 读写边界最清晰

缺点：

- 前端协议更复杂
- 页面会经历“先旧后新”的一次跳变
- 工作台兼容逻辑泄漏到前端

### 推荐

采用方案 B。

原因：

- 它保持前端无感
- 它能把兼容升级稳定落库
- 它把旧会话补算收敛成一个后端独立能力，而不是继续把逻辑糊进 session 读取函数

## 5. 目标行为

### 5.1 触发条件

当用户打开某个 session 时：

1. 读取最新 state
2. 判断是否属于旧会话兼容形态
3. 如果缺少显式闭环字段，则触发一次补算
4. 补算成功后返回补算后的最新 snapshot
5. 如果已经补算过，则直接返回，不重复写库

### 5.2 补算输入源优先级

补算时的数据来源优先级如下：

1. 旧 state 中的 `prd_draft.sections`
2. 旧 state 中的 `prd_snapshot.sections`
3. 最新持久化 `prd_snapshot.sections`

补算目标不是“重新理解用户历史”，而是“把已有结构化产物恢复成显式闭环状态”。

### 5.3 补算结果

补算至少要生成以下字段：

- `prd_draft`
- `critic_result`
- `finalization_ready`
- `workflow_stage`

补算结果规则：

- 如果 readiness 不满足：
  - `workflow_stage = "refine_loop"`
  - `finalization_ready = False`
- 如果 readiness 满足：
  - `workflow_stage = "finalize"`
  - `finalization_ready = True`

无论哪种情况：

- 都不能生成 `workflow_stage = "completed"`

### 5.4 补算后的用户感知

用户第一次打开旧会话后，体验应当是：

- 如果内容还不够完整：
  - 会话显示为“草稿中”
  - 可以继续 refinement
- 如果内容已经足够完整：
  - 会话显示为“可整理终稿”
  - 用户仍需重新确认，才能进入 `completed`

这保证了旧会话不会因为历史内容完整，就被系统擅自宣告“已完成”。

## 6. 后端职责边界

### 6.1 新增 legacy backfill service

建议新增独立 service，例如：

- `apps/api/app/services/legacy_session_backfill.py`

职责：

- 判断当前 session 是否需要补算
- 从旧 state / snapshot 中提取可用 section
- 构造兼容态 `prd_draft`
- 调用 readiness evaluator
- 生成新的显式 state
- 持久化新的 `state_version` 与 `prd_snapshot`

### 6.2 `sessions.py` 只负责按需编排

`get_session_snapshot()` 本身不直接承载补算细节。

它只做：

1. 获取 session 与 latest state
2. 如果需要补算，则调用 legacy backfill service
3. 再读取最新 snapshot 返回

这样可以保持读取服务的职责清晰。

### 6.3 readiness 继续复用现有规则

旧会话补算不引入新的 ready 判定标准。

直接复用现有 `evaluate_finalize_readiness(...)`：

- 保证新旧会话进入 `finalize` 的门槛一致
- 避免形成两套 finalize 规则

### 6.4 补算必须生成新的 state version

补算不能原地覆盖旧 state。

必须：

- 新建一条 `state_version`
- 新建对应版本的 `prd_snapshot`

这样可以保留：

- 审计链
- 回滚可能性
- 与现有 `state_version -> prd_snapshot` 语义一致

## 7. 数据结构建议

### 7.1 补算标记

建议在补算后的 state 中写入轻量标记：

- `legacy_backfill_version = "closure_v1"`

作用：

- 防止重复补算
- 为后续升级策略留版本位

### 7.2 `prd_draft` 最小合同

补算生成的 `prd_draft` 至少应包含：

- `version`
- `status`
- `sections`

其中：

- 若 readiness 不满足，`status` 设为草稿态
- 若 readiness 满足，`status` 设为可终稿对应草稿态，但不设为 `finalized`

## 8. 失败处理

### 8.1 回滚策略

如果补算过程中任何一步写库失败：

- 整个补算事务回滚
- 不写入半成品 state

### 8.2 对用户的影响

补算失败时：

- 不阻断用户继续打开会话
- 不阻断继续聊天
- 不阻断导出

系统应直接返回原始快照，让旧会话继续以兼容模式工作。

### 8.3 可观测性

补算失败必须记录日志，至少包含：

- `session_id`
- 失败阶段
- 异常信息

便于后续统计哪些旧会话无法自动升级。

## 9. 测试策略

### 9.1 后端单测

必须覆盖：

- 旧会话缺显式字段时，会触发一次补算
- readiness 不足时补成 `refine_loop`
- readiness 满足时补成 `finalize`
- 已补算过的旧会话不会重复生成新版本
- 旧会话不会被直接补成 `completed`
- 补算失败时会回滚并返回原始快照

### 9.2 后端集成测试

必须覆盖：

- 打开 legacy session 时，返回的是补算后的 snapshot
- 补算后的旧会话还能继续 finalize
- 补算后的旧会话导出语义正确
- 补算后的旧会话 reopen 语义继续成立

### 9.3 前端回归

前端只补最小必要回归：

- 打开 legacy session 后，store 能稳定消费补算后的：
  - `workflow_stage`
  - `finalization_ready`
  - `prd_draft`

## 10. 风险与控制

### 风险 1：旧 snapshot 信息不足，导致补算质量不稳定

控制：

- 不做消息重放
- 只使用已有结构化 sections
- 若信息不足，宁可退回 `refine_loop`，也不强推到 `finalize`

### 风险 2：补算逻辑与新会话规则分叉

控制：

- 统一复用 readiness evaluator
- 不新增旧会话专属 finalize 门槛

### 风险 3：读取接口引入写操作，放大副作用

控制：

- 只在单 session 读取时触发
- 只在缺少显式闭环字段时触发
- 加补算标记，确保幂等

### 风险 4：旧会话被错误补成完成态

控制：

- 明确禁止补算成 `completed`
- `completed` 仍然只允许通过显式 finalize 确认进入

## 11. 结论

本次旧会话兼容升级的推荐方案是：

- 在 `get_session_snapshot()` 中按需触发
- 由独立 `legacy session backfill service` 负责补算
- 补算结果写回数据库
- 旧会话最多补到 `finalize`
- 绝不直接补成 `completed`

这样可以在不扩大全局改造范围的前提下，把旧会话升级到“可被当前闭环稳定消费”的状态，同时继续守住“completed 必须来自真实确认”这条核心业务规则。

## 12. 实施结果补充

已实现：

- 打开单个 `workspace session` 时按需检测 legacy state，并补算显式闭环字段
- 补算结果写入新的 `state_version` 与 `prd_snapshot`
- readiness 不足时补到 `refine_loop`
- readiness 满足时最多补到 `finalize`
- legacy 会话补算后仍需显式 finalize 确认，绝不会直接进入 `completed`
- 补算写库失败时回滚，并继续返回原始兼容 snapshot

未实现：

- 后台批量迁移历史 session
- 列表页批量扫描补算
- 基于历史消息重放 agent 链
- 自动将 legacy session 推进到 `completed`
