# 性能测试

## 目标

性能测试文档聚焦后端上传主链路，而不是文档站点本身。

重点关注：

- `POST /api/mu-packets/` 在不同事件量下的吞吐和时延
- IoTDB 写入失败或延迟增加时的行为
- `Detector.last_seen_at` 更新是否影响主链路延迟

## 前置条件

- 本地或测试环境的 PostgreSQL、IoTDB 已启动
- 已创建测试用户和测试设备
- 后端服务可以正常访问

## 建议步骤

1. 准备一组合法 Muon 上传样本
2. 准备一组合合法 Timeline 上传样本
3. 记录单请求延迟、每秒请求量与失败率
4. 观察 IoTDB 与应用日志，确认是否出现连接池耗尽或写入异常

## 观察指标

- 请求成功率
- 平均与 P95 响应时间
- `IOTDB_WRITE_ERROR` 出现频率
- 按 `packet_type` 统计的 `records_written`

## 日志维度

建议按以下上下文检索日志：

- `request_id`
- `user_id`
- `mac_address`
- `packet_type`
- `error_code`
