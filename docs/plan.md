# CosRay-Backend 完整开发实施计划

本计划为下级 Agent 提供详尽的上下文与步骤指导，用于构建一个基于 Django Ninja 的轻量级 IoT 后端服务，实现与 CosRay-App 的无缝对接。

---

## 1. 项目背景与上下文

### 1.1 工作区项目关系

```
CosRay-App (Android)
    ↓ HTTP API
CosRay-Backend (Django Ninja)
    ↓ 写入
PostgreSQL (元数据) + IoTDB (时序数据)
    ↑ 数据上报
CosRay-Detector-Firmware (ESP32)
```

### 1.2 数据流向

1. **固件 → App**: ESP32 通过 BLE 将 Muon/Timeline 数据包发送给 Android App
2. **App → Backend**: App 解析数据包后通过 HTTP API 上传至后端
3. **Backend → IoTDB**: 后端将时序数据写入 IoTDB
4. **Backend → PostgreSQL**: 设备元数据、用户信息存入 PostgreSQL

---

## 2. App API 契约详解

### 2.1 当前认证方式

App 目前使用 `X-Session-Token` Header（基于 django-allauth headless）：

```kotlin
// CosRayApi.kt
private fun HttpRequestBuilder.sessionToken(currentToken: String) {
    header("X-Session-Token", currentToken)
}
```

**迁移目标**: 标准 JWT Bearer Token

```
Authorization: Bearer <access_token>
```

### 2.2 API 端点清单

| 端点                 | 方法   | 认证 | 说明                                |
| -------------------- | ------ | ---- | ----------------------------------- |
| `/api/auth/login`    | POST   | 否   | JWT 登录，返回 access/refresh token |
| `/api/auth/refresh`  | POST   | 否   | 刷新 access token                   |
| `/api/users/me`      | GET    | 是   | 获取当前用户信息                    |
| `/api/devices/`      | GET    | 是   | 获取用户设备列表                    |
| `/api/devices/`      | POST   | 是   | 注册新设备                          |
| `/api/devices/{id}/` | GET    | 是   | 获取设备详情                        |
| `/api/devices/{id}/` | PATCH  | 是   | 更新设备信息                        |
| `/api/devices/{id}/` | DELETE | 是   | 删除设备                            |
| `/api/mu-packets/`   | POST   | 是   | 上传数据包                          |

### 2.3 请求/响应数据结构

#### 认证相关

```python
# 登录请求
class LoginRequest:
    username: str
    password: str

# 用户响应
class UserResponse:
    id: str
    username: str
    email: str
    display: str
    avatar_url: str | None
    organization: str | None
    roles: list[str]
```

#### 设备相关

```python
# 设备响应 (对应 App 的 DeviceDto)
class DeviceOutSchema:
    id: int
    mac_address: str          # 格式: AA:BB:CC:DD:EE:FF
    name: str
    description: str | None
    is_active: bool
    owner_id: int
    owner_username: str
    created_at: datetime
    updated_at: datetime
    last_seen_at: datetime | None

# 设备注册请求
class DeviceCreateSchema:
    mac_address: str          # 需验证格式
    name: str
    description: str | None
```

#### 数据包相关

```python
# 数据包上传请求
class PacketUploadSchema:
    device: str               # MAC 地址
    packet_type: Literal["muon", "timeline"]
    muon_packet: MuonPacketSchema | None
    timeline_packet: TimelinePacketSchema | None

# 数据包上传响应
class PacketUploadResponseSchema:
    device: str
    device_name: str
    packet_type: str
    records_written: int
```

---

## 3. 数据包格式规范

### 3.1 Muon Packet 结构

**固件原始格式 (512字节)**:

| 字段         | 偏移 | 大小 | 类型         | 描述                      |
| ------------ | ---- | ---- | ------------ | ------------------------- |
| head         | 0    | 3    | bytes        | 包头 `[0xAA, 0xBB, 0xCC]` |
| pkgCnt       | 3    | 4    | uint32       | 全局包计数                |
| utc          | 7    | 4    | uint32       | 首事件 UTC 时间           |
| muonDataList | 11   | 490  | MuonData[35] | 35 个事件                 |
| tail         | 501  | 3    | bytes        | 包尾 `[0xDD, 0xEE, 0xFF]` |
| crc          | 504  | 2    | uint16       | XOR 校验                  |
| reserved     | 506  | 6    | bytes        | 预留                      |

