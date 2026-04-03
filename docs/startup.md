# 项目启动文档

本文档用于在 Windows PowerShell 环境下启动 `AI Co-founder` 项目，包含：

- `uv` 虚拟环境创建与激活
- 前后端依赖安装
- 数据库启动与迁移
- 前后端本地启动

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

- 根目录 [`.env`](D:/AI/chat-prd/.env)
- 前端 [`apps/web/.env.local`](D:/AI/chat-prd/apps/web/.env.local)

当前配置如下：

根目录 `.env`

```env
DATABASE_URL=postgresql+psycopg://aimovie:xtCGcStxwnJS3T6R@111.228.37.74:5432/aimovie
AUTH_SECRET_KEY=ai-cofounder-local-dev-secret-change-me
```

前端 `apps/web/.env.local`

```env
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

## 3. 创建并激活 uv 虚拟环境

在项目根目录 [D:\AI\chat-prd](D:/AI/chat-prd) 执行：

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
Set-Location D:\AI\chat-prd
pnpm dev:web
```

前端默认地址通常为：

```text
http://localhost:3000
```

## 9. 推荐启动顺序

建议严格按下面顺序执行：

```powershell
Set-Location D:\AI\chat-prd
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
Set-Location D:\AI\chat-prd
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

## 11. 一键启动脚本

如果你已经完成了依赖安装，并且根目录 `.venv` 已创建，可以直接运行：

```powershell
Set-Location D:\AI\chat-prd
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1
```

这个脚本会做两件事：

- 先执行 `alembic upgrade head`
- 再分别打开两个新窗口启动后端和前端

如果你这次不想跑迁移，可以加参数：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\dev.ps1 -SkipMigrate
```

## 12. 常见问题

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
- [`apps/web/.env.local`](D:/AI/chat-prd/apps/web/.env.local) 的 `NEXT_PUBLIC_API_BASE_URL` 是否正确

## 13. 一键理解版

如果你现在就是要本地跑起来，最短路径是：

```powershell
Set-Location D:\AI\chat-prd
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
Set-Location D:\AI\chat-prd
pnpm dev:web
```
