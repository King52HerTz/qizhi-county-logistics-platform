# 第九阶段开发任务：基础数据中心

## 1. 阶段目标

第八阶段补齐了企业登录、用户治理与审计能力。本阶段进入调度业务的数据底座建设，将目前仅用于演示场景的数据表升级为可维护、可校验、可追溯的基础数据中心：

- 建立订单、车辆、服务网点三类正式业务台账；
- 提供筛选、分页、新建、编辑和受保护删除能力；
- 增加客户、货物、车辆状态、联系人、服务半径等实际运营字段；
- 建立数据质量汇总，阻止无效网点、不可用车辆和非法时间窗进入调度；
- 所有变更写入审计日志，后续可追溯到操作者和变更对象；
- 使用独立路由与懒加载组件，避免继续扩大主业务首屏。

## 2. 信息架构与权限

新增路由：

- `/master-data/orders`
- `/master-data/vehicles`
- `/master-data/nodes`

访问规则：

- `admin`、`dispatcher` 可查看和维护；
- `viewer`、`driver` 不进入基础数据维护路由；
- 所有写接口要求 `admin` 或 `dispatcher` JWT；
- 订单、车辆、网点操作均记录 `master_data` 类审计事件。

侧边栏调整：

- 原“数据中心”更名为“方案历史”；
- 新增“基础数据”，进入订单台账；
- 基础数据页面内部使用“订单台账、车辆档案、网点站点”横向页签。

## 3. 业务模型

### 3.1 订单

保留调度求解使用的订单编号、网点、重量、时间窗、服务时长、冷链、优先级和状态，并新增：

- `cargo_name`：货物名称；
- `customer_name`：客户名称；
- `customer_phone`：联系电话；
- `delivery_address`：配送地址；
- `updated_at`：最近更新时间。

约束：

- 重量必须大于 0；
- 时间窗结束必须晚于开始；
- 网点必须存在且处于启用状态；
- `planned`、`completed` 订单不能直接删除；
- 状态限定为 `pending`、`planned`、`completed`、`cancelled`。

### 3.2 车辆

保留车牌、载重、冷链能力、公里成本和班次，并新增：

- `vehicle_type`：厢式车、货车或冷藏车；
- `driver_name`、`driver_phone`：默认驾驶员信息；
- `status`：可用、已分配、维护中、停用；
- `updated_at`。

`available` 继续供求解器使用，并由车辆状态同步维护：只有 `available` 状态可进入求解。

### 3.3 服务网点

保留网点编号、名称、经纬度和类型，并新增：

- `address`：详细地址；
- `contact_name`、`contact_phone`：联系人信息；
- `service_radius_km`：服务半径；
- `is_active`：启停状态；
- `updated_at`。

被订单引用的网点不可删除；停用网点不允许承接新订单。

## 4. 数据库与性能

Alembic `20260726_0008` 对现有三张表做增量升级，不破坏已有演示数据；`20260726_0009` 将早期演示数据的相对分钟转换为 08:00 起的实际运营时间，避免台账显示为凌晨时间。

索引设计：

- 订单保留 `node_id` 外键索引、`(status, created_at)` 组合索引和待调度部分索引；
- 新增订单 `(priority, cold_chain, updated_at)` 组合索引；
- 车辆新增 `(status, cold_chain)` 组合索引；
- 网点新增 `(is_active, kind)` 组合索引；
- 所有时间字段使用带时区时间戳，金额和公里成本使用精确数值类型。

当前页面采用总量统计加有限偏移分页，单页最大 100 条；当单表超过 10 万行时切换为 `(updated_at, id)` 游标分页。

## 5. API

汇总：

- `GET /api/v1/master-data/summary`

订单：

- `GET /api/v1/master-data/orders`
- `POST /api/v1/master-data/orders`
- `PUT /api/v1/master-data/orders/{order_id}`
- `DELETE /api/v1/master-data/orders/{order_id}`

车辆：

- `GET /api/v1/master-data/vehicles`
- `POST /api/v1/master-data/vehicles`
- `PUT /api/v1/master-data/vehicles/{vehicle_id}`
- `DELETE /api/v1/master-data/vehicles/{vehicle_id}`

网点：

- `GET /api/v1/master-data/nodes`
- `POST /api/v1/master-data/nodes`
- `PUT /api/v1/master-data/nodes/{node_id}`
- `DELETE /api/v1/master-data/nodes/{node_id}`

统一列表响应包含 `items` 和 `total`。输入冲突返回 409，业务校验错误返回 422，不存在返回 404。

## 6. 前端设计

视觉基准：

- [基础数据中心订单概念稿](concepts/phase9-master-data-orders.png)

设计系统延续第八阶段：

- 真白色表面、森林绿主色、冷灰色边框；
- 24–26px 页面标题，12–14px 控件文字；
- 44px 表单控件，8–10px 圆角；
- 表格优先，不使用卡片网格替代表格；
- 新建、编辑使用约 500px 右侧抽屉；
- 状态使用轻量语义标识，不使用装饰性标签。

新增组件：

- `MasterDataCenter.vue`：路由页签与数据汇总；
- `MasterOrders.vue`：订单筛选、表格和抽屉；
- `MasterVehicles.vue`：车辆筛选、表格和抽屉；
- `MasterNodes.vue`：网点筛选、表格和抽屉；
- `ConfirmDialog.vue`：受保护删除确认。

## 7. 验收路径

1. 未登录访问 `/master-data/orders`，跳转企业登录页；
2. 管理员登录后返回目标页面；
3. 按状态、优先级、冷链和关键词筛选订单；
4. 新建订单并校验网点、重量和时间窗；
5. 编辑车辆状态，确认不可用车辆不再计入可用运力；
6. 新建或停用网点，验证停用网点不能创建订单；
7. 删除未被引用的测试数据，验证受保护数据返回明确原因；
8. 在审计中心检索 `master_data` 操作记录。

## 8. 完成定义

- 数据库迁移到 `20260726_0009`；
- 三类台账 API 的权限、校验、冲突、审计和删除保护测试通过；
- Vue TypeScript 与生产构建通过；
- Docker 中数据库、缓存、API、任务队列与前端健康；
- 1600×1000 桌面视口完成订单、车辆、网点的核心交互回归；
- 390×844 视口无整页横向溢出；
- 浏览器控制台无相关错误；
- 概念稿与最终订单页面完成视觉对照。

## 9. 后续阶段

第十阶段继续建设订单批量导入、错误行回执、数据质量规则配置，以及从基础数据生成并激活调度场景的发布流程。
