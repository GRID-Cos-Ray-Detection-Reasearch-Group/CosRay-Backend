# CosRay-Backend

宇宙射线探测系统的现代化 IoT 后端服务，基于 Django 6 + Django Ninja 构建。

## ✨ 特性

- 🚀 **现代技术栈**: Django 6, Django Ninja, JWT 认证
- 📊 **读写分离**: PostgreSQL (元数据) + IoTDB (时序数据)
- ⚡ **高性能**: SessionPool 连接池，批量写入优化
- 🎨 **现代后台**: Django Unfold Admin UI
- 🔒 **安全**: JWT Bearer Token 认证，CORS 保护
- 📦 **依赖管理**: 使用 `uv` 快速管理依赖

## 📋 前置要求

- Python 3.13+
- uv
- Docker & Docker Compose (用于数据库)

## 🚀 快速开始

### 1. 安装依赖

```bash
uv sync
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 根据需要编辑 .env 文件
```

`.env` 仅用于本地开发，默认应保持未跟踪状态。

### 3. 启动数据库服务

```bash
docker compose up -d
```

等待 PostgreSQL 和 IoTDB 启动（约 10 秒）。本地未配置 Redis 时，限流与 Refresh Token 失效控制会回退到进程内缓存。

### 4. 数据库迁移

```bash
uv run python manage.py migrate
```

### 5. 创建超级用户

```bash
uv run python manage.py createsuperuser
```

### 6. 启动开发服务器

```bash
uv run python manage.py runserver
```

访问:

- API 文档: http://localhost:8000/api/docs
- 管理后台: http://localhost:8000/admin

## 📚 API 端点

### 认证

- `POST /api/token/pair` - 获取 JWT Token
- `POST /api/token/refresh` - 刷新 Token
- `POST /api/token/verify` - 验证 Token

### 设备管理

- `GET /api/devices/` - 获取设备列表
- `POST /api/devices/` - 注册新设备
- `GET /api/devices/{id}/` - 获取设备详情
- `PATCH /api/devices/{id}/` - 更新设备信息
- `DELETE /api/devices/{id}/` - 删除设备

### 数据上传

- `POST /api/mu-packets/` - 上传 Muon/Timeline 数据包

## 🏗️ 项目结构

```
CosRay-Backend/
├── config/              # Django 配置
│   ├── settings.py      # 核心配置
│   └── urls.py          # 路由配置
├── core/                # 主业务模块
│   ├── models.py        # 数据模型 (Detector)
│   ├── schemas.py       # Pydantic Schema
│   ├── services.py      # IoTDB 服务层
│   ├── api.py           # API 路由
│   └── admin.py         # 管理后台
├── docker-compose.yml   # 数据库服务编排
├── .env.example         # 环境变量模板
└── pyproject.toml       # 项目依赖
```

## 🔧 开发命令

```bash
# 代码格式化
uv run ruff format .

# Lint 检查
uv run ruff check . --fix

# 运行测试
uv run pytest

# 创建迁移
uv run python manage.py makemigrations

# 执行迁移
uv run python manage.py migrate
```

## 性能测试

- 压测与资源开销测量说明见 `docs/ops/performance-testing.md`
- 执行脚本：`scripts/perf/run_pressure_test.py`

## 部署检查

- 生产部署前请先核对 `docs/ops/deployment-checklist.md`

## 文档站点

- 文档站点基于 VitePress，源文件位于 `docs/`
- 本地预览：`cd docs && pnpm install --frozen-lockfile && pnpm dev`
- 生产发布目标：GitHub Pages

## 📦 数据模型

### Detector (探测器设备)

- `mac_address` - MAC 地址 (唯一标识)
- `name` - 设备名称
- `owner` - 所有者
- `description` - 描述
- `is_active` - 激活状态
- `last_seen_at` - 最后上报时间

### IoTDB 时序数据

#### Muon 数据路径

```
root.cosray.<MAC>_sanitized.muon.{cpu_time, energy, pps}
```

#### Timeline 数据路径

```
root.cosray.<MAC>_sanitized.timeline.{cpu_time, pps, utc, gps_long, gps_lat, ...}
```

## 🔐 认证方式

使用 JWT Bearer Token:

```bash
# 1. 获取 Token
curl -X POST http://localhost:8000/api/token/pair \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin"}'

# 2. 使用 Token 访问 API
curl -X GET http://localhost:8000/api/devices/ \
  -H "Authorization: Bearer <access_token>"
```

## 📊 IoTDB 配置

默认配置:

- Host: localhost
- Port: 6667
- User: root
- Password: root

可通过 `.env` 文件修改。

## 🧠 缓存配置

- `REDIS_URL` 已配置时，Django 使用 Redis 作为限流和 Refresh Token 失效控制的共享缓存
- `REDIS_URL` 留空时，Django 回退到进程内缓存，仅适合本地开发或单进程环境

## 🐳 Docker 服务

### PostgreSQL 18

- Port: 5432
- Database: cosray
- User: cosray
- Password: cosray

### Apache IoTDB 2.0.6

- RPC Port: 6667
- REST API Port: 6668

## 📝 License

MIT License

## 🤝 贡献

欢迎提交 Pull Request！请遵循以下规范：

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'feat: 添加某个功能'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 开启 Pull Request

## 📮 联系

GRID Cosmic Ray Detection Research Group
