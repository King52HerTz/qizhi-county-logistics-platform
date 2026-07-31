# 开源复用清单

项目优先复用成熟能力，不自行实现通用求解器、地图引擎或图表库。

| 项目 | 许可证 | 本项目用途 | 采用方式 |
|---|---|---|---|
| [Google OR-Tools](https://github.com/google/or-tools) | Apache-2.0 | CVRPTW、容量、时间窗与车辆兼容求解 | MVP 直接依赖 |
| [PyVRP](https://github.com/PyVRP/PyVRP) | MIT | 大规模、多车型、多仓算法扩展 | 已安装，第二阶段 |
| [Apache ECharts](https://github.com/apache/echarts) | Apache-2.0 | 县域边界、节点、线路和指标 | 前端直接依赖 |
| [ChinaGeoJson](https://github.com/zhChuXiao/ChinaGeoJson) | MIT | 祁东县离线行政区边界 | GeoJSON 数据复用 |
| [VROOM](https://github.com/VROOM-Project/vroom) | BSD-2-Clause | 高性能路径优化服务参考 | 后续可替换求解服务 |
| [OSRM Backend](https://github.com/Project-OSRM/osrm-backend) | BSD-2-Clause | 离线路网矩阵与导航 | 生产阶段候选 |
| [FastAPI full-stack template](https://github.com/fastapi/full-stack-fastapi-template) | MIT | API 分层、测试与部署结构参考 | 仅参考，不复制模板 |
| [vue-pure-admin](https://github.com/pure-admin/vue-pure-admin) | MIT | 后台布局和权限设计参考 | 仅参考 |

## 已安装技能

- `ortools`：约束规划和车辆路径求解。
- `xgboost-lightgbm`：后续订单需求量与到货量预测。
- `geopandas`：行政区、网点、路网和空间数据处理。

未采用会强制克隆并覆盖项目目录的模板技能，以保护现有代码；也未安装来源路径不一致的物流技能。

## 自研范围

自研内容集中在竞赛业务价值：

- 祁东县黄花菜订单、节点、车辆与事件场景；
- 冷链兼容、故障车辆剔除等约束组合；
- 动态事件处置流程与可解释输出；
- 面向答辩的调度大屏和指标体系。
