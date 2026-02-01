# Project: CosRay-Backend (Vibe Coding Edition)

## 1. 角色与目标

你是一个 Python 专家开发者（全栈视野，后端专精）。
你的目标是构建 `CosRay-Backend`，这是一个用于宇宙射线探测的高性能、轻量级 IoT 后端服务。

**核心哲学：**

1.  **极简主义**：不使用复杂的模板，不做过度封装，代码扁平化。
2.  **基础设施即代码**：利用 `uv` 管理环境，`docker-compose` 管理服务。
3.  **拥抱成熟库**：
    - 鉴权交给 `ninja-jwt`。
    - 后台交给 `django-unfold`。
    - 配置交给 `django-environ`。
    - 部署交给 `uvicorn` & `whitenoise`。
    - 格式化交给 `ruff`。
4.  **读写分离**：
    - 业务/元数据 -> PostgreSQL (Django ORM)。
    - 海量时序数据 -> Apache IoTDB (SessionPool)。

## 2. 技术栈 (The Vibe Stack)

- **语言环境**: Python 3.13 (由 `uv` 管理)
- **Web 框架**: Django 6+ & Django Ninja (API)
- **应用服务器**: Uvicorn (ASGI Production Server)
- **鉴权**: Django Ninja JWT (JWT Auth)
- **后台 UI**: Django Unfold (替代原生 Admin，提供现代 UX)
- **配置管理**: django-environ (遵循 12-Factor App)
- **中间件**:
  - django-cors-headers (解决跨域)
  - whitenoise (静态文件服务)
- **数据库**:
  - PostgreSQL 17+ (Primary - 元数据)
  - Apache IoTDB 2.0.6+ (Time-series - 遥测数据)
- **测试**: Pytest + Pytest-Django + Pytest-Asyncio + Model Bakery (数据工厂)
- **工具链**: Ruff (Lint/Format), Pre-commit, Django Extensions

## 3. 项目结构规范

保持扁平，拒绝深层嵌套。关键路径如下：

```text
CosRay-Backend/
├── .venv/               # uv 自动生成
├── .env                 # (GitIgnored) 本地敏感配置
├── .env.example         # 环境变量模版
├── config/              # Django 项目配置
│   ├── settings.py      # 核心配置 (读取 os.environ)
│   ├── urls.py          # 顶层路由
│   └── wsgi.py
├── Backend/                # 唯一的业务 App
│   ├── api.py           # 所有 API 入口 (Django Ninja)
│   ├── models.py        # 核心关系模型 (Detector, Event)
│   ├── schemas.py       # Pydantic 数据模型 (Request/Response)
│   ├── services.py      # 业务逻辑 & IoTDB 封装
│   ├── tests/           # 测试目录
│   │   ├── conftest.py  # Pytest fixtures
│   │   └── test_api.py
│   └── admin.py         # Unfold 后台配置
├── manage.py
├── pyproject.toml       # 依赖管理 & 工具配置
├── docker-compose.yml   # 数据库编排
└── .pre-commit-config.yaml
```

## 4. 开发命令指南 (基于 uv)

**严禁使用 `pip` 或 `virtualenv`，必须使用 `uv`。**

- **初始化环境**: `uv sync`
- **运行服务**: `uv run python manage.py runserver 0.0.0.0:8000`
- **添加依赖**: `uv add <package_name>`
- **开发依赖**: `uv add --dev <package_name>`
- **数据库迁移**: `uv run python manage.py migrate`
- **创建超级用户**: `uv run python manage.py createsuperuser`
- **运行测试**: `uv run pytest`
- **代码格式化**: `uv run ruff format .`
- **Lint 检查**: `uv run ruff check . --fix`

## 5. 编码实施细节

### A. 环境变量配置

复制 `.env.example` 到 `.env` 并填入：

```bash
DEBUG=True
SECRET_KEY=unsafe-development-key
DATABASE_URL=postgres://admin:password@localhost:5432/cosray
IOTDB_HOST=localhost
IOTDB_PORT=6667
IOTDB_USER=root
IOTDB_PASSWORD=root
ALLOWED_HOSTS=localhost,127.0.0.1
CORS_ALLOWED_ORIGINS=http://localhost:3000
```

### B. API 开发规范

**兼容性要求**: 必须兼容 `CosRay-App` 的现有业务逻辑。

**核心约定**:

- **Router**: 使用 Django Ninja 路由
- **Auth**: 统一使用 JWT 认证 (`Authorization: Bearer <token>`)，替代原有的 `X-Session-Token` 方式
  - 注意: App 端需同步更新认证方式
- **Endpoints**:
  1.  `POST /api/mu-packets/`: 接收遥测数据 (Payload: `PacketUploadSchema`)。
  2.  `GET /api/devices/` & `POST /api/devices/`: 设备管理。
  3.  `GET /api/devices/{id}/` ... : CRUD 操作。

**Schema 契约 (Pydantic)**:

