# 第八阶段开发任务：企业治理、正式路由与审计中心

## 1. 阶段目标

第七阶段完成了统一登录门禁和 AI 多连接管理。本阶段继续补齐企业后台的治理能力：

- 建立正式 URL 路由和页面级角色门禁；
- 建立用户、角色、账号状态和密码生命周期管理；
- 将后端审计记录开放为可筛选、可查看、可导出的管理页面；
- 统一系统设置下的 AI 服务、用户与权限、审计日志和安全策略导航。

## 2. 前端路由

引入 Vue Router，页面可直接访问并保留刷新状态：

- `/login`
- `/overview`
- `/dispatch`
- `/events`
- `/execution`
- `/experiments`
- `/history`
- `/scenarios`
- `/settings/ai`
- `/settings/users`
- `/settings/audit`
- `/settings/security`

路由守卫规则：

- 未登录访问业务页面时跳转 `/login`，并保留原始目标地址；
- 已登录访问 `/login` 时跳转运营总览；
- 场景管理和系统设置仅允许管理员；
- 令牌失效时清理浏览器会话并回到登录页。

登录页与业务应用采用懒加载分包，登录首屏不再下载完整地图、图表和算法实验模块。

## 3. 用户治理

管理员可执行：

- 按姓名、账号、角色和状态筛选用户；
- 新建用户并分配 `admin`、`dispatcher`、`driver`、`viewer` 角色；
- 修改姓名、角色和账号启停状态；
- 解除连续登录失败产生的账号锁定；
- 重置密码并同步清空锁定状态。

保护规则：

- 密码至少 12 位，并包含大小写字母、数字和特殊字符；
- 不能停用当前管理员账号或移除自己的管理员角色；
- 系统必须保留至少一个已启用管理员；
- 登录账号创建后不可修改；
- 密码只存储 PBKDF2 哈希，不写入审计详情。

## 4. 审计中心

支持按以下条件查询：

- 最近 1、7、30 或 90 天；
- 身份认证、AI 配置、用户管理；
- 成功、失败、已拦截；
- 操作者；
- 资源或动作关键词。

详情面板展示事件编号、时间、操作者、来源 IP、User-Agent、资源、结果和结构化详情。服务端对包含 `key`、`password`、`token`、`secret`、`authorization`、`credential` 的字段递归脱敏。

导出接口最多输出当前筛选条件下 5000 条 UTF-8 CSV 记录。

## 5. 数据库

Alembic `20260726_0007` 为用户表新增：

- `password_changed_at`
- `updated_at`
- `(role, is_active)` 联合索引

审计中心复用第七阶段的 `audit_logs`。

## 6. API

用户治理：

- `GET /api/v1/users`
- `POST /api/v1/users`
- `PUT /api/v1/users/{id}`
- `POST /api/v1/users/{id}/reset-password`

审计中心：

- `GET /api/v1/audit-logs`
- `GET /api/v1/audit-logs/export`

以上接口均要求管理员 JWT。

## 7. 视觉与组件

- [用户与权限概念稿](concepts/phase8-user-governance.png)
- [审计日志概念稿](concepts/phase8-audit-logs.png)

设计继续沿用森林绿企业后台体系：白色表面、细边框、44px 表单控件、表格优先、右侧抽屉和轻量状态标识。

新增组件：

- `UserGovernance.vue`
- `AuditLogs.vue`
- `SecurityPolicy.vue`
- `SystemSettings.vue`
- `LoginRoute.vue`
- `router.ts`

## 8. 完成定义

- Alembic 升级到 `20260726_0007`；
- 用户治理和审计接口权限、校验、脱敏测试通过；
- 后端 15 项自动化测试全部通过；
- Vue TypeScript 与生产构建通过；
- Docker 中 PostgreSQL、Redis、FastAPI、Celery 和前端全部健康；
- 浏览器完成路由门禁、用户新建/编辑/重置密码和审计筛选/详情/导出验收；
- 在 1600×1000 桌面视口和移动视口完成视觉检查。

## 9. 后续阶段建议

第九阶段进入主业务数据管理：

- 订单、车辆、网点正式 CRUD；
- 通用表格、分页、确认对话框和表单验证组件；
- 车辆可用性、冷链能力和班次日历；
- 订单批量导入、异常行回执和数据质量面板；
- 将业务应用大包继续拆分为页面级懒加载模块。
