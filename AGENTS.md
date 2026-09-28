# AGENTS.md — 祁智运县域物流平台维护指南

> 本文件是交给后续开发者（包括 GLM）的工作入口。先读本文件，再读
> [`PROJECT_HISTORY.md`](PROJECT_HISTORY.md)，最后根据任务范围阅读 `docs/` 下的专项文档。

## 1. 项目定位

祁智运是面向祁东县县域物流场景的智能调度与路径规划平台，服务于现代物流设计竞赛第二赛道。系统围绕“需求申请 → 数据审核 → 约束求解 → 方案审批 → 任务下发 → 驾驶员执行 → 动态重调度 → 结果追溯”形成闭环。

核心能力包括：

- 农产品上行与工业品下行的双向运输建模；
- 容量、时间窗、冷链、班次和车辆可用性约束下的确定性路径求解；
- OSRM 实时路网矩阵，服务异常时回退到离线距离估算；
- 县域地图、节点、车辆、订单、路线和事件的可视化；
- 车辆故障、紧急订单等动态事件的剩余任务重调度；
- 用户在线提交订单申请，管理员审核后转成运营订单；
- 驾驶员接单、下一站导航、发车和完成任务；
- 可选的 OpenAI 兼容模型解释与方案复核；
- 场景版本、运行编号、空间快照、实验结果和审计记录留痕。

系统是竞赛演示和县域样本验证平台，不应被表述为已经接入真实生产运输网络的商业 SaaS。新增功能必须明确其数据来源、演示边界和降级行为。

## 2. 开始工作前必须确认的事实

1. 运行时使用 Docker Compose，默认服务包括 PostgreSQL/PostGIS、Redis、FastAPI API、Celery Worker、迁移服务和 Nginx 前端。
2. 前端是 Vue 3 + TypeScript + Vite；后端是 Python 3.11 + FastAPI + SQLAlchemy/Alembic。
3. OR-Tools 是路径可行性和约束校验的权威求解器；AI 只能做解释、策略建议或候选方案复核，不能绕过硬约束直接改写路线。
4. `新增资料/` 是本地参考资料目录，已在 `.gitignore` 中排除，不能提交到 GitHub。
5. `.env`、数据库文件、备份、Docker Volume、地图/模型凭据和测试输出均属于本机状态，不能提交。
6. 当前分支可能包含用户尚未提交的文档、截图或脚本修改。开始工作前先运行 `git status --short`，只处理与当前任务直接相关的文件，不要覆盖或回滚无关改动。

## 3. 技术拓扑

```text
浏览器
  │  Vue 3 / TypeScript / ECharts / 高德 JS 或离线 GeoJSON
  ▼
Nginx frontend :80  ── /api 反向代理 ──► FastAPI api :8000
                                           │
                     ┌─────────────────────┼────────────────────┐
                     ▼                     ▼                    ▼
             PostgreSQL + PostGIS       Redis             OSRM 公共服务
             订单/场景/审计/凭据密文     Celery Broker      道路矩阵（可回退）
                                           │
                                           ▼
                                  Celery worker / OR-Tools
```

| 层次 | 目录/服务 | 责任 |
| --- | --- | --- |
| 页面层 | `frontend/` | 登录、注册、运营总览、调度、事件、执行、主数据、设置和报告入口 |
| API 层 | `backend/app/main.py` | 路由、认证、权限、参数校验、报告下载和运行时聚合 |
| 领域服务 | `backend/app/*_service.py` | 调度、导航、订单申请、主数据、实验、AI、地图和审计逻辑 |
| 数据层 | `backend/app/models.py`、`repository.py`、`alembic/` | 数据模型、初始化种子、场景版本、历史运行和迁移 |
| 求解层 | `optimization_orchestrator.py`、`routing_matrix.py` | OR-Tools/PyVRP、OSRM 矩阵、离线回退、指标与解释素材 |
| 异步层 | `celery_app.py`、`tasks.py` | 长耗时优化任务和 Redis 结果查询 |
| 编排层 | `docker-compose.yml`、`deploy/` | 数据库初始化、迁移和服务健康检查 |

## 4. 目录职责

- `backend/app/data/`：稳定的县域演示场景、双向运输事实和参考数据适配，不放密钥。
- `backend/tests/`：API、双向场景、求解器、导航和数据契约测试。
- `frontend/src/`：页面、组件、状态与 API 客户端。请求路径统一经过 `services/api.ts`。
- `docs/`：设计方案、接口契约、部署、验收、阶段记录和参考资料接入说明。
- `scripts/`：启动控制、分享隧道、截图、报告构建和 QA 脚本。
- `deploy/postgres/`：PostgreSQL 初始化脚本和应用数据库角色配置。
- `tools/`：辅助工具和离线数据处理工具，不承担运行时业务逻辑。
- `backups/`、`outputs/`、`qizhi.db`：本机生成物，不应进入版本库。

## 5. 角色和业务边界

