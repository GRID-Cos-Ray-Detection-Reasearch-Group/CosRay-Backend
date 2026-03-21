# 部署到 GitHub Pages

## 目标

文档站点默认部署到 GitHub Pages，而不是挂载到 Django 生产容器中。

这样做的原因如下：

- VitePress 输出是纯静态资源，适合独立发布
- 不增加后端生产容器复杂度
- 文档发布可与后端部署解耦

## 当前方案

仓库中提供独立 GitHub Actions workflow，用于完成以下步骤：

1. 安装 Node.js 与 pnpm
2. 在 `docs/` 下执行 `pnpm install --frozen-lockfile`
3. 执行 `pnpm build`
4. 发布 `docs/.vitepress/dist` 到 GitHub Pages

## 站点配置要求

由于以仓库 Pages 形式部署，VitePress 需要设置：

```ts
base: "/CosRay-Backend/";
```

如果未来改为自定义域名或组织级 Pages，需要同步调整 `base` 配置。

## 启用步骤

1. 在 GitHub 仓库设置中启用 Pages
2. Source 选择 GitHub Actions
3. 确认默认分支上的 workflow 拥有 `pages` 与 `id-token` 权限

## 何时发布

当前 workflow 会在以下情况触发：

- `docs/**` 变化
- `.github/workflows/docs-pages.yml` 变化
- `README.md` 变化

## 本地验证

发布前建议先在本地执行：

```bash
cd docs
pnpm install --frozen-lockfile
pnpm build
```

## 备选方案

如果未来必须与后端共域部署，可再评估：

- 独立静态容器
- 挂载到现有反向代理

这两种方式都比 GitHub Pages 更重，因此不作为当前默认路径。
