# 冷链仓储共享调度与全程温控监测预警

本文档描述冷链增强模块（阶段 19）的接口契约、数据模型与演示边界。模块目标：把祁东县分散的田头冷库 / 县域冷库纳入共享调度，并为冷链任务建立"出库—在途—入库—库内"全程温度链路与预警闭环。

## 演示边界（必须随方案一起陈述）

- 冷库库容来自研究资料汇总口径（田头冷库约 95 座、集中冷库能力约 4 万吨的抽样映射），不是实时库存；
- 温度读数由受控模拟过程生成（SHA-256 派生的确定性扰动序列），不代表真实车载或库内传感数据；
- 预警只作为调度参考信号，冷链订单与冷链车辆的硬约束仍由 OR-Tools 求解器校验；
- 异常检测当前为滚动残差统计基线（z 分数阈值 2.5σ），样本积累后按需求预测模块的门控约定升级时序模型。

## 角色与权限

| 操作 | admin | dispatcher | driver | viewer | user |
| --- | --- | --- | --- | --- | --- |
| 查看冷库 / 预约 / 传感器 / 读数 / 预警 / 总览 | ✓ | ✓ | ✓ | ✓ | ✗（403） |
| 创建共享库容预约 | ✓ | ✓ | ✗ | ✗ | ✗ |
| 生成演示温度数据 | ✓ | ✓ | ✗ | ✗ | ✗ |
| 确认预警 | ✓ | ✓ | ✗ | ✗ | ✗ |

写操作全部写入审计（category=`cold_chain`）。

## 接口契约（/api/v1/cold-chain）

| 方法与路径 | 说明 | 备注 |
| --- | --- | --- |
| GET `/cold-chain/stores` | 共享冷库台账，含当日已约 / 可用吨位与最新库温 | 读取时幂等补种演示资产 |
| GET `/cold-chain/bookings?limit=` | 最近共享库容预约记录 | limit ≤ 200 |
| POST `/cold-chain/bookings` | 创建预约 `{cold_store_id, booking_date(YYYY-MM-DD), purpose, tons, note?}` | 201；库容不足 / 冷库不可用返回 409；常温存点仅允许 `transit` |
| GET `/cold-chain/sensors` | 温控采集点列表（车载 / 库内），含最新读数 | |
| GET `/cold-chain/sensors/{sensor_id}/readings?limit=` | 温度时序读数（升序），含目标区间 | 404=采集点不存在；limit ≤ 240 |
| GET `/cold-chain/alerts?alert_status=&limit=` | 预警列表，`alert_status ∈ open/acknowledged/resolved` | |
| POST `/cold-chain/alerts/{alert_id}/acknowledge` | 确认预警（open → acknowledged） | 404=不存在；重复确认幂等返回 200 |
| POST `/cold-chain/temperature/simulate` | 生成近 N 小时演示温度曲线并评估预警 `{hours: 1~48}` | 返回读数 / 预警生成数量；只补充上次最新读数之后的数据 |
| GET `/cold-chain/overview` | 总览指标（采集点、读数、未处理 / 严重预警、共享冷库数） | |

错误约定与其他分组一致：401 未认证、403 角色不足、404 不存在、409 业务冲突、422 参数错误。

## 数据模型

| 表 | 关键字段 | 说明 |
| --- | --- | --- |
| `cold_stores` | `store_type`(county_hub/township/field_precool)、`temperature_zone`(chilled/frozen/ambient)、`capacity_tons`、`shared`、`status` | 冷库资源台账，`node_id` 关联服务网点 |
| `cold_store_bookings` | `booking_date`、`purpose`(precool/short_storage/transit)、`tons`、`status`(reserved/active/completed/cancelled) | 共享占库记录，`order_id` 可选关联运营订单 |
| `temperature_sensors` | `sensor_type`(vehicle/storage)、`vehicle_id` / `cold_store_id`、`target_low_c`、`target_high_c` | 车载 / 库内采集点与目标温区 |
| `temperature_readings` | `recorded_at`、`temperature_c`、`humidity_pct`、`context`(outbound/in_transit/inbound/storage)、`assignment_id` | 温度时序，`(sensor_id, recorded_at)` 组合索引 |
| `temperature_alerts` | `level`(info/warning/critical)、`alert_type`(threshold_breach/anomaly_trend)、`measured_c`、`threshold_c`、`deviation_c`、`status` | 阈值越限与趋势异常双通道预警及处置留痕 |

迁移：`backend/alembic/versions/20260928_0016_cold_chain_tables.py`（linear head）。

## 演示数据与恢复

- 应用启动（lifespan）与 `GET stores/sensors` 时幂等补种：6 个演示冷库（绑定标准场景节点 D-01、P-HUANG、V-001、V-003、V-006）+ 每库 1 个库内传感器 + 每台冷链车 1 个车载传感器；
- `一键恢复标准演示数据` 会清空上述 5 表并重置序列，重启或首次访问页面后自动恢复演示资产；
- 温度读数不自动生成，需在温控监测页点击"生成演示温度数据"或调用 simulate 接口；`TS-VEH-01` 的模拟曲线包含一段受控升温越限过程，用于完整展示两类预警。

## 前端入口

- `frontend/src/components/ColdChainStorage.vue`：菜单"冷链仓储"（/cold-chain）；
- `frontend/src/components/TemperatureMonitor.vue`：菜单"温控监测"（/cold-monitor）；
- 两个页面对 admin / dispatcher 可见，页面内置演示边界提示。

## 相关测试

`backend/tests/test_cold_chain.py`：演示资产补种、预约与库容校验（409）、模拟读数与预警生成、预警确认闭环、总览指标与 `user` 角色 403 隔离。