**MuonData 结构 (14字节)**:

| 字段    | 大小 | 类型   | 描述          |
| ------- | ---- | ------ | ------------- |
| cpuTime | 8    | uint64 | CPU 时钟      |
| energy  | 2    | uint16 | 能量 (ADC 值) |
| pps     | 4    | uint32 | PPS 脉冲计数  |

**Pydantic Schema**:

```python
class MuonEventSchema(Schema):
    cpu_time: int             # 对应 cpuTime
    energy: int               # 16位 ADC 值
    pps: int                  # PPS 计数
    timestamp: int | None = None

class MuonPacketSchema(Schema):
    package_counter: int      # 对应 pkgCnt
    utc: int                  # 首事件 UTC
    events: list[MuonEventSchema]
    head: list[int] | None = None
    tail: list[int] | None = None
    crc: int | None = None
```

### 3.2 Timeline Packet 结构

**固件原始格式 (512字节)**:

| 字段             | 偏移 | 大小 | 类型             | 描述                      |
| ---------------- | ---- | ---- | ---------------- | ------------------------- |
| head             | 0    | 3    | bytes            | 包头 `[0x12, 0x34, 0x56]` |
| pkgCnt           | 3    | 4    | uint32           | 全局包计数                |
| timeLineDataList | 7    | 480  | TimeLineData[10] | 10 个事件                 |
| tail             | 487  | 3    | bytes            | 包尾 `[0x78, 0x9A, 0xBC]` |
| crc              | 490  | 2    | uint16           | XOR 校验                  |
| reserve          | 492  | 20   | bytes            | 预留                      |

**TimeLineData 结构 (48字节)**:

| 字段       | 大小 | 类型   | 描述                 |
| ---------- | ---- | ------ | -------------------- |
| cpuTime    | 8    | uint64 | CPU 时钟             |
| pps        | 4    | uint32 | 当前 PPS             |
| utc        | 4    | uint32 | UTC 时间戳           |
| ppsUtc     | 4    | uint32 | 上次 UTC 的 PPS      |
| cpuTimePps | 8    | uint64 | 上次 PPS 的 CPU 时钟 |
| gpsLong    | 4    | int32  | GPS 经度             |
| gpsLat     | 4    | int32  | GPS 纬度             |
| gpsAlt     | 2    | int16  | GPS 海拔             |
| accX       | 1    | int8   | X 轴加速度           |
| accY       | 1    | int8   | Y 轴加速度           |
| accZ       | 1    | int8   | Z 轴加速度           |
| siPMTmp    | 2    | uint16 | SiPM 温度            |
| mcUTmp     | 1    | uint8  | MCU 温度             |
| siPMImon   | 2    | uint16 | SiPM 漏电流          |
| siPMVmon   | 2    | uint16 | SiPM 偏压            |

**Pydantic Schema**:

```python
class TimelineEventSchema(Schema):
    cpu_time: int
    pps: int
    utc: int
    pps_utc: int
    cputime_pps: int
    gps_long: int
    gps_lat: int
    gps_alt: int
    acc_x: int
    acc_y: int
    acc_z: int
    sipm_tmp: int             # 对应 SiPMTmp
    mcu_tmp: int              # 对应 MCUTmp
    sipm_imon: int            # 对应 SiPMImon
    sipm_vmon: int            # 对应 SiPMVmon
    timestamp: int | None = None

class TimelinePacketSchema(Schema):
    package_counter: int
    events: list[TimelineEventSchema]
    head: list[int] | None = None
    tail: list[int] | None = None
    crc: int | None = None
```

### 3.3 字段命名映射

App 使用 `@SerialName` 注解，后端需要对应处理：

| App (Kotlin)     | 后端 (Python)     | 说明         |
| ---------------- | ----------------- | ------------ |
| `cpuTime`        | `cpu_time`        | 驼峰 → 蛇形  |
| `packageCounter` | `package_counter` | -            |
| `SiPMTmp`        | `sipm_tmp`        | 大写缩写处理 |
| `MCUTmp`         | `mcu_tmp`         | -            |
| `ppsUtc`         | `pps_utc`         | -            |
| `cputimePps`     | `cputime_pps`     | -            |