```python
class MuonEventSchema(Schema):
    cpu_time: int
    energy: int
    pps: int
    timestamp: int | None = None

class MuonPacketSchema(Schema):
    package_counter: int
    utc: int
    events: list[MuonEventSchema]
    # ... head, tail, crc (Optional)

class PacketUploadSchema(Schema):
    device: str = Field(..., description="Device MAC Address")
    packet_type: Literal["muon", "timeline"]
    muon_packet: MuonPacketSchema | None = None
    timeline_packet: TimelinePacketSchema | None = None
```

### C. 数据库设计

**PostgreSQL 模型**:

- `Detector` (对应 App 的 `Device`):
  - `mac_address`: CharField(17), unique - 设备唯一标识
  - `owner`: ForeignKey(User) - 设备所有者
  - `name`: CharField(100) - 设备名称
  - `description`: TextField - 描述信息
  - `is_active`: BooleanField - 激活状态
  - `last_seen_at`: DateTimeField - 最后上报时间

- `Event` (可选): 仅存储极少量高价值异常事件，常规数据全部写入 IoTDB

**IoTDB 时序结构**:

- Root path: `root.cosray`
- Path pattern: `root.cosray.<mac_address_sanitized>.<packet_type>.<metric>`
- MAC 规范化: 将 `:` 替换为 `_` (例: `AA:BB:CC` → `AA_BB_CC`)
- 数据类型:
  - `energy`: INT32 - 能量 ADC 值
  - `pps`: INT64 - PPS 脉冲计数
  - `cpu_time`: INT64 - CPU 时钟
  - `sipm_tmp`, `mcu_tmp`: INT32 - 温度传感器 (Timeline)

### D. IoTDB 连接管理

使用 SessionPool 实现连接池，避免频繁握手：

```python
from iotdb.SessionPool import SessionPool
from django.conf import settings

_session_pool = None

def get_iotdb_session():
    global _session_pool
    if _session_pool is None:
        _session_pool = SessionPool(
            settings.IOTDB_HOST,
            int(settings.IOTDB_PORT),
            settings.IOTDB_USER,
            settings.IOTDB_PASSWORD,
            max_size=5  # 根据并发量调整
        )
    return _session_pool
```

_在测试中，请使用 `unittest.mock.patch` 拦截 `get_iotdb_session`，不要连接真实数据库。_

### E. 系统配置与中间件

**关键配置项**:

- **配置管理**: 使用 `django-environ` 读取 `.env` 文件
- **跨域处理**: `corsheaders.middleware.CorsMiddleware` 必须置于 `CommonMiddleware` 之前
- **Unfold Admin**: `INSTALLED_APPS` 中确保 `unfold` 在 `django.contrib.admin` **之前**
- **静态文件**: `whitenoise.middleware.WhiteNoiseMiddleware` 用于生产环境静态资源服务

### F. Docker 基础设施

配置 PostgreSQL 和 IoTDB 服务，确保健康检查正常：

以下仅为示例，不要直接使用，建议参考旧的后端进行修改

```yaml
services:
  db:
    image: postgres:17
    container_name: cosray_pg
    environment:
      POSTGRES_DB: cosray
      POSTGRES_USER: admin
      POSTGRES_PASSWORD: password
    ports:
      - "5432:5432"
    volumes:
      - pg_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U admin"]
      interval: 5s
      timeout: 5s
      retries: 5

  iotdb:
    image: apache/iotdb:2.0.6-standalone
    container_name: cosray_iotdb
    ports:
      - "6667:6667"
    environment:
      - dn_rpc_address=0.0.0.0
      - dn_rpc_port=6667
    volumes:
      - iotdb_data:/iotdb/data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/ping"] # 假设开启了监控端口，或者用 tcp check
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  pg_data:
  iotdb_data:
```

## 6. 常见问题排查

1.  **连接拒绝**: 检查 `.env` 中的 `DB_HOST` 在 Docker 内是否应为 `db` 而非 `localhost` (如果 App 也在容器内)。
2.  **Unfold 样式丢失**: 运行 `uv run python manage.py collectstatic` 并确保 `whitenoise` 配置正确。
3.  **IoTDB 写入慢**: 检查是否使用了 SessionPool 以及是否批量写入 (InsertTablet)。
4.  **JWT 认证失败**: 检查 Header 是否为 `Bearer <token>`。

---

## 7. 通用约束与规范

### A. 代码风格

1.  **语言**: 所有注释、文档字符串使用中文
2.  **格式化**: 必须使用 `ruff format` 格式化代码
3.  **类型注解**: 所有函数必须有完整的类型注解，使用 Python 3.13 新语法 (如 `list[str]` 而非 `List[str]`，`str | None` 而非 `Optional[str]`)
4.  **导入顺序**: 标准库 → 第三方库 → 本地模块，由 ruff 自动排序
5.  **禁止事项**:
    - 不要使用 emoji
    - 不要写冗余注释 (代码即文档)
    - 不要使用 `print()` 调试，使用 `logging`
    - 不要硬编码配置值，全部走环境变量

### B. Git 工作流

