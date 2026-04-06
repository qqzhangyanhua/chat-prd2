# Workspace 重生成版本历史设计

## 背景

当前工作区的“重新生成”只是前端行为：

1. 前端把上一条 assistant 消息从当前内存态里移除。
2. 前端重放上一条 `lastSubmittedInput`，再次调用 `POST /api/sessions/{session_id}/messages`。
3. 前端为了避免当前页面重复显示 user message，会在 store 层跳过 regenerate 场景下的 user 气泡追加。

这套实现有两个核心问题：

1. 后端并不知道这是 regenerate，每次都会新建一条 user message。
2. 当前页里看起来没有重复 user message，但刷新或恢复会话后，数据库中的重复 user turn 仍可能重新出现。

同时，现有对话协议只显式支持：

1. `message.accepted`
2. `action.decided`
3. `assistant.delta`
4. `assistant.done`

它并没有把“同一条 user message 的多个 assistant 版本”建模为正式会话数据。

## 目标

本次设计需要满足以下目标：

1. 将 regenerate 升级为后端显式语义，而不是再次发送同一条用户输入。
2. 同一条 user message 下允许存在多个 assistant 回复版本。
3. 主界面默认只展示 latest assistant version。
4. 用户通过弹层查看该轮的全部 regenerate 历史版本。
5. 版本历史需要持久化，刷新、恢复会话、跨设备后仍可见。
6. 后续继续发送消息时，永远基于 latest assistant version 继续。
7. 旧版本只读查看，不参与后续上下文。
8. 版本生成过程需要保留 action、模型信息、state、PRD 快照等可追溯数据。

## 非目标

本次不包含以下范围：

1. 不支持从旧版本分叉出新的独立对话分支。
2. 不支持在主时间线中直接展开所有历史版本。
3. 不支持版本 diff、高亮差异或版本比对视图。
4. 不支持用户手动将旧版本重新设为 latest。
5. 不改变“继续补充”输入框的主位置和主流程结构。

## 方案对比

### 方案 A：显式引入 reply group + reply version 建模

内容：

1. 每条 user message 对应一个 assistant reply group。
2. group 下保存多个 assistant reply version。
3. group 维护一个 `latest_version_id`。
4. 主时间线只显示 latest，历史版本在弹层查看。

优点：

1. 产品语义最清晰。
2. regenerate 不再伪装成“再次发送用户消息”。
3. 后续继续对话时，上下文拼装规则稳定。
4. 便于导出、审计、回放和测试。

缺点：

1. 需要新增数据模型和接口。
2. 前后端都要补一层版本组织结构。

### 方案 B：继续使用消息表，但给 assistant 消息补充版本字段

内容：

1. 仍以 `conversation_messages` 为中心。
2. 给 assistant message 增加 `parent_user_message_id`、`revision_no`、`is_latest`。

优点：

1. 初期改动比方案 A 更小。

缺点：

1. 数据语义分散。
2. 查询一轮历史版本时需要依赖额外约定拼装。
3. 后续演进成正式版本系统时会越来越别扭。

### 方案 C：把历史版本塞进 assistant message 的 `meta`

优点是实现很快。

缺点：

1. 核心会话数据落在非结构化字段里。
2. 查询、导出、过滤、测试都不稳定。
3. 后续很难继续扩展。

### 结论

采用方案 A。

原因：

1. 本次要解决的是产品语义错误，不只是前端展示问题。
2. regenerate 一旦被定义成正式能力，就应该在后端显式建模。
3. 方案 A 能让“最新版本继续对话、旧版本只读查看”这条规则在全链路保持一致。

## 核心语义

### 1. 一轮用户输入只产生一条 user message

`user message` 表示用户本轮的真实输入，不因 regenerate 而新增。

### 2. 一轮用户输入对应一个 assistant reply group

`assistant reply group` 表示系统对这条 user message 的所有回复集合。

### 3. 一个 group 下可以有多个 assistant reply version

每次 regenerate 都是在同一个 group 下新增一个 version，而不是新增一个 user turn。

### 4. latest version 才参与主流程

以下逻辑都只基于 latest version：

1. 主时间线展示
2. 后续上下文拼装
3. 恢复会话后的主视图
4. 默认导出结果

### 5. 历史版本只读

用户可以查看历史版本，但查看动作不会改变后续对话基线。

## 数据模型设计

### 现有表：`conversation_messages`

继续保留，用于承载：

1. user message
2. 主时间线 latest assistant 的镜像消息

第一阶段不强行移除 assistant message，避免现有读接口、导出逻辑和测试一次性全部重写。

