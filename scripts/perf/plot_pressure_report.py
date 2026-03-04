from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from PIL import Image
    from PIL import ImageDraw
    from PIL import ImageFont
except ModuleNotFoundError as exc:  # pragma: no cover
    msg = "缺少 pillow 依赖, 请先执行: uv add --dev pillow"
    raise RuntimeError(msg) from exc


FONT_CANDIDATES = [
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/noto-cjk/NotoSerifCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/wenquanyi/wqy-zenhei.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]

FONT_CACHE: dict[int, ImageFont.ImageFont] = {}
FONT_CONFIG: dict[str, str | None] = {"override_path": None}


@dataclass(slots=True)
class StagePoint:
    name: str
    request_rps: float
    latency_avg_ms: float
    latency_p95_ms: float
    error_rate_percent: float


@dataclass(slots=True)
class SeriesData:
    name: str
    points: list[tuple[float, float]]
    color: tuple[int, int, int]


@dataclass(slots=True)
class ChartSpec:
    output_path: Path
    title: str
    x_label: str
    y_label: str
    series_list: list[SeriesData]
    x_tick_labels: list[str]
    width: int
    height: int


@dataclass(slots=True)
class AxisRange:
    x_min: float
    x_max: float
    y_min: float
    y_max: float


@dataclass(slots=True)
class PlotArea:
    left: int
    right: int
    top: int
    bottom: int


@dataclass(slots=True)
class FontSet:
    title: ImageFont.ImageFont
    label: ImageFont.ImageFont
    tick: ImageFont.ImageFont
    legend: ImageFont.ImageFont


def load_font(size: int) -> ImageFont.ImageFont:
    cached = FONT_CACHE.get(size)
    if cached is not None:
        return cached

    override_path = FONT_CONFIG["override_path"]
    if override_path is not None:
        try:
            font = ImageFont.truetype(override_path, size=size)
        except OSError as exc:
            msg = f"指定字体不可用: {override_path}"
            raise RuntimeError(msg) from exc
        else:
            FONT_CACHE[size] = font
            return font

    for candidate in FONT_CANDIDATES:
        path = Path(candidate)
        if not path.exists():
            continue
        try:
            font = ImageFont.truetype(str(path), size=size)
            FONT_CACHE[size] = font
        except OSError:
            continue
        else:
            return font

    font = ImageFont.load_default()
    FONT_CACHE[size] = font
    return font


def build_font_set() -> FontSet:
    return FontSet(
        title=load_font(28),
        label=load_font(20),
        tick=load_font(16),
        legend=load_font(16),
    )