| 角色 | 允许的主要操作 | 不应拥有的能力 |
| --- | --- | --- |
| `admin` | 全部运营数据、场景发布、方案审批、系统设置、用户治理、审计 | 不应在前端展示明文密钥 |
| `dispatcher` | 查看场景、生成方案、提交/下发方案、查看执行状态 | 不能管理密钥和系统用户 |
| `driver` | 查看自己的任务、接受、发车、下一站导航、完成任务 | 不能读取其他驾驶员任务或触发全局求解 |
| `viewer` | 只读查看运营结果和报告 | 不能修改业务数据 |
| `user` | 注册、提交/查看/撤回自己的订单申请 | 不能读取运营订单总表、调度或审批 |

标准业务状态：

```text
用户申请 pending_review
  ├─ needs_info ──► pending_review
  ├─ rejected
  ├─ cancelled
  └─ converted ──► 运营订单

方案 draft ──► pending_review ──► approved ──► dispatched
                                      └──────► rejected
驾驶任务 pending ──► accepted ──► executing ──► completed
```

管理员审核用户申请时，后端事务会创建运营订单并发布新的场景版本；不要在前端自行复制订单或直接修改场景 JSON。

## 6. 运行和演示

### 6.1 推荐的 Windows 启动方式

前置条件：安装并启动 Docker Desktop，80 端口未被占用。非技术用户优先双击根目录的 `安装并启动祁智运平台.bat`；已完成安装后可双击 `启动祁智运平台.bat`。脚本会自动检查 Docker、创建本地 `.env`（缺失时从 `.env.example` 复制）、构建镜像并等待健康检查。

浏览器访问：`http://127.0.0.1`。

常用入口：

```text
启动祁智运平台.bat        启动/构建服务并打开浏览器
检查平台状态.bat          查看容器和健康状态
停止祁智运平台.bat        停止服务但保留数据库卷
一键恢复标准演示数据.bat  备份后恢复稳定的演示订单、车辆和事件
分享给同学.bat            启动临时 Cloudflare Quick Tunnel
停止分享链接.bat          停止临时公网隧道
```

恢复标准数据会先创建数据库备份。不要用 `docker compose down -v` 作为日常停止命令；它会删除数据库和 Redis 数据卷。只在明确要清空本机数据并已确认备份可用时使用。

### 6.2 命令行启动和状态检查

```powershell
Set-Location E:\wuliu_project
Copy-Item .env.example .env   # 仅首次使用；随后编辑本地 .env
docker compose up -d --build
docker compose ps
Invoke-RestMethod http://127.0.0.1/api/v1/health/ready
docker compose logs --tail=100 api worker frontend
```

停止但保留数据：

```powershell
docker compose stop
```

临时分享使用 Quick Tunnel，公网地址只在 `分享给同学.bat` 和隧道进程保持运行时有效。地址变化会导致高德 Web Key 的域名白名单再次校验；这属于当前演示部署限制，不要把临时 URL 写入代码。

### 6.3 标准演示顺序

1. 管理员登录，打开“运营总览”确认订单、车辆、路网和预测卡片。
2. 进入“智能调度”，选择当前场景，生成可行方案并查看约束、里程、成本、车辆数和未分配订单。
3. 提交并审批方案，再下发驾驶任务。
4. 使用独立浏览器窗口/无痕窗口登录驾驶员账号；进入“执行中心”，接受任务，查看下一站导航，确认发车。
5. 回到管理员窗口打开“动态事件”，触发车辆故障或紧急订单，执行剩余任务重调度。
6. 查看执行状态、方案历史、运营评估和可打印报告。
7. 演示结束使用“一键恢复标准演示数据.bat”，下一次演示从同一基线开始。

## 7. 配置和安全

### 7.1 `.env` 变量

`.env.example` 是可提交模板；`.env` 只保存在本机。常见变量包括：

```text
DATABASE_URL
REDIS_URL
JWT_SECRET
AI_CONFIG_ENCRYPTION_KEY
ADMIN_USERNAME / ADMIN_PASSWORD
DRIVER_USERNAME / DRIVER_PASSWORD
CORS_ORIGINS
ROUTING_PROVIDER
OSRM_BASE_URL / OSRM_PROFILE / OSRM_TIMEOUT_SECONDS
```

不要在代码、Markdown、截图、日志、测试输出或 Git 历史中写入真实 API Key、数据库密码、JWT 密钥、地图安全密钥或用户口令。示例只使用 `YOUR_API_KEY_HERE`、`<本地配置>` 等占位符。

### 7.2 AI 配置

管理员在系统设置中填写 OpenAI 兼容服务的 Base URL、模型 ID 和 API Key。后端使用 Fernet 加密保存 API Key；读取接口只返回掩码，浏览器和报告不应拿到明文。服务商不是官方 OpenAI 时，Base URL 必须使用服务商实际兼容接口，不能盲填官方地址。

AI 的职责是生成解释、风险提示或对候选方案进行复核。路线必须先经过容量、时间窗、冷链和车辆可用性等确定性约束校验；AI 不可作为唯一安全判定。

### 7.3 地图和路网

