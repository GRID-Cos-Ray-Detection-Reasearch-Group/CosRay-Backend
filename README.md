# CosRay-Backend

宇宙射线探测系统的后端服务，基于 Django 6 + Django Ninja 构建，提供高性能 IoT 数据采集和管理能力。

## 特性

- 现代 API 框架：Django 6 + Django Ninja
- 读写分离：PostgreSQL (元数据) + Apache IoTDB (时序数据)
- JWT 认证：标准 Bearer Token
- 现代管理后台：Django Unfold
- 容器化部署：Docker Compose 支持
- 高性能：IoTDB SessionPool 连接池

## 快速开始

### Docker 部署（推荐）

#### 本地开发

```bash
# 1. 启动服务（自动加载 .envs/.local 配置）
docker compose -f docker-compose.local.yml up --build
```

访问：

- API 文档：http://localhost:8000/api/docs
- 管理后台：http://localhost:8000/admin

#### 生产环境

```bash
# 1. 配置环境变量
# 检查 .envs/.production/.django 和 .envs/.production/.postgres
# 修改：SECRET_KEY, 密码等敏感信息

# 2. 启动服务
docker compose -f docker-compose.production.yml up -d --build
```

### 本地开发 (非 Docker)

```bash
# 1. 安装依赖
uv sync

# 2. 启动数据库
docker compose -f docker-compose.local.yml up -d postgres iotdb

# 3. 数据库迁移
uv run python manage.py migrate

# 4. 创建超级用户
uv run python manage.py createsuperuser

# 5. 启动服务
uv run python manage.py runserver
```

## 项目结构

```
CosRay-Backend/
├── config/              # Django 配置
├── core/                # 核心业务模块
│   ├── api.py           # API 路由
│   ├── models.py        # 数据模型
│   ├── schemas.py       # Pydantic Schema
│   └── services.py      # IoTDB 服务层
├── compose/             # Docker 配置
├── docs/               # 项目文档
├── .envs/               # 环境变量配置目录
│   ├── .local/          # 本地开发配置
│   └── .production/     # 生产环境配置
├── .env.example         # 环境变量模板
└── pyproject.toml       # 项目依赖
```

## 常用命令

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

# 收集静态文件
uv run python manage.py collectstatic
```

## 文档

- [架构说明](docs/architecture.md) - 系统架构和数据流向
- [API 文档](docs/api.md) - API 端点和数据格式
- [开发指南](docs/development.md) - 本地开发环境设置

## 关联项目

- [CosRay-App](https://github.com/GRID-Cos-Ray-Detection-Reasearch-Group/CosRay-App) - Android 客户端
- [CosRay-Detector-Firmware](https://github.com/GRID-Cos-Ray-Detection-Reasearch-Group/CosRay-Detector-Firmware) - ESP32 固件

## License

AGPL-3.0 License 详见 [LICENSE](LICENSE) 文件。