### 新增表：`assistant_reply_groups`

字段建议：

```text
id: string
session_id: string
user_message_id: string
latest_version_id: string | null
created_at: datetime
updated_at: datetime
```

字段说明：

1. `session_id`
   方便按会话查询所有 group。
2. `user_message_id`
   绑定该轮真实用户输入。
3. `latest_version_id`
   指向当前 latest assistant version。

### 新增表：`assistant_reply_versions`

字段建议：

```text
id: string
reply_group_id: string
session_id: string
user_message_id: string
version_no: int
content: text
action_snapshot: json
model_meta: json
state_version_id: string | null
prd_snapshot_version: int | null
created_at: datetime
```

字段说明：

1. `version_no`
   从 1 开始递增，用于历史展示和排序。
2. `action_snapshot`
   保留该版本生成时的 `action.decided` 结果。
3. `model_meta`
   保留生成该版本时使用的模型信息。
4. `state_version_id` / `prd_snapshot_version`
   建立 assistant version 与状态快照、PRD 快照的追溯关系。

## 状态与快照策略

虽然 regenerate 不新增 user message，但它仍是一轮新的系统决策，因此需要新增：

1. state version
2. PRD snapshot

原因：

1. regenerate 可能对应不同 action。
2. regenerate 后最新版本会参与后续对话上下文。
3. 如果后续 agent 真正开始产出 `state_patch` 和 `prd_patch`，版本快照必须有独立归档能力。

因此 regenerate 不只是“文本替换”，而是“同一轮用户输入下的一次新版系统回应”。

## API 设计

### 1. 新消息接口

保留现有接口：

`POST /api/sessions/{session_id}/messages`

用途：

1. 创建新的 user turn。
2. 创建 reply group。
3. 生成 version 1。

请求体：

```json
{
  "content": "...",
  "model_config_id": "..."
}
```

### 2. 新增 regenerate 接口

新增接口：

`POST /api/sessions/{session_id}/messages/{user_message_id}/regenerate`

用途：

1. 对已有 user message 追加新的 assistant version。
2. 不新增 user message。

请求体建议：

```json
{
  "model_config_id": "..."
}
```

第一版不引入额外 regenerate 指令字段，先保持语义单纯。

### 3. 会话读取接口

`GET /api/sessions/{session_id}` 建议扩展返回：

1. `messages`
   主时间线使用，只包含 user message 与 latest assistant。
2. `assistant_reply_groups`
   版本历史使用，供弹层展示。

返回示意：

```json
{
  "messages": [
    { "id": "u1", "role": "user", "content": "..." },
    {
      "id": "a1v3",
      "role": "assistant",
      "content": "...最新版...",
      "reply_group_id": "g1",
      "version_no": 3,
      "is_latest": true
    }
  ],
  "assistant_reply_groups": [
    {
      "id": "g1",
      "user_message_id": "u1",
      "latest_version_id": "a1v3",
      "versions": [
        { "id": "a1v1", "version_no": 1, "content": "..." },
        { "id": "a1v2", "version_no": 2, "content": "..." },
        { "id": "a1v3", "version_no": 3, "content": "...", "is_latest": true }
      ]
    }
  ]
}
```

## SSE 事件协议

### 新消息

建议事件顺序：

1. `message.accepted`
2. `reply_group.created`
3. `action.decided`
4. `assistant.version.started`
5. 多个 `assistant.delta`
6. `assistant.done`

关键字段建议：

#### `message.accepted`

```json
{ "user_message_id": "u1" }
```

#### `reply_group.created`

```json
{
  "reply_group_id": "g1",
  "user_message_id": "u1"
}
```

#### `assistant.version.started`

```json
{
  "reply_group_id": "g1",
  "assistant_version_id": "a1v1",
  "version_no": 1,
  "is_regeneration": false
}
```

#### `assistant.delta`

```json
{
  "assistant_version_id": "a1v1",
  "delta": "..."
}
```

#### `assistant.done`

```json
{
  "assistant_version_id": "a1v1",
  "reply_group_id": "g1",
  "version_no": 1,
  "is_latest": true
}
```

### regenerate

建议事件顺序：

1. `action.decided`
2. `assistant.version.started`
3. 多个 `assistant.delta`
4. `assistant.done`

regenerate 不再发送 `message.accepted`，因为没有新增 user message。

## Web 交互设计

### 主时间线

主时间线继续只显示 latest assistant version。

这样可以最大程度复用现有：

1. `ConversationPanel`
2. `AssistantTurnCard`
3. `Composer`

### 重新生成按钮

“重新生成”仍放在当前分析卡中。

