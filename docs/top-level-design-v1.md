# CosRay 顶层设计文档（V1）

## 1. 文档范围

本文档定义 CosRay 系统 V1 的顶层设计，覆盖：

- 系统分层与组件边界
- 核心运行时流程
- 数据与接口设计
- 安全、可观测性与可靠性设计
- 约束与变更控制

本文档不包含开发排期、里程碑和资源计划。

## 2. 设计输入与约束

### 2.1 输入文档

- 需求基线：[docs/requirements-v1.md](requirements-v1.md)
- 硬件协议真值：
  - [../../CosRay-Detector-Firmware/main/typedefs.h](../../CosRay-Detector-Firmware/main/typedefs.h)

### 2.2 顶层约束

- 真值优先级：硬件协议 > 后端契约 > App 实现。
- 后端是系统对外唯一业务契约出口。
- App 采用“薄客户端”策略：最小业务逻辑、最小协议再定义。
- 鉴权统一为 JWT Bearer。
- 生产主链路必须基于硬件二进制协议（非 JSON 调试流）。

## 3. 架构目标与质量属性

### 3.1 架构目标

- 构建稳定的端到端数据链路（采集、上报、落库）。
- 降低三端契约漂移风险，保障协议一致性。
- 保障设备与用户隔离，避免越权写入。
- 在最小代码量前提下提供可验证、可观测、可维护架构。

### 3.2 关键质量属性

- 一致性：字段命名、语义、类型在三端保持一致。
- 安全性：JWT 鉴权 + owner 级设备隔离。
- 可靠性：失败可定位、可重试、可追踪。
- 可扩展性：新增 packet_type 或 metric 时可局部演进。

## 4. 系统上下文与边界

## 4.1 上下文关系

- Firmware（ESP32）：数据采集、组包、BLE 发送。
- App（Android）：BLE 接收、协议解析、HTTP 上传。
- Backend（Django + Ninja）：鉴权、校验、设备管理、入库。
- PostgreSQL：元数据（用户、设备）。
- IoTDB：时序事件数据。

## 4.2 边界定义

- Firmware 边界：只保证协议正确与稳定输出，不承担云端业务逻辑。
- App 边界：只做连接、解析、上传，不定义业务规则真值。
- Backend 边界：统一定义 API/错误码/数据落库规则。

## 5. 逻辑架构设计

## 5.1 分层视图

### L1：接入层

- BLE 接入（App）
- HTTP API（Backend）

### L2：应用层

- App：会话管理、上传编排
- Backend：设备管理服务、上传服务

### L3：领域与契约层

- 协议模型（Muon/Timeline）
- API Schema（请求/响应/错误）

### L4：基础设施层

- PostgreSQL（Django ORM）
- IoTDB（SessionPool）
- 日志与监控

## 5.2 组件视图（按仓库）

### Firmware 侧（参考，不在本仓库实现）

- 协议定义组件：包结构、字段、校验规则
- 采集与组包组件：Muon/Timeline 包生成
- BLE 发送组件：通知下发与状态上报

### Backend 侧（本仓库核心）

- API 路由组件：
  - 认证路由（token pair/refresh/verify）
  - 用户路由（users/me）
  - 设备路由（devices CRUD）
  - 上传路由（mu-packets）
- 校验组件：Schema 校验 + 设备归属校验
- 时序写入组件：按 packet_type 写 IoTDB
- 元数据组件：Detector 模型与 last_seen_at 更新

### App 侧（适配层）

- BLE 控制组件：Scanner Compat 扫描 + BleManager 连接/通知/写入
- 协议解析组件：二进制包组装（512B）与 DTO 映射
- 网络组件：JWT 鉴权、设备接口、上传接口
- 本地状态组件：token、上传结果、基础重试状态

## 6. 运行时设计

## 6.1 认证流程

1. App 调用 `POST /api/token/pair` 获取 access/refresh。
2. App 调用 `GET /api/users/me` 拉取当前用户信息。
3. App 后续请求带 `Authorization: Bearer <access>`。
4. access 失效时调用 `POST /api/token/refresh` 刷新。

## 6.2 设备注册与管理流程

1. App 提交 MAC 与设备名称到 `POST /api/devices/`。
2. Backend 校验 MAC 唯一性并绑定 owner。
3. 查询/更新/删除流程均按 owner + device_id 访问控制。

## 6.3 数据上传流程（主链路）

1. Firmware 发送 Muon/Timeline 二进制包。
2. App 将通知数据分片组装为完整 512B 包。
3. App 按协议解析成统一上传 DTO。
4. App 调用 `POST /api/mu-packets/` 上传（device=MAC）。
5. Backend 执行：
   - JWT 鉴权
   - 设备归属校验（MAC + owner）
   - packet_type 与包体一致性校验
   - 写入 IoTDB
   - 更新 Detector.last_seen_at
6. Backend 返回 `records_written` 与兼容响应字段。

## 6.4 异常流程（统一语义）

- 设备不存在或越权：`404 DEVICE_NOT_FOUND`
- 包体缺失/不匹配：`400 INVALID_PACKET`
- IoTDB 写入失败：`400 IOTDB_WRITE_ERROR`
- 认证失败：标准 JWT 失败语义（401）

