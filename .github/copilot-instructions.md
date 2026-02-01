# CosRay-Backend: AI Coding Agent Instructions

## 项目概览

CosRay-Backend 是宇宙射线探测系统的**全新轻量级** IoT 后端服务，基于 Django 6+ & Django Ninja 从零构建。项目采用**极简主义哲学**：零历史包袱、拒绝过度封装、优先最佳实践。

**设计原则**:

- 🎯 **从零开始**: 不继承旧架构，按现代标准重新设计
- ⚡ **性能优先**: 读写分离 (PostgreSQL + IoTDB)，连接池优化
- 🔧 **实用主义**: 用成熟库解决问题，不重复造轮子
- 📦 **扁平简洁**: 最小化抽象层，代码即文档

**生态系统架构**:

```
ESP32固件 (BLE) → Android App (HTTP API) → Django Backend → PostgreSQL + IoTDB
```

- **CosRay-Detector-Firmware**: ESP32 固件，通过 BLE 发送 Muon/Timeline 数据包
- **CosRay-App**: Android 客户端，解析数据包并上传至后端
- **CosRay-Backend** (本项目): 全新 API 服务，专注设备管理与时序数据存储

## 核心技术栈

- **语言**: Python 3.13 (强制使用新式类型注解: `list[str]`, `str | None`)
- **Web 框架**: Django 6+, Django Ninja (API), Uvicorn (ASGI 服务器)
- **数据库**: PostgreSQL 17 (元数据/业务), Apache IoTDB 2.0.6+ (时序数据)
- **鉴权**: Django Ninja JWT (标准 Bearer Token，替代旧 `X-Session-Token`)
- **后台**: Django Unfold (现代化 Admin UI，必须在 `django.contrib.admin` **之前**注册)
- **工具链**: `uv` (包管理), `ruff` (lint/format), `pytest` (测试)

## 依赖管理规范

**严禁使用 `pip` 或 `virtualenv`，必须使用 `uv`**:

```bash
uv sync                           # 初始化/同步环境
uv add <package>                  # 添加生产依赖
uv add --dev <package>            # 添加开发依赖
uv run python manage.py <cmd>    # 运行 Django 命令
uv run pytest                     # 运行测试
```

## 项目结构约定

保持扁平化，避免深层嵌套。预期结构:

```
CosRay-Backend/
├── config/              # Django 配置
│   ├── settings.py      # 核心配置 (使用 django-environ)
│   └── urls.py          # 顶层路由
├── core/                # 主业务 App (当前为空模板)
│   ├── api.py           # Django Ninja API 路由
│   ├── models.py        # PostgreSQL 模型 (Detector, Event)
│   ├── schemas.py       # Pydantic 请求/响应模型
│   ├── services.py      # 业务逻辑 & IoTDB 封装
│   ├── admin.py         # Unfold 后台配置
│   └── tests/           # Pytest 测试
├── pyproject.toml       # uv 依赖管理 & ruff 配置
├── .env                 # (GitIgnored) 本地环境变量
└── docker-compose.yml   # PostgreSQL + IoTDB 服务编排
```

**注意**: 当前 `core/` 为空模板，所有业务代码待实现。遵循 `AGENT.md` 和 `docs/plan.md` 的详细规范。

## 数据模型设计

### PostgreSQL (Django ORM)

- **Detector** (核心设备模型):
  - `mac_address`: `CharField(17, unique=True)` - 格式: `AA:BB:CC:DD:EE:FF`
  - `owner`: `ForeignKey(User)` - 设备所有者
  - `name`: `CharField(100)` - 用户自定义名称
  - `description`: `TextField(blank=True)` - 描述信息
  - `is_active`: `BooleanField(default=True)` - 激活状态
  - `last_seen_at`: `DateTimeField(null=True)` - 最后上报时间

### IoTDB (时序数据)

- **路径模式**: `root.cosray.<mac_sanitized>.<packet_type>.<metric>`
  - MAC 规范化: `AA:BB:CC:DD:EE:FF` → `AA_BB_CC_DD_EE_FF`
  - 示例: `root.cosray.AA_BB_CC_DD_EE_FF.muon.energy`
- **数据类型**: `energy`/`cpu_time`/`pps` (INT32/INT64)
- **连接管理**: 必须使用 `SessionPool`，不要频繁创建 Session

```python
# services.py 参考实现
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
            max_size=5
        )
    return _session_pool
```

## API 契约 (与 CosRay-App 对接)

