# 架构说明

## 系统概述

CosRay-Backend 是一个宇宙射线探测系统的后端服务，负责接收、存储和管理探测器数据。系统采用读写分离架构，PostgreSQL 存储元数据，Apache IoTDB 存储时序数据。

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                    CosRay-App (Android)                │
│                    (数据采集与上传)                    │
└────────────────────┬────────────────────────────────────┘
                     │ HTTP API
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                  CosRay-Backend (Django)              │
│                                                      │
│  ┌──────────────┐  ┌──────────────┐              │
│  │  API Layer   │  │ Auth Service │              │
│  │ (Django Ninja)│  │   (JWT)      │              │
│  └──────┬───────┘  └──────┬───────┘              │
│         │                 │                         │
│         └────────┬────────┘                         │
│                  │                                   │
│  ┌───────────────┼──────────────────┐              │
│  │               │                  │              │
│  ▼               ▼                  ▼              │
│ ┌──────────┐  ┌──────────┐  ┌─────────────┐  │
│ │ PostgreSQL│  │  IoTDB   │  │ Admin Panel │  │
│ │ (元数据)  │  │(时序数据) │  │  (Unfold)   │  │
│ └──────────┘  └──────────┘  └─────────────┘  │
│                 ▲                                   │
│                 │                                   │
│  ┌──────────────────────────────────────────────┐     │
│  │     ESP32 Detector (BLE → App)          │     │
│  │  (CosRay-Detector-Firmware)            │     │
│  └──────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

## 数据流向

### 1. 数据采集流程

```
ESP32 Detector
    ↓ BLE
CosRay-App (Android)
    ↓ HTTP API
CosRay-Backend
    ├─→ PostgreSQL (设备元数据、用户信息)
    └─→ IoTDB (时序测量数据)
```

### 2. 数据上传

1. **ESP32 → App**：探测器通过 BLE 发送 Muon/Timeline 数据包
2. **App → Backend**：App 解析数据包后通过 HTTP API 上传
3. **Backend → 数据库**：
   - 设备信息、用户数据写入 PostgreSQL
   - 时序数据写入 IoTDB

## 技术栈

### 后端框架

- **Django 6**：Web 框架
- **Django Ninja**：API 框架（类型安全、自动文档）
- **Django Unfold**：现代管理后台
- **django-jwt**：JWT 认证

### 数据库

- **PostgreSQL 17**：元数据存储
  - 设备信息
  - 用户信息
  - 权限关系

- **Apache IoTDB 2.0**：时序数据存储
  - Muon 数据：能量、PPS、CPU 时间
  - Timeline 数据：GPS、加速度、温度等

### 服务器

- **Uvicorn**：ASGI 服务器（开发环境）
- **Gunicorn**：WSGI 服务器（生产环境）
- **Nginx**：反向代理和静态文件服务

### 开发工具

- **uv**：快速包管理器
- **ruff**：代码格式化和 Lint
- **pytest**：测试框架

## 数据模型

### PostgreSQL 模型

#### Detector（探测器设备）

| 字段         | 类型           | 说明                 |
| ------------ | -------------- | -------------------- |
| mac_address  | CharField(17)  | MAC 地址（唯一标识） |
| name         | CharField(100) | 设备名称             |
| owner        | ForeignKey     | 设备所有者           |
| description  | TextField      | 描述信息             |
| is_active    | BooleanField   | 激活状态             |
| last_seen_at | DateTimeField  | 最后上报时间         |

### IoTDB 时序结构

#### Muon 数据路径

```
root.cosray.<MAC_SANITIZED>.muon.{cpu_time, energy, pps, timestamp}
```

#### Timeline 数据路径

```
root.cosray.<MAC_SANITIZED>.timeline.{cpu_time, pps, utc, gps_long, gps_lat, gps_alt, acc_x, acc_y, acc_z, sipm_tmp, mcu_tmp, sipm_imon, sipm_vmon}
```

**MAC 地址规范化**：将冒号替换为下划线（如 `AA:BB:CC` → `AA_BB_CC`）

## 性能优化

### IoTDB 连接池

使用 SessionPool 管理连接，避免频繁握手：

```python
from iotdb.SessionPool import SessionPool

pool = SessionPool(
    host=host,
    port=port,
    user=user,
    password=password,
    max_size=5
)
```

### 批量写入

使用 `insert_tablet` 批量写入数据，减少网络开销。

## 安全设计

### 认证

- JWT Bearer Token 认证
- Access Token 有效期：1 小时
- Refresh Token 有效期：7 天

### 权限

- 用户只能访问自己拥有的设备
- API 端点验证用户权限

### 数据保护

- PostgreSQL 连接使用 SSL（生产环境）
- 环境变量隔离敏感信息

## 部署架构

### 本地开发

- 单机部署
- 热重载支持
- 开发工具集成

### 生产环境

- Docker 容器化
- Gunicorn 多 Worker
- Nginx 反向代理
- 数据持久化

## 监控与日志

- 健康检查：`/api/health`
- 应用日志：标准输出
- 数据库日志：容器日志
- IoTDB 日志：容器日志

## 相关文档

- [API 文档](api.md) - API 端点详细说明
- [开发指南](development.md) - 本地开发环境设置
