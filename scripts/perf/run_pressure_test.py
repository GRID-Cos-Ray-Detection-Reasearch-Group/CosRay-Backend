from __future__ import annotations

import argparse
import json
import logging
import random
import shlex
import statistics
import subprocess
import threading
import time
from collections import Counter
from dataclasses import asdict
from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib import error
from urllib import request

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class StageConfig:
    concurrency: int
    duration_seconds: int


@dataclass(slots=True)
class StageResult:
    stage_name: str
    concurrency: int
    duration_seconds: int
    request_total: int
    request_success: int
    request_failed: int
    records_written: int
    request_rps: float
    records_rps: float
    error_rate: float
    latency_ms_avg: float
    latency_ms_p50: float
    latency_ms_p95: float
    latency_ms_p99: float
    status_code_counts: dict[str, int]


@dataclass(slots=True)
class PostgresSizeSnapshot:
    data_dir_bytes: int | None
    database_bytes: int | None
    core_detector_total_relation_bytes: int | None
    core_detector_table_bytes: int | None
    core_detector_index_bytes: int | None


@dataclass(slots=True)
class StageRuntimeConfig:
    mac_address: str
    timeline_ratio: float
    seed: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="后端压测与资源采样工具")
    parser.add_argument(
        "--base-url", default="http://localhost:8080/api", help="API 基础 URL, 例如 http://localhost:8080/api"
    )
    parser.add_argument("--username", required=True, help="压测用户用户名")
    parser.add_argument("--password", required=True, help="压测用户密码")
    parser.add_argument("--device-mac", default="AA:BB:CC:DD:EE:FF", help="压测设备 MAC 地址")
    parser.add_argument("--device-name", default="Perf Detector", help="压测设备名称")
    parser.add_argument("--timeline-ratio", type=float, default=0.2, help="timeline 请求占比, 0.0~1.0")
    parser.add_argument(
        "--stages",
        default="100:600,300:600,500:600",
        help="压测阶段定义, 格式为并发:秒, 多个阶段用逗号分隔, 如 100:600,300:600",
    )
    parser.add_argument("--request-timeout", type=float, default=10.0, help="单次请求超时秒数")
    parser.add_argument("--sample-interval", type=float, default=1.0, help="容器内存采样间隔秒")
    parser.add_argument("--seed", type=int, default=20260301, help="随机种子, 保证可复现")
    parser.add_argument("--skip-device-bootstrap", action="store_true", help="跳过设备预创建检查")
    parser.add_argument(
        "--containers",
        default=(
            "cosray_backend_production_django,"
            "cosray_backend_production_postgres,"
            "cosray_backend_production_iotdb,"
            "cosray_backend_production_nginx"
        ),
        help="需要采样内存的容器名, 逗号分隔",
    )
    parser.add_argument("--postgres-container", default="cosray_backend_production_postgres", help="PostgreSQL 容器名")
    parser.add_argument("--iotdb-container", default="cosray_backend_production_iotdb", help="IoTDB 容器名")
    parser.add_argument("--postgres-data-path", default="/var/lib/postgresql/data", help="PostgreSQL 数据目录")
    parser.add_argument("--iotdb-data-path", default="/iotdb/data", help="IoTDB 数据目录")
    parser.add_argument("--postgres-user", default="admin", help="PostgreSQL 用户名")
    parser.add_argument("--postgres-db", default="cosray", help="PostgreSQL 数据库名")
    parser.add_argument("--output", default="reports/perf/report.json", help="压测结果 JSON 输出路径")
    parser.add_argument("--verbose", action="store_true", help="输出详细日志")
    args = parser.parse_args()

    if not 0.0 <= args.timeline_ratio <= 1.0:
        msg = "--timeline-ratio 必须在 [0.0, 1.0]"
        raise ValueError(msg)

    return args


def normalize_mac(mac_address: str) -> str:
    cleaned = mac_address.strip().replace("-", ":").upper()
    parts = cleaned.split(":")
    if len(parts) != 6:
        msg = f"MAC 格式无效: {mac_address}"
        raise ValueError(msg)
    if not all(len(part) == 2 and all(character in "0123456789ABCDEF" for character in part) for part in parts):
        msg = f"MAC 格式无效: {mac_address}"
        raise ValueError(msg)
    return cleaned


