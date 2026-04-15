# Workspace 对话闭环后端梳理

## 1. 目标

本文面向业务和研发，梳理 `apps/web/src/app/workspace` 当前对话相关的后端主链，并判断“新会话 PRD 对话闭环”是否已经真正打通。

这里说的闭环，指的是这条主线：

- 草稿沉淀
- 达到终稿门槛
- 用户确认终稿
- 生成 finalized PRD
- 完成态继续输入时自动 reopen
- 导出结果随状态切换

## 2. 真相源

后端已经把以下字段作为显式真相源写入 session state：

- `workflow_stage`
- `finalization_ready`
- `prd_draft`
- `critic_result`
- `finalize_confirmation_source`
- `finalize_preference`

初始状态在 session 创建时落库，默认是：

- `workflow_stage = "idea_parser"`
- `finalization_ready = False`

这意味着前端不需要再根据文案、回复内容或 PRD 展示结果去猜当前处于什么阶段。

## 3. 后端主链

### 3.1 普通消息入口

普通对话从 `app/services/messages.py` 的 `handle_user_message()` 进入：

1. 持久化 user message
2. 读取最新 state
3. 调用 `run_agent(...)`
4. 根据 agent 返回结果决定：
   - 走普通 reply 持久化
   - 或走 finalize 动作持久化

### 3.2 状态机编排

`app/agent/runtime.py` 负责对话状态机分流，核心规则有四条：

1. `completed` 下，如果用户输入只是“收到/继续/导出”等非修改语义，不 reopen，直接返回完成态引导。
2. `completed` 下，如果用户输入带有明确修改意图，或是足够长的实质跟进输入，则自动 reopen，把状态切回 `refine_loop`。
3. `finalize` 下，如果用户给出明确确认终稿语义，则返回 `action = "finalize"`。
4. 其余普通对话继续走 `pm_mentor`，再由 readiness evaluator 决定停在 `refine_loop` 还是进入 `finalize`。

### 3.3 readiness 判定

`app/agent/readiness.py` 目前使用规则型判定，而不是模型自由判断。

当前进入 `finalize_ready` 的必要内容是：

- `target_user`
- `problem`
- `solution`
- `mvp_scope`
- `constraints`
- `success_metrics`

只要这些关键 section 有缺口，就不会进入 `finalize`。

### 3.4 finalize 两个入口

现在 finalize 有两个入口，但底层走的是同一套服务：

- 按钮确认：
  - `POST /api/sessions/{session_id}/finalize`
  - 路由在 `app/api/routes/finalize.py`
- 对话确认：
  - `messages.py` 识别到 `action = "finalize"` 后，直接复用 finalize service

这保证了“按钮确认”和“自然语言确认”不会出现两套业务语义。

### 3.5 finalize 服务

真正把会话推进到完成态的唯一地方是 `app/services/finalize_session.py`。

它做的事情是：

1. 校验当前必须已处于 `workflow_stage = "finalize"`
2. 校验 `finalization_ready = True`
3. 校验确认来源合法，只接受 `button` 或 `message`
4. 基于当前 `prd_draft` 生成 finalized sections
5. 新建 state version
6. 新建 prd snapshot
7. 把 `workflow_stage` 切到 `completed`
8. 把 `prd_draft.status` 切到 `finalized`
9. 返回最新 session snapshot

这意味着 `completed` 不再允许被普通对话链路直接写入，只能经过 finalize service。

### 3.6 回复与版本持久化

普通回复和 regenerate 的 state / prd / reply version 持久化在 `app/services/message_persistence.py`。

它保证以下三类数据同步推进：

- `state_version`
- `prd_snapshot`
- `assistant_reply_version`

这样前端只要刷新 session snapshot，就能拿到一致的阶段状态和 PRD 快照。

### 3.7 导出链路

导出逻辑在 `app/services/exports.py`。

导出优先级是：

1. 如果当前 `prd_draft.sections` 存在，优先从 draft 导出
2. 当 `prd_draft.status == "finalized"` 时，导出结果标记为“终稿”
3. 如果 reopen 之后又回到草稿态，则导出结果重新回到“草稿”

因此，导出已经和闭环状态一致，不会出现 completed 后仍导出草稿快照的问题。

## 4. 业务是否闭环

结论：对“新会话”范围来说，当前业务已经闭环。

原因是以下关键条件都已经成立：

- 只有 readiness 满足时，才会进入 `finalize`
- 只有用户确认时，才会进入 `completed`
- `completed` 后继续输入实质修改会自动 reopen
- finalize 后 PRD 会落成 finalized draft 和 snapshot
- 导出会跟随 finalized / reopened 状态切换
- 前后端都消费显式状态，而不是靠展示层猜测业务阶段

## 5. 当前边界

本轮闭环结论只覆盖以下范围：

- 只保证新会话闭环
- 旧会话不做补算和迁移兜底
- reopen 判定目前仍是规则型关键词加长度判断，不是更细的语义分类器

这些都属于当前实现接受的边界，不影响“新会话完整闭环”成立。

## 6. 验证结论

本轮验证覆盖了后端状态机、finalize、导出和前端状态消费主路径。

验证命令：

- 后端：
  - `PYTHONPATH=apps/api uv run pytest apps/api/tests/test_messages_stream.py apps/api/tests/test_messages_service.py apps/api/tests/test_sessions.py apps/api/tests/test_agent_runtime.py apps/api/tests/test_finalize_session.py apps/api/tests/test_readiness.py -q`
- 前端：
  - `pnpm --filter web exec vitest run src/test/workspace-store.test.ts src/test/workspace-composer.test.tsx src/test/assistant-turn-card.test.tsx src/test/workspace-session-shell.test.tsx`
- 类型检查：
  - `pnpm --filter web exec tsc --noEmit`

在这些验证通过的前提下，可以把“workspace 新会话 PRD 对话完整闭环”视为已完成。
