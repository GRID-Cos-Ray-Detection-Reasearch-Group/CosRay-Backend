# CosRay 详细设计文档（LLD，V1）

## 1. 文档目标

本文档在 [requirements-v1.md](requirements-v1.md) 与 [top-level-design-v1.md](top-level-design-v1.md) 基础上，给出实现级详细设计，覆盖：

- 模块划分
- 关键数据结构
- 函数签名
- 处理流程与错误语义

本文档不包含排期与人力规划。

## 2. 设计总原则

- 硬件协议第一真值：包结构、字节布局、校验规则以 Firmware 为准。
- 后端契约第二真值：API 字段、错误码、鉴权与隔离规则以 Backend 为准。
- App 最小化适配：以“连接、解析、上传”为核心，不扩展业务真值。

## 3. 跨端数据模型

### 3.1 Packet 类型

- `muon`
- `timeline`

### 3.2 统一上传请求模型（逻辑视图）

```text
PacketUpload
- device: str  (MAC, AA:BB:CC:DD:EE:FF)
- packet_type: "muon" | "timeline"
- muon_packet: MuonPacket | null
- timeline_packet: TimelinePacket | null
```

### 3.3 统一错误模型

```text
ErrorResponse
- detail: str
- code: str | null
```

## 4. Firmware 协议对齐（参考）

> Firmware 非本仓库实现责任，本节用于三端协议联调对齐。

### 4.1 结构体签名（C）

```c
#pragma pack(push, 1)
typedef struct {
    uint64_t cpu_time;
    uint16_t energy;
    uint32_t pps;
} MuonData_t;
#pragma pack(pop)

#pragma pack(push, 1)
typedef struct {
    uint8_t  head[3];      // AA BB CC
    uint32_t PkgCnt;
    uint32_t utc;
    MuonData_t MuonData[35];
    uint8_t  tail[3];      // DD EE FF
    uint8_t  reserved[6];
    uint16_t crc;
} MuonDataPkg_t;
#pragma pack(pop)

#pragma pack(push, 1)
typedef struct {
    uint64_t cpu_time;
    uint32_t pps;
    uint32_t utc;
    uint32_t pps_utc;
    uint64_t cputime_pps;
    uint32_t gps_long;
    int32_t  gps_lat;
    int16_t  gps_alt;
    int8_t   acc_x;
    int8_t   acc_y;
    int8_t   acc_z;
    uint16_t SiPMTmp;
    uint8_t  MCUTmp;
    uint16_t SiPMImon;
    uint16_t SiPMVmon;
} TimeLineData_t;
#pragma pack(pop)

#pragma pack(push, 1)
typedef struct {
    uint8_t head[3];        // 12 34 56
    uint32_t PkgCnt;
    TimeLineData_t TimeLineData[10];
    uint8_t tail[3];        // 78 9A BC
    uint8_t reserved[20];
    uint16_t crc;
} TimeLinePkg_t;
#pragma pack(pop)
```

## 5. Backend 详细设计

### 5.1 模块结构

- `core/models.py`：关系模型（Detector）
- `core/schemas.py`：请求/响应模型
- `core/validators.py`：MAC 与包体一致性校验
- `core/services.py`：IoTDB 写入与路径规范化
- `core/api.py`：路由、鉴权、归属校验、上传编排

### 5.2 关键 Schema 签名（Python）

```python
class PacketUpload(Schema):
    device: str
    packet_type: Literal["muon", "timeline"]
    muon_packet: MuonPacket | None = None
    timeline_packet: TimelinePacket | None = None

class PacketUploadResponse(Schema):
    device: str
    device_name: str
    packet_type: str
    records_written: int
    message: str

class ErrorResponse(Schema):
    detail: str
    code: str | None = None

class CurrentUserOut(Schema):
    id: int
    username: str
    email: str
```

### 5.3 关键函数签名（Python）

```python
def resolve_request_id(request: HttpRequest) -> str: ...

def resolve_authenticated_user(request: HttpRequest) -> User: ...

def get_owned_detector_or_error(
    user: User,
    mac_address: str,
) -> tuple[Detector | None, ErrorResponse | None]: ...

def normalize_mac_or_error(raw_mac: str) -> tuple[str | None, ErrorResponse | None]: ...

def validate_packet_payload(payload: PacketUpload) -> ErrorResponse | None: ...

def ingest_muon_packet(device_mac: str, packet: MuonPacket) -> int: ...

def ingest_timeline_packet(device_mac: str, packet: TimelinePacket) -> int: ...
```

### 5.4 `upload_packet` 处理流程

1. 读取/生成 `request_id`。
2. 校验并规范化 `device`（MAC）。
3. 校验设备归属（`owner + mac_address`）。
4. 校验 `packet_type` 与包体、head/tail、事件上限。
5. 根据 `packet_type` 调用 IoTDB 写入服务。
6. 更新 `Detector.last_seen_at`。
7. 返回 `PacketUploadResponse`（含兼容字段 `device_name`、`message`）。

### 5.5 错误码语义（当前实现）

- `INVALID_MAC_ADDRESS`
- `DEVICE_NOT_FOUND`
- `DEVICE_EXISTS`
- `INVALID_PACKET`
- `MUON_EVENTS_OVER_LIMIT`
- `TIMELINE_EVENTS_OVER_LIMIT`
- `INVALID_MUON_HEAD`
- `INVALID_MUON_TAIL`
- `INVALID_TIMELINE_HEAD`
- `INVALID_TIMELINE_TAIL`
- `IOTDB_WRITE_ERROR`

