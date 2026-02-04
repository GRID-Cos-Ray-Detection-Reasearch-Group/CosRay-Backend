# 开发指南

## 环境要求

- Python 3.13+
- Docker & Docker Compose（用于数据库）
- uv（推荐）或 pip

## 安装依赖

### 使用 uv（推荐）

```bash
# 安装 uv（如果未安装）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 同步依赖
uv sync

# 激活虚拟环境
source .venv/bin/activate
```

### 使用 pip

```bash
pip install -r requirements.txt
```

## 启动数据库服务

```bash
# 启动 PostgreSQL 和 IoTDB
docker compose -f docker-compose.local.yml up -d postgres iotdb

# 查看日志
docker compose -f docker-compose.local.yml logs -f postgres iotdb
```

## 配置环境变量

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 文件
vim .env
```

本地开发环境可以使用默认配置。

## 数据库迁移

```bash
# 创建迁移文件
uv run python manage.py makemigrations

# 执行迁移
uv run python manage.py migrate

# 查看迁移状态
uv run python manage.py showmigrations
```

## 创建超级用户

```bash
uv run python manage.py createsuperuser
```

按照提示输入用户名、邮箱和密码。

## 启动开发服务器

```bash
# 启动 Django 开发服务器
uv run python manage.py runserver
```

服务将在 http://localhost:8000 启动。

## 访问服务

- **API 文档**：http://localhost:8000/api/docs
- **管理后台**：http://localhost:8000/admin
- **健康检查**：http://localhost:8000/api/health

## 代码风格

### 格式化

```bash
# 格式化所有代码
uv run ruff format .

# 格式化特定文件
uv run ruff format core/api.py
```

### Lint 检查

```bash
# 检查并自动修复
uv run ruff check . --fix

# 仅检查，不修复
uv run ruff check .
```

## 测试

```bash
# 运行所有测试
uv run pytest

# 运行特定测试文件
uv run pytest core/tests/test_api.py

# 显示详细输出
uv run pytest -v

# 显示覆盖率
uv run pytest --cov=core --cov-report=html
```

## 常用 Django 命令

```bash
# 创建新 App
uv run python manage.py startapp <app_name>

# 创建超级用户
uv run python manage.py createsuperuser

# 启动 Python Shell
uv run python manage.py shell

# 启动数据库 Shell
uv run python manage.py dbshell

# 收集静态文件
uv run python manage.py collectstatic

# 清除静态文件
uv run python manage.py collectstatic --clear

# 重置数据库（危险！）
uv run python manage.py flush
```

## 调试

### 查看日志

Django 开发服务器会在终端输出日志，包括：

- HTTP 请求
- 数据库查询
- 错误信息

### Django Debug Toolbar

安装 Django Debug Toolbar 可以在浏览器中查看调试信息：

```bash
uv add django-debug-toolbar
```

添加到 `config/settings.py`：

```python
INSTALLED_APPS = [
    ...
    'debug_toolbar',
]

MIDDLEWARE = [
    'debug_toolbar.middleware.DebugToolbarMiddleware',
    ...
]
```

### 断点调试

在代码中添加断点：

```python
import pdb; pdb.set_trace()
```

或使用 ipdb：

```bash
uv add ipdb
```

```python
import ipdb; ipdb.set_trace()
```

## 进入 Docker 容器

```bash
# 进入 Django 容器
docker compose -f docker-compose.local.yml exec django bash

# 在容器内运行命令
python manage.py migrate
python manage.py shell
```

## 查看数据库

### PostgreSQL

```bash
# 进入数据库容器
docker compose -f docker-compose.local.yml exec postgres psql -U cosray cosray

# 查看数据库列表
\l

# 查看表
\dt

# 查看表结构
\d core_detector

# 执行 SQL 查询
SELECT * FROM core_detector;

# 退出
\q
```

### IoTDB

```bash
# 进入 IoTDB 容器
docker compose -f docker-compose.local.yml exec iotdb bash

# 启动 CLI
iotdb-cli -h localhost -p 6667 -u root -pw root

# 查看存储组
show storage groups

# 查看设备
show devices

# 查询数据
select * from root.cosray.*;

# 退出
quit
```

## 清理环境

```bash
# 停止所有服务
docker compose -f docker-compose.local.yml down

# 停止并删除数据卷（会丢失数据！）
docker compose -f docker-compose.local.yml down -v

# 删除数据库和 IoTDB 数据
docker compose -f docker-compose.local.yml down -v
docker volume rm cosray-backend_postgres_data cosray-backend_iotdb_data
```

## 常见问题

### 端口被占用

如果 8000 端口被占用，使用其他端口：

```bash
uv run python manage.py runserver 8001
```

### 数据库连接失败

检查数据库容器是否运行：

```bash
docker compose -f docker-compose.local.yml ps
```

查看数据库日志：

```bash
docker compose -f docker-compose.local.yml logs postgres
```

### IoTDB 连接失败

检查 IoTDB 容器状态：

```bash
docker compose -f docker-compose.local.yml ps iotdb
```

查看 IoTDB 日志：

```bash
docker compose -f docker-compose.local.yml logs iotdb
```

### 迁移错误

如果迁移出现问题，可以重置迁移：

```bash
# 删除迁移文件（保留 __init__.py）
rm core/migrations/*.py

# 删除数据库
docker compose -f docker-compose.local.yml down -v

# 重新启动数据库并迁移
docker compose -f docker-compose.local.yml up -d postgres iotdb
uv run python manage.py migrate
```

## 生产环境部署

生产环境部署请参考 README.md 中的 Docker 部署部分。
