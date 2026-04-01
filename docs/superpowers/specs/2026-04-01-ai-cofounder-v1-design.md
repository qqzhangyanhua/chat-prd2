# AI Co-founder 系统设计（V1）

## 1. 产品定义

### 1.1 产品定位

AI Co-founder 是一个面向普通创业者和独立开发者的引导型智能体系统。它通过递进式对话持续追问、挑战、提示和结构化沉淀，帮助用户把模糊想法逐步挖清楚，并形成一份可执行的 PRD 包与轻量执行建议。

### 1.2 产品本质

它不是：

- 聊天机器人
- PRD 写作工具
- 表单式需求收集器
- 通用创业助手
- 多智能体秀场

它真正是：

一个会持续跟进用户、帮助用户把想法挖深、并推动用户做出关键产品决策的 AI Co-founder。

### 1.3 核心价值

- 帮用户想清楚，而不是只帮用户写清楚
- 模拟真实 co-founder 的 challenge、追问和建议
- 通过多轮递进式对话实现决策收敛
- 将过程实时沉淀为结构化 PRD 和决策记录

### 1.4 核心闭环

```text
模糊 idea
→ 智能体持续引导与挖掘
→ 用户认知逐步清晰
→ 状态与 PRD 实时沉淀
→ 输出可执行 PRD 包
→ 用户进入设计 / 开发准备阶段
```

## 2. 目标用户与产出定义

### 2.1 核心用户

V1 只服务一类核心用户：

- 普通创业者
- 独立开发者
- 个人做产品的人

这些用户通常具备以下特征：

- 有产品想法，但定义仍然模糊
- 没有成熟 PM 流程
- 不一定会写规范 PRD
- 需要有人帮助厘清方向、控制范围并输出能开工的东西

### 2.2 V1 最终产出

V1 输出的不是聊天记录，而是一份 PRD 包，包含两层结果。

第一层是轻量可执行 PRD，至少包括：

- 产品概述
- 目标用户
- 核心问题
- 解决方案
- MVP 范围
- 核心用户流程
- 成功指标
- 风险与待确认项

第二层是轻量执行建议，至少包括：

- 推荐开发优先级
- 哪些部分先做，哪些部分后做
- 明显的风险和不该一开始做的内容
- 对后续设计和开发启动有帮助的提醒

## 3. 智能体交互模型

### 3.1 系统定位

AI Co-founder 不是固定步骤的工作流系统，而是一个持续引导用户挖掘想法、澄清认知、推动收敛的智能体系统。

它的关键特征是：

- 用户想到哪里说到哪里，智能体都能接住
- 智能体能判断哪些信息还浅、还虚、还没挖出来
- 智能体会持续追问、挑战、举例和重构表达
- 只要用户的想法还在展开，系统就继续跟进
- 当信息成熟到足够支撑决策时，再推动收敛与沉淀

### 3.2 核心机制

```text
用户表达想法
→ 智能体理解当前表达
→ 识别还没被挖出来的认知、约束、假设和风险
→ 决定最有价值的引导动作
→ 通过追问 / challenge / 举例 / 给选项继续深入
→ 用户继续补充
→ 状态持续更新
→ 在足够成熟时推动收敛并生成 PRD 包
```

### 3.3 对话推进原则

- 每轮只推进一个关键问题
- 优先推进最影响后续判断的信息缺口
- 能让用户选，就不要让用户长篇输入
- challenge 必须服务于收敛，而不是展示聪明
- 信息足够时不再追问，直接帮助收口

### 3.4 单轮输出结构

AI 每轮输出保持稳定结构，但按当前引导动作动态取舍：

- 我当前的理解
- 我的判断
- 风险 / 不确定点
- 可选方向
- 我的建议
- 下一步问题

### 3.5 阶段感

用户侧需要轻量阶段感，但阶段不是硬流程，只是认知进展提示：

```text
理解想法
→ 挖掘用户与问题
→ 收敛方案
→ 定义 MVP
→ 形成 PRD 包
```

## 4. 技术架构设计

### 4.1 技术选型

后端：

- Python
- FastAPI

