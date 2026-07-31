# API 契约

基础地址：`http://127.0.0.1:8000/api/v1`

## GET `/health`

返回服务版本与 OR-Tools、PyVRP 可用状态。

## GET `/scenario`

返回默认演示场景，包括节点、订单和车辆。

## GET `/dashboard`

返回竞赛大屏摘要数据。

## POST `/optimize`

请求：

```json
{
  "scenario_id": "qidong-demo-001",
  "solver": "ortools",
  "time_limit_seconds": 5,
  "options": {
    "cold_chain_first": true,
    "backhaul_enabled": true
  }
}
```

响应主要字段：

```json
{
  "run_id": "run-...",
  "status": "optimal",
  "solver": "ortools-routing",
  "solve_time_ms": 1000,
  "routes": [],
  "unassigned_order_ids": [],
  "metrics": {
    "distance_km": 0,
    "estimated_cost_cny": 0,
    "on_time_rate": 100,
    "empty_distance_rate": 0,
    "vehicles_used": 0
  },
  "baseline_metrics": {},
  "explanations": [],
  "routing": {
    "requested_provider": "osrm",
    "source": "osrm",
    "cache_hit": false,
    "fallback_used": false,
    "fallback_reason": null,
    "data_version": "2026-07-20T00:00:00Z",
    "coordinate_count": 13
  }
}
```

## POST `/events/reoptimize`

请求：

```json
{
  "event": {
    "type": "vehicle_breakdown",
    "vehicle_id": "V-COLD-01",
    "occurred_at_minute": 90
  },
  "lock_completed": true,
  "urgent_orders": ["O-URGENT-01"]
}
```

响应结构与 `/optimize` 相同。新路线中不会出现故障车辆，并包含新增紧急冷链订单。

完整交互文档启动后访问 `/docs`。

## POST `/auth/login`

使用用户名和密码换取 JWT：

```json
{
  "username": "admin",
  "password": "QizhiDemo2026!"
}
```

## GET `/auth/me`

请求头携带 `Authorization: Bearer <token>`，返回当前用户名和角色。

## GET `/runs`

返回已持久化的调度历史。支持 `limit` 和 `before` 时间游标，避免深分页使用 OFFSET。

## GET `/runs/{run_id}`

从 PostgreSQL 读取指定方案的完整路线、指标和解释。

## POST `/jobs/optimize`

将求解任务发送到 Redis/Celery，返回 HTTP 202 和 `task_id`。

## GET `/jobs/{task_id}`

查询异步任务的 `PENDING`、`STARTED`、`SUCCESS` 或 `FAILURE` 状态；成功后返回完整求解结果。

## AI 服务配置

以下接口均需 `Authorization: Bearer <token>`。配置读写和连接测试只允许 `admin` 角色。

### GET `/ai/config`

返回当前启用配置。`api_key_masked` 仅为掩码，接口不会返回明文 API Key；未配置时返回 `null`。

### PUT `/ai/config`

```json
{
  "provider": "openai-compatible",
  "base_url": "https://provider.example/v1",
  "model_name": "provider-model-id",
  "api_key": "replace-with-real-key",
  "enabled": true,
  "temperature": 0.2
}
```

首次保存必须提供 `api_key`。更新其他字段时可以省略或留空，服务端会保留原密钥。

### POST `/ai/config/test`

向已保存的 `/chat/completions` 发起最小请求，返回是否成功、响应消息和耗时。测试结果会写入配置记录。

### POST `/ai/explain/{run_id}`

读取指定调度方案，将聚合指标和脱敏线路摘要交给已配置模型，返回中文决策解释。路径本身仍由 OR-Tools 求解，模型不直接更改路线。

## 场景版本与 Excel 导入

以下接口需要管理员 JWT。

### GET `/scenarios/template`

下载标准 `.xlsx` 模板。模板包含使用说明、场景、节点、订单和车辆工作表，并附带一组可直接导入的祁东县示例数据。

### GET `/scenarios`

按创建时间倒序返回场景版本。状态包括：

- `draft`：已校验、等待激活；
- `active`：当前调度使用；
- `archived`：曾经激活的历史版本。

### POST `/scenarios/import`

使用 `multipart/form-data` 上传字段名为 `file` 的 `.xlsx`。文件最大 5 MB。服务端整批校验：

- 工作表与字段完整性；
- ID 和车牌唯一性；
- 坐标、重量、时间窗和车辆班次；
- 订单节点引用；
- 唯一共配中心；
- 冷链订单与可用冷链车辆。

校验失败返回 HTTP 422 和错误列表，不写入场景版本。

### POST `/scenarios/{scenario_id}/activate`

激活指定数据库版本，同时将原激活版本归档。同一时刻只能存在一个激活版本。

### GET `/scenario`

返回当前激活场景。`POST /optimize` 未指定 `scenario_id` 时自动使用该版本。

## 路网矩阵与预测

### GET `/routing/status`

返回当前请求的矩阵服务、是否启用安全回退以及进程内矩阵缓存使用量。

### GET `/analytics/forecast?days=7`

