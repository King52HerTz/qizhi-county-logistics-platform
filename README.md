# 祁智运

面向祁东县黄花菜产业的县域物流 AI 智能调度、路径规划与可视化平台。项目对应第十一届湖南省大学生现代物流设计竞赛第二赛道，以“可解释的约束优化 + 动态重调度 + 县域可视化”为核心演示闭环。

## 当前成果

- Vue 3 + TypeScript 调度大屏与动态事件页面。
- FastAPI + OR-Tools 容量/时间窗/冷链兼容路径求解。
- 祁东县离线 GeoJSON，无地图密钥也可演示。
- 冷链车辆故障、新增紧急订单和剩余任务重调度。
- 管理员可在系统设置中配置 OpenAI 兼容模型服务，API Key 加密入库。
- 标准 Excel 场景模板、整批校验、版本留痕和一键激活。
- 数据中心可对历史调度方案发起 AI 解读。
- 可配置 OSRM 真实道路矩阵，异常时自动回退离线路网估算。
- 七日需求预测、乡镇需求排行、冷链需求和建议运力驾驶舱。
- 调度方案审批、任务下发、驾驶员接单和执行完成闭环。
- 自包含执行报告下载与浏览器打印。
- 三压力算法对照实验、场景指纹、历史留痕与实验报告。
- 自动化接口测试、生产构建与浏览器交互验证。

## Docker 一键启动（推荐）

```powershell
cd E:\wuliu_project
Copy-Item .env.example .env
docker compose up -d --build
```

浏览器打开 `http://127.0.0.1`。该方式会启动 PostgreSQL/PostGIS、Redis、迁移服务、FastAPI、Celery Worker 和 Nginx 前端，数据保存在 Docker Volume 中。

首次进入“系统设置”使用 `.env` 中的管理员账号登录，再填写模型服务的 Base URL、模型 ID 和 API Key。默认演示账号为 `admin / QizhiDemo2026!`，正式部署必须修改。

详细说明见 [Docker 部署与运维](docs/DEPLOYMENT.md)。

接收者可先阅读 [开发文档](docs/DEVELOPMENT.md)，其中包含注册、AI/地图配置、测试、标准数据恢复和继续开发约定。

## 本地开发启动

后端：

```powershell
cd E:\wuliu_project\backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

前端：

```powershell
cd E:\wuliu_project\frontend
pnpm dev --host 127.0.0.1
```

浏览器打开 `http://127.0.0.1:5173`，接口文档位于 `http://127.0.0.1:8000/docs`。

## 文档

- [总体设计与开发方案](docs/DEVELOPMENT_PLAN.md)
- [开源复用清单](docs/OPEN_SOURCE_REUSE.md)
- [API 契约](docs/API.md)
- [验收标准](docs/ACCEPTANCE.md)
- [Docker 部署与运维](docs/DEPLOYMENT.md)
- [AI 服务配置](docs/AI_CONFIGURATION.md)
- [第三阶段开发任务](docs/PHASE3_DEVELOPMENT.md)
- [第四阶段开发任务](docs/PHASE4_DEVELOPMENT.md)
- [第五阶段开发任务](docs/PHASE5_DEVELOPMENT.md)
- [第六阶段开发任务](docs/PHASE6_DEVELOPMENT.md)

## 目录

```text
backend/             FastAPI、场景数据、OR-Tools 求解器与测试
frontend/            Vue 3 调度大屏
docs/                设计、接口、开源与验收文档
docs/concepts/       ImageGen 页面概念设计图
```

演示数据用于竞赛原型验证，不代表真实生产订单。