智能体运行框架：

- LangGraph

数据层：

- Postgres
- pgvector（可选增强）

前端：

- Next.js
- React
- Tailwind CSS
- shadcn/ui

### 4.2 总体架构

```text
Frontend (Next.js)
   ↓
FastAPI API Layer
   ↓
Service Layer
   ↓
LangGraph Agent Runtime
   ↓
Postgres
├── Users / Sessions
├── Messages
├── State Versions
├── PRD Snapshots
└── Decision Logs
```

### 4.3 架构原则

- 外在体验是智能体，不是流程表单
- 内部实现依赖结构化状态，而不是只依赖聊天历史
- 节点化能力服务于智能体判断，不直接暴露为用户流程
- 聊天历史用于语境参考，结构化状态用于系统决策

## 5. 智能体内部能力设计

### 5.1 LangGraph 的角色

LangGraph 在 V1 中不是固定工作流引擎，而是智能体的运行框架，用于承载：

- 可持续状态
- 可拆分判断模块
- 可追踪决策过程
- 可插入 challenge、分析和生成能力

### 5.2 核心内部模块

- `parse_user_turn`
- `update_state`
- `analyze_depth`
- `critic`
- `decide_next_action`
- `respond`

### 5.3 模块职责

#### parse_user_turn

负责理解用户本轮真正表达了什么，例如：

- 补充背景
- 暴露真实动机
- 摇摆不定
- 否定之前判断
- 引出新的方向分支

#### update_state

将用户自然语言转成结构化认知结果，包括：

- 新增明确信息
- 新增假设
- 修正冲突点
- 调整字段置信度

#### analyze_depth

识别哪些信息看起来提到了，但其实没挖透，例如：

- 用户群体过大
- 问题描述抽象
- 方案很多但核心价值点不清楚
- 需求表达仍停留在愿望层

#### critic

作为内部 challenge 模块，输出结构化判断：

```python
class CriticOutput:
    fatal_issues: list[str]
    major_risks: list[str]
    weak_assumptions: list[str]
    unexplored_areas: list[str]
```

#### decide_next_action

决定当前最有价值的引导动作：

```python
class NextAction:
    action: Literal[
        "probe_deeper",
        "challenge_assumption",
        "offer_options",
        "summarize_understanding",
        "confirm_decision",
        "generate_prd_package"
    ]
    target: Optional[str]
    reason: str
```

#### respond

将内部判断转成自然、有引导感的用户可读输出，让用户感觉：

- 智能体真的理解了当前重点
- 智能体发现了没说透的地方
- 智能体是在帮助继续思考，而不是重复总结

## 6. 状态管理设计

### 6.1 状态定位

状态不是流程表单，而是智能体对当前产品认知的结构化记忆。

### 6.2 推荐状态结构

```python
class ProjectState(TypedDict):
    session_id: str
    idea: str

    stage_hint: str
    iteration: int

    goal: str | None
    target_user: str | None
    problem: str | None
    solution: str | None
    mvp_scope: list[str]
    success_metrics: list[str]

    known_facts: dict
    assumptions: list[str]
    risks: list[str]
    unexplored_areas: list[str]

    options: list[dict]
    decisions: list[dict]
    open_questions: list[str]

    prd_snapshot: dict
    last_action: str | None
```

### 6.3 状态原则

- 结构化记忆优先于长聊天历史
- 允许 `已确认 / AI 推断 / 待补充` 长期并存
- 每轮都增量更新
- 可版本化、可回溯、可恢复

### 6.4 PRD 快照机制

PRD 不是最后一次性生成，而是边对话边生成 section 级快照。

机制如下：

- 每轮更新结构化状态
- 基于状态生成各 section 当前版本
- 前端右侧实时展示 section 级内容
- 导出时再拼成完整文档

## 7. 后端与数据设计

### 7.1 认证与用户绑定

V1 需要最小账户系统，支持：

- 邮箱注册
- 邮箱登录

说明：

- 账号建议直接采用邮箱
- 密码必须哈希存储
- 所有核心业务数据必须绑定 `user_id`

