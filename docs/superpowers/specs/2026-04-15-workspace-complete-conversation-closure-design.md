# Workspace 对话完整闭环设计

## 1. 背景

当前 `apps/web/src/app/workspace` 对应的主业务链已经具备以下能力：

- 创建会话并自动带入首轮 idea
- 多轮消息流式回复
- 回复版本历史与重新生成
- `state / prd_snapshot / turn_decision` 持久化
- PRD Markdown 导出

但它仍然不是一个真正“完整闭环”的 PRD 工作流，核心问题有两个：

- 运行时只有“继续聊天”这条主链，没有真正接入 `refine -> 可终稿 -> 终稿确认 -> completed -> reopen`
- 前后端已经预埋了 `prd_draft / critic_result / finalization_ready / workflow_stage` 相关结构，但运行主链并没有稳定生产这些状态

这导致当前系统虽然能聊天、能沉淀 PRD、能导出，但用户还不能稳定地完成这条业务路径：

```text
新会话
  -> 多轮补充
  -> 形成实际 PRD 输出
  -> 满足可终稿门槛
  -> 用户明确确认
  -> 生成最终版 PRD
  -> 继续补充时自动 reopen
```

本次设计的目标不是重做整个对话架构，而是在当前代码骨架上把这条业务链真正打通。

## 2. 目标

本次设计只解决一个核心问题：

把 `workspace` 新会话升级成一个支持“草稿沉淀 -> 可终稿 -> 用户确认 -> 终稿生成 -> 自动 reopen”的完整 PRD 对话闭环。

本次范围内必须达成：

- 新会话对话轮次持续沉淀 `prd_draft`
- 系统只在达到业务门槛时进入 `finalize_ready`
- 只有“已有实际 PRD 输出，且用户明确确认”时才进入 `completed`
- 终稿后继续输入会自动 reopen 到编辑流
- 导出在 `completed` 时默认导出 finalized PRD
- 自动化测试可以证明上述链路成立

本次范围外暂不做：

- 旧会话自动迁移或补算历史状态
- 独立联网 critic agent
- 全新工作台 UI 架构
- 多模型并行推理或多 agent 流水线
- 额外新增复杂数据表

## 3. 关键业务约束

### 3.1 只有新会话保证完整闭环

本次改造只保证新会话进入新状态机。

旧会话：

- 继续能聊天
- 继续能导出
- 不强制补齐 `prd_draft / critic_result / finalization_ready`
- 不做历史状态重放

### 3.2 终稿必须满足两个条件

进入 `completed` 必须同时满足：

1. 已经存在实际 PRD 输出
2. 用户明确确认

这里的“明确确认”包括：

- 点击专门的“生成最终版 PRD”按钮
- 在对话中明确表达“确认 / 可以 / 就这样”等确认语义

### 3.3 可终稿门槛由业务规则决定

第一阶段不把“是否可以终稿”完全交给模型判断，而是以后端业务规则为准。

最低门槛固定为：

- 核心 4 段必须都有内容：
  - `target_user`
  - `problem`
  - `solution`
  - `mvp_scope`
- 扩展段必须同时具备：
  - `constraints`
  - `success_metrics`
- 且已形成实际 `prd_draft`

### 3.4 终稿后默认自动 reopen

当会话已处于 `completed`，用户继续输入实质修改内容时：

- 不要求用户手动点击 reopen
- 系统自动回到编辑流
- 状态从 `completed` 切回 `refine_loop`

## 4. 方案对比

### 方案 A：继续把终稿逻辑塞进 `pm_mentor`

做法：

- 继续让 `pm_mentor` 同时负责收集、判定、终稿
- 通过扩充 LLM 输出直接补 `prd_draft / critic_result / finalization_ready`

优点：

- 改动最小
- 首期最快

缺点：

- 职责继续糊在一个模型输出里
- 后续很难把 critic 独立出来
- 状态可信度仍然高度依赖模型

### 方案 B：直接重构成显式三阶段

做法：

- `pm_mentor` 只负责收集和草稿推进
- `critic` 独立负责是否可终稿
- `finalize_flow` 独立负责最终版生成

优点：

- 架构最清晰
- 长期维护最好

缺点：

- 首期改动面过大
- 前后端、测试、状态管理都要一起重整

### 方案 C：首期快速闭环，边界按未来三阶段设计

做法：

- 保持一次请求内主链不变
- `pm_mentor` 继续负责草稿推进
- 新增规则型 `readiness evaluator`
- 正式接入 `finalize_flow`
- 前后端状态、接口、测试全部按未来可拆分 critic 的边界设计

优点：

- 能最快打通完整闭环
- 不需要首期引入独立 critic 模型
- 后续可平滑升级成显式三阶段

缺点：

- 第一阶段仍然是“单请求内多职责编排”
- readiness evaluator 与未来 critic 会有一轮替换成本

