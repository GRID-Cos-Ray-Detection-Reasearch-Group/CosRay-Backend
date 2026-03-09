# 快速开始

本文档面向两类维护者：

- 后端开发者：需要理解 API、模型、上传行为与运维约束。
- 跨端联调人员：需要确认 Firmware、App、Backend 三端协议是否一致。

## 工作区关系

当前工作区包含四个直接相关仓库：

- `CosRay-Backend`：Django Ninja 后端与本 VitePress 文档站点
- `CosRay-App`：Android 客户端，负责 BLE 解析与 HTTP 上传
- `CosRay-Detector-Firmware`：ESP32 固件，负责采集、组包与 BLE 发送
- `CosRay-Backend-Archive`：旧后端归档，仅用于避坑参考，不作为实现来源

## 启动后端

```bash
uv sync
cp .env.example .env
docker compose -f docker-compose.local.yml up -d
uv run python manage.py migrate
uv run python manage.py runserver
```

启动后可访问：

- 后端 API 文档：`http://localhost:8000/api/docs`
- 管理后台：`http://localhost:8000/admin`

## 启动文档站点

```bash
cd docs
pnpm install --frozen-lockfile
pnpm dev
```

默认开发地址为 `http://localhost:5173`。

## 推荐阅读顺序

1. [架构总览](/architecture)
2. [认证与用户](/api/authentication)
3. [设备管理](/api/device-management)
4. [数据包上传](/api/packet-upload)
5. [协议与字段映射](/integration/protocol-contracts)
6. [部署到 GitHub Pages](/ops/deployment)

## 文档真值来源

当前站点按照以下优先级维护：

1. Backend 当前实现与测试
2. Firmware 协议结构体与 App DTO
3. 设计性说明与运维文档

当三者不一致时，应先修正实现或契约，再修正文档页面，不再回到旧的大型规划文档。