---

## 4. IoTDB 数据存储规范

### 4.1 路径结构

```
root.cosray
├── AA_BB_CC_DD_EE_FF          # 设备 MAC (冒号替换为下划线)
│   ├── muon                   # Muon 数据
│   │   ├── cpu_time
│   │   ├── energy
│   │   ├── pps
│   │   └── timestamp
│   └── timeline               # Timeline 数据
│       ├── cpu_time
│       ├── pps
│       ├── utc
│       ├── gps_long
│       ├── gps_lat
│       ├── gps_alt
│       ├── acc_x
│       ├── acc_y
│       ├── acc_z
│       ├── sipm_tmp
│       ├── mcu_tmp
│       ├── sipm_imon
│       └── sipm_vmon
```

### 4.2 MAC 地址规范化

```python
def normalize_device_path(mac_address: str) -> str:
    """将 MAC 地址转换为 IoTDB 路径格式"""
    sanitized = mac_address.strip().upper().replace(":", "_").replace("-", "_")
    return f"root.cosray.{sanitized}"
```

### 4.3 数据类型映射

| 指标             | IoTDB 类型 | 说明          |
| ---------------- | ---------- | ------------- |
| cpu_time         | INT64      | CPU 时钟计数  |
| energy           | INT32      | 16位 ADC 值   |
| pps              | INT64      | PPS 脉冲计数  |
| timestamp        | INT64      | 毫秒级时间戳  |
| gps_long/lat     | INT32      | GPS 坐标      |
| gps_alt          | INT32      | 海拔 (米)     |
| acc_x/y/z        | INT32      | 加速度        |
| sipm_tmp/mcu_tmp | INT32      | 温度          |
| sipm_imon/vmon   | INT32      | 电压/电流监测 |

---

## 5. 实施阶段

### Phase 1: 基础设施配置

#### 1.1 完善 config/settings.py

- [ ] 引入 `django-environ`
- [ ] 配置 PostgreSQL (`DATABASE_URL`)
- [ ] 配置 IoTDB 参数
- [ ] 调整 `INSTALLED_APPS` 顺序 (`unfold` 在 `admin` 之前)
- [ ] 添加 `corsheaders` 中间件
- [ ] 添加 `whitenoise` 中间件

#### 1.2 创建 docker-compose.yml

- [ ] PostgreSQL 15 服务
- [ ] IoTDB 1.3 服务
- [ ] 健康检查配置
- [ ] 数据卷持久化

#### 1.3 创建 .env.example

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

### Phase 2: 数据模型层

#### 2.1 创建 Backend App

```bash
uv run python manage.py startapp Backend
```

#### 2.2 实现 Detector 模型

```python
# Backend/models.py
class Detector(models.Model):
    mac_address = models.CharField(max_length=17, unique=True)
    name = models.CharField(max_length=100)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="detectors"
    )
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
```

#### 2.3 实现 Pydantic Schemas

- [ ] `MuonEventSchema`, `MuonPacketSchema`
- [ ] `TimelineEventSchema`, `TimelinePacketSchema`
- [ ] `PacketUploadSchema`, `PacketUploadResponseSchema`
- [ ] `DeviceOutSchema`, `DeviceCreateSchema`, `DeviceUpdateSchema`

### Phase 3: IoTDB 集成层

#### 3.1 实现 SessionPool 管理

```python
# Backend/services.py
from iotdb.SessionPool import SessionPool
from functools import lru_cache

@lru_cache(maxsize=1)
def get_iotdb_pool() -> SessionPool:
    return SessionPool(
        host=settings.IOTDB_HOST,
        port=int(settings.IOTDB_PORT),
        user=settings.IOTDB_USER,
        password=settings.IOTDB_PASSWORD,
        max_size=5,
    )
```

#### 3.2 实现数据写入服务

- [ ] `normalize_device_path()`: MAC 地址路径化
- [ ] `ingest_muon_packet()`: 写入 Muon 数据
- [ ] `ingest_timeline_packet()`: 写入 Timeline 数据

