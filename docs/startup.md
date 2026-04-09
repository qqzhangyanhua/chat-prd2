# 项目启动文档

本文档用于在 Windows PowerShell 环境下启动 `AI Co-founder` 项目，包含：

- `uv` 虚拟环境创建与激活
- 前后端依赖安装
- 数据库启动与迁移
- 前后端本地启动

## 文档导航

如果你正在维护“生成 PRD”链路，建议同时查看下面这组契约文档：

- [PRD 契约索引](/Users/zhangyanhua/AI/chat-prd2/docs/contracts/README.md)
- [PRD 运行时契约](/Users/zhangyanhua/AI/chat-prd2/docs/contracts/prd-runtime-contract.md)
- [PRD Meta 共享样例](/Users/zhangyanhua/AI/chat-prd2/docs/contracts/prd-meta-cases.json)

## 1. 环境准备

建议先确认本机已安装：

- Node.js
- `pnpm`
- Python 3.12+
- `uv`
- Docker Desktop

如果还没有安装 `pnpm`，可以先执行：

```powershell
npm install -g pnpm
```

如果还没有安装 `uv`，可以参考官方安装方式；安装完成后确认：

```powershell
uv --version
```

## 2. 项目环境变量

当前项目已经准备好以下环境变量文件：

- 根目录 [`.env`](/Users/zhangyanhua/AI/chat-prd2/.env)
- 前端 [`apps/web/.env.local`](/Users/zhangyanhua/AI/chat-prd2/apps/web/.env.local)

当前配置如下：

根目录 `.env`

```env
DATABASE_URL=postgresql+psycopg://aimovie:xtCGcStxwnJS3T6R@111.228.37.74:5432/aimovie
AUTH_SECRET_KEY=ai-cofounder-local-dev-secret-change-me
ADMIN_EMAILS=admin@example.com
```

前端 `apps/web/.env.local`

```env
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

### 2.1 管理员邮箱白名单

`ADMIN_EMAILS` 用于声明管理员邮箱白名单，多个邮箱使用英文逗号分隔：

```env
ADMIN_EMAILS=admin@example.com,ops@example.com
```

命中白名单的用户在登录后会从后端拿到 `is_admin=true`，前端会自动显示管理员入口；未命中的普通用户不会看到模型管理页入口，也不能调用管理员接口。

### 2.2 OpenAI 兼容模型配置

本项目支持通过管理员页面接入外部“OpenAI 兼容接口”模型。管理员登录后可进入：

```text
/admin/models
```

在该页面中维护以下字段：

- `name`：模型配置显示名称
- `base_url`：外部模型服务的 OpenAI 兼容接口地址
- `api_key`：调用该模型的密钥
- `model`：真实请求时传给上游服务的模型 ID
- `enabled`：是否启用

启用后的模型会出现在工作台会话页的模型选择器中，用户每次发送消息前都可以切换。后端会根据所选模型配置，使用对应的 `base_url + api_key + model` 发起真实对话请求。

## 3. 创建并激活 uv 虚拟环境

在项目根目录 [`/Users/zhangyanhua/AI/chat-prd2`](/Users/zhangyanhua/AI/chat-prd2) 执行：

```powershell
uv venv
```

PowerShell 激活虚拟环境：

```powershell
.\.venv\Scripts\Activate.ps1
```

激活成功后，命令行前面通常会出现 `(.venv)`。

如果 PowerShell 阻止脚本执行，可以先临时放开当前会话：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
```

然后再次执行：

```powershell
.\.venv\Scripts\Activate.ps1
```

## 4. 安装依赖

### 4.1 安装前端依赖

在项目根目录执行：

```powershell
pnpm install
```

### 4.2 安装后端依赖

虚拟环境激活后，在项目根目录执行：

```powershell
uv pip install -e "apps/api[dev]"
```

如果你不想用 `uv pip`，也可以用：

```powershell
pip install -e "apps/api[dev]"
```

## 5. 数据库准备

### 5.1 如果你使用远程数据库

你当前 `.env` 已经配置为远程 PostgreSQL：

```env
DATABASE_URL=postgresql+psycopg://aimovie:xtCGcStxwnJS3T6R@111.228.37.74:5432/aimovie
```

这种情况下，一般不需要执行 `docker compose up -d`。

你只需要确认：

- 服务器 `111.228.37.74:5432` 可访问
- 用户名密码正确
- 数据库 `aimovie` 已存在

### 5.2 如果你要切回本地数据库

可以把根目录 `.env` 改回：

```env
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/ai_cofounder
```

然后执行：

```powershell
docker compose up -d
```

## 6. 执行数据库迁移

当前项目使用 Alembic 管理数据库迁移。

在虚拟环境激活状态下执行：