def center_text_x(draw: ImageDraw.ImageDraw, text: str, x: int, font: ImageFont.ImageFont) -> int:
    left, _, right, _ = draw.textbbox((0, 0), text, font=font)
    return int(x - (right - left) // 2)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="根据压测 JSON 报告生成 PNG 折线图")
    parser.add_argument(
        "--input",
        required=True,
        nargs="+",
        help="压测报告 JSON 文件路径, 支持多个文件",
    )
    parser.add_argument("--out-dir", default="reports/perf/plots", help="图表输出目录")
    parser.add_argument("--width", type=int, default=1280, help="PNG 宽度")
    parser.add_argument("--height", type=int, default=720, help="PNG 高度")
    parser.add_argument("--font-path", default=None, help="可选: 指定中文字体文件路径 (.ttf/.ttc)")
    return parser.parse_args()


def load_report(path: Path) -> dict[str, Any]:
    content = path.read_text(encoding="utf-8")
    parsed = json.loads(content)
    if not isinstance(parsed, dict):
        msg = f"报告格式无效: {path}"
        raise TypeError(msg)
    return parsed


def extract_stage_points(report: dict[str, Any]) -> list[StagePoint]:
    raw_stages = report.get("stages")
    if not isinstance(raw_stages, list):
        return []

    points: list[StagePoint] = []
    for index, item in enumerate(raw_stages, start=1):
        if not isinstance(item, dict):
            continue
        stage_name = str(item.get("stage_name") or f"stage_{index}")
        point = StagePoint(
            name=stage_name,
            request_rps=float(item.get("request_rps") or 0.0),
            latency_avg_ms=float(item.get("latency_ms_avg") or 0.0),
            latency_p95_ms=float(item.get("latency_ms_p95") or 0.0),
            error_rate_percent=float(item.get("error_rate") or 0.0) * 100,
        )
        points.append(point)
    return points


def get_memory_samples(report: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    raw_memory = report.get("container_memory")
    if not isinstance(raw_memory, dict):
        return {}
    raw_samples = raw_memory.get("samples")
    if not isinstance(raw_samples, dict):
        return {}

    samples: dict[str, list[dict[str, Any]]] = {}
    for key, value in raw_samples.items():
        if isinstance(value, list):
            samples[str(key)] = [item for item in value if isinstance(item, dict)]
    return samples


def find_first_timestamp(samples: dict[str, list[dict[str, Any]]]) -> float | None:
    first_timestamp: float | None = None
    for entries in samples.values():
        for entry in entries:
            timestamp = entry.get("timestamp")
            if not isinstance(timestamp, (int, float)):
                continue
            current = float(timestamp)
            if first_timestamp is None or current < first_timestamp:
                first_timestamp = current
    return first_timestamp


def extract_container_points(entries: list[dict[str, Any]], first_timestamp: float) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for entry in entries:
        timestamp = entry.get("timestamp")
        memory_bytes = entry.get("memory_bytes")
        if not isinstance(timestamp, (int, float)) or not isinstance(memory_bytes, int):
            continue
        x_value = float(timestamp) - first_timestamp
        y_value = memory_bytes / (1024**2)
        points.append((x_value, y_value))
    return points


def extract_memory_series(report: dict[str, Any]) -> list[SeriesData]:
    samples = get_memory_samples(report)
    if not samples:
        return []

    first_timestamp = find_first_timestamp(samples)

    if first_timestamp is None:
        return []

    palette = [
        (32, 126, 255),
        (22, 163, 74),
        (245, 158, 11),
        (220, 38, 38),
        (147, 51, 234),
        (14, 165, 233),
    ]

    result: list[SeriesData] = []
    palette_index = 0
    for container_name, entries in samples.items():
        points = extract_container_points(entries, first_timestamp)

        if not points:
            continue

        color = palette[palette_index % len(palette)]
        palette_index += 1
        result.append(SeriesData(name=str(container_name), points=points, color=color))

    return result


def safe_float(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0


def extract_storage_series(report: dict[str, Any]) -> list[SeriesData]:
    postgres = report.get("postgresql")
    iotdb = report.get("iotdb")
    postgres_metrics: dict[str, Any] = {}
    iotdb_metrics: dict[str, Any] = {}

    if isinstance(postgres, dict):
        raw_postgres_metrics = postgres.get("per_event_bytes")
        if isinstance(raw_postgres_metrics, dict):
            postgres_metrics = raw_postgres_metrics

    if isinstance(iotdb, dict):
        raw_iotdb_metrics = iotdb.get("per_event_bytes")
        if isinstance(raw_iotdb_metrics, dict):
            iotdb_metrics = raw_iotdb_metrics

    points = [
        (0.0, safe_float(postgres_metrics.get("data_dir_approx"))),
        (1.0, safe_float(postgres_metrics.get("database_size"))),
        (2.0, safe_float(postgres_metrics.get("core_detector_total_relation"))),
        (3.0, safe_float(iotdb_metrics.get("data_dir_approx"))),
    ]
    return [SeriesData(name="bytes/event", points=points, color=(32, 126, 255))]


def compute_axis_range(series_list: list[SeriesData]) -> AxisRange | None:
    xs = [point[0] for series in series_list for point in series.points]
    ys = [point[1] for series in series_list for point in series.points]
    if not xs or not ys:
        return None

    x_min = min(xs)
    x_max = max(xs)
    y_min = 0.0
    y_max = max(ys)
    if x_max <= x_min:
        x_max = x_min + 1.0
    if y_max <= y_min:
        y_max = y_min + 1.0
    return AxisRange(x_min=x_min, x_max=x_max, y_min=y_min, y_max=y_max)


def project_points(
    points: list[tuple[float, float]],
    axis_range: AxisRange,
    plot_area: PlotArea,
) -> list[tuple[int, int]]:
    mapped: list[tuple[int, int]] = []
    for x_value, y_value in points:
        px = int(
            plot_area.left
            + (x_value - axis_range.x_min) / (axis_range.x_max - axis_range.x_min) * (plot_area.right - plot_area.left)
        )
        py = int(
            plot_area.bottom
            - (y_value - axis_range.y_min) / (axis_range.y_max - axis_range.y_min) * (plot_area.bottom - plot_area.top)
        )
        mapped.append((px, py))
    return mapped


def draw_grid(
    draw: ImageDraw.ImageDraw,
    plot_area: PlotArea,
    axis_range: AxisRange,
    tick_font: ImageFont.ImageFont,
) -> None:
    draw.rectangle(
        (plot_area.left, plot_area.top, plot_area.right, plot_area.bottom),
        outline=(180, 180, 180),
        width=1,
    )
    grid_count = 5
    for index in range(grid_count + 1):
        ratio = index / grid_count
        y = int(plot_area.bottom - (plot_area.bottom - plot_area.top) * ratio)
        draw.line((plot_area.left, y, plot_area.right, y), fill=(235, 235, 235), width=1)
        value = axis_range.y_min + (axis_range.y_max - axis_range.y_min) * ratio
        draw.text((20, y - 8), f"{value:.1f}", fill=(80, 80, 80), font=tick_font)


def draw_x_ticks(
    draw: ImageDraw.ImageDraw,
    plot_area: PlotArea,
    x_tick_labels: list[str],
    tick_font: ImageFont.ImageFont,
) -> None:
    tick_count = len(x_tick_labels)
    if tick_count == 0:
        return

    for index, label in enumerate(x_tick_labels):
        ratio = 0.0 if tick_count == 1 else index / (tick_count - 1)
        x = int(plot_area.left + (plot_area.right - plot_area.left) * ratio)
        draw.line((x, plot_area.bottom, x, plot_area.bottom + 4), fill=(130, 130, 130), width=1)
        draw.text(
            (center_text_x(draw, label, x, tick_font), plot_area.bottom + 10),
            label,
            fill=(80, 80, 80),
            font=tick_font,
        )


def draw_legend(
    draw: ImageDraw.ImageDraw,
    right: int,
    top: int,
    series_list: list[SeriesData],
    legend_font: ImageFont.ImageFont,
) -> None:
    legend_x = right - 220
    legend_y = top + 10
    for series in series_list:
        draw.line((legend_x, legend_y + 7, legend_x + 20, legend_y + 7), fill=series.color, width=3)
        draw.text((legend_x + 26, legend_y), series.name, fill=(50, 50, 50), font=legend_font)
        legend_y += 20


def draw_line_chart(spec: ChartSpec) -> None:
    if not spec.series_list:
        return

    axis_range = compute_axis_range(spec.series_list)
    if axis_range is None:
        return

    plot_area = PlotArea(left=90, right=spec.width - 40, top=60, bottom=spec.height - 120)
    fonts = build_font_set()

    image = Image.new("RGB", (spec.width, spec.height), (255, 255, 255))
    draw = ImageDraw.Draw(image)

    draw_grid(draw, plot_area, axis_range, fonts.tick)

    for series in spec.series_list:
        mapped = project_points(series.points, axis_range, plot_area)
        if len(mapped) >= 2:
            draw.line(mapped, fill=series.color, width=3)
        for px, py in mapped:
            draw.ellipse((px - 3, py - 3, px + 3, py + 3), fill=series.color)

    draw_x_ticks(draw, plot_area, spec.x_tick_labels, fonts.tick)
    draw.text((plot_area.left, 20), spec.title, fill=(0, 0, 0), font=fonts.title)
    x_label_x = center_text_x(draw, spec.x_label, (plot_area.left + plot_area.right) // 2, fonts.label)
    draw.text((x_label_x, spec.height - 45), spec.x_label, fill=(30, 30, 30), font=fonts.label)
    draw.text((20, plot_area.top - 25), spec.y_label, fill=(30, 30, 30), font=fonts.label)
    draw_legend(draw, plot_area.right, plot_area.top, spec.series_list, fonts.legend)
    image.save(spec.output_path, format="PNG")


def plot_throughput(stage_points: list[StagePoint], output_path: Path, width: int, height: int) -> None:
    labels = [point.name for point in stage_points]
    values = [point.request_rps for point in stage_points]
    points = [(float(index), value) for index, value in enumerate(values)]
    draw_line_chart(
        ChartSpec(
            output_path=output_path,
            title="阶段吞吐量趋势",
            x_label="阶段",
            y_label="请求吞吐量 (req/s)",
            series_list=[SeriesData(name="request_rps", points=points, color=(32, 126, 255))],
            x_tick_labels=labels,
            width=width,
            height=height,
        )
    )


def plot_latency(stage_points: list[StagePoint], output_path: Path, width: int, height: int) -> None:
    labels = [point.name for point in stage_points]
    avg_values = [point.latency_avg_ms for point in stage_points]
    p95_values = [point.latency_p95_ms for point in stage_points]
    avg_points = [(float(index), value) for index, value in enumerate(avg_values)]
    p95_points = [(float(index), value) for index, value in enumerate(p95_values)]
    draw_line_chart(
        ChartSpec(
            output_path=output_path,
            title="阶段延迟趋势",
            x_label="阶段",
            y_label="延迟 (ms)",
            series_list=[
                SeriesData(name="avg", points=avg_points, color=(32, 126, 255)),
                SeriesData(name="p95", points=p95_points, color=(220, 38, 38)),
            ],
            x_tick_labels=labels,
            width=width,
            height=height,
        )
    )


def plot_error_rate(stage_points: list[StagePoint], output_path: Path, width: int, height: int) -> None:
    labels = [point.name for point in stage_points]
    values = [point.error_rate_percent for point in stage_points]
    points = [(float(index), value) for index, value in enumerate(values)]
    draw_line_chart(
        ChartSpec(
            output_path=output_path,
            title="阶段错误率趋势",
            x_label="阶段",
            y_label="错误率 (%)",
            series_list=[SeriesData(name="error_rate", points=points, color=(220, 38, 38))],
            x_tick_labels=labels,
            width=width,
            height=height,
        )
    )


def plot_memory(report: dict[str, Any], output_path: Path, width: int, height: int) -> None:
    memory_series = extract_memory_series(report)
    if not memory_series:
        return
    draw_line_chart(
        ChartSpec(
            output_path=output_path,
            title="容器内存趋势",
            x_label="相对时间 (s)",
            y_label="内存 (MiB)",
            series_list=memory_series,
            x_tick_labels=["0", "25%", "50%", "75%", "100%"],
            width=width,
            height=height,
        )
    )


def plot_per_event_storage(report: dict[str, Any], output_path: Path, width: int, height: int) -> None:
    storage_series = extract_storage_series(report)
    draw_line_chart(
        ChartSpec(
            output_path=output_path,
            title="每 event 存储成本趋势",
            x_label="口径",
            y_label="字节/事件 (bytes/event)",
            series_list=storage_series,
            x_tick_labels=["pg_dir", "pg_db", "pg_table", "iotdb_dir"],
            width=width,
            height=height,
        )
    )


def write_summary(report: dict[str, Any], output_path: Path) -> None:
    summary = report.get("summary")
    scenario = report.get("scenario")
    result = {
        "generated_at": report.get("generated_at"),
        "scenario": scenario if isinstance(scenario, dict) else {},
        "summary": summary if isinstance(summary, dict) else {},
        "charts": [
            "throughput.png",
            "latency.png",
            "error_rate.png",
            "memory.png",
            "per_event_storage.png",
        ],
    }
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


def plot_single_report(report_path: Path, out_dir: Path, width: int, height: int) -> None:
    report = load_report(report_path)
    stage_points = extract_stage_points(report)

    out_dir.mkdir(parents=True, exist_ok=True)

    if stage_points:
        plot_throughput(stage_points, out_dir / "throughput.png", width, height)
        plot_latency(stage_points, out_dir / "latency.png", width, height)
        plot_error_rate(stage_points, out_dir / "error_rate.png", width, height)

    plot_memory(report, out_dir / "memory.png", width, height)
    plot_per_event_storage(report, out_dir / "per_event_storage.png", width, height)
    write_summary(report, out_dir / "summary.json")


def set_font_override(path: str | None) -> None:
    if path:
        FONT_CONFIG["override_path"] = str(Path(path))


def main() -> None:
    args = parse_args()
    set_font_override(args.font_path)

    input_paths = [Path(path) for path in args.input]
    output_root = Path(args.out_dir)

    if len(input_paths) == 1:
        plot_single_report(input_paths[0], output_root, args.width, args.height)
        return

    for report_path in input_paths:
        run_name = report_path.stem
        plot_single_report(report_path, output_root / run_name, args.width, args.height)


if __name__ == "__main__":
    main()