返回 3–30 日需求预测。响应包含：

- 近 7 日运营画像和未来预测点；
- 预测上下界；
- 乡镇需求排行；
- 今日需求、峰值日期和冷链需求；
- 建议车辆数、风险等级、预测方法与数据边界说明。

当前算法为“四期加权移动平均 + 星期季节因子”。接入连续真实订单后可保持接口不变替换预测模型。

## 调度审批与驾驶员执行

以下接口均需 JWT。

### GET `/dispatch/plans`

管理员或调度员查看执行单列表、审批状态和车辆任务。

### POST `/dispatch/plans`

```json
{ "run_id": "run-..." }
```

将可行求解结果提交审批。同一 `run_id` 只生成一个执行单。

### POST `/dispatch/plans/{plan_id}/approve`

管理员批准待审批方案。重复审批或非法状态返回 HTTP 409。

### POST `/dispatch/plans/{plan_id}/reject`

管理员驳回待审批方案，可在 `note` 中填写原因。

### POST `/dispatch/plans/{plan_id}/dispatch`

管理员或调度员将已批准方案按路线拆分为驾驶员任务。

### GET `/driver/assignments`

驾驶员只获取分配给自己的任务；管理员可查看全部任务。

### POST `/driver/assignments/{id}/accept`

确认接单，状态由 `pending` 变为 `accepted`。

### POST `/driver/assignments/{id}/start`

确认发车，状态由 `accepted` 变为 `executing`。

### POST `/driver/assignments/{id}/complete`

确认送达，状态由 `executing` 变为 `completed`。所有任务完成后执行单自动完成。

### GET `/dispatch/plans/{plan_id}/report`

下载自包含 HTML 执行报告，可使用浏览器打印为 PDF。

## 算法对照实验

以下接口需要管理员或调度员 JWT。

### POST `/experiments`

```json
{
  "name": "县域物流三压力算法对照实验",
  "scenario_id": "qidong-demo-v1",
  "time_limit_seconds": 1
}
```

`scenario_id` 可省略，默认读取当前激活场景。接口依次运行：

- 标准负荷：原始订单货量；
- 旺季峰值：全部订单货量增加 18%；
- 冷链压力：冷链订单增加 22%，常温订单增加 8%。

每个案例使用约束校验轮询启发式作为业务基线，与 OR-Tools Routing 推荐方案比较。响应保存里程、成本、车辆数、服务率、未分配订单、求解耗时和矩阵来源。

### GET `/experiments`

按创建时间倒序返回实验历史，支持 `limit=1..100`。

### GET `/experiments/{id}`

返回实验摘要、三个压力案例和完整复现元数据，包括场景版本、SHA-256 指纹、求解器和单案例时限。

### GET `/experiments/{id}/report`

下载自包含 HTML 实验报告，可使用浏览器打印为 PDF。报告明确说明业务基线不是数学最优解。

## 竞赛答辩与成果证据

以下接口需要管理员或调度员 JWT，且不会返回 AI 密钥、密码等敏感配置。

### GET `/operations/readiness`

聚合当前激活场景、最近一次算法实验、最近一次可行优化、异常重调度、调度执行和系统审计记录，返回：

- 数据、算法、执行、系统四个就绪度维度及整体得分；
- 390 秒现场演示脚本和对应系统入口；
- 里程、成本、服务率、求解时间等可追溯指标；
- 人工基线与 AI 优化方案的量化对比；
- 比赛要求证据矩阵、成果引用编号和答辩提示。

该接口仅聚合数据库中已有事实，不会为提高得分伪造记录。

### GET `/operations/report`

下载自包含、可打印的 HTML 成果证据报告。报告中的指标和证据编号与 `/operations/readiness` 同源，可用于运营归档、复盘和管理汇报。

## 地图服务

### GET `/map/runtime`

管理员或调度员读取当前地图运行方式。未启用第三方连接时返回 `offline`；启用高德地图后返回 Web JS Key、地图样式和同源安全代理地址，不返回 `securityJsCode`。

### GET `/map/configs`

管理员查看地图连接列表。Web Key 和安全密钥仅返回掩码。

### POST `/map/configs`

```json
{
  "name": "生产环境高德地图",
  "provider": "amap",
  "web_key": "由高德开放平台签发",
  "security_code": "与 Web Key 配套的安全密钥",
  "map_style": "whitesmoke",
  "enabled": true
}
```

新增连接并加密保存两项凭据。更新接口为 `PUT /map/configs/{id}`，编辑时凭据留空表示保留原值。

### POST `/map/configs/{id}/activate`

将连接设为默认地图，并自动停用其他第三方地图连接。

### POST `/map/configs/{id}/disable`

停用连接。没有启用连接时，前端自动使用离线运营地图。

### POST `/map/configs/{id}/test`

检查高德 Web JS 脚本连通性与 Key 平台类型。域名白名单和安全代理会在真实地图加载时继续校验。

### GET `/map/amap-service/{path}`

高德安全密钥服务端代理。平台在服务端追加安全密钥，不向浏览器返回明文。
