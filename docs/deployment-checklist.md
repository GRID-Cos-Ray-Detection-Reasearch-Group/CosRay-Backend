# CosRay Backend 部署检查清单

本清单用于生产或准生产环境部署前的最终核对。

## 1. 环境变量

- 必须为 `SECRET_KEY` 配置独立的强随机值。
- 必须为 `ALLOWED_HOSTS` 配置实际域名或 IP，禁止使用通配写法。
- 必须配置 `DATABASE_URL`，且密码不得使用示例值。
- 必须配置 `REDIS_URL`，生产环境禁止回退到进程内缓存。
- 必须替换 PostgreSQL、Redis、IoTDB 的默认或示例密码。
- 必须配置 `CORS_ALLOWED_ORIGINS` 和 `CSRF_TRUSTED_ORIGINS`，禁止在生产开启 `CORS_ALLOW_ALL_ORIGINS=True`。

## 2. Django 安全项

- 确认 `DEBUG=False`。
- 确认 `SECURE_SSL_REDIRECT=True`。
- 确认 `SESSION_COOKIE_SECURE=True`。
- 确认 `CSRF_COOKIE_SECURE=True`。
- 确认 `SECURE_HSTS_SECONDS` 已启用并符合部署策略。
- 确认反向代理会正确传递 `X-Forwarded-Proto`。

## 3. 缓存与认证

- 确认 Redis 可连接，并且 Django 实际使用 Redis 作为默认缓存。
- 确认登录限流、注册限流和上传限流在多实例部署下仍然生效。
- 确认 Refresh Token 轮换后旧 Token 会失效。
- 确认 Redis 密码未出现在仓库模板文件以外的位置。

## 4. 数据存储

- 确认 PostgreSQL 数据卷、备份目录和恢复流程可用。
- 确认 IoTDB 数据卷已挂载，且对外端口未暴露给不必要的网络。
- 确认 IoTDB 账号密码已经替换，不使用 `root/root`。
- 确认应用容器到 PostgreSQL、Redis、IoTDB 的内网连通性正常。

## 5. 容器与网络

- 确认仅暴露必要的入口端口。
- 确认反向代理、Nginx、Traefik 的健康检查全部通过。
- 确认容器重启策略和依赖顺序符合预期。
- 确认上线前执行过 `docker compose config`，检查合并后的配置无误。

## 6. 发布前验证

- 执行 `uv run pytest`。
- 执行 `uv run ruff check . --fix`。
- 执行 `uv run ruff format --check .`。
- 确认 `/api/health`、`/api/token/pair`、`/api/token/refresh`、`/api/devices/` 基本路径可用。
- 确认 Admin 登录与设备权限隔离行为正常。

## 7. 本地开发约束

- `.env` 仅作为本地开发文件使用，不应加入 Git 跟踪。
- 共享配置通过 `.env.example` 和 `.envs/.local/*` 模板维护。
- 若本地未启用 Redis，可以使用进程内缓存，但不得把该配置迁移到生产环境。
