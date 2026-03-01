# 后端压测与资源开销测量

本文档用于执行后端压力测试，并记录：

- 每个容器的内存开销
- PostgreSQL 与 IoTDB 的磁盘增量
- 按 event（`records_written`）归一化后的每条数据硬盘开销

## 1. 前置条件

1. 启动生产编排容器（推荐作为性能基线）
2. 已创建可登录用户（JWT）
3. 后端 API 可通过 Nginx 访问（默认 `http://localhost:8080/api`）

## 2. 脚本位置

- 执行脚本：`scripts/perf/run_pressure_test.py`

## 3. 标准基线命令

```bash
uv run python scripts/perf/run_pressure_test.py \
  --base-url http://localhost:8080/api \
  --username <用户名> \
  --password <密码> \
  --device-mac AA:BB:CC:DD:EE:FF \
  --timeline-ratio 0.2 \
  --stages 100:600,300:600,500:600 \
  --output reports/perf/report.json
```

## 4. 输出说明

报告为 JSON，默认输出到 `reports/perf/report.json`，包含：

- `summary`：总请求数、总错误数、总写入 event 数、整体 RPS
- `stages`：分阶段并发下的吞吐、错误率、P50/P95/P99
- `container_memory.summary`：每个容器的平均、P95、峰值内存
- `postgresql.per_event_bytes`：PostgreSQL 每 event 字节成本（多口径）
- `iotdb.per_event_bytes.data_dir_approx`：IoTDB 每 event 近似字节成本

## 5. 关键参数

- `--stages`：并发与持续时间，格式 `并发:秒,并发:秒`
- `--timeline-ratio`：timeline 包占比，muon 比例为 `1 - timeline_ratio`
- `--containers`：容器采样列表（逗号分隔）
- `--postgres-container` / `--iotdb-container`：数据库容器名
- `--sample-interval`：内存采样间隔（秒）

## 6. 口径说明

1. 每条数据按 event 计数（来源为接口响应 `records_written`）。
2. PostgreSQL 提供多口径：
   - 数据目录增量（`du -sb`）
   - `pg_database_size` 增量
   - `core_detector` 表总关系大小增量
3. IoTDB 默认使用数据目录差分近似值：`(测试后 - 测试前) / event 数`。
4. IoTDB 单条精确字节值受压缩与 compaction 影响，难以稳定精确测量，报告会保留该说明。

## 7. 建议执行流程

1. 清理历史数据或记录初始快照
2. 运行脚本完成 30 分钟标准基线
3. 固定同一环境重复 3 轮，比较方差
4. 基于 JSON 报告生成趋势图（吞吐、内存、每 event 成本）
