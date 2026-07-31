# 第十七阶段开发文档：交付加固与一键验收

## 1. 阶段目标

第十六阶段已经打通空间坐标、求解、路线和事件位置链路。本阶段不扩张业务范围，集中完成正式交付前的工程收口：

- 健康检查能够区分“进程存活”和“依赖可用”；
- 对外接口使用运营业务命名，旧路径仅作为隐藏兼容层；
- 地图与图表代码按需加载，降低非地图页面首屏体积；
- Docker 能分别识别 API、任务进程和前端状态；
- 提供一条命令完成交付环境的关键链路自检；
- 完成桌面端、移动端和主要业务路径回归。

## 2. 健康检查分层

新增：

- `GET /api/v1/health/live`：只判断 API 进程是否存活；
- `GET /api/v1/health/ready`：检查 PostgreSQL、Alembic 版本表和 Redis。

就绪检查任一依赖失败时返回 HTTP 503，使 Docker、反向代理和监控系统能够正确摘除异常实例。原 `/health` 保留用于兼容现有调用。

## 3. 容器健康状态

- API 容器使用 `/health/ready`；
- Celery Worker 使用节点定向 `inspect ping`；
- Nginx 前端使用容器内 HTTP 请求；
- PostgreSQL 与 Redis 沿用各自原生探针。

`docker compose ps` 应同时显示数据库、缓存、API、Worker 和前端健康或正常运行。

## 4. 专业化接口

正式接口调整为：

- `GET /api/v1/operations/readiness`
- `GET /api/v1/operations/report`

历史路径继续可用，但通过 `include_in_schema=False` 从 OpenAPI 文档中隐藏。前端仅调用正式路径。

OpenAPI、Swagger UI 和 ReDoc 统一部署在 `/api/v1/openapi.json`、`/api/v1/docs`、`/api/v1/redoc`，确保能够通过 Nginx 反向代理访问。

## 5. 前端性能

- `ProfessionalCountyMap` 改为异步组件；
- ECharts 改用 `echarts/core`，只注册地图实际使用的 Geo、Lines、Scatter、EffectScatter 和 Canvas Renderer；
- Vue 框架与图标库拆为稳定缓存分包；
- 登录、用户治理、系统设置等非地图页面不再同步加载地图运行时代码。

## 6. 一键自检

新增：

```powershell
.\scripts\release_check.ps1
```

检查范围：

- API 存活与依赖就绪；
- 管理员登录；
- 运营评估接口；
- 空间数据治理状态；
- OpenAPI 不暴露历史路径；
- Docker 核心服务是否运行。

正式交付前使用：

```powershell
.\scripts\release_check.ps1 -StrictSecurity
```

严格模式会阻止使用默认管理员密码通过验收。

## 7. 验收标准

- 后端自动化测试全部通过；
- 前端类型检查和生产构建通过，主包体积显著下降；
- Docker 全部运行服务通过健康检查；
- 一键自检无失败项；
- 登录、智能调度、故障重调度、运营评估和系统设置主要路径可访问；
- 桌面端和 390px 移动端无横向溢出；
- 浏览器无框架错误遮罩和应用控制台错误；
- 业务界面及公开 OpenAPI 不出现非业务化赛事措辞。

## 8. 实施与验收记录

- 后端自动化测试：`24 passed`。
- 前端生产构建通过，主入口 JavaScript 由约 `1.23 MB` 降至约 `21 KB`。
- 地图业务分包约 `97 KB`，最大图表运行时分包约 `478 KB`，构建无超大分包警告。
- API 就绪探针确认 PostgreSQL、Alembic 和 Redis 全部正常。
- PostgreSQL、Redis、API、Celery Worker、Nginx 前端全部通过容器健康检查。
- 一键自检全部通过；本地默认管理员密码显示安全警告。
- 浏览器确认前端只请求 `/operations/readiness`，历史路径未出现在 OpenAPI。
- 1536×1024 与 390×844 视口均无横向溢出，地图、预测图表、运营评估和系统设置正常。
- 浏览器控制台无应用错误。