1.  **分支策略**:
    - **保护分支**: `main` (生产) 和 `dev` (开发) 为保护分支，严禁直接提交
    - **开发流程**: 从 `dev` 创建特性分支 → 开发 → 提交 → 合并回 `dev`
    - **分支命名**:
      - `feature/<功能描述>`: 新功能 (例: `feature/device-api`)
      - `fix/<问题描述>`: Bug 修复 (例: `fix/iotdb-connection`)
      - `refactor/<模块名>`: 重构 (例: `refactor/services`)
      - `docs/<文档类型>`: 文档更新 (例: `docs/api-spec`)
    - **创建分支**: `git checkout dev && git pull && git checkout -b feature/xxx`

2.  **提交规范** (约定式提交):
    - **格式**: `<类型>: <简洁描述>` (不超过 50 字符)
    - **类型**:
      - `feat`: 新功能
      - `fix`: Bug 修复
      - `refactor`: 重构 (不改变功能)
      - `docs`: 文档更新
      - `test`: 测试相关
      - `chore`: 构建/工具配置
      - `style`: 代码格式调整
    - **描述要求**:
      - 使用中文
      - 简洁凝练，无废话
      - 动词开头，省略主语 (例: `实现xxx` 而非 `我实现了xxx`)
      - 不使用句号结尾
    - **示例**:
      - `feat: 实现设备注册 API`
      - `fix: 修复 IoTDB 连接池泄露`
      - `refactor: 提取数据包处理服务`
      - `docs: 更新 API 使用文档`

3.  **增量提交**:
    - 每次提交只做**一件事**，保持原子性
    - 单次修改文件数建议不超过 5 个
    - 大功能拆分为多个小提交 (例: 模型定义 → Schema → API → 测试)
    - 每个提交后确保代码可运行、测试通过

4.  **提交前检查**:
    - 运行 `uv run ruff format .` 格式化代码
    - 运行 `uv run ruff check . --fix` 修复 lint 问题
    - 运行 `uv run pytest` 确保测试通过
    - 使用 `git diff --staged` 检查暂存区变更

### C. 错误处理

1.  **API 层**: 使用 Django Ninja 的异常处理机制
2.  **服务层**: 抛出自定义业务异常，在 API 层统一捕获
3.  **日志级别**:
    - `ERROR`: 需要立即关注的错误
    - `WARNING`: 潜在问题但不影响主流程
    - `INFO`: 关键业务事件 (用户登录、数据上传等)
    - `DEBUG`: 开发调试信息

```python
# 自定义异常示例
class DeviceNotFoundError(Exception):
    pass

class DevicePermissionDeniedError(Exception):
    pass

class IoTDBWriteError(Exception):
    pass
```

### D. 测试规范

1.  **命名**: `test_<功能>_<场景>_<预期结果>`
    - 例: `test_create_device_valid_mac_returns_201`
2.  **隔离**: 每个测试必须独立，不依赖其他测试的状态
3.  **Mock 策略**:
    - IoTDB 操作必须 mock，不连接真实数据库
    - 外部 API 调用必须 mock
4.  **覆盖率**: 核心业务逻辑覆盖率不低于 80%

### E. 安全规范

1.  **敏感信息**: 永远不要将密钥、密码提交到代码库
2.  **输入验证**: 所有用户输入必须通过 Pydantic Schema 验证
3.  **权限检查**: API 端点必须验证用户对资源的访问权限
4.  **SQL 注入**: 使用 ORM，禁止拼接 SQL 字符串

### F. 性能考量

1.  **数据库查询**: 使用 `select_related` / `prefetch_related` 避免 N+1
2.  **批量操作**: IoTDB 写入必须使用批量接口 (InsertTablet)
3.  **连接池**: IoTDB 使用 SessionPool，PostgreSQL 使用 Django 默认连接池
4.  **分页**: 列表 API 必须支持分页，默认每页 20 条

---

## 8. 关联项目说明

本后端需要与以下项目协同工作，开发时需参考其实现:

| 项目                     | 路径                          | 说明                         |
| ------------------------ | ----------------------------- | ---------------------------- |
| CosRay-App               | `../CosRay-App`               | Android 客户端，API 契约来源 |
| CosRay-Detector-Firmware | `../CosRay-Detector-Firmware` | ESP32 固件，数据包格式来源   |
| CosRay-Backend-Archive   | `../CosRay-Backend-Archive`   | 旧后端实现，参考代码来源     |

详细实施计划参见 `docs/plan.md`。

---

## 9. 输出质量要求

生成的代码应当:

1.  **可直接运行**: 不需要额外修改即可通过测试
2.  **风格一致**: 与项目现有代码风格保持一致
3.  **完整实现**: 不要留下 `TODO` 或 `pass` 占位符
4.  **有意义的变量名**: 使用描述性命名，避免单字母变量 (循环计数器除外)
5.  **最小化变更**: 每次提交保持原子性，修改文件数不超过 5 个
6.  **遵循规范**: 严格遵守本文档约定的代码风格、Git 工作流和测试要求