```powershell
Set-Location .\apps\api
alembic upgrade head
Set-Location ..\..
```

如果迁移成功，数据库表会自动创建到当前 `DATABASE_URL` 指向的库里。

## 7. 启动后端

在项目根目录、且虚拟环境已激活的前提下执行：

```powershell
python -m uvicorn app.main:app --reload --app-dir apps/api
```

后端默认地址：

```text
http://127.0.0.1:8000
```

健康检查接口：

```text
http://127.0.0.1:8000/api/health
```

## 8. 启动前端

新开一个 PowerShell 窗口，进入项目根目录：

```powershell
Set-Location D:\AI\chat-prd2
pnpm dev:web
```

前端默认地址通常为：

```text
http://localhost:3000
```

## 9. 推荐启动顺序

建议严格按下面顺序执行：

```powershell
Set-Location D:\AI\chat-prd2
uv venv
.\.venv\Scripts\Activate.ps1
uv pip install -e "apps/api[dev]"
pnpm install
Set-Location .\apps\api
alembic upgrade head
Set-Location ..\..
python -m uvicorn app.main:app --reload --app-dir apps/api
```

然后新开一个窗口：

```powershell
Set-Location D:\AI\chat-prd2
pnpm dev:web
```

## 10. 常用验证命令

### 前端测试

```powershell
pnpm --filter web test
```

### 前端构建

```powershell
pnpm --filter web build
```

### 后端测试

```powershell
python -m pytest apps/api/tests -q
```

## 11. PRD 定向回归

如果你只改了“生成 PRD”链路，优先跑这组最小回归：

前端：

```bash
pnpm --filter web test -- src/test/workspace-store.test.ts src/test/workspace-session-shell.test.tsx src/test/prd-panel.test.tsx
```

后端：

```bash
PYTHONPATH=apps/api uv run pytest apps/api/tests/test_messages_service.py apps/api/tests/test_messages_stream.py -q
```

如果只是改 `prd.meta` 阶段判断或文案，最小验证可以再收窄为：

前端：

```bash
pnpm --filter web test -- src/test/workspace-store.test.ts
```

后端：

```bash
PYTHONPATH=apps/api uv run pytest apps/api/tests/test_messages_service.py::test_preview_prd_meta_matches_shared_contract -q
```

更多背景和排查顺序见：

- [PRD 契约索引](/Users/zhangyanhua/AI/chat-prd2/docs/contracts/README.md)
- [PRD 运行时契约](/Users/zhangyanhua/AI/chat-prd2/docs/contracts/prd-runtime-contract.md)

## 12. 一键启动脚本

如果你已经完成了依赖安装，并且根目录 `.venv` 已创建，可以直接运行：

```powershell
Set-Location D:\AI\chat-prd2
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1
```

这个脚本会做两件事：

- 先执行 `alembic upgrade head`
- 再分别打开两个新窗口启动后端和前端

如果你这次不想跑迁移，可以加参数：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -SkipMigrate
```

## 13. 常见问题

### 12.1 PowerShell 无法激活 `.venv`

执行：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
```

然后重新激活：

```powershell
.\.venv\Scripts\Activate.ps1
```

### 12.2 后端启动报数据库连接失败

优先检查：

- `.env` 里的 `DATABASE_URL` 是否正确
- 远程数据库是否开放了白名单
- 5432 端口是否可访问
- 数据库用户名密码是否正确

### 12.3 前端页面打开但接口报错

优先检查：

- 后端是否已经启动在 `http://127.0.0.1:8000`
- [`apps/web/.env.local`](/Users/zhangyanhua/AI/chat-prd2/apps/web/.env.local) 的 `NEXT_PUBLIC_API_BASE_URL` 是否正确

如果你能登录、也能创建会话，但进入会话页时看到 `Failed to fetch`、`当前会话加载失败`，或者浏览器控制台里出现看起来像 CORS 的报错，优先先执行一次数据库迁移：

```powershell
Set-Location .\apps\api
alembic upgrade head
Set-Location ..\..
```

这是因为最近新增了 `agent_turn_decisions` 等表，如果本地数据库还停在旧 revision，后端在读取会话快照时会失败，前端往往只会表现成加载失败。

## 14. 一键理解版

如果你现在就是要本地跑起来，最短路径是：

```powershell
Set-Location D:\AI\chat-prd2
uv venv
.\.venv\Scripts\Activate.ps1
uv pip install -e "apps/api[dev]"
pnpm install
Set-Location .\apps\api
alembic upgrade head
Set-Location ..\..
python -m uvicorn app.main:app --reload --app-dir apps/api
```

再开一个窗口：

```powershell
Set-Location D:\AI\chat-prd2
pnpm dev:web
```
