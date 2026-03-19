# 数据包上传

## 上传入口

统一上传端点为：

```text
POST /api/mu-packets/
```

虽然路径名历史上使用 `mu-packets`，但实际同时承载 Muon 与 Timeline 两种上传类型。

## 请求结构

```json
{
  "device": "AA:BB:CC:DD:EE:FF",
  "packet_type": "muon",
  "muon_packet": {
    "package_counter": 123,
    "utc": 1735689600,
    "events": [
      {
        "cpu_time": 100,
        "energy": 42,
        "pps": 7,
        "timestamp": 1735689600000
      }
    ],
    "head": [170, 187, 204],
    "tail": [221, 238, 255],
    "crc": 1
  }
}
```

约束：

- `device` 必须是合法 MAC 地址
- `packet_type` 只能是 `muon` 或 `timeline`
- `packet_type=muon` 时必须提供 `muon_packet`
- `packet_type=timeline` 时必须提供 `timeline_packet`

## 上传处理流程

1. 标准化并校验 MAC 地址
2. 根据当前用户与 MAC 校验设备归属
3. 执行上传限流
4. 校验包体、包头包尾和事件数限制
5. 根据 `packet_type` 选择 IoTDB 写入函数
6. 更新 `Detector.last_seen_at`
7. 返回写入记录数与兼容字段

## 成功响应

```json
{
  "device": "AA:BB:CC:DD:EE:FF",
  "device_name": "实验室一号机",
  "packet_type": "muon",
  "records_written": 35,
  "message": "成功写入 35 条记录",
  "request_id": "<uuid-hex>"
}
```

`device_name` 与 `message` 属于兼容字段，当前仍保留在响应中。

## 常见错误码

- `INVALID_MAC`
- `DEVICE_NOT_FOUND`
- `INVALID_PACKET_TYPE`
- `MISSING_PAYLOAD`
- `MUON_EVENTS_OVER_LIMIT`
- `TIMELINE_EVENTS_OVER_LIMIT`
- `INVALID_MUON_HEAD`
- `INVALID_MUON_TAIL`
- `INVALID_TIMELINE_HEAD`
- `INVALID_TIMELINE_TAIL`
- `RATE_LIMIT_EXCEEDED`（HTTP 429）
- `IOTDB_WRITE_ERROR`

IoTDB 写入失败时返回 `IOTDB_WRITE_ERROR`，HTTP 状态码为 503。

## IoTDB 写入语义

### Muon

- 设备路径：`root.cosray.<MAC>.muon`
- 测点：`cpu_time`、`energy`、`pps`
- 时间戳：优先事件级 `timestamp`，否则使用包级 `utc * 1000`

示例：MAC `AA:BB:CC:DD:EE:FF` 在 IoTDB 中的写入路径为：

```
root.cosray.AA_BB_CC_DD_EE_FF.muon
```

该路径由 `core/services.py` 中的 `normalize_device_path()` 生成，行为为将 MAC 中的 `:` 替换为 `_` 并转为大写。

写入行为要点：

- 时间戳优先使用事件级 `timestamp`（毫秒）；若事件未提供则回退到包级 `utc * 1000`。
- 每条记录包含对应的测点顺序：`cpu_time`, `energy`, `pps`（详见 `core/services.ingest_muon_packet` 的 `measurements` 顺序）。

### Timeline

- 设备路径：`root.cosray.<MAC>.timeline`
- 测点包括 `cpu_time`、`pps`、`utc`、`gps_long`、`gps_lat`、`gps_alt`、`acc_*`、`sipm_*` 等
- 时间戳：优先事件级 `timestamp`，否则使用 `event.utc * 1000`
