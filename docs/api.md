# API 文档

## 认证方式

使用 JWT Bearer Token 认证。

### 获取 Token

```bash
POST /api/token/pair
Content-Type: application/json

{
  "username": "your_username",
  "password": "your_password"
}
```

响应：

```json
{
  "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

### 使用 Token

```bash
GET /api/devices/
Authorization: Bearer <access_token>
```

### 刷新 Token

```bash
POST /api/token/refresh
Content-Type: application/json

{
  "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

## API 端点

### 设备管理

#### 获取设备列表

```bash
GET /api/devices/
Authorization: Bearer <token>
```

响应：

```json
[
  {
    "id": 1,
    "mac_address": "AA:BB:CC:DD:EE:FF",
    "name": "Detector-01",
    "description": "Primary detector",
    "is_active": true,
    "owner_id": 1,
    "owner_username": "admin",
    "created_at": "2026-01-01T00:00:00Z",
    "updated_at": "2026-01-01T00:00:00Z",
    "last_seen_at": "2026-01-01T12:00:00Z"
  }
]
```

#### 注册新设备

```bash
POST /api/devices/
Authorization: Bearer <token>
Content-Type: application/json

{
  "mac_address": "AA:BB:CC:DD:EE:FF",
  "name": "Detector-01",
  "description": "Primary detector"
}
```

#### 获取设备详情

```bash
GET /api/devices/{id}/
Authorization: Bearer <token>
```

#### 更新设备信息

```bash
PATCH /api/devices/{id}/
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "Updated Name",
  "description": "Updated description"
}
```

#### 删除设备

```bash
DELETE /api/devices/{id}/
Authorization: Bearer <token>
```

### 数据上传

#### 上传数据包

```bash
POST /api/mu-packets/
Authorization: Bearer <token>
Content-Type: application/json

{
  "device": "AA:BB:CC:DD:EE:FF",
  "packet_type": "muon",
  "muon_packet": {
    "package_counter": 12345,
    "utc": 1704067200,
    "events": [
      {
        "cpu_time": 1234567890,
        "energy": 1234,
        "pps": 100,
        "timestamp": null
      }
    ]
  }
}
```

或上传 Timeline 数据包：

```json
{
  "device": "AA:BB:CC:DD:EE:FF",
  "packet_type": "timeline",
  "timeline_packet": {
    "package_counter": 12345,
    "events": [
      {
        "cpu_time": 1234567890,
        "pps": 100,
        "utc": 1704067200,
        "pps_utc": 95,
        "cputime_pps": 1234567000,
        "gps_long": 121473650,
        "gps_lat": 31230410,
        "gps_alt": 50,
        "acc_x": 10,
        "acc_y": 5,
        "acc_z": 98,
        "sipm_tmp": 250,
        "mcu_tmp": 35,
        "sipm_imon": 100,
        "sipm_vmon": 2800
      }
    ]
  }
}
```

响应：

```json
{
  "device": "AA:BB:CC:DD:EE:FF",
  "device_name": "Detector-01",
  "packet_type": "muon",
  "records_written": 35
}
```

## 数据格式

### Muon Packet

**固件原始格式**（512 字节）：

| 字段         | 偏移 | 大小 | 类型         | 说明                      |
| ------------ | ---- | ---- | ------------ | ------------------------- |
| head         | 0    | 3    | bytes        | 包头 `[0xAA, 0xBB, 0xCC]` |
| pkgCnt       | 3    | 4    | uint32       | 全局包计数                |
| utc          | 7    | 4    | uint32       | 首事件 UTC 时间           |
| muonDataList | 11   | 490  | MuonData[35] | 35 个事件                 |
| tail         | 501  | 3    | bytes        | 包尾 `[0xDD, 0xEE, 0xFF]` |
| crc          | 504  | 2    | uint16       | XOR 校验                  |
| reserved     | 506  | 6    | bytes        | 预留                      |

**MuonEvent 结构**（14 字节）：

```python
{
  "cpu_time": 1234567890,  # CPU 时钟（uint64）
  "energy": 1234,          # 能量 ADC 值（uint16）
  "pps": 100,              # PPS 脉冲计数（uint32）
  "timestamp": null          # 可选时间戳
}
```

### Timeline Packet

**固件原始格式**（512 字节）：

| 字段             | 偏移 | 大小 | 类型             | 说明                      |
| ---------------- | ---- | ---- | ---------------- | ------------------------- |
| head             | 0    | 3    | bytes            | 包头 `[0x12, 0x34, 0x56]` |
| pkgCnt           | 3    | 4    | uint32           | 全局包计数                |
| timeLineDataList | 7    | 480  | TimeLineData[10] | 10 个事件                 |
| tail             | 487  | 3    | bytes            | 包尾 `[0x78, 0x9A, 0xBC]` |
| crc              | 490  | 2    | uint16           | XOR 校验                  |
| reserve          | 492  | 20   | bytes            | 预留                      |

**TimelineEvent 结构**（48 字节）：

```python
{
  "cpu_time": 1234567890,      # CPU 时钟（uint64）
  "pps": 100,                  # 当前 PPS（uint32）
  "utc": 1704067200,            # UTC 时间戳（uint32）
  "pps_utc": 95,               # 上次 UTC 的 PPS（uint32）
  "cputime_pps": 1234567000,   # 上次 PPS 的 CPU 时钟（uint64）
  "gps_long": 121473650,        # GPS 经度（int32）
  "gps_lat": 31230410,          # GPS 纬度（int32）
  "gps_alt": 50,               # GPS 海拔（int16）
  "acc_x": 10,                 # X 轴加速度（int8）
  "acc_y": 5,                  # Y 轴加速度（int8）
  "acc_z": 98,                 # Z 轴加速度（int8）
  "sipm_tmp": 250,             # SiPM 温度（uint16）
  "mcu_tmp": 35,               # MCU 温度（uint8）
  "sipm_imon": 100,            # SiPM 漏电流（uint16）
  "sipm_vmon": 2800            # SiPM 偏压（uint16）
}
```

### 字段命名映射

| App (Kotlin)   | 后端 (Python)   | 说明         |
| -------------- | --------------- | ------------ |
| cpuTime        | cpu_time        | 驼峰转蛇形   |
| packageCounter | package_counter | -            |
| SiPMTmp        | sipm_tmp        | 大写缩写处理 |
| MCUTmp         | mcu_tmp         | -            |
| ppsUtc         | pps_utc         | -            |
| cputimePps     | cputime_pps     | -            |
| gpsLong        | gps_long        | -            |
| gpsLat         | gps_lat         | -            |

## 错误处理

### 401 Unauthorized

认证失败或 Token 过期。

```json
{
  "detail": "Authentication credentials were not provided."
}
```

### 403 Forbidden

权限不足（尝试访问其他用户的设备）。

```json
{
  "detail": "You do not have permission to perform this action."
}
```

### 404 Not Found

资源不存在（设备 ID 无效）。

```json
{
  "detail": "Not found."
}
```

### 422 Validation Error

请求数据格式错误。

```json
{
  "detail": [
    {
      "loc": ["body", "mac_address"],
      "msg": "Invalid MAC address format",
      "type": "value_error"
    }
  ]
}
```

## 健康检查

```bash
GET /api/health
```

响应：

```json
{
  "status": "healthy",
  "service": "cosray-backend"
}
```

## 交互式文档

启动服务后访问：

- Swagger UI：http://localhost:8000/api/docs
- ReDoc：http://localhost:8000/api/redoc