必须严格遵守 App 端的数据结构 (参见 `docs/plan.md` 第 2.3 节):

**关键端点**:

- `POST /api/auth/login`: JWT 登录 (返回 `access_token` / `refresh_token`)
- `GET /api/users/me`: 获取当前用户信息
- `GET/POST /api/devices/`: 设备列表/注册
- `POST /api/mu-packets/`: 上传 Muon/Timeline 数据包

**Schema 示例** (`schemas.py`):

```python
from ninja import Schema
from typing import Literal

class MuonEventSchema(Schema):
    cpu_time: int
    energy: int
    pps: int
    timestamp: int | None = None

class PacketUploadSchema(Schema):
    device: str  # MAC 地址
    packet_type: Literal["muon", "timeline"]
    muon_packet: MuonPacketSchema | None = None
    timeline_packet: TimelinePacketSchema | None = None
```

## 代码风格规范

1. **类型注解**: 强制使用 Python 3.13 新语法 (`list[str]` 而非 `List[str]`)
2. **格式化**: 所有代码必须通过 `ruff format` 格式化
3. **Lint**: 提交前运行 `ruff check . --fix` (pre-commit 会自动检查)
4. **注释语言**: 所有注释、文档字符串使用中文
5. **禁止事项**:
   - 不使用 emoji
   - 不使用 `print()` 调试 (使用 `logging` 模块)
   - 不硬编码配置值 (全部通过 `settings.py` 读取环境变量)
   - 不留 `TODO` 或 `pass` 占位符 (代码必须完整)

## Git 工作流

**分支策略**:

- 保护分支: `main` (生产), `dev` (开发)
- 从 `dev` 创建特性分支: `git checkout -b feature/device-api`
- 分支命名: `feature/<描述>`, `fix/<描述>`, `refactor/<描述>`, `docs/<描述>`

**提交规范** (约定式提交):

```
<类型>: <简洁描述>

类型: feat | fix | refactor | docs | test | chore | style
示例: feat: 实现设备注册 API
```

**提交要求**:

- 每次提交只做一件事 (原子性)
- 使用中文，动词开头，无句号
- 提交前运行: `ruff format . && ruff check . --fix && pytest`

## 测试规范

- **框架**: Pytest + Pytest-Django + Pytest-Asyncio
- **命名**: `test_<功能>_<场景>_<预期结果>`
- **Mock 策略**: IoTDB 操作必须 mock，使用 `unittest.mock.patch('core.services.get_iotdb_session')`
- **隔离性**: 每个测试独立，不依赖其他测试状态
- **覆盖率**: 核心业务逻辑不低于 80%

## 环境配置

复制 `.env.example` 到 `.env` (如不存在需创建):

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

## 常见陷阱

1. **Unfold 顺序错误**: `INSTALLED_APPS` 中 `unfold` 必须在 `django.contrib.admin` 之前
2. **CORS 中间件顺序**: `CorsMiddleware` 必须在 `CommonMiddleware` 之前
3. **IoTDB 连接泄露**: 禁止直接 `Session()`，必须用 `SessionPool`
4. **类型注解兼容性**: 使用 `from __future__ import annotations` 或确保 Python 3.13+
5. **JWT vs Session**: App 已迁移到 JWT (`Authorization: Bearer <token>`)，不再使用 `X-Session-Token`

## 参考文档

- **实施蓝图**: [docs/plan.md](docs/plan.md) - 完整的 API 契约和数据流设计
- **编码规范**: [AGENT.md](AGENT.md) - 开发标准、工作流和质量要求
- **避坑参考**: `../CosRay-Backend-Archive` - 旧后端的技术债务与经验教训 (仅供避坑，**不要照搬实现**)

---

## 开发理念

**重要**: 本项目是全新的轻量级实现，不受旧后端约束。Archive 仅用于:

- ✅ 了解过去的技术债务和设计缺陷
- ✅ 验证业务逻辑的边界情况
- ❌ **绝不** 复制旧代码的架构或实现模式

实施时优先考虑:

1. **现代 Python 生态**: 充分利用 Python 3.13、Django 6、Pydantic v2 的新特性
2. **简洁性**: 如果一个功能可以用 10 行实现，就不要写 100 行
3. **类型安全**: 完整的类型注解 + Pydantic 验证，消除运行时错误
4. **可测试性**: 每个模块独立、可 mock、易验证

从数据库模型、Schema、API 到测试逐步构建，保持增量提交，拥抱变化。
