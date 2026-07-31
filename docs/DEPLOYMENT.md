# Docker 部署与运维

## 1. 服务组成

| 服务 | 容器 | 作用 |
|---|---|---|
| Web | `frontend` | Nginx 静态站点与 `/api` 反向代理 |
| API | `api` | FastAPI、同步求解、认证和历史查询 |
| Worker | `worker` | Celery 异步 OR-Tools 求解 |
| Database | `db` | PostgreSQL 16 + PostGIS 3.4 |
| Cache | `redis` | Celery Broker、任务结果和缓存 |
| Migration | `migrate` | 启动时执行 Alembic 升级后退出 |

## 2. 一键启动

在项目根目录执行：

```powershell
Copy-Item .env.example .env
docker compose up -d --build
docker compose ps
```

访问地址：

- 平台：`http://127.0.0.1`
- API 文档：`http://127.0.0.1/api/v1` 由前端代理；开发文档可在容器内 API 端口映射后查看。

默认管理员仅用于首次演示：

```text
用户名：admin
密码：QizhiDemo2026!
```

正式部署前必须修改 `.env` 中的数据库密码、管理员密码、不少于 32 字节的 `JWT_SECRET`，并生成独立的 `AI_CONFIG_ENCRYPTION_KEY`：

```powershell
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

该密钥用于加密数据库中的模型 API Key。生产环境应通过密钥管理服务或受控环境变量注入，不能提交到 Git。已有模型配置后不要直接更换此密钥，否则旧密文将无法解密；轮换时需先解密、换钥重加密并验证。

## 3. 常用命令

```powershell
# 查看状态
docker compose ps -a

# 查看日志
docker compose logs -f api worker

# 重新执行迁移
docker compose run --rm migrate

# 查看数据库中的方案数
docker compose exec db psql -U qizhi_owner -d qizhi -c "select count(*) from optimization_runs;"

# 停止服务，保留数据卷
docker compose down

# 删除服务和数据卷（会清空数据库）
docker compose down -v
```

## 4. 数据持久化

- `postgres_data`：订单、车辆、用户、调度方案、事件和加密后的 AI 服务配置。
- `redis_data`：异步任务队列和短期任务结果。
- 重新构建镜像不会删除数据卷。

## 5. 数据库权限

PostgreSQL 初始化时创建：

- `qizhi_owner`：仅用于数据库初始化和运维。
- `qizhi_app`：API 与 Worker 使用，拥有应用 schema 的建表和读写权限，不使用超级用户连接。

应用角色设置 30 秒语句超时和空闲事务超时。

## 6. 健康检查

```powershell
Invoke-RestMethod http://127.0.0.1/api/v1/health
```

应返回：

```json
{
  "status": "ok",
  "database": true,
  "solvers": {
    "ortools": true,
    "pyvrp": true
  }
}
```

## 7. 备份与恢复

备份：

```powershell
docker compose exec -T db pg_dump -U qizhi_owner -d qizhi -Fc > qizhi.dump
```

恢复前应暂停 API 和 Worker，并在测试环境验证备份文件。不要将包含真实业务数据的备份提交到代码仓库。