def parse_stage_configs(raw_value: str) -> list[StageConfig]:
    stage_items: list[StageConfig] = []
    for chunk in raw_value.split(","):
        trimmed = chunk.strip()
        if not trimmed:
            continue
        try:
            concurrency_raw, duration_raw = trimmed.split(":", maxsplit=1)
            stage = StageConfig(concurrency=int(concurrency_raw), duration_seconds=int(duration_raw))
        except ValueError as exc:
            msg = f"阶段定义无效: {trimmed}"
            raise ValueError(msg) from exc
        if stage.concurrency <= 0 or stage.duration_seconds <= 0:
            msg = f"阶段参数必须为正数: {trimmed}"
            raise ValueError(msg)
        stage_items.append(stage)
    if not stage_items:
        msg = "至少需要一个有效阶段"
        raise ValueError(msg)
    return stage_items


def build_json_request(url: str, token: str | None, payload: dict[str, Any]) -> request.Request:
    headers: dict[str, str] = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return request.Request(  # noqa: S310
        url=url,
        data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
        headers=headers,
        method="POST",
    )


def post_json(
    url: str, token: str | None, payload: dict[str, Any], timeout: float
) -> tuple[int, dict[str, Any] | None]:
    req = build_json_request(url=url, token=token, payload=payload)
    try:
        with request.urlopen(req, timeout=timeout) as response:  # noqa: S310
            body = response.read().decode("utf-8")
            try:
                parsed = json.loads(body) if body else None
            except json.JSONDecodeError:
                parsed = None
            return response.status, parsed if isinstance(parsed, dict) else None
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        try:
            parsed = json.loads(body) if body else None
        except json.JSONDecodeError:
            parsed = None
        return exc.code, parsed if isinstance(parsed, dict) else None


def get_json(url: str, token: str | None, timeout: float) -> tuple[int, Any]:
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = request.Request(url=url, headers=headers, method="GET")  # noqa: S310
    with request.urlopen(req, timeout=timeout) as response:  # noqa: S310
        body = response.read().decode("utf-8")
        parsed = json.loads(body) if body else None
        return response.status, parsed


def parse_bytes_to_int(raw_value: str) -> int:
    value = raw_value.strip()
    if not value:
        return 0
    normalized = value.replace(" ", "")
    unit_table: dict[str, int] = {
        "B": 1,
        "KB": 1000,
        "MB": 1000**2,
        "GB": 1000**3,
        "TB": 1000**4,
        "KIB": 1024,
        "MIB": 1024**2,
        "GIB": 1024**3,
        "TIB": 1024**4,
    }
    index = 0
    while index < len(normalized) and (normalized[index].isdigit() or normalized[index] in {".", "-"}):
        index += 1
    number_text = normalized[:index]
    unit_text = normalized[index:].upper() or "B"
    if number_text in {"", "-"}:
        return 0
    factor = unit_table.get(unit_text)
    if factor is None:
        msg = f"无法识别的字节单位: {raw_value}"
        raise ValueError(msg)
    return int(float(number_text) * factor)


def run_command(command: list[str], timeout_seconds: float = 10.0) -> tuple[int, str, str]:
    completed = subprocess.run(  # noqa: S603
        command,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )
    return completed.returncode, completed.stdout.strip(), completed.stderr.strip()


def capture_container_memory_bytes(container_name: str) -> int | None:
    command = ["docker", "stats", "--no-stream", "--format", "{{json .}}", container_name]
    code, stdout, stderr = run_command(command)
    if code != 0:
        logger.warning("采样容器内存失败 container=%s stderr=%s", container_name, stderr)
        return None
    if not stdout:
        return None
    try:
        parsed = json.loads(stdout)
        memory_usage = str(parsed.get("MemUsage", ""))
        used_text = memory_usage.split("/", maxsplit=1)[0].strip()
        return parse_bytes_to_int(used_text)
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        logger.warning("解析容器内存失败 container=%s error=%s raw=%s", container_name, exc, stdout)
        return None


def capture_path_size_bytes(container_name: str, container_path: str) -> int | None:
    safe_path = shlex.quote(container_path)
    command = ["docker", "exec", container_name, "sh", "-lc", f"du -sb {safe_path}"]
    code, stdout, stderr = run_command(command)
    if code != 0:
        logger.warning(
            "采样路径大小失败 container=%s path=%s stderr=%s",
            container_name,
            container_path,
            stderr,
        )
        return None
    if not stdout:
        return None
    head = stdout.split()[0]
    try:
        return int(head)
    except ValueError:
        logger.warning("路径大小输出无法解析 container=%s raw=%s", container_name, stdout)
        return None


