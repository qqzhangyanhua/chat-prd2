# PRD 契约索引

这份索引面向后续维护“生成 PRD”链路的开发者，目标是快速回答三个问题：

1. 现在 PRD 的真源在哪里？
2. 前后端各自是哪段代码在做派生和预览？
3. 改完之后应该跑哪几组测试来确认没有漂移？

## 1. 文档入口

- [PRD 运行时契约](/Users/zhangyanhua/AI/chat-prd2/docs/contracts/prd-runtime-contract.md)
  说明 `prd.updated`、`snapshot.state`、`prd_snapshot.sections` 三类来源的职责划分，以及前后端当前的刷新顺序与不变量。

- [PRD Meta 共享样例](/Users/zhangyanhua/AI/chat-prd2/docs/contracts/prd-meta-cases.json)
  固化 `prd.meta` 的阶段判断与文案样例。前后端测试都读这同一份 fixture。

## 2. 前端代码入口

- [workspace-store.ts](/Users/zhangyanhua/AI/chat-prd2/apps/web/src/store/workspace-store.ts)
  工作台全局状态编排入口。负责：
  - hydrate / refresh
  - 流式事件分发
  - 消息版本与回复组状态

- [prd-store-helpers.ts](/Users/zhangyanhua/AI/chat-prd2/apps/web/src/store/prd-store-helpers.ts)
  PRD 相关派生逻辑单点。负责：
  - 主 section 派生
  - 补充 section 派生
  - `prd.meta` 派生
  - `prd.updated` section 分流
  - refresh 时的“保留更新版本”判断

- [prd-panel.tsx](/Users/zhangyanhua/AI/chat-prd2/apps/web/src/components/workspace/prd-panel.tsx)
  右侧 PRD 面板的展示层。只消费 `workspaceStore.prd`，不再自行判断真源。

## 3. 后端代码入口

- [messages.py](/Users/zhangyanhua/AI/chat-prd2/apps/api/app/services/messages.py)
  消息流和持久化编排入口。负责：
  - 正常发送消息
  - regenerate
  - 流式事件顺序
  - state / prd snapshot 版本写入

- [prd_runtime.py](/Users/zhangyanhua/AI/chat-prd2/apps/api/app/services/prd_runtime.py)
  PRD 运行时预览 helper 单点。负责：
  - `preview_prd_sections()`
  - `preview_prd_meta()`
  - `build_prd_updated_event_data()`

- [message.py](/Users/zhangyanhua/AI/chat-prd2/apps/api/app/schemas/message.py)
  `prd.updated` 等消息事件的 schema 定义。

## 4. 关键测试入口

### 4.1 前端

- [workspace-store.test.ts](/Users/zhangyanhua/AI/chat-prd2/apps/web/src/test/workspace-store.test.ts)
  核心 store 行为与 `prd.meta` 共享契约。

- [prd-panel.test.tsx](/Users/zhangyanhua/AI/chat-prd2/apps/web/src/test/prd-panel.test.tsx)
  右侧 PRD 面板展示与 `prd.updated` 渲染。

- [workspace-session-shell.test.tsx](/Users/zhangyanhua/AI/chat-prd2/apps/web/src/test/workspace-session-shell.test.tsx)
  更接近真实用户路径的集成测试，覆盖 regenerate 后面板刷新。

### 4.2 后端

- [test_messages_service.py](/Users/zhangyanhua/AI/chat-prd2/apps/api/tests/test_messages_service.py)
  服务层持久化与 `prd.updated` payload 断言。

- [test_messages_stream.py](/Users/zhangyanhua/AI/chat-prd2/apps/api/tests/test_messages_stream.py)
  实际 SSE 流顺序与事件内容断言。

## 5. 推荐排查顺序

当你遇到 PRD 展示异常、阶段文案漂移、或 regenerate 后状态不一致时，建议按这个顺序排查：

1. 看 [prd-runtime-contract.md](/Users/zhangyanhua/AI/chat-prd2/docs/contracts/prd-runtime-contract.md)
   先确认这是“实时事件问题”“快照问题”还是“兼容回退问题”。

2. 看 [prd-meta-cases.json](/Users/zhangyanhua/AI/chat-prd2/docs/contracts/prd-meta-cases.json)
   如果是阶段文案或 stage 判断问题，先确认有没有违背共享样例。

3. 看前端 store helper
   如果是主 section / 补充 section / meta 显示不对，优先看 [prd-store-helpers.ts](/Users/zhangyanhua/AI/chat-prd2/apps/web/src/store/prd-store-helpers.ts)。

4. 看后端 PRD runtime helper
   如果是 `prd.updated` payload 不对，优先看 [prd_runtime.py](/Users/zhangyanhua/AI/chat-prd2/apps/api/app/services/prd_runtime.py)。

5. 再看消息流编排
   只有在 payload 本身没问题时，才回头看 [messages.py](/Users/zhangyanhua/AI/chat-prd2/apps/api/app/services/messages.py) 的发送顺序、持久化版本和 regenerate 逻辑。

## 6. 推荐最小回归命令

前端：

```bash
pnpm --filter web test -- src/test/workspace-store.test.ts src/test/workspace-session-shell.test.tsx src/test/prd-panel.test.tsx
```

后端：

```bash
PYTHONPATH=apps/api uv run pytest apps/api/tests/test_messages_service.py apps/api/tests/test_messages_stream.py -q
```

如果只是改 `prd.meta` 文案或阶段判断，最小验证可先跑：

前端：

```bash
pnpm --filter web test -- src/test/workspace-store.test.ts
```

后端：

```bash
PYTHONPATH=apps/api uv run pytest apps/api/tests/test_messages_service.py::test_preview_prd_meta_matches_shared_contract -q
```
