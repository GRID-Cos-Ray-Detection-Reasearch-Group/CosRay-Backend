# 架构总览

## 系统边界

CosRay 采集链路采用三端分工：

- Firmware：采集数据、按固定二进制协议组包、通过 BLE 发送
- App：接收 BLE 分片、拼接 512B 包、解析为 DTO 并调用 HTTP API
- Backend：统一承接鉴权、设备归属校验、IoTDB 写入和元数据管理

## 数据流

```text
ESP32 Firmware -> Android App -> Django Backend -> PostgreSQL + IoTDB
```

### Firmware

- 定义 Muon 与 Timeline 包结构
- 维护 BLE 特征与分片发送逻辑
- 不承担云端业务规则和用户隔离

### App

- 负责 BLE 连接、分片重组、DTO 映射
- 管理 JWT 登录态与上传请求
- 不应重新定义后端业务真值

### Backend

- 统一对外契约出口
- 定义 JWT、设备 CRUD、数据包上传行为
- 按用户隔离设备，并将事件写入 IoTDB

## 真值来源

### 后端行为真值

- `core/api.py`
- `core/models.py`
- `core/schemas.py`
- `core/services.py`
- `core/validators.py`

### 跨端契约真值

- Firmware：`CosRay-Detector-Firmware/main/typedefs.h`
- App DTO：`CosRay-App/app/src/main/java/com/grid/cosrayapp/core/network/model/DevicePacketDtos.kt`
- App 协议映射：`CosRay-App/app/src/main/java/com/grid/cosrayapp/data/telemetry/FirmwarePacketMapper.kt`

## 后端模块

### API 层

- 认证：注册、登录、刷新、校验、当前用户
- 设备：列表、创建、详情、更新、删除
- 上传：统一入口 `POST /api/mu-packets/`

### 领域与契约层

- `Detector` 作为关系型元数据实体
- Pydantic Schema 统一请求/响应结构
- 错误码对外保持稳定语义

### 基础设施层

- PostgreSQL：用户与设备元数据
- IoTDB：Muon / Timeline 时序数据
- Redis 或本地缓存：限流与 refresh token 撤销控制

## 文档治理原则

1. 不再保留“需求文档 / 设计文档 / 计划文档”并列作为主入口。
2. 文档按维护任务拆分，围绕接口、协议、部署和运维组织。
3. App 与 Firmware 只在站内保留必要摘要，完整实现保持在各自仓库。

## 服务组件

- **Django ASGI 应用** 通过 `uvicorn` 托管，单体模块按照 Django App 模式划分。
- **数据库**
  - PostgreSQL：使用官方镜像，`cosray` 数据库承载用户/设备表。
  - IoTDB：时序数据，单实例部署，必须通过 `SessionPool` 复用连接。
- **缓存/队列**
  - Redis（可选）：用于限流计数、refresh token 黑名单，以及未来的异步任务。
- **外部依赖**
  - 邮件服务（SMTP）用于账户验证与通知。
  - Sentry/Prometheus/Grafana 针对日志与指标。

## 部署架构

本项目使用 `docker-compose` 统一本地和生产部署模式：

1. `docker-compose.local.yml` 展示开发环境，包含后端服务、PostgreSQL、IoTDB，
   所有配置来自 `.env`。
2. `docker-compose.production.yml` 在 CI/CD 中由 `./scripts/deploy.sh` 调用，
   通过 Kubernetes 或云 VM 运行，敏感变量通过 Vault/Secrets 管理。

生产中的典型拓扑：

```text
Ingress → HPA Nginx → Gunicorn/uvicorn → Django
           │
           ├── PostgreSQL 主从 读写分离
           └── IoTDB 集群 (后续规划)
```

- **证书与 TLS**：前端负载均衡层负责 HTTPS 终端，加密内部流量。
- **备份**：每日 PostgreSQL dump 与 IoTDB snapshot，存储至对象存储。

## 扩展性与演进

- **多区域部署**: API 与 IoTDB 支持跨区写入，后端仓库里 `services.iotdb` 已预留 region 参数。
- **插件机制**: `core/services.py` 使用策略模式，未来可添加新的时序存储或解析器。
- **版本控制**: 所有对外契约（API path、错误码、Schema）均在 `core/schemas.py` 明确声明，并
  在 `docs/api.md` 通过生成脚本维持同步。

---

请在新增内容后继续保持架构文档简洁、易读。如需迁移到其他格式（PlantUML、Mermaid），
可在 docs/architecture-diagrams 下创建相应文件并在此处引用。