def capture_postgres_scalar(
    container_name: str,
    postgres_user: str,
    postgres_db: str,
    sql: str,
) -> int | None:
    command = [
        "docker",
        "exec",
        container_name,
        "psql",
        "-U",
        postgres_user,
        "-d",
        postgres_db,
        "-At",
        "-c",
        sql,
    ]
    code, stdout, stderr = run_command(command)
    if code != 0:
        logger.warning("PostgreSQL 查询失败 sql=%s stderr=%s", sql, stderr)
        return None
    if not stdout:
        return None
    first_line = stdout.splitlines()[0].strip()
    try:
        return int(first_line)
    except ValueError:
        logger.warning("PostgreSQL 返回值无法解析 sql=%s output=%s", sql, stdout)
        return None


def capture_postgres_snapshot(args: argparse.Namespace) -> PostgresSizeSnapshot:
    return PostgresSizeSnapshot(
        data_dir_bytes=capture_path_size_bytes(args.postgres_container, args.postgres_data_path),
        database_bytes=capture_postgres_scalar(
            args.postgres_container,
            args.postgres_user,
            args.postgres_db,
            "SELECT pg_database_size(current_database());",
        ),
        core_detector_total_relation_bytes=capture_postgres_scalar(
            args.postgres_container,
            args.postgres_user,
            args.postgres_db,
            "SELECT COALESCE(pg_total_relation_size(to_regclass('public.core_detector')), 0);",
        ),
        core_detector_table_bytes=capture_postgres_scalar(
            args.postgres_container,
            args.postgres_user,
            args.postgres_db,
            "SELECT COALESCE(pg_relation_size(to_regclass('public.core_detector')), 0);",
        ),
        core_detector_index_bytes=capture_postgres_scalar(
            args.postgres_container,
            args.postgres_user,
            args.postgres_db,
            "SELECT COALESCE(pg_indexes_size(to_regclass('public.core_detector')), 0);",
        ),
    )


def capture_iotdb_snapshot(args: argparse.Namespace) -> dict[str, int | None]:
    return {
        "data_dir_bytes": capture_path_size_bytes(args.iotdb_container, args.iotdb_data_path),
    }


