# CosRay 系统需求文档（V1）

## 1. 文档目的

本文档用于统一 CosRay 三端（Firmware / Backend / App）需求口径，明确系统边界、数据契约、功能要求与验收标准。

本文档**不包含开发排期、迭代时间点与人力分配**。

## 2. 优先级与真值来源

### 2.1 优先级顺序

1. 硬件协议（第一真值）
2. 后端契约（系统对外真值）
3. App 实现（按后端契约最小化适配）

### 2.2 真值锚点（必须遵循）

- 硬件包结构与字段语义：
  - [CosRay-Detector-Firmware/main/typedefs.h](../CosRay-Detector-Firmware/main/typedefs.h)
- 后端 API 与鉴权：
  - [CosRay-Backend/core/api.py](../CosRay-Backend/core/api.py)
  - [CosRay-Backend/config/urls.py](../CosRay-Backend/config/urls.py)
- 后端 Schema：
  - [CosRay-Backend/core/schemas.py](../CosRay-Backend/core/schemas.py)
- 后端时序写入规则：
  - [CosRay-Backend/core/services.py](../CosRay-Backend/core/services.py)
- App 网络与 DTO：
  - [CosRay-App/app/src/main/java/com/grid/cosrayapp/core/network/CosRayApi.kt](../CosRay-App/app/src/main/java/com/grid/cosrayapp/core/network/CosRayApi.kt)
  - [CosRay-App/app/src/main/java/com/grid/cosrayapp/core/network/model/DevicePacketDtos.kt](../CosRay-App/app/src/main/java/com/grid/cosrayapp/core/network/model/DevicePacketDtos.kt)

## 3. 系统目标与非目标

### 3.1 系统目标

- 建立稳定的端到端链路：设备产包 -> App 解析 -> 后端校验 -> IoTDB 写入。
- 统一数据契约：Muon 与 Timeline 包在三端字段语义一致。
- 建立设备归属安全模型：上传时必须校验设备属于当前 JWT 用户。
- 保证后端为对外唯一契约出口，避免 App 与硬件直接形成第二套业务真值。

### 3.2 非目标

- 不定义 UI/视觉改版需求。
- 不定义复杂离线分析、回放、报表系统。
- 不引入多套认证并行（例如 session token 与 JWT 并行长期共存）。

## 4. 术语定义

- Detector：设备实体（后端业务模型）。
- MAC：设备网络地址，V1 作为设备业务唯一标识语义。
- Muon Packet：35 事件粒子包。
- Timeline Packet：10 事件状态包。
- records_written：后端成功写入 IoTDB 的记录条数。

## 5. 角色与职责

### 5.1 硬件端（非本项目开发责任）

- 按协议组包并发送 BLE 数据。
- 保证包结构、字节序、校验正确。
- 输出错误状态（例如发送失败、缓存溢出）。

### 5.2 后端端（本项目核心责任）

- 鉴权与用户隔离。
- 设备管理（注册、查询、更新、删除）。
- 上传校验、设备归属校验、IoTDB 写入。
- 对外提供统一错误码与可观测日志。

### 5.3 App 端（最小化适配责任）

- 连接 BLE 并按协议解析。
- 调用后端 API 上传数据。
- 管理 JWT 与最小错误提示。

## 6. 系统边界与约束

- 认证只允许 Bearer Token：`Authorization: Bearer <token>`。
- App 不得自行定义与后端冲突的字段名、状态码语义。
- 后端不得绕过设备归属校验直接写入时序库。
- 生产主链路以二进制协议为准，不以 JSON 调试格式作为上传真值。

## 7. 功能需求（FR）

### FR-01 鉴权

- 系统必须支持 JWT 登录、刷新、校验。
- 登录成功后 App 必须可获取当前用户信息。
- 认证端点以以下为准：
  - `POST /api/token/pair`
  - `POST /api/token/refresh`
  - `POST /api/token/verify`
  - `GET /api/users/me`

### FR-02 设备管理

- 系统必须支持设备 CRUD：
  - `GET /api/devices/`
  - `POST /api/devices/`
  - `GET /api/devices/{device_id}/`
  - `PATCH /api/devices/{device_id}/`
  - `DELETE /api/devices/{device_id}/`
- 设备注册必须包含 `mac_address`、`name`，`description` 可选。
- 响应字段统一采用 `owner_id`。

### FR-03 数据包上传

