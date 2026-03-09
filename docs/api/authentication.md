# 认证与用户

## 目标

当前认证体系完全基于 JWT Bearer Token，后端对外提供注册、登录、刷新、校验和当前用户查询接口。

## 端点

### `POST /api/auth/register`

- 作用：注册用户并返回 access / refresh token
- 认证：否
- 限流：按客户端 IP 执行注册限流

请求体：

```json
{
  "username": "alice",
  "email": "alice@example.com",
  "password": "strong-password"
}
```

成功响应：

```json
{
  "access": "<jwt-access>",
  "refresh": "<jwt-refresh>",
  "user": {
    "id": 1,
    "username": "alice",
    "email": "alice@example.com"
  }
}
```

### `POST /api/token/pair`

- 作用：用户名密码登录
- 认证：否
- 限流：按 `IP + 用户名` 执行登录限流

失败时返回：

- `401 INVALID_CREDENTIALS`
- `429` 速率限制错误

### `POST /api/token/refresh`

- 作用：刷新 access token，并在启用轮换撤销时废弃旧 refresh token
- 认证：否

失败时返回：

- `401 INVALID_TOKEN`

### `POST /api/token/verify`

- 作用：验证 access token
- 实现来源：Django Ninja JWT 内置 verify router

### `GET /api/users/me`

- 作用：返回当前登录用户
- 认证：必须携带 Bearer Token

成功响应：

```json
{
  "id": 1,
  "username": "alice",
  "email": "alice@example.com"
}
```

## 错误语义

- `INVALID_CREDENTIALS`：用户名或密码错误
- `INVALID_TOKEN`：refresh token 无效、已撤销或不属于活跃用户

## 附加端点与配置

- `/health`：容器与负载均衡的健康检查端点，返回 `{"status":"ok"}`，用于 k8s/反向代理探活。
- `/token/verify`：由 `ninja_jwt` 提供的内置 verify 路由，可用于校验 access token 的合法性（通常用于调试或短期集中校验）。

速率限制配置位于应用配置中（`config/settings.py`），常用配置项：

- `LOGIN_RATE_LIMIT_COUNT` / `LOGIN_RATE_LIMIT_WINDOW_SECONDS`
- `REGISTER_RATE_LIMIT_COUNT` / `REGISTER_RATE_LIMIT_WINDOW_SECONDS`
- `UPLOAD_RATE_LIMIT_COUNT` / `UPLOAD_RATE_LIMIT_WINDOW_SECONDS`

例如在 `.env` 中可以覆盖默认值：

```
LOGIN_RATE_LIMIT_COUNT=5
LOGIN_RATE_LIMIT_WINDOW_SECONDS=300
REGISTER_RATE_LIMIT_COUNT=3
REGISTER_RATE_LIMIT_WINDOW_SECONDS=3600
UPLOAD_RATE_LIMIT_COUNT=120
UPLOAD_RATE_LIMIT_WINDOW_SECONDS=60
```

这些配置影响 API 层的限流策略，文档中提到的 "按 IP" / "按 IP+用户名" 的限流策略即基于上述配置实现。
