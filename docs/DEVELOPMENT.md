# 祁智运开发文档

本文档面向接收、运行和继续开发本项目的同学。项目是一个面向祁东县县域物流场景的智能调度平台，核心流程是“基础数据 → 路线求解 → 方案审批 → 任务执行 → 动态重调度 → 结果追溯”。

## 1. 项目组成

```text
backend/       FastAPI 接口、数据库模型、OR-Tools 求解、Celery Worker
frontend/      Vue 3 + TypeScript 管理端界面
deploy/        PostgreSQL 初始化脚本、迁移与容器辅助文件
docs/          设计方案、接口契约、部署文档和本开发文档
scripts/       测试、截图、数据恢复和文档构建脚本
tools/         辅助工具与离线数据
docker-compose.yml  PostgreSQL/PostGIS、Redis、API、Worker、Nginx 编排
```

系统角色包括系统管理员、调度员、驾驶员和查看者。公开注册只创建最低权限的运营账号，管理员账号不能由注册页自助创建。

## 2. 推荐启动方式

### 2.1 Windows + Docker Desktop

要求：Docker Desktop 已启动，并且 80 端口没有被其他程序占用。

面向非技术使用者，优先双击项目根目录的 `安装并启动祁智运平台.bat`。该向导会检查 Docker Desktop；首次使用时打开官方安装页面并显示 WSL2、重启等提示，安装完成后再次双击即可自动启动。后续使用不需要重复安装。

如果 Docker Desktop 已经安装，也可以直接双击 `启动祁智运平台.bat`。状态检查和停止操作分别使用 `检查平台状态.bat`、`停止祁智运平台.bat`。

```powershell
Copy-Item .env.example .env
# 首次使用前编辑 .env，至少修改数据库密码、JWT_SECRET 和管理员密码
docker compose up -d --build
```

浏览器访问 `http://127.0.0.1`。停止服务：

```powershell
docker compose stop
```

查看状态：

```powershell
docker compose ps
docker compose logs --tail=100 api
```

项目根目录的中文 `.bat` 脚本也可用于启动、停止、检查状态和恢复标准数据。

### 2.2 首次使用

1. 使用 `.env` 中的管理员账号登录。
2. 普通用户可从登录页进入注册页，注册后自动登录。
3. 管理员进入“系统设置”，添加 AI 服务或地图服务连接；API Key 只显示掩码，后端加密保存。
4. 先查看“运营总览”，再进入“智能调度”生成方案。
5. 方案需要提交、审批、下发后，驾驶员账号才能看到对应任务。

## 3. AI 与地图服务配置

系统使用 OpenAI 兼容的 Chat Completions 接口。配置时必须同时确认：

- Base URL 与服务商实际接口地址一致；
- 模型 ID 是服务商支持的模型；
- API Key 有效且具备调用权限；
- 如果服务商不是官方 OpenAI，不能直接把 Base URL 填成 `https://api.openai.com/v1`。

地图配置分为浏览器地图 Key 与服务端路线矩阵服务。地图服务不可用时，系统保留离线底图和确定性求解能力，并明确显示降级状态。

## 4. 本地开发

后端需要 Python 3.11 及项目依赖：

```powershell
cd backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

前端需要 Node.js 与 pnpm：

```powershell
cd frontend
pnpm install
pnpm dev --host 127.0.0.1
```

本地前端地址为 `http://127.0.0.1:5173`，接口文档为 `http://127.0.0.1:8000/docs`。本地开发时应使用独立数据库，不要直接操作交付用 Docker Volume。

## 5. 测试与质量检查

后端测试：

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest -q
```

前端构建：

```powershell
cd frontend
pnpm build
```

涉及页面修改时，应同时检查登录、注册、运营总览、智能调度、动态事件、执行中心和系统设置。涉及数据库或配置修改时，应检查迁移、恢复标准数据和敏感信息脱敏。

## 6. 标准数据恢复

如果订单、车辆或故障事件被误操作，使用根目录的“一键恢复标准演示数据.bat”，或按部署文档执行恢复脚本。恢复前系统会保留备份；不要使用 `docker compose down -v`，该命令会删除数据库卷。

## 7. 继续开发约定

- 新接口统一放在 `/api/v1` 下，并补充权限校验、错误码和测试。
- 新业务结果必须记录场景版本、空间快照、道路矩阵来源和运行编号。
- AI 只能提供策略建议或候选方案复核，容量、时间窗、冷链和车辆可用性仍由确定性求解器校验。
- API Key、JWT 密钥、数据库密码和地图安全密钥不得提交到 Git。
- 提交前执行 `git diff --check`、后端测试和前端构建。
- 提交信息建议使用 `feat`、`fix`、`docs`、`test`、`chore` 前缀。

## 8. GitHub 交付检查

推送前确认：

```powershell
git status --short
git diff --check
git check-ignore .env qizhi.db outputs
```

确认 `.env`、数据库文件、Docker Volume、`node_modules`、`.venv` 和 QA 输出没有进入暂存区，再执行提交和推送。
