# 协议与字段映射

## 目的

本页只保留跨端联调必须理解的契约，不复制 App 或 Firmware 的完整实现细节。

## 三端角色

- Firmware：定义二进制结构体和 BLE 分片格式
- App：将二进制包还原为 DTO，并调用 Backend 上传
- Backend：验证 DTO、归属设备并写入 IoTDB

## Firmware 结构体来源

协议真值来源：

- `https://github.com/GRID-Cos-Ray-Detection-Reasearch-Group/CosRay-Detector-Firmware/blob/main/main/typedefs.h`
- `https://github.com/GRID-Cos-Ray-Detection-Reasearch-Group/CosRay-Detector-Firmware/blob/main/BSP/bleprph.c`

### Muon 包摘要

- 固定长度：512B
- 包头：`AA BB CC`
- 包尾：`DD EE FF`
- 事件数上限：35
- 关键字段：`cpu_time`、`energy`、`pps`

### Timeline 包摘要

- 固定长度：512B
- 包头：`12 34 56`
- 包尾：`78 9A BC`
- 事件数上限：10
- 关键字段：`cpu_time`、`pps`、`utc`、`gps_*`、`acc_*`、`sipm_*`

## App DTO 与上传来源

App 侧关键来源：

- `https://github.com/GRID-Cos-Ray-Detection-Reasearch-Group/CosRay-App/blob/dev/app/src/main/java/com/grid/cosrayapp/domain/model/Protocol.kt`
- `https://github.com/GRID-Cos-Ray-Detection-Reasearch-Group/CosRay-App/blob/dev/app/src/main/java/com/grid/cosrayapp/core/network/model/DevicePacketDtos.kt`
- `https://github.com/GRID-Cos-Ray-Detection-Reasearch-Group/CosRay-App/blob/dev/app/src/main/java/com/grid/cosrayapp/data/telemetry/FirmwarePacketMapper.kt`
- `https://github.com/GRID-Cos-Ray-Detection-Reasearch-Group/CosRay-App/blob/dev/docs/firmware-link-validation.md`

### App 到 Backend 的职责转换

1. BLE 收到 22B 左右的分片
2. 在 App 侧重组为完整 512B 包
3. 按协议映射为 JSON DTO
4. 调用 `POST /api/mu-packets/`

## 字段映射

### 命名规则

- Backend 对外统一使用 snake_case
- App 若内部使用其他命名，应在 DTO 层完成映射，不向 Backend 暴露驼峰字段

### 典型映射

| 固件语义     | App/历史命名     | Backend 字段      |
| ------------ | ---------------- | ----------------- |
| `PkgCnt`     | `packageCounter` | `package_counter` |
| `cpuTime`    | `cpuTime`        | `cpu_time`        |
| `ppsUtc`     | `ppsUtc`         | `pps_utc`         |
| `cputimePps` | `cputimePps`     | `cputime_pps`     |
| `SiPMTmp`    | `siPMTmp`        | `sipm_tmp`        |
| `MCUTmp`     | `mcuTmp`         | `mcu_tmp`         |
| `SiPMImon`   | `siPMImon`       | `sipm_imon`       |
| `SiPMVmon`   | `siPMVmon`       | `sipm_vmon`       |

## 不应复制到本站的内容

以下内容只应在本站引用源仓库，不应复制实现：

- Android 网络层和协程实现细节
- Firmware 的 FreeRTOS 调度与驱动逻辑
- BLE 连接生命周期与 GATT 回调细节

## 联调建议

1. 先确认 Firmware 结构体和包头包尾未变化。
2. 再确认 App DTO 字段名是否仍与 Backend Schema 一致。
3. 最后用真实设备或样本请求验证 `records_written` 与事件数是否一致。

联调验收步骤应以 App 仓库中的 `firmware-link-validation.md` 为源头。