## 6. App 详细设计

### 6.1 模块结构

- `core/ble/NordicBleDeviceManager.kt`：BLE 连接、通知、写入
- `core/ble/BleController.kt`：连接状态与原始包事件分发
- `domain/model/Protocol.kt`：二进制协议解析模型
- `domain/mapper/ProtocolMapper.kt`：协议模型 -> 上传 DTO
- `core/network/CosRayApi.kt`：后端 API 客户端
- `data/auth/AuthRepository.kt`：登录态、refresh、token 有效性检查
- `data/telemetry/TelemetryRepository.kt`：组包、缓存、上传

### 6.2 关键函数签名（Kotlin）

```kotlin
class CosRayApi(private val client: HttpClient) {
  suspend fun login(username: String, password: String): Pair<User, AuthTokens>
  suspend fun refreshToken(refreshToken: String): AuthTokens
  suspend fun fetchCurrentUser(accessToken: String): User
  suspend fun uploadPacket(accessToken: String, request: PacketUploadRequest): PacketUploadResponse
}

class AuthRepository {
  suspend fun ensureValidToken(): CosRayResult<String>
}

class TelemetryRepository {
  suspend fun uploadBufferedSamples(): CosRayResult<Unit>
}
```

### 6.3 `uploadBufferedSamples` 处理流程

1. 从 `_uploadBuffer` 读取待上传请求。
2. 空队列直接返回成功。
3. 对每个请求调用 `authRepository.ensureValidToken()` 获取有效 access token。
4. 调用 `api.uploadPacket(token, request)` 上传。
5. 全部成功则清空 `_buffer`、`_liveTelemetry`、`_uploadBuffer`。

## 7. 二进制包字节布局（512B）

### 7.1 MuonDataPkg_t

| 偏移区间 | 长度 | 字段 |
|---|---:|---|
| `0..2` | 3 | `head` |
| `3..6` | 4 | `PkgCnt` |
| `7..10` | 4 | `utc` |
| `11..500` | 490 | `MuonData[35]` |
| `501..503` | 3 | `tail` |
| `504..509` | 6 | `reserved` |
| `510..511` | 2 | `crc` |

### 7.2 TimeLinePkg_t

| 偏移区间 | 长度 | 字段 |
|---|---:|---|
| `0..2` | 3 | `head` |
| `3..6` | 4 | `PkgCnt` |
| `7..486` | 480 | `TimeLineData[10]` |
| `487..489` | 3 | `tail` |
| `490..509` | 20 | `reserved` |
| `510..511` | 2 | `crc` |

## 8. 状态机（实现约束）

### 8.1 App 上传状态机

```text
IDLE
  -> 收到 raw chunk
  -> BUFFERING
BUFFERING
  -> 凑满 512B 且协议校验通过 -> PARSED
  -> 协议不合法 -> DROP -> BUFFERING
PARSED
  -> 映射 DTO -> QUEUED
QUEUED
  -> 触发上传 -> UPLOADING
UPLOADING
  -> 成功 -> DONE
  -> 失败 -> RETRYABLE_FAILED
```

### 8.2 Backend 上传状态机

```text
RECEIVED
  -> MAC 校验失败 -> 400 INVALID_MAC_ADDRESS
  -> 归属校验失败 -> 404 DEVICE_NOT_FOUND
  -> 包体校验失败 -> 400 (INVALID_PACKET / HEAD_TAIL / LIMIT)
  -> 写入失败 -> 400 IOTDB_WRITE_ERROR
  -> 写入成功 -> 200 OK + 更新 last_seen_at
```

## 9. 联调验收用例（无排期）

### 9.1 用例 A：Muon 正常上报

- 前置：有效 JWT、设备已归属。
- 步骤：上传合法 `muon` 包。
- 预期：HTTP 200，`records_written == events.size`。

### 9.2 用例 B：Timeline 正常上报

- 步骤：上传合法 `timeline` 包。
- 预期：HTTP 200，`records_written == events.size`。

### 9.3 用例 C：非归属设备上传

- 步骤：使用 U1 token 上传 U2 设备 MAC。
- 预期：HTTP 404，`code == "DEVICE_NOT_FOUND"`。

### 9.4 用例 D：包体缺失

- 步骤：`packet_type="muon"` 且缺少 `muon_packet`。
- 预期：HTTP 400，`code == "INVALID_PACKET"`。

### 9.5 用例 E：IoTDB 写入失败

- 步骤：Mock `ingest_*_packet` 抛异常。
- 预期：HTTP 400，`code == "IOTDB_WRITE_ERROR"`。

## 10. 一致性检查清单

1. `typedefs.h` 与 `Protocol.kt` 字段长度一致。
2. `ProtocolMapper.kt` 与 `DevicePacketDtos.kt` 字段一致。
3. `DevicePacketDtos.kt` 与 `core/schemas.py` 一致。
4. `core/api.py` 返回字段与 `schemas` 一致。
5. 错误码在需求文档、设计文档、实现和测试中一致。

## 11. 文档维护规则

- 协议字段变化：先改需求文档，再改顶层设计，再改详细设计，再改实现。
- 错误码变化：同步更新 `requirements-v1.md`、本文件和测试断言。
- 评审必须检查“硬件协议 -> Backend Schema -> App DTO”三点一致。
