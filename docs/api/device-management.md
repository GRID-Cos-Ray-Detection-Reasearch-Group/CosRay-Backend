# 设备管理

## 模型概览

`Detector` 是当前后端唯一的核心业务模型，承载设备元数据与用户归属关系。

关键字段：

- `mac_address`：设备业务唯一标识，格式必须为 `AA:BB:CC:DD:EE:FF`
- `owner`：设备所有者
- `name`：用户可读名称
- `description`：可选说明
- `is_active`：设备启用状态
- `last_seen_at`：最近一次成功上传时间

## 端点

### `GET /api/devices/`

- 返回当前用户拥有的全部设备
- 查询时只暴露 owner 自己的数据

### `POST /api/devices/`

- 创建设备并绑定到当前用户
- 创建前会先校验并标准化 MAC 地址
- 全局重复 MAC 会返回错误，不允许重复注册

示例请求：

```json
{
  "mac_address": "AA:BB:CC:DD:EE:FF",
  "name": "实验室一号机",
  "description": "固定在实验台上的主测量设备"
}
```

典型错误：

- `INVALID_MAC_ADDRESS`
- `DEVICE_REGISTRATION_UNAVAILABLE`

### `GET /api/devices/{device_id}/`

- 返回当前用户单个设备详情
- 未找到或越权会返回 404

### `PATCH /api/devices/{device_id}/`

- 支持部分更新：`name`、`description`、`is_active`

### `DELETE /api/devices/{device_id}/`

- 删除当前用户设备
- 成功返回 `204 No Content`

## 隔离规则

设备相关接口统一按用户隔离：

- 列表接口按 `owner=request.user` 查询
- 详情、更新、删除按 `device_id + owner` 定位
- 上传接口按 `mac_address + owner` 定位

这意味着 MAC 地址虽是业务语义主键，但任何设备操作都必须同时满足当前用户归属。

## 后台管理

管理员界面基于 Django Unfold，自定义后台在 `core/admin.py` 中实现。后台同样需要遵循用户隔离和设备只读字段展示逻辑。

## Django 后台注意事项

- 后台实现位于 `core/admin.py`，使用 `unfold.admin.ModelAdmin` 定制了设备列表、筛选与只读字段。
- 非超级用户在后台只能查看和管理属于自己的设备（`get_queryset` 与权限方法会按 `owner` 过滤）。
- 保存时：普通用户创建/修改设备会自动绑定 `owner` 为当前用户（`save_model` 中覆盖行为），管理员可指定任意 `owner`。

提示：确保 `unfold` 在 `INSTALLED_APPS` 中位于 `django.contrib.admin` 之前（见 `config/settings.py`），否则 Unfold 的自定义界面可能无法生效。