### 推荐

采用方案 C。

原因：

- 它满足“先完整闭环”的交付目标
- 可终稿门槛本身更适合先用业务规则兜底
- 它最适合在当前仓库基础上做低风险增量改造

## 5. 目标状态机

新的新会话生命周期收敛为 4 个明确状态：

- `idea_parser`
  - 会话刚创建或信息很少
  - 不允许出现终稿确认入口
- `refine_loop`
  - 已经进入结构化草稿持续沉淀阶段
  - 每轮会更新 `prd_draft` 与 `prd_snapshot`
- `finalize_ready`
  - 已满足业务门槛
  - 前端出现明确的“生成最终版 PRD”动作
  - 但还不算终稿
- `completed`
  - 用户已明确确认
  - 已生成 finalized PRD
  - 导出默认导出终稿
  - 继续输入会自动 reopen

状态迁移如下：

```text
idea_parser
  -> refine_loop
  -> finalize_ready
  -> completed

completed
  -> refine_loop   (用户继续补充或修改)
```

第一阶段保持 `workflow_stage` 这个字段名不变，但规范其语义：

- `idea_parser`
- `refine_loop`
- `finalize`
- `completed`

其中：

- `finalize` 等价于“已满足可终稿条件”
- 前端展示文案对应为“可整理终稿”

## 6. 后端职责边界

### 6.1 `agent/runtime.py`

`runtime` 只做状态路由与边界分发，不直接决定终稿内容。

目标分支：

- `completed + 实质修改输入` -> 自动 reopen -> 回到 `refine_loop`
- `completed + 非修改类输入` -> 返回完成态引导
- `finalize_ready + 明确确认语义` -> 走 finalize
- `greeting / fallback` -> 保持现状
- 其他 -> 交给 `pm_mentor`

### 6.2 `agent/pm_mentor.py`

`pm_mentor` 首期继续是主要对话模型，但职责收窄为：

- 生成本轮 `reply`
- 生成 `suggestions / recommendation / next_best_questions`
- 生成 `prd_patch`
- 生成普通 `state_patch`

它不再直接把 `workflow_stage` 写成 `completed`。

### 6.3 新增 `agent/readiness.py`

新增规则型 readiness evaluator，职责只有一个：

判断“当前草稿是否已经达到可终稿门槛”。

建议输出：

- `is_ready_for_finalize: bool`
- `missing_requirements: list[str]`
- `readiness_summary: str`
- `critic_result: dict`

第一阶段完全规则化，不依赖模型。

### 6.4 正式接入 `agent/finalize_flow.py`

`finalize_flow` 负责：

- 识别用户确认偏好
- 基于当前 `prd_draft` 生成 finalized sections
- 写入 finalized `prd_draft`
- 切换到 `completed`

它支持两种入口：

- 按钮触发 finalize
- 对话确认语义触发 finalize

### 6.5 `services/message_state.py`

统一负责状态装配与持久化前的标准化，不让持久化层知道太多业务语义。

需要支持 3 类写入：

- `refine_loop`：普通对话推进草稿
- `finalize_ready`：满足业务门槛，写入 `finalization_ready=True`
- `completed`：写入 finalized `prd_draft`

### 6.6 `services/messages.py`

继续负责消息流式主链：

- 新消息
- 重生成
- SSE 事件输出

但 finalize 不再塞进消息服务里。

### 6.7 新增 `services/finalize_session.py`

新增 finalize service，职责：

- 校验当前 session 是否允许 finalize
- 调用 `finalize_flow`
- 写新 state version / prd snapshot
- 返回 finalize 结果或最新 snapshot

## 7. API 设计

### 7.1 保留现有接口

- `POST /api/sessions/{id}/messages`
- `POST /api/sessions/{id}/messages/{msg_id}/regenerate`
- `GET /api/sessions/{id}`
- `POST /api/sessions/{id}/export`

### 7.2 新增 finalize 接口

新增：

- `POST /api/sessions/{session_id}/finalize`

建议 payload：

```json
{
  "confirmation_source": "button",
  "preference": "balanced"
}
```

其中：

- `confirmation_source`: `button | message`
- `preference`: `balanced | business | technical | null`

### 7.3 Session Snapshot 作为前端唯一真相源

`GET /api/sessions/{id}` 必须稳定返回：

- `workflow_stage`
- `prd_draft`
- `critic_result`
- `finalization_ready`
- `prd_snapshot`
- `messages`
- `assistant_reply_groups`
- `turn_decisions`

前端不应自己猜测业务状态。

## 8. 前端设计

### 8.1 `workspace-store`

补充显式业务状态：

- `workflowStage`
- `isFinalizeReady`
- `isCompleted`

`prd.meta` 保留，但作为展示层派生信息，不作为按钮显隐的唯一依据。

