import { defineConfig } from "vitepress";

export default defineConfig({
  lang: "zh-CN",
  title: "CosRay-Backend",
  description: "CosRay 后端、跨端协议与部署维护文档",
  base: "/CosRay-Backend/",
  lastUpdated: true,
  themeConfig: {
    nav: [
      { text: "概览", link: "/" },
      { text: "快速开始", link: "/getting-started" },
      { text: "API", link: "/api/authentication" },
      { text: "协议对接", link: "/integration/protocol-contracts" },
      { text: "部署运维", link: "/ops/deployment" },
    ],
    sidebar: [
      {
        text: "开始使用",
        items: [
          { text: "项目概览", link: "/" },
          { text: "快速开始", link: "/getting-started" },
          { text: "架构总览", link: "/architecture" },
        ],
      },
      {
        text: "后端 API",
        items: [
          { text: "认证与用户", link: "/api/authentication" },
          { text: "设备管理", link: "/api/device-management" },
          { text: "数据包上传", link: "/api/packet-upload" },
        ],
      },
      {
        text: "跨端契约",
        items: [
          { text: "协议与字段映射", link: "/integration/protocol-contracts" },
        ],
      },
      {
        text: "运维",
        items: [{ text: "部署到 GitHub Pages", link: "/ops/deployment" }],
      },
    ],
    socialLinks: [
      {
        icon: "github",
        link: "https://github.com/GRID-Cos-Ray-Detection-Reasearch-Group/CosRay-Backend",
      },
    ],
    search: {
      provider: "local",
    },
    footer: {
      message: "文档站点基于 VitePress 构建，源代码与契约说明保存在仓库中。",
      copyright: "GRID CosRay Backend",
    },
  },
});
