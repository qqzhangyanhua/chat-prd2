# PRD 运行时契约

本文档描述当前项目里“生成 PRD”链路的运行时职责划分，目标是避免后续修改时再次出现前后端真源不一致、流式更新与快照互相覆盖、或 regenerate 只改回复不改 PRD 的问题。

## 1. 三类数据来源

当前会话页里与 PRD 相关的数据，主要有三类来源：

### 1.1 `prd.updated`

这是实时事件来源，职责是：

- 在消息流式生成过程中，第一时间把最新 PRD 预览推给前端
- 支持正常发送消息与 regenerate 两条链路
- 当前 payload 结构为：

```json
{
  "sections": {
    "...": {
      "title": "string",
      "content": "string",
      "status": "confirmed | inferred | missing"
    }
  },
  "meta": {
    "stageLabel": "探索中 | 草稿中 | 可整理终稿 | 已生成终稿",
    "stageTone": "draft | ready | final",
    "criticSummary": "string",
    "criticGaps": ["string"],
    "draftVersion": 1,
    "nextQuestion": "string | null"
  }
}
```

职责边界：

- `sections` 用于驱动右侧 PRD 内容实时更新
- `meta` 用于驱动阶段徽章、Critic 摘要、缺口列表、下一问
- 这是“实时预览来源”，优先级高于随后可能到达的旧快照

### 1.2 `snapshot.state`

这是会话状态真源，职责是：

- 持久化当前工作流状态
- 为前端 hydrate / refresh 提供完整上下文
- 目前与 PRD 直接相关的关键字段包括：

- `workflow_stage`
- `prd_draft`
- `critic_result`
- `finalization_ready`

前端基于 `snapshot.state` 派生：

- `prd.meta`
- `prd.extraSections`
- 主 section 的优先真源（`prd_draft.sections`）

### 1.3 `prd_snapshot.sections`

这是兼容层与导出层仍会使用的持久化 section 快照，职责是：

- 为旧链路和导出提供稳定 section 结构
- 在前端 hydrate 时作为主 section 的回退来源

职责边界：

- 它不再是前端主卡片的唯一真源
- 当前主卡片 section 的优先级是：

`state.prd_draft.sections -> prd_snapshot.sections -> 默认占位`

## 2. 前端渲染规则

### 2.1 主 section

主卡片固定 4 个 key：

- `target_user`
- `problem`
- `solution`
- `mvp_scope`

hydrate 时优先顺序：

1. `state.prd_draft.sections`
2. `prd_snapshot.sections`
3. `createInitialPrdSections()`

流式 `prd.updated` 到来时：

- 只把这 4 个 key 写入 `prd.sections`

### 2.2 草稿补充 section

当前补充区 key：

- `constraints`
- `success_metrics`
- `out_of_scope`
- `open_questions`

hydrate 时来源：

- `state.prd_draft.sections`

流式 `prd.updated` 到来时：

- 只把这些 key 写入 `prd.extraSections`
- 不允许污染主卡片 `prd.sections`

### 2.3 PRD meta

当前 `prd.meta` 允许字段：

- `stageLabel`
- `stageTone`
- `criticSummary`
- `criticGaps`
- `draftVersion`
- `nextQuestion`

hydrate 时来源：

- 由 `snapshot.state` 派生

流式 `prd.updated` 到来时：

- 若 payload 带 `meta`，则直接覆盖 `prd.meta`
- 若不带 `meta`，保持现值不动

### 2.4 刷新保护

`refreshSessionSnapshot()` 只在一种情况下保留当前 store 的 PRD：

- 当前 `prd.meta.draftVersion` 明确大于快照中的 `draftVersion`

这是为了避免：

- SSE 已收到较新的 PRD
- 随后 `getSession` 返回旧快照
- 旧快照把新状态覆盖回去

该保护只作用在 refresh 路径，不作用在首次 `hydrateSession()`。

## 3. 后端持久化规则

### 3.1 正常发送消息

发送消息完成后，必须：

1. 写入新的 state version
2. 写入新的 PRD snapshot
3. 发送 `prd.updated`
4. 发送 `assistant.done`

### 3.2 regenerate

regenerate 当前也必须遵守与正常发送一致的 PRD 更新语义：

1. 写入新的 state version
2. 写入新的 PRD snapshot
3. 把新的 `state_version_id / prd_snapshot_version` 绑定到新的 assistant version
4. 发送 `prd.updated`
5. 再发送 `assistant.done`

不允许再出现“回复版本更新了，但 PRD 状态还挂在旧快照版本上”的情况。

## 4. 共享契约基线

当前 `prd.meta` 的阶段文案和阶段判断，使用共享 fixture 固化在：

[prd-meta-cases.json](/Users/zhangyanhua/AI/chat-prd2/docs/contracts/prd-meta-cases.json)

目的：

- 前端 `workspace-store` 派生逻辑和后端 `_preview_prd_meta()` 必须对齐
- 任一侧修改阶段判断或文案时，都会在共享契约测试里暴露

当前覆盖的阶段样例包括：

- 默认探索态
- `refine_loop` 缺口态
- `finalize` ready 态
- `completed/finalized` 终稿态
- 带单一 `nextQuestion` 的 refine 态

## 5. 当前推荐修改原则

后续修改 PRD 链路时，建议按下面顺序判断：

1. 这是“实时预览”问题，还是“持久化真源”问题？
2. 这个字段应该来自 `prd.updated`，还是来自 `snapshot.state`？
3. 这是主 section、补充 section，还是 meta？
4. 修改后是否同时覆盖了正常发送与 regenerate？
5. 是否需要同步更新共享 fixture `[prd-meta-cases.json](/Users/zhangyanhua/AI/chat-prd2/docs/contracts/prd-meta-cases.json)`？

## 6. 不变量

目前默认应始终满足以下不变量：

- 前端主卡片 4 个 section 优先使用 `prd_draft.sections`
- `constraints/success_metrics/out_of_scope/open_questions` 只能进入 `extraSections`
- `prd.updated` 与 `refreshSessionSnapshot` 不能互相把更新版本覆盖成更旧版本
- regenerate 必须生成新的 state / prd snapshot 版本
- 前后端对 `prd.meta` 的阶段判断必须通过同一份共享契约 fixture