点击后行为改为：

1. 不删除当前 user message。
2. 当前 assistant 卡进入生成中态。
3. 请求新的 regenerate 接口。
4. 成功后主卡切换到 latest version。

### 重新生成历史入口

在当前分析卡中增加“重新生成历史”入口，点击后打开弹层或抽屉。

弹层内容：

1. 按版本倒序列出该轮所有 assistant version。
2. 默认高亮 latest。
3. 点击任一版本可查看完整内容。
4. 旧版本只读，不影响主时间线继续对话的基线。

### 继续补充

Composer 永远基于 latest assistant version 继续。

即使用户当前在弹层中查看旧版本，也不改变发送行为。

## 持久化策略

### 新消息

事务内完成以下写入：

1. 新建 user message。
2. 新建 reply group。
3. 新建 version 1。
4. 更新 group.latest_version_id。
5. 写 latest assistant 镜像 message。
6. 写 state version。
7. 写 PRD snapshot。

### regenerate

事务内完成以下写入：

1. 查找既有 reply group。
2. 新建 version N+1。
3. 更新 group.latest_version_id。
4. 覆盖 latest assistant 镜像 message。
5. 新增 state version。
6. 新增 PRD snapshot。

## 兼容迁移策略

建议分两步完成迁移。

### 第一步：加表并双写新数据

内容：

1. 新增 `assistant_reply_groups`。
2. 新增 `assistant_reply_versions`。
3. 新消息与 regenerate 开始按新结构写入。
4. 主时间线继续依赖现有 `messages` 输出。

### 第二步：回填历史会话

内容：

1. 对存量会话中的 user + assistant 配对回填 group + version 1。
2. 对没有版本历史的老会话，历史弹层也能稳定显示至少一版。

### 兼容兜底

在历史回填前，读接口应允许：

1. 没有 group/version 的老会话继续正常打开。
2. 历史弹层显示“暂无历史版本”或仅显示 latest。

## 错误处理

### 前置校验错误

以下情况直接返回 4xx：

1. `session_id` 不存在或不属于当前用户。
2. `user_message_id` 不存在或不属于当前会话。
3. `model_config_id` 不存在。
4. `model_config_id` 已禁用。

### 用户主动取消

用户主动停止生成时：

1. 前端本地结束 loading。
2. 后端不创建新的 assistant version。
3. 不更新 latest。
4. 不推进 state version 与 PRD snapshot。

### 上游模型异常

模型流式生成失败时：

1. 记录日志。
2. 不创建 assistant version。
3. 不更新 latest。
4. 不推进 state / PRD。

### 持久化失败

若流生成完成但写 version、group、state、PRD 任一环节失败：

1. 当前事务整体回滚。
2. 不允许出现“历史版本已追加，但 latest 未更新”的半成功状态。

## 测试策略

### 后端 service 单测

覆盖：

1. 新消息会创建 user message、reply group、version 1。
2. regenerate 只新增 version，不新增 user message。
3. latest_version_id 正确更新。
4. regenerate 后上下文只基于 latest。
5. 流式异常或取消时不落空版本。

### API / SSE 集成测试

覆盖：

1. 新消息事件顺序。
2. regenerate 事件顺序。
3. regenerate 不发送 `message.accepted`。
4. `assistant.version.started` 与 `assistant.done` 字段完整。

### 前端 store 单测

覆盖：

1. 新消息时主时间线追加 user + latest assistant。
2. regenerate 时只替换 latest assistant，不新增 user message。
3. 版本历史数组正确追加。
4. 切换旧版本查看不影响继续发送的基线。

### 组件交互测试

覆盖：

1. 当前分析卡 regenerate loading 态。
2. 历史弹层打开、关闭、切换版本。
3. regenerate 失败时主卡保持当前 latest。
4. 刷新恢复后版本历史仍然存在。

## 推荐落地顺序

1. 先新增 regenerate 显式接口。
2. 同时引入 reply group + reply version 数据模型。
3. 保留 latest assistant 镜像，降低主时间线改造成本。
4. 增加“重新生成历史”弹层。
5. 等主流程稳定后，再评估是否移除 assistant latest 镜像。

## 结论

本次不建议继续在现有“再次发送同一条用户输入”的模式上修补。

正确方向是：

1. 把 regenerate 建模成同一条 user message 下的新 assistant version。
2. 把版本历史作为正式会话数据持久化。
3. 让主时间线永远只基于 latest version 运转。

这样既能满足“可回看历史版本”的产品目标，也能保证后续上下文、刷新恢复、导出与测试语义保持一致。
