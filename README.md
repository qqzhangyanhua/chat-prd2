# AI Co-founder V1

AI Co-founder 是一个通过持续对话引导用户挖掘想法、收敛关键决策，并实时沉淀 PRD 的智能体工作台。

当前仓库为 monorepo：

- `apps/web`：Next.js 15 + React 19 前端
- `apps/api`：FastAPI 后端与智能体运行时
- `docs/superpowers/specs`：产品与技术设计文档
- `docs/superpowers/plans`：实现计划与任务拆解

## 当前已实现

- 账号注册、登录、`/me` 鉴权接口
- 用户绑定的项目会话创建与读取
- 智能体消息流式返回（SSE）
- 工作台三栏布局：会话侧栏、对话区、PRD 面板
- 登录态 token 持久化与基础用户信息缓存
- 会话恢复到当前工作台状态
- PRD Markdown 导出

## 产品边界

当前 V1 的核心不是固定工作流，而是一个状态驱动的智能体：

- AI 会根据当前状态持续追问和引导用户补充想法
- 如果用户的想法还没有被充分挖掘，系统会继续跟进而不是机械跳步骤
- 对话过程中会持续更新结构化状态和 PRD 草稿

## 本地启动

### 1. 安装依赖

```bash
pnpm install
pip install -e "apps/api[dev]"
```

### 2. 启动数据库

```bash
docker compose up -d
```

默认会启动本地 Postgres：

- 数据库：`ai_cofounder`
- 用户名：`postgres`
- 密码：`postgres`

### 3. 启动前后端

前端：

```bash
pnpm dev:web
```

后端：

```bash
python -m uvicorn app.main:app --reload --app-dir apps/api
```

## 常用命令

```bash
pnpm --filter web test
pnpm --filter web build
python -m pytest apps/api/tests -q
```

## 当前默认行为说明

- 工作台默认使用 `NEXT_PUBLIC_DEFAULT_SESSION_ID`，未设置时回退为 `demo-session`
- 前端使用 Zustand 持久化 token 和基础用户信息
- 会话恢复与导出入口位于左侧 `SessionSidebar`

## 后续建议

- 补齐数据库迁移执行与初始化说明
- 将默认单会话切换为真实用户多会话列表
- 继续增强智能体的状态推进、追问策略和 PRD 结构化填充