### Phase 4: API 开发层

#### 4.1 配置 JWT 认证

```python
# config/settings.py
NINJA_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=1),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "AUTH_HEADER_TYPES": ("Bearer",),
}
```

#### 4.2 实现 API 路由

```python
# Backend/api.py
from ninja import Router
from ninja_jwt.authentication import JWTAuth

router = Router(auth=JWTAuth())

@router.get("/devices/")
def list_devices(request):
    ...

@router.post("/devices/")
def create_device(request, payload: DeviceCreateSchema):
    ...

@router.post("/mu-packets/")
def upload_packet(request, payload: PacketUploadSchema):
    ...
```

#### 4.3 更新 URL 配置

```python
# config/urls.py
from ninja import NinjaAPI
from ninja_jwt.controller import NinjaJWTDefaultController
from Backend.api import router as backend_router

api = NinjaAPI()
api.register_controllers(NinjaJWTDefaultController)
api.add_router("/", backend_router)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", api.urls),
]
```

### Phase 5: 管理后台

#### 5.1 配置 Unfold Admin

```python
# Backend/admin.py
from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import Detector

@admin.register(Detector)
class DetectorAdmin(ModelAdmin):
    list_display = ["mac_address", "name", "owner", "is_active", "last_seen_at"]
    list_filter = ["is_active", "created_at"]
    search_fields = ["mac_address", "name", "owner__username"]
```

### Phase 6: 测试层

#### 6.1 测试配置

```python
# Backend/tests/conftest.py
import pytest
from model_bakery import baker

@pytest.fixture
def user(db):
    return baker.make("auth.User")

@pytest.fixture
def detector(db, user):
    return baker.make("Backend.Detector", owner=user)

@pytest.fixture
def mock_iotdb(monkeypatch):
    captured = {"records": []}
    def fake_write(device, records):
        captured["records"].extend(records)
        return len(records)
    monkeypatch.setattr("Backend.services.write_records", fake_write)
    return captured
```

#### 6.2 测试用例

- [ ] 设备 CRUD 测试
- [ ] 数据包上传测试 (mock IoTDB)
- [ ] 认证流程测试
- [ ] 权限控制测试

---

## 6. 兼容性注意事项

### 6.1 认证迁移

App 端需要同步修改 `CosRayApi.kt`:

```kotlin
// 原来
header("X-Session-Token", currentToken)

// 改为
header("Authorization", "Bearer $accessToken")
```

### 6.2 时间戳精度

- 固件使用秒级 UTC 时间戳
- IoTDB 使用毫秒级时间戳
- 写入时需要乘以 1000

### 6.3 字节序

- 固件数据包: 小端序 (Little-Endian)
- 网络传输: App 已解析为整数，无需后端处理

---

## 7. 参考资源

### 7.1 旧后端代码位置

| 功能         | 文件路径                                                              |
| ------------ | --------------------------------------------------------------------- |
| 设备模型     | `CosRay-Backend-Archive/cosray_backend/devices/models.py`             |
| IoTDB 客户端 | `CosRay-Backend-Archive/cosray_backend/iotdb/client.py`               |
| 数据包服务   | `CosRay-Backend-Archive/cosray_backend/mu_packets/services.py`        |
| API 序列化   | `CosRay-Backend-Archive/cosray_backend/mu_packets/api/serializers.py` |

### 7.2 App 代码位置

| 功能       | 文件路径                                                                           |
| ---------- | ---------------------------------------------------------------------------------- |
| API 定义   | `CosRay-App/app/src/main/java/com/grid/cosray/data/remote/CosRayApi.kt`            |
| 数据包 DTO | `CosRay-App/app/src/main/java/com/grid/cosray/data/remote/dto/DevicePacketDtos.kt` |
| 协议解析   | `CosRay-App/app/src/main/java/com/grid/cosray/data/ble/Protocol.kt`                |

### 7.3 固件代码位置

| 功能     | 文件路径                                 |
| -------- | ---------------------------------------- |
| 主程序   | `CosRay-Detector-Firmware/main/main.c`   |
| 配置定义 | `CosRay-Detector-Firmware/main/config.h` |
