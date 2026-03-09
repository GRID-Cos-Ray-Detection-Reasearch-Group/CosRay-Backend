---
layout: home

hero:
  name: "CosRay-Backend 文档站"
  text: "后端实现、跨端协议与部署维护统一入口"
  tagline: "以 Backend 为主仓，收敛 App 与 Firmware 的接口契约，支持 GitHub Pages 持续发布。"
  actions:
    - theme: brand
      text: 快速开始
      link: /getting-started
    - theme: alt
      text: 查看 API
      link: /api/authentication

features:
  - title: 后端契约
    details: 认证、设备管理、数据包上传以当前 Django Ninja 实现为准，文档按主题拆分，避免单个大文档失控。
  - title: 跨端对接
    details: 提炼 App DTO、Firmware 协议结构与联调约束，只在站内保留摘要，源实现继续归属各自仓库。
  - title: 可部署维护
    details: 文档站点构建与发布流程独立，默认部署到 GitHub Pages，不依赖后端生产容器。
---

## 文档范围

本站覆盖三类内容：

- CosRay-Backend 当前实现与接口行为
- CosRay-App 与 CosRay-Detector-Firmware 的对接契约摘要
- 文档站点自身的部署、发布与维护规则

## 站点结构

- [快速开始](/getting-started)：本地启动后端与文档站点
- [架构总览](/architecture)：系统边界、数据流和真值来源
- [认证与用户](/api/authentication)：JWT、注册、刷新、当前用户
- [设备管理](/api/device-management)：Detector 模型、CRUD、隔离规则
- [数据包上传](/api/packet-upload)：上传约束、错误码、IoTDB 写入语义
- [协议与字段映射](/integration/protocol-contracts)：Firmware、App、Backend 三端对齐说明

- 额外端点：`/health`（健康检查）与 `token/verify`（Ninja-JWT 内置）。
- [部署到 GitHub Pages](/ops/deployment)：文档站点的构建与发布路径

## 维护原则

1. 后端运行行为以 core 下实现和测试为准。
2. 跨端字段和协议以 Firmware 结构体与 App DTO 为源头约束。
3. 文档只保留当前有效内容，历史规划与模板页不再作为长期入口。