- 高德 Web JS Key、地图样式和服务端安全密钥通过系统设置配置，密钥由服务端保存并代理敏感请求。
- 没有可用地图配置时使用离线县域底图/GeoJSON，不能因此阻断调度求解。
- `ROUTING_PROVIDER=osrm` 时优先请求 OSRM；公共服务超时、限流或网络失败时自动使用离线距离和乡村绕行系数，并在结果中标注来源和回退原因。
- 坐标必须区分 WGS84、GCJ-02 和前端展示坐标；修改节点时同步检查空间快照和地图标点，不能只改名称不改坐标。

## 8. 开发规范

1. 开始改动前先读本文件、`PROJECT_HISTORY.md`、相关专项文档和目标代码；先写可验证的成功标准。
2. 只修改完成任务所需的文件，不顺手重构相邻模块。保留工作区已有改动，不使用 `git reset --hard` 或 `git checkout --` 覆盖用户文件。
3. 后端新接口放在 `/api/v1`，补充 Pydantic schema、角色依赖、错误状态码、审计（如涉及写操作）和测试。
4. 涉及数据库结构时新增 Alembic migration；不要靠启动时隐式改表。种子/演示数据改动要同步更新恢复脚本和相关验收文档。
5. 方案结果必须保留场景版本、空间快照、运行编号、矩阵来源、求解器和约束摘要，保证结果可复现。
6. 前端请求只通过 API 服务封装；加载、空态、错误态和权限不足状态要有明确反馈。修改地图或执行页时至少做一次宽屏和窄屏检查。
7. 每个可独立验证的改动使用小而明确的提交：`feat`、`fix`、`test`、`docs`、`chore`。提交前检查 `git diff --check`，暂存时使用明确文件列表。
8. 不把 `新增资料/`、真实数据备份、截图导出物、`node_modules/`、`.venv/`、`.env` 或密钥加入提交。

## 9. 测试和验收

后端依赖项目虚拟环境（Python 3.11）：

```powershell
Set-Location E:\wuliu_project\backend
..\.venv\Scripts\python.exe -m compileall -q app
..\.venv\Scripts\python.exe -m pytest -q tests/test_navigation_service.py
..\.venv\Scripts\python.exe -m pytest -q tests/test_bidirectional_scenario.py tests/test_bidirectional_solver.py tests/test_flow_schema.py
```

完整 API 测试：

```powershell
..\.venv\Scripts\python.exe -m pytest -q
```

测试默认可能使用本地 SQLite 文件 `qizhi.db`，而测试会产生用户、运行和历史状态；要验证干净结果，应在独立临时目录/临时数据库中运行，或先备份并清理测试数据库。Docker 运行时的真实数据在 PostgreSQL Volume 中，两者不要混用。

前端检查：

```powershell
Set-Location E:\wuliu_project\frontend
pnpm install
pnpm build
```

涉及完整页面流程时，应检查登录/注册、运营总览、智能调度、动态事件、执行中心、用户订单申请、基础数据、系统设置和退出登录。涉及导航时还要验证：导航起点不是共配中心重复点、下一站是实际服务节点、OSRM 不可用时回退提示仍清晰、打开高德后原平台标签仍可返回。

容器验收：

```powershell
Set-Location E:\wuliu_project
docker compose up -d --build
docker compose ps
Invoke-RestMethod http://127.0.0.1/api/v1/health/ready
```

## 10. 故障排查顺序

1. 页面白屏或一直加载：先看 `docker compose ps`、`docker compose logs --tail=100 api frontend`，再请求 `/api/v1/health/ready`。
2. 驾驶员页面没有任务：确认方案已审批且已下发，驾驶员只会读取自己的 assignment；不要通过修改前端条件绕过权限。
3. OSRM 暂不可用：查看 `/api/v1/routing/status` 和 API 日志；确认结果中的 `fallback_used`、`source` 和 `fallback_reason`，先保证离线回退可用，再决定是否重试公共服务。
4. 高德地图空白：检查当前 URL 是否加入 Web Key 白名单、Key 类型是否为 Web JS、服务端安全代理是否启用；离线地图仍应能打开。
5. AI 401/403：确认 Base URL、模型 ID、Key 权限和服务商兼容路径；不要把错误响应中的 Key 复制到日志或工单。
6. 恢复演示数据失败：保留脚本打印的备份路径，先不要重复执行破坏性命令；检查 `migrate`、`db` 容器状态，再由维护人员决定恢复方式。

## 11. 交接完成检查单

- [ ] 已阅读 `PROJECT_HISTORY.md` 和相关专项文档。
- [ ] `git status --short` 中的原有改动已区分，未被覆盖。
- [ ] `.env`、数据库、备份、`新增资料/` 和密钥未被暂存。
- [ ] 后端目标测试、前端构建和 Docker 健康检查有实际结果记录。
- [ ] 新接口、迁移、权限、审计和文档已同步。
- [ ] 演示从标准数据恢复后可重复执行。
- [ ] 提交信息能说明改动范围，远程推送前确认目标分支和远程最新提交。
