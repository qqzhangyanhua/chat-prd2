# PRD 链路改造摘要

本文档用于总结这一轮“生成 PRD”逻辑的补强与整理结果，方便后续提交代码、做交接说明，或快速回顾改动边界。

## 1. 本轮目标

这轮改造的核心目标有三类：

- 修正 PRD 真源不一致
- 补齐 regenerate 后 PRD 状态不更新的问题
- 把前后端 PRD 运行时规则从“隐含逻辑”收敛成“代码 + 测试 + 文档”三层契约

## 2. 已完成的关键改动

### 2.1 前端 PRD 真源切换

前端主卡片的 4 个核心 section：

- `target_user`
- `problem`
- `solution`
- `mvp_scope`

现在统一按这个优先级派生：

1. `state.prd_draft.sections`
2. `prd_snapshot.sections`
3. 默认占位内容

影响文件：

- [workspace-store.ts](/Users/zhangyanhua/AI/chat-prd2/apps/web/src/store/workspace-store.ts)
- [prd-store-helpers.ts](/Users/zhangyanhua/AI/chat-prd2/apps/web/src/store/prd-store-helpers.ts)

### 2.2 草稿补充区实时更新

以下补充 key：

- `constraints`
- `success_metrics`
- `out_of_scope`
- `open_questions`

现在在前端有独立的 `extraSections` 分流，不会再误写进主卡片 `sections`。

### 2.3 PRD meta 实时更新

`prd.updated` 事件已经从只传 `sections` 扩成可选传：

- `sections`
- `meta`

其中 `meta` 当前包含：

- `stageLabel`
- `stageTone`
- `criticSummary`
- `criticGaps`
- `draftVersion`
- `nextQuestion`

这意味着右侧 PRD 面板在 SSE 到达时，可以直接更新阶段徽章、Critic 摘要与下一问，而不必再等 `getSession` 刷新。

### 2.4 regenerate 持久化闭环修复

regenerate 现在不再只是替换 assistant 文本，而是与正常发送消息保持一致：

1. 生成新的 state version
2. 生成新的 PRD snapshot
3. 新 assistant version 绑定新的 `state_version_id / prd_snapshot_version`
4. 流式补发 `prd.updated`
5. 再发 `assistant.done`

这样 regenerate 后，PRD 状态不会再和回复文本脱节。

影响文件：

- [messages.py](/Users/zhangyanhua/AI/chat-prd2/apps/api/app/services/messages.py)

### 2.5 旧快照覆盖保护

前端 `refreshSessionSnapshot()` 现在会在一种场景下保留当前 PRD：

- 当前 store 的 `draftVersion` 明确大于刷新快照里的 `draftVersion`

作用：

- 防止 SSE 已推到更高版本
- 但随后旧快照返回时把新状态覆盖回去

### 2.6 前后端结构整理

为了降低后续维护成本，这轮也做了模块收口：

前端：

- 新增 [prd-store-helpers.ts](/Users/zhangyanhua/AI/chat-prd2/apps/web/src/store/prd-store-helpers.ts)

后端：

- 新增 [prd_runtime.py](/Users/zhangyanhua/AI/chat-prd2/apps/api/app/services/prd_runtime.py)

这样 PRD 运行时派生和预览逻辑，都不再散落在大文件里。

## 3. 已落地的契约文档

### 3.1 运行时契约

- [prd-runtime-contract.md](/Users/zhangyanhua/AI/chat-prd2/docs/contracts/prd-runtime-contract.md)

明确了：

- `prd.updated`
- `snapshot.state`
- `prd_snapshot.sections`

三类来源各自的职责，以及前端 hydrate / refresh / 流式更新的优先顺序。

### 3.2 共享 meta 基线

- [prd-meta-cases.json](/Users/zhangyanhua/AI/chat-prd2/docs/contracts/prd-meta-cases.json)

这是一份前后端共用的 fixture，用来锁定 `prd.meta` 的阶段判断与文案样例。

### 3.3 契约索引

- [README.md](/Users/zhangyanhua/AI/chat-prd2/docs/contracts/README.md)

用于快速定位：

- 文档入口
- 前端代码入口
- 后端代码入口
- 测试入口
- 推荐最小回归命令

## 4. 关键测试覆盖

### 4.1 前端

- [workspace-store.test.ts](/Users/zhangyanhua/AI/chat-prd2/apps/web/src/test/workspace-store.test.ts)
  - 主 section 真源优先级
  - `extraSections` 分流
  - `prd.updated.meta` 消费
  - 旧快照覆盖保护
  - 共享 `prd.meta` 契约测试

- [prd-panel.test.tsx](/Users/zhangyanhua/AI/chat-prd2/apps/web/src/test/prd-panel.test.tsx)
  - 阶段态展示
  - 草稿补充展示
  - `prd.updated` 驱动的实时渲染

- [workspace-session-shell.test.tsx](/Users/zhangyanhua/AI/chat-prd2/apps/web/src/test/workspace-session-shell.test.tsx)
  - regenerate -> `prd.updated` -> 面板刷新

### 4.2 后端

- [test_messages_service.py](/Users/zhangyanhua/AI/chat-prd2/apps/api/tests/test_messages_service.py)
  - `prd.updated` payload
  - regenerate 的 state/prd snapshot 持久化
  - 共享 `prd.meta` 契约测试

- [test_messages_stream.py](/Users/zhangyanhua/AI/chat-prd2/apps/api/tests/test_messages_stream.py)
  - SSE 顺序
  - regenerate 流里 `prd.updated` 的存在
  - `meta` 字段随流下发

## 5. 当前稳定不变量

截至本轮结束，默认应始终成立：

- 主卡片 section 优先吃 `prd_draft.sections`
- 草稿补充 key 只会进入 `extraSections`
- `prd.updated` 可以同步更新 `sections + meta`
- regenerate 必须生成新的 state / PRD snapshot 版本
- 旧快照不能把更新版本的 SSE 状态覆盖回去
- 前后端的 `prd.meta` 规则由同一份 JSON fixture 锁定

## 6. 建议的最小回归命令

前端：

```bash
pnpm --filter web test -- src/test/workspace-store.test.ts src/test/workspace-session-shell.test.tsx src/test/prd-panel.test.tsx
```

后端：

```bash
PYTHONPATH=apps/api uv run pytest apps/api/tests/test_messages_service.py apps/api/tests/test_messages_stream.py -q
```

## 7. 后续建议

这轮改造已经把“生成 PRD”链路从功能修补推进到结构整理。后续如果继续，优先级建议如下：

1. 保持现有契约，不再随意新增并行真源
2. 如果要改 `prd.meta` 文案或阶段判断，先更新共享 fixture
3. 如果要改流式 payload，优先改 helper 模块而不是在调用点散改
4. 如果后续新增 section key，先明确它属于：
   - 主卡片
   - 草稿补充
   - 仅快照导出层