### 7.2 核心数据对象

- `users`
- `project_sessions`
- `conversation_messages`
- `project_state_versions`
- `prd_snapshots`
- `decision_logs`

### 7.3 用户模型

```python
class User:
    id: str
    email: str
    password_hash: str
    status: str
    created_at: datetime
    updated_at: datetime
```

### 7.4 会话模型

```python
class ProjectSession:
    id: str
    user_id: str
    title: str
    initial_idea: str
    status: str
    created_at: datetime
    updated_at: datetime
```

### 7.5 消息模型

```python
class ConversationMessage:
    id: str
    session_id: str
    role: Literal["user", "assistant", "system"]
    content: str
    message_type: str
    meta: dict
    created_at: datetime
```

### 7.6 状态版本模型

```python
class ProjectStateRecord:
    id: str
    session_id: str
    version: int
    state_json: dict
    created_at: datetime
```

采用追加版本而不是覆盖写，便于：

- 回溯
- 调试
- 后续支持版本恢复

### 7.7 PRD 快照模型

```python
class PrdSnapshot:
    id: str
    session_id: str
    version: int
    sections: dict
    generated_from_state_version: int
    created_at: datetime
```

每个 section 至少包含：

- `content`
- `status`
- `updated_at`

### 7.8 决策记录模型

```python
class DecisionLog:
    id: str
    session_id: str
    category: str
    decision: str
    rationale: str
    confidence: str
    created_at: datetime
```

### 7.9 数据库选型建议

- Postgres 为主存储
- pgvector 作为可选增强层
- Redis 不是 V1 必需依赖

pgvector 仅在以下能力中考虑接入：

- 历史项目召回
- 模板召回
- 产品知识辅助

## 8. 前端信息架构与组件设计

### 8.1 页面结构

V1 建议控制为 4 类页面：

- 注册页
- 登录页
- 工作台页
- 导出预览页（或导出弹层）

### 8.2 工作台布局

桌面端采用三栏布局：

```text
左：轻量会话导航
中：智能体对话主区
右：PRD / 认知沉淀面板
```

移动端改为单主视图切换：

- 对话
- PRD
- 会话

### 8.3 三栏定义

左侧：

- 项目标题
- 当前阶段提示
- 历史会话入口
- 导出入口

中间：

- 智能体对话卡片流
- 当前引导问题
- 选项交互
- 用户输入区

右侧：

- PRD section 卡片
- 关键决策
- 风险与待确认项
- 执行建议

### 8.4 核心组件

- `SessionSidebar`
- `ConversationPanel`
- `AssistantTurnCard`
- `UserMessageBubble`
- `ActionOptions`
- `Composer`
- `StageHintBar`
- `PrdPanel`
- `PrdSectionCard`
- `DecisionList`
- `RiskList`
- `ExecutionSuggestionsCard`

### 8.5 关键组件说明

#### AssistantTurnCard

承载 AI 单轮结构化输出，建议支持：

- 当前理解
- 当前判断
- 风险提示
- 可选方向
- 推荐建议
- 下一步问题

#### ActionOptions

核心交互组件，支持：

- 单选卡片
- 双选分叉
- 三选推荐
- 自定义补充输入

#### PrdSectionCard

承载右侧 PRD section，包含：

- 标题
- 内容
- 状态标签
- 最近更新时间
- 折叠能力

### 8.6 视觉原则

- 不是聊天助手风，而是思考工作台风格
- 强化卡片层次、状态标签和完整度感
- 突出“正在构建产品定义”的感觉

## 9. 接口契约与数据流

### 9.1 API 分组

- `auth`
- `sessions`
- `messages`
- `exports`

### 9.2 认证接口

- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/auth/me`

### 9.3 会话接口

- `POST /api/sessions`
- `GET /api/sessions`
- `GET /api/sessions/{session_id}`

### 9.4 消息接口

- `GET /api/sessions/{session_id}/messages`
- `POST /api/sessions/{session_id}/messages`

### 9.5 状态与 PRD 接口

- `GET /api/sessions/{session_id}/state`
- `GET /api/sessions/{session_id}/prd`

### 9.6 导出接口

- `POST /api/sessions/{session_id}/export`

### 9.7 流式事件建议

消息发送接口建议采用 SSE 或流式 chunk，事件至少包括：

- `assistant.delta`
- `assistant.done`
- `action.decided`
- `state.updated`
- `prd.updated`
- `decision.logged`
- `error`

### 9.8 主数据流

```text
用户发送消息
→ 前端调用 POST /messages
→ 后端读取当前 session state
→ 智能体生成引导动作与回复
→ 后端写入 message / state version / prd snapshot / decision log
→ 后端流式返回文本与结构化事件
→ 前端同步更新对话区和右侧 PRD 面板
```

## 10. V1 功能边界

### 10.1 必做能力

- 单项目对话式探索
- 结构化状态沉淀
- 智能体引导动作
- 右侧 PRD / 认知面板实时更新
- PRD 包生成与导出
- 基础注册登录与用户绑定

### 10.2 不做内容

- 多用户协作
- 多智能体编排
- 复杂外部集成
- 重知识检索系统
- 代码生成主链路
- 复杂项目管理
- 第三方登录

### 10.3 可预留但不首发

- 模板库
- 历史项目对比与复用
- 竞品 / 市场信息辅助分析
- 技术实现建议增强版
- 自动拆任务和路线图
- 多版本 PRD diff
- 团队协作与评审

## 11. MVP 交付顺序

### 11.1 阶段划分

```text
阶段 1：跑通单会话闭环
阶段 2：补齐状态沉淀与 PRD 面板
阶段 3：补齐认证与用户绑定
阶段 4：补齐导出与历史恢复
阶段 5：体验优化与稳定性增强
```

### 11.2 阶段说明

#### 阶段 1：跑通单会话闭环

完成：

- 最小工作台页面
- 消息发送与智能体响应
- 最小 state
- 最基础 PRD section 展示

#### 阶段 2：补齐状态沉淀与 PRD 面板

完成：

- 完整 state 结构
- state version 化
- prd snapshot version 化
- 右侧 section 状态标签
- 决策记录
- 风险 / 待确认项展示

#### 阶段 3：补齐认证与用户绑定

完成：

- 注册
- 登录
- 用户查询
- token 鉴权
- 用户数据隔离

#### 阶段 4：补齐导出与历史恢复

完成：

- session 列表
- 历史会话恢复
- markdown 导出

#### 阶段 5：体验优化与稳定性增强

完成：

- 结构化卡片优化
- 空状态引导
- 异常兜底
- 加载与重试机制
- 基础埋点与日志

## 12. 风险、难点与关键决策

### 12.1 最大风险

最大风险不是技术，而是产品形态滑向：

- 普通聊天助手
- PRD 写作工具
- 表单 / 向导产品
- 万能创业助手

### 12.2 关键决策

- 始终把“持续挖掘用户想法，并推动形成可执行产品定义”作为唯一主线
- 智能体质量优先看引导能力，不看文案是否华丽
- 状态是认知记忆，不是流程表单
- 右侧要持续沉淀，但必须带状态语义
- 每轮只推进一个关键问题，并解释为什么问
- 选项用于降低表达成本，不用于替代真实思考
- 只要达到“足够开工”的成熟度，就生成当前版本 PRD 包
- 宁可保守更新，也不要写坏状态
- V1 只验证 idea → 可执行 PRD 包 这一条闭环

### 12.3 V1 成功标准

如果 V1 成立，用户会明确感受到：

- 智能体真的帮我把脑子里的东西挖出来了
- 它不是在陪聊，而是在推进我思考
- 我不需要一次写很多，但仍然在往前走
- 最终拿到的结果确实能继续做设计或开发

## 13. 一句话总结

AI Co-founder 是一个以递进式对话为核心、以结构化状态为记忆、以持续挖掘和决策收敛为能力、以 PRD 包沉淀为结果的产品决策智能体。

对外表达可以使用：

把你脑子里还说不清的产品想法，和 AI 一起一步步挖清楚，最后变成一份真的能开工的 PRD。