## 7. 数据架构设计

## 7.1 关系数据模型（PostgreSQL）

### Detector（核心）

- `mac_address`：唯一约束，设备语义主键
- `owner`：用户关联
- `name` / `description`
- `is_active`
- `last_seen_at`
- `created_at` / `updated_at`

设计原则：

- 业务查找优先 `owner + mac_address`。
- App 展示可用 `device_id`，但上传语义必须使用 MAC。

## 7.2 时序数据模型（IoTDB）

### 路径规范

- `root.cosray.<mac_sanitized>.<packet_type>.<metric>`

### 写入规则

- Muon：逐事件写 `cpu_time/energy/pps`
- Timeline：逐事件写全部 15 个指标
- 时间戳来源：优先事件 `timestamp`，否则使用服务端当前毫秒时间

## 7.3 字段命名规范

- API 对外仅使用 snake_case。
- Timeline 字段仅接受：
  - `sipm_tmp`
  - `mcu_tmp`
  - `sipm_imon`
  - `sipm_vmon`

## 8. 接口设计

## 8.1 对外 API 集

### 认证

- `POST /api/token/pair`
- `POST /api/token/refresh`
- `POST /api/token/verify`
- `GET /api/users/me`

### 设备

- `GET /api/devices/`
- `POST /api/devices/`
- `GET /api/devices/{device_id}/`
- `PATCH /api/devices/{device_id}/`
- `DELETE /api/devices/{device_id}/`

### 上传

- `POST /api/mu-packets/`

## 8.2 错误响应约束

统一错误结构：

- `detail`：人类可读描述
- `code`：机器可判定错误码

## 8.3 兼容策略（V1）

上传成功响应同时返回：

- `device_name`（兼容历史 App 读取）
- `message`（用户可读反馈）

说明：兼容字段属于 V1 过渡契约，不改变核心业务语义。

## 9. 安全架构设计

## 9.1 认证与授权

- 所有受保护接口必须通过 JWT。
- 设备相关接口必须执行 owner 隔离。
- 禁止匿名写入时序数据。

## 9.2 输入与校验

- 所有请求体必须通过 Schema 校验后进入业务逻辑。
- `packet_type` 与包体组合关系必须强约束。

## 9.3 敏感信息保护

- 日志不得记录 token、密码。
- 错误响应不暴露内部栈追踪。

## 10. 可靠性与容错设计

## 10.1 后端容错

- IoTDB 使用 SessionPool 单例连接池。
- 写入异常转化为标准业务错误码。
- API 保证幂等边界：
  - 设备创建按 MAC 唯一约束阻止重复。

## 10.2 App 容错（约束）

- 上传失败可重试，但不得改变上传契约字段。
- 认证过期需先刷新再重放请求。

## 10.3 Firmware 容错（对接要求）

- 需暴露丢包、发送失败等状态统计用于联调。

## 11. 可观测性设计

## 11.1 日志维度

后端日志必须可按以下维度检索：

- 用户
- 设备 MAC
- packet_type
- records_written
- error_code

## 11.2 指标建议

- 上传请求总量、成功率、失败率
- IoTDB 写入时延与失败次数
- 按 packet_type 的数据量分布

## 11.3 跟踪建议

- 单次上传请求建议生成请求级关联标识（request_id），便于跨层排障。

## 12. 一致性治理设计

## 12.1 契约变更规则

- 先更新需求文档与字段字典，再变更后端 schema。
- App DTO 变更必须以后端 schema 合并结果为准。
- 硬件协议变更必须同步触发后端与 App 契约评审。

## 12.2 评审检查清单

每次涉及协议/API 的变更，必须检查：

1. 硬件字段是否变化
2. 后端 schema 是否同步
3. App DTO 是否同步
4. 错误码是否保持一致
5. 验收样包是否更新

## 13. 扩展点设计（不改变 V1 边界）

- 新 packet_type 扩展：
  - 在 schema 增加联合类型
  - 在服务层增加对应写入策略
- 指标扩展：
  - 新增 IoTDB metric，不破坏现有路径前缀
- 上传模式扩展：
  - 单包上传 -> 批量上传（未来）

## 14. 架构决策记录（ADR 摘要）

- ADR-001：后端作为唯一外部契约源。
- ADR-002：鉴权统一 JWT Bearer，弃用 Session Token。
- ADR-003：上传语义以 MAC 作为设备标识。
- ADR-004：IoTDB 连接统一 SessionPool。
- ADR-005：App 采用薄客户端策略，减少业务规则下沉。

## 15. 验证与验收映射

需求文档中的 FR 映射到设计验证点：

- FR-01 -> 认证流程设计（第 6.1 节）
- FR-02 -> 设备管理流程设计（第 6.2 节）
- FR-03/04/05 -> 上传主链路（第 6.3 节）
- FR-06 -> 异常流程与错误模型（第 6.4 / 8.2 节）

## 16. 结论

V1 顶层设计采用“硬件协议驱动、后端契约收敛、App 最小化适配”的架构路线。该路线可以在最小实现复杂度下建立稳定一致的数据主链路，并为后续扩展留出清晰演进接口。