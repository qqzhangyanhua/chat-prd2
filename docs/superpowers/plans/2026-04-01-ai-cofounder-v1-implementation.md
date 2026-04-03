# AI Co-founder V1 实现计划

## 目标

交付一个可运行的 AI Co-founder V1 MVP，覆盖以下闭环：

- 用户注册登录
- 创建并绑定用户会话
- 在工作台中与智能体持续对话
- 流式更新结构化状态与 PRD
- 恢复当前会话
- 导出 PRD Markdown

## 已完成任务

### 任务 1：Monorepo 初始化

- 根目录脚本、工作区配置、`docker-compose.yml`
- `apps/web` 与 `apps/api` 基础项目结构

### 任务 2：FastAPI 应用壳

- `GET /api/health`
- API 主入口与基础配置

### 任务 3：数据库模型与迁移

- 用户、项目会话、状态版本、PRD 快照、消息表
- Alembic 初始迁移

### 任务 4：认证系统

- 注册、登录、`/api/auth/me`
- 密码哈希
- JWT 鉴权

### 任务 5：会话与初始状态

- 创建项目会话
- 生成初始状态与 PRD 快照
- 用户与会话绑定

### 任务 6：智能体运行时

- 状态驱动的下一步动作判断
- 基础智能体结果结构

### 任务 7：消息流式接口

- `POST /api/sessions/{session_id}/messages`
- SSE 事件流
- 助手消息持久化

### 任务 8：前端认证页

- 登录页、注册页
- API client
- token 持久化

### 任务 9：工作台布局

- 三栏结构
- 会话侧栏、对话区、PRD 面板骨架

### 任务 10：工作台接入流式事件

- Zustand 工作台状态
- 对话流式消费
- PRD 面板实时更新

### 任务 11：会话恢复与导出

- `GET /api/sessions/{session_id}` 获取最新快照
- `POST /api/sessions/{session_id}/export` 导出 Markdown
- 左侧侧栏恢复和导出入口

## 当前实现状态

### 后端

已具备：

- 认证接口
- 会话创建与读取
- SSE 对话接口
- 会话快照恢复
- Markdown 导出

当前仍建议补充：

- 数据库迁移执行文档
- 更完善的配置管理
- 更细的 agent state patch 逻辑

### 前端

已具备：

- 注册登录页
- token 与用户信息持久化
- 工作台三栏 UI
- 对话流式渲染
- PRD 实时展示
- 恢复 / 导出操作

当前仍建议补充：

- 多会话列表与切换
- 首次进入工作台的会话创建引导
- 更完整的错误提示与加载态

## 验证基线

当前分支最近一次收尾验证命令：

```bash
python -m pytest apps/api/tests -q
pnpm --filter web test
pnpm --filter web build
```

验证结果：

- 后端测试：`23 passed`
- 前端测试：`13 passed`
- 前端构建：成功

## 下一阶段建议

### P1

- 把默认 `demo-session` 替换成真实“创建会话 -> 进入工作台”链路
- 增强 agent 对状态缺口的判断和连续追问能力
- 细化 PRD section 的状态标记与来源标记

### P2

- 增加用户历史会话列表
- 支持会话标题编辑、重命名和最近访问时间
- 为导出增加文件名策略和更多格式

### P3

- 增加 RAG / 模板检索
- 增加更强的 critic 机制
- 为后续团队协作能力预留数据模型

## 提交记录

当前与 V1 工作台闭环直接相关的最近提交包括：

- `0aa6e73` `feat: add auth pages and persisted client auth`
- `e3caf1e` `feat: add workspace layout skeleton`
- `88d8c0c` `feat: wire workspace to streaming agent events`
- `3e06e0e` `feat: add session recovery and markdown export`