class ApiClient:
    def __init__(self, base_url: str, timeout_seconds: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.token: str | None = None

    def login(self, username: str, password: str) -> str:
        status, body = post_json(
            url=f"{self.base_url}/token/pair",
            token=None,
            payload={"username": username, "password": password},
            timeout=self.timeout_seconds,
        )
        if status != 200 or body is None:
            msg = f"登录失败 status={status} body={body}"
            raise RuntimeError(msg)
        token = body.get("access")
        if not isinstance(token, str) or not token:
            msg = f"登录响应缺少 access token: {body}"
            raise RuntimeError(msg)
        self.token = token
        return token

    def ensure_device(self, mac_address: str, device_name: str) -> None:
        if not self.token:
            msg = "需要先登录"
            raise RuntimeError(msg)
        status, body = get_json(f"{self.base_url}/devices/", token=self.token, timeout=self.timeout_seconds)
        if status != 200:
            msg = f"获取设备列表失败 status={status} body={body}"
            raise RuntimeError(msg)
        normalized = normalize_mac(mac_address)
        if isinstance(body, list):
            for item in body:
                if isinstance(item, dict) and str(item.get("mac_address", "")).upper() == normalized:
                    return
        create_status, create_body = post_json(
            url=f"{self.base_url}/devices/",
            token=self.token,
            payload={"mac_address": normalized, "name": device_name, "description": "压力测试设备"},
            timeout=self.timeout_seconds,
        )
        if create_status not in {201, 400}:
            msg = f"创建设备失败 status={create_status} body={create_body}"
            raise RuntimeError(msg)

    def upload_packet(self, payload: dict[str, Any]) -> tuple[int, dict[str, Any] | None]:
        if not self.token:
            msg = "需要先登录"
            raise RuntimeError(msg)
        return post_json(
            url=f"{self.base_url}/mu-packets/",
            token=self.token,
            payload=payload,
            timeout=self.timeout_seconds,
        )


class StageAccumulator:
    def __init__(self) -> None:
        self.request_total = 0
        self.request_success = 0
        self.request_failed = 0
        self.records_written = 0
        self.latency_ms: list[float] = []
        self.status_code_counts: Counter[str] = Counter()
        self.lock = threading.Lock()

    def record(self, status_code: int, latency_ms: float, records_written: int) -> None:
        with self.lock:
            self.request_total += 1
            self.latency_ms.append(latency_ms)
            self.status_code_counts[str(status_code)] += 1
            if status_code == 200:
                self.request_success += 1
                self.records_written += records_written
            else:
                self.request_failed += 1

    def record_exception(self, error_type: str, latency_ms: float) -> None:
        with self.lock:
            self.request_total += 1
            self.request_failed += 1
            self.latency_ms.append(latency_ms)
            self.status_code_counts[error_type] += 1


class ContainerMemorySampler:
    def __init__(self, containers: list[str], interval_seconds: float) -> None:
        self.containers = containers
        self.interval_seconds = interval_seconds
        self.samples: dict[str, list[dict[str, float | int]]] = {container: [] for container in containers}
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        self.thread.join(timeout=5)

    def _run(self) -> None:
        while not self.stop_event.is_set():
            timestamp = time.time()
            for container_name in self.containers:
                memory_bytes = capture_container_memory_bytes(container_name)
                if memory_bytes is None:
                    continue
                self.samples[container_name].append({"timestamp": timestamp, "memory_bytes": memory_bytes})
            time.sleep(self.interval_seconds)


def quantile(values: list[float], ratio: float) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    index = int((len(sorted_values) - 1) * ratio)
    return sorted_values[index]


def summarize_memory_samples(
    raw_samples: dict[str, list[dict[str, float | int]]],
) -> dict[str, dict[str, float | int]]:
    summary: dict[str, dict[str, float | int]] = {}
    for container_name, item_samples in raw_samples.items():
        values = [int(item["memory_bytes"]) for item in item_samples]
        if not values:
            summary[container_name] = {
                "sample_count": 0,
                "avg_bytes": 0,
                "min_bytes": 0,
                "max_bytes": 0,
                "p95_bytes": 0,
            }
            continue
        summary[container_name] = {
            "sample_count": len(values),
            "avg_bytes": int(statistics.fmean(values)),
            "min_bytes": int(min(values)),
            "max_bytes": int(max(values)),
            "p95_bytes": int(quantile([float(value) for value in values], 0.95)),
        }
    return summary


def build_muon_payload(mac_address: str, package_counter: int, rng: random.Random) -> dict[str, Any]:
    utc_seconds = int(time.time())
    events: list[dict[str, int]] = [
        {
            "cpu_time": package_counter * 1000 + offset,
            "energy": 100 + rng.randint(0, 4000),
            "pps": 10_000 + rng.randint(0, 20_000),
            "timestamp": int(time.time() * 1000),
        }
        for offset in range(35)
    ]
    return {
        "device": mac_address,
        "packet_type": "muon",
        "muon_packet": {
            "package_counter": package_counter,
            "utc": utc_seconds,
            "events": events,
            "head": [170, 187, 204],
            "tail": [221, 238, 255],
            "crc": rng.randint(0, 65535),
        },
    }


def build_timeline_payload(mac_address: str, package_counter: int, rng: random.Random) -> dict[str, Any]:
    utc_seconds = int(time.time())
    events: list[dict[str, int]] = [
        {
            "cpu_time": package_counter * 1000 + offset,
            "pps": 10_000 + rng.randint(0, 20_000),
            "utc": utc_seconds + offset,
            "pps_utc": 9_000 + rng.randint(0, 1_000),
            "cputime_pps": package_counter * 1000 + offset - 1,
            "gps_long": 121_473_700 + rng.randint(-500, 500),
            "gps_lat": 31_230_400 + rng.randint(-500, 500),
            "gps_alt": 20 + rng.randint(-3, 3),
            "acc_x": rng.randint(-4, 4),
            "acc_y": rng.randint(-4, 4),
            "acc_z": rng.randint(-4, 4),
            "sipm_tmp": 2000 + rng.randint(-30, 30),
            "mcu_tmp": 35 + rng.randint(-3, 3),
            "sipm_imon": 300 + rng.randint(-10, 10),
            "sipm_vmon": 600 + rng.randint(-30, 30),
            "timestamp": int(time.time() * 1000),
        }
        for offset in range(10)
    ]
    return {
        "device": mac_address,
        "packet_type": "timeline",
        "timeline_packet": {
            "package_counter": package_counter,
            "events": events,
            "head": [18, 52, 86],
            "tail": [120, 154, 188],
            "crc": rng.randint(0, 65535),
        },
    }


def build_payload(mac_address: str, package_counter: int, timeline_ratio: float, rng: random.Random) -> dict[str, Any]:
    if rng.random() < timeline_ratio:
        return build_timeline_payload(mac_address=mac_address, package_counter=package_counter, rng=rng)
    return build_muon_payload(mac_address=mac_address, package_counter=package_counter, rng=rng)


def run_stage(
    api_client: ApiClient,
    stage: StageConfig,
    stage_name: str,
    runtime_config: StageRuntimeConfig,
) -> StageResult:
    start_monotonic = time.monotonic()
    stage_deadline = start_monotonic + stage.duration_seconds
    accumulator = StageAccumulator()
    counter_lock = threading.Lock()
    package_counter = 0

    def next_package_counter() -> int:
        nonlocal package_counter
        with counter_lock:
            package_counter += 1
            return package_counter

    def worker(worker_id: int) -> None:
        local_rng = random.Random(runtime_config.seed + worker_id)  # noqa: S311
        while time.monotonic() < stage_deadline:
            package_id = next_package_counter()
            payload = build_payload(
                mac_address=runtime_config.mac_address,
                package_counter=package_id,
                timeline_ratio=runtime_config.timeline_ratio,
                rng=local_rng,
            )
            request_start = time.perf_counter()
            try:
                status_code, body = api_client.upload_packet(payload)
                latency_ms = (time.perf_counter() - request_start) * 1000
                records_written = 0
                if isinstance(body, dict):
                    raw_records = body.get("records_written")
                    if isinstance(raw_records, int):
                        records_written = raw_records
                accumulator.record(status_code=status_code, latency_ms=latency_ms, records_written=records_written)
            except TimeoutError:
                latency_ms = (time.perf_counter() - request_start) * 1000
                accumulator.record_exception("timeout", latency_ms)
            except error.URLError:
                latency_ms = (time.perf_counter() - request_start) * 1000
                accumulator.record_exception("network_error", latency_ms)

    workers: list[threading.Thread] = []
    for worker_id in range(stage.concurrency):
        thread = threading.Thread(target=worker, args=(worker_id,), daemon=True)
        workers.append(thread)
        thread.start()

    for thread in workers:
        thread.join()

    elapsed_seconds = max(time.monotonic() - start_monotonic, 0.001)
    request_total = accumulator.request_total
    request_failed = accumulator.request_failed
    latency_values = accumulator.latency_ms

    return StageResult(
        stage_name=stage_name,
        concurrency=stage.concurrency,
        duration_seconds=stage.duration_seconds,
        request_total=request_total,
        request_success=accumulator.request_success,
        request_failed=request_failed,
        records_written=accumulator.records_written,
        request_rps=request_total / elapsed_seconds,
        records_rps=accumulator.records_written / elapsed_seconds,
        error_rate=(request_failed / request_total) if request_total else 0.0,
        latency_ms_avg=float(statistics.fmean(latency_values)) if latency_values else 0.0,
        latency_ms_p50=quantile(latency_values, 0.50),
        latency_ms_p95=quantile(latency_values, 0.95),
        latency_ms_p99=quantile(latency_values, 0.99),
        status_code_counts=dict(accumulator.status_code_counts),
    )


def compute_delta(after: int | None, before: int | None) -> int | None:
    if after is None or before is None:
        return None
    return after - before


def compute_per_event(delta_bytes: int | None, event_count: int) -> float | None:
    if delta_bytes is None or event_count <= 0:
        return None
    return delta_bytes / event_count


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    random.seed(args.seed)
    stages = parse_stage_configs(args.stages)
    mac_address = normalize_mac(args.device_mac)
    containers = [item.strip() for item in args.containers.split(",") if item.strip()]

    api_client = ApiClient(base_url=args.base_url, timeout_seconds=args.request_timeout)
    logger.info("登录获取 Token")
    api_client.login(args.username, args.password)
    if not args.skip_device_bootstrap:
        logger.info("检查或创建设备 mac=%s", mac_address)
        api_client.ensure_device(mac_address=mac_address, device_name=args.device_name)

    logger.info("采集测试前数据库快照")
    postgres_before = capture_postgres_snapshot(args)
    iotdb_before = capture_iotdb_snapshot(args)

    sampler = ContainerMemorySampler(containers=containers, interval_seconds=args.sample_interval)
    sampler.start()

    stage_results: list[StageResult] = []
    for index, stage in enumerate(stages, start=1):
        stage_name = f"stage_{index}_{stage.concurrency}c"
        logger.info(
            "开始阶段 stage=%s duration=%ss concurrency=%s", stage_name, stage.duration_seconds, stage.concurrency
        )
        stage_result = run_stage(
            api_client=api_client,
            stage=stage,
            stage_name=stage_name,
            runtime_config=StageRuntimeConfig(
                mac_address=mac_address,
                timeline_ratio=args.timeline_ratio,
                seed=args.seed + index * 10000,
            ),
        )
        stage_results.append(stage_result)
        logger.info(
            "阶段结束 stage=%s req_total=%s req_success=%s records=%s err_rate=%.4f",
            stage_name,
            stage_result.request_total,
            stage_result.request_success,
            stage_result.records_written,
            stage_result.error_rate,
        )

    sampler.stop()

    logger.info("采集测试后数据库快照")
    postgres_after = capture_postgres_snapshot(args)
    iotdb_after = capture_iotdb_snapshot(args)

    total_records_written = sum(item.records_written for item in stage_results)
    total_requests = sum(item.request_total for item in stage_results)
    total_failed = sum(item.request_failed for item in stage_results)
    elapsed_seconds = sum(item.duration_seconds for item in stage_results)

    postgres_data_delta = compute_delta(postgres_after.data_dir_bytes, postgres_before.data_dir_bytes)
    postgres_db_delta = compute_delta(postgres_after.database_bytes, postgres_before.database_bytes)
    postgres_detector_delta = compute_delta(
        postgres_after.core_detector_total_relation_bytes,
        postgres_before.core_detector_total_relation_bytes,
    )
    iotdb_data_delta = compute_delta(iotdb_after.get("data_dir_bytes"), iotdb_before.get("data_dir_bytes"))

    report: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "scenario": {
            "base_url": args.base_url,
            "device_mac": mac_address,
            "timeline_ratio": args.timeline_ratio,
            "stages": [asdict(stage) for stage in stages],
            "sample_interval_seconds": args.sample_interval,
            "containers": containers,
        },
        "summary": {
            "total_requests": total_requests,
            "total_failed_requests": total_failed,
            "total_records_written": total_records_written,
            "elapsed_seconds": elapsed_seconds,
            "request_rps_overall": (total_requests / elapsed_seconds) if elapsed_seconds else 0.0,
            "records_rps_overall": (total_records_written / elapsed_seconds) if elapsed_seconds else 0.0,
            "error_rate_overall": (total_failed / total_requests) if total_requests else 0.0,
        },
        "stages": [asdict(item) for item in stage_results],
        "container_memory": {
            "summary": summarize_memory_samples(sampler.samples),
            "samples": sampler.samples,
        },
        "postgresql": {
            "before": asdict(postgres_before),
            "after": asdict(postgres_after),
            "delta": {
                "data_dir_bytes": postgres_data_delta,
                "database_bytes": postgres_db_delta,
                "core_detector_total_relation_bytes": postgres_detector_delta,
            },
            "per_event_bytes": {
                "data_dir_approx": compute_per_event(postgres_data_delta, total_records_written),
                "database_size": compute_per_event(postgres_db_delta, total_records_written),
                "core_detector_total_relation": compute_per_event(postgres_detector_delta, total_records_written),
            },
        },
        "iotdb": {
            "before": iotdb_before,
            "after": iotdb_after,
            "delta": {
                "data_dir_bytes": iotdb_data_delta,
            },
            "per_event_bytes": {
                "data_dir_approx": compute_per_event(iotdb_data_delta, total_records_written),
                "exact": None,
            },
            "exact_unavailable_reason": (
                "IoTDB 单条落盘大小受压缩与 compaction 影响, 常规接口无法稳定给出精确每条字节值, "
                "当前报告提供批量差分近似值。"
            ),
        },
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    logger.info("压测完成 output=%s", output_path)


if __name__ == "__main__":
    main()