### 8.2 `PrdPanel`

右侧 PRD 区负责表达“当前产物状态”：

- `refine_loop` -> 显示“草稿中”
- `finalize_ready` -> 显示“可整理终稿”并出现主按钮 `生成最终版 PRD`
- `completed` -> 显示“已生成终稿”，并提示继续输入会 reopen

### 8.3 `AssistantTurnCard`

主对话区负责表达“当前对话动作语义”：

- `finalize_ready` 时出现终稿确认主动作
- `completed` 时出现已完成提示与 reopen 说明

### 8.4 `Composer`

继续保持单一输入模式，不新增复杂交互分支。

当会话处于 `completed` 时：

- 用户继续输入照常发送
- 前端不自行判断 reopen
- 以后端 snapshot 返回的最新状态为准

### 8.5 左侧导出入口保持不变

左侧栏继续保留 `导出 PRD` 按钮。

差异只在导出内容：

- `refine_loop / finalize_ready` 导出草稿
- `completed` 导出终稿

## 9. 数据与持久化策略

第一阶段不新增新表，继续复用当前：

- `project_state_versions`
- `prd_snapshots`
- `conversation_messages`
- `assistant_reply_groups`
- `assistant_reply_versions`
- `agent_turn_decisions`

状态承载原则：

- `prd_snapshot` 继续表示当前工作快照
- `prd_draft` 表示结构化草稿或终稿候选
- `critic_result` 表示可终稿判定结果
- `workflow_stage` 表示当前业务阶段
- `finalization_ready` 表示当前是否已达到可确认门槛

## 10. 导出策略

导出保持现有原则，但将语义正式化：

- `completed` 时优先导出 finalized `prd_draft`
- 非 `completed` 时优先导出当前 `prd_draft`
- 若无 `prd_draft`，则回退 `prd_snapshot`

这样前后端与导出视图保持一致：

- 聊天看到什么阶段
- PRD 面板看到什么阶段
- 导出得到什么版本

三者必须一致

## 11. 测试设计

### 11.1 后端单元测试

必须补充：

- readiness evaluator 规则测试
- finalize_flow 测试
- completed 后 reopen 测试
- completed / 非 completed 导出版本测试

### 11.2 后端服务/接口测试

必须覆盖：

- 新会话进入 `refine_loop`
- 多轮消息后进入 `finalize_ready`
- `POST /finalize` 后进入 `completed`
- `completed` 后继续发消息自动 reopen
- 导出在不同状态下返回正确内容

同时必须先修复：

- `apps/api/tests/test_messages_service.py` 当前收集阶段的缩进错误

### 11.3 前端状态测试

必须覆盖：

- `PrdPanel` 在 3 个阶段下的 badge 与按钮显隐
- `AssistantTurnCard` 的 finalize action 展示
- `workspace-store` 对 finalize 后 snapshot 的消费
- `Composer` 在 completed 后继续输入的 reopen 行为

### 11.4 端到端验收路径

至少固定 3 条主路径：

1. 创建新会话 -> 多轮补充 -> 可终稿 -> 点击按钮生成最终版 -> 导出终稿
2. 达到可终稿 -> 用户在对话中明确说“可以，就这样” -> 进入终稿
3. 已生成终稿 -> 用户继续补充修改 -> 自动 reopen -> 导出重新变为草稿

## 12. 验收标准

只有以下 6 条同时成立，才算“workspace 对话完整闭环”完成：

- 新会话能稳定沉淀 `prd_draft`
- 只有满足业务门槛时才进入 `finalize_ready`
- 只有用户明确确认时才进入 `completed`
- `completed` 后导出的是终稿
- `completed` 后继续输入会自动 reopen
- 以上链路有可运行的自动化测试覆盖

## 13. 风险与控制

### 风险 1：模型继续错误地提前结束流程

控制：

- 去掉 `pm_mentor` 直接写 `completed` 的权限
- 终稿阶段统一由 readiness evaluator + finalize_flow 控制

### 风险 2：前端 badge 文案与后端真实状态不一致

控制：

- 前端从 snapshot 中读取显式状态
- 不再只靠派生文案判断

### 风险 3：终稿后 reopen 造成用户困惑

控制：

- `completed` 状态下在 PRD 区和对话区都明确提示：
  “继续输入会重新打开编辑流程”

### 风险 4：旧会话兼容问题放大改造范围

控制：

- 第一阶段只保证新会话完整闭环
- 旧会话明确按兼容模式继续工作

## 14. 实施建议

实施顺序建议如下：

1. 修复测试链并补 readiness/finalize 单元测试
2. 接入后端状态机、readiness evaluator、finalize service
3. 补前端 finalize action 与显式状态消费
4. 跑通主链与 reopen 链
5. 最后补导出与回归测试

这样能保证每一步都能独立验证，不把风险堆到最后。