- 系统必须支持统一上传端点：`POST /api/mu-packets/`。
- `packet_type` 只允许 `muon` 或 `timeline`。
- 当 `packet_type=muon` 时必须提供 `muon_packet`。
- 当 `packet_type=timeline` 时必须提供 `timeline_packet`。
- 上传 `device` 字段必须为 MAC 地址。

### FR-04 设备归属校验

- 后端必须按 `device MAC + 当前用户` 查询设备。
- 未找到设备或非归属设备必须返回 `404 DEVICE_NOT_FOUND`。

### FR-05 写入与状态更新

- 后端写入成功后必须更新 Detector 的 `last_seen_at`。
- 上传响应必须返回：
  - `device`
  - `packet_type`
  - `records_written`
  - `device_name`（过渡兼容）
  - `message`（过渡兼容）

### FR-06 错误处理

- 包体缺失或类型不匹配返回 `400 INVALID_PACKET`。
- IoTDB 写入异常返回 `400 IOTDB_WRITE_ERROR`。
- 错误响应统一结构：`detail` + `code`。

## 8. 数据契约需求

## 8.1 Muon 事件字段

- `cpu_time`：整型，设备 CPU 时间。
- `energy`：整型，能量 ADC 值。
- `pps`：整型，PPS 计数。
- `timestamp`：可选，毫秒级时间戳。

## 8.2 Timeline 事件字段

- `cpu_time`
- `pps`
- `utc`
- `pps_utc`
- `cputime_pps`
- `gps_long`
- `gps_lat`
- `gps_alt`
- `acc_x`
- `acc_y`
- `acc_z`
- `sipm_tmp`
- `mcu_tmp`
- `sipm_imon`
- `sipm_vmon`
- `timestamp`（可选）

> 命名口径：Timeline 仅接受下划线命名，不接受驼峰或历史大小写别名。

## 8.3 包级字段

- Muon 包：`package_counter`、`utc`、`events`、`head`、`tail`、`crc`
- Timeline 包：`package_counter`、`events`、`head`、`tail`、`crc`
- V1 上传契约不要求 `reserved` 字段。

## 9. 存储与路径需求

### 9.1 关系型数据（PostgreSQL）

- Detector 必须包含：
  - `mac_address`（唯一）
  - `owner`
  - `name`
  - `description`
  - `is_active`
  - `last_seen_at`

### 9.2 时序数据（IoTDB）

- 路径必须符合：`root.cosray.<mac_sanitized>.<packet_type>.<metric>`。
- 后端必须使用连接池（SessionPool），禁止频繁新建连接。

## 10. 安全与合规需求

- 所有受保护 API 必须要求 JWT。
- 所有设备操作必须按 owner 隔离。
- 日志中不得输出 token、密码等敏感信息。
- 输入必须经过 schema 校验后进入业务逻辑。

## 11. 可观测性需求

- 后端必须记录：
  - 上传成功条数（按设备、包型）
  - 错误码分布
  - IoTDB 写入失败日志
- App 至少记录：
  - 上传成功/失败次数
  - 鉴权失败与刷新次数
- 硬件侧（由硬件团队负责）应可导出：
  - 丢包统计
  - 发送失败统计

## 12. 一致性约束（防止再次混乱）

- 任一字段名变更必须先改后端 schema，再同步 App DTO。
- 任一协议语义变更必须以硬件协议文档为源头，并更新后端需求文档。
- PR 评审时必须检查“硬件协议 -> 后端 schema -> App DTO”三点一致。

## 13. 验收标准（无排期）

### 13.1 功能验收

- 使用有效 JWT 可以完成：登录后查询当前用户、设备注册、设备查询、数据上传。
- 使用非归属设备 MAC 上传会被拒绝并返回标准错误码。
- Muon 与 Timeline 上传均可成功写入并返回正确 `records_written`。

### 13.2 契约验收

- App 发送字段名与后端 schema 完全一致。
- 后端响应字段满足 V1 兼容要求（含 `device_name` 与 `message`）。

### 13.3 稳定性验收

- 后端在正常负载下无明显连接泄露。
- 错误场景下可通过日志定位到设备、包型、错误码。

## 14. 变更控制

- 本文档为 V1 基线文档。
- 任何契约变更必须先更新本文档，再更新代码实现。
- 若硬件协议变更，与其冲突的后端/App 行为必须以硬件协议更新为准同步收敛。
