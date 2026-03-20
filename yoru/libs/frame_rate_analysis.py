from __future__ import annotations

import csv
import statistics
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class FrameRateReport:
    log_path: Path
    target_fps: float | None
    frame_count: int
    interval_count: int
    start_time_s: float
    end_time_s: float
    duration_s: float
    mean_interval_s: float
    median_interval_s: float
    stdev_interval_s: float
    min_interval_s: float
    max_interval_s: float
    measured_fps: float
    achieved_fps: float
    monotonic: bool
    non_monotonic_steps: int
    suspected_dropped_frames: int
    target_interval_s: float | None
    interval_tolerance_s: float | None
    intervals_within_tolerance: int | None
    intervals_within_tolerance_pct: float | None

    def summary(self) -> str:
        parts = [
            f"log={self.log_path.name}",
            f"frames={self.frame_count}",
            f"measured_fps={self.measured_fps:.4f}",
            f"achieved_fps={self.achieved_fps:.4f}",
            f"duration_s={self.duration_s:.4f}",
            f"monotonic={self.monotonic}",
            f"suspected_dropped_frames={self.suspected_dropped_frames}",
        ]
        if self.target_fps is not None:
            parts.append(f"target_fps={self.target_fps:.4f}")
        if self.intervals_within_tolerance_pct is not None:
            parts.append(
                "intervals_within_tolerance_pct="
                f"{self.intervals_within_tolerance_pct:.2f}"
            )
        return ", ".join(parts)


def paired_config_path(log_path: str | Path) -> Path:
    log_path = Path(log_path)
    name = log_path.name
    if name.endswith("_log.csv"):
        return log_path.with_name(name[: -len("_log.csv")] + ".yaml")
    return log_path.with_suffix(".yaml")


def load_target_fps_from_yaml(yaml_path: str | Path) -> float:
    yaml_path = Path(yaml_path)
    with yaml_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)

    try:
        return float(data["hardware"]["camera_fps"])
    except Exception as exc:
        raise ValueError(f"Could not read hardware.camera_fps from {yaml_path}") from exc


def load_frame_timestamps(log_path: str | Path) -> list[float]:
    log_path = Path(log_path)
    with log_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if "total_time" not in (reader.fieldnames or []):
            raise ValueError(f"{log_path} is missing required column 'total_time'")

        timestamps: list[float] = []
        for row in reader:
            total_time = str(row.get("total_time", "")).strip()
            if not total_time:
                continue
            timestamps.append(float(total_time))

    if len(timestamps) < 2:
        raise ValueError(f"{log_path} must contain at least 2 frame timestamps")

    return timestamps


def analyze_frame_log(
    log_path: str | Path,
    target_fps: float | None = None,
    interval_tolerance_s: float | None = 0.002,
) -> FrameRateReport:
    log_path = Path(log_path)
    timestamps = load_frame_timestamps(log_path)

    if target_fps is None:
        yaml_path = paired_config_path(log_path)
        if yaml_path.exists():
            target_fps = load_target_fps_from_yaml(yaml_path)

    deltas = [
        timestamps[idx] - timestamps[idx - 1] for idx in range(1, len(timestamps))
    ]
    non_monotonic_steps = sum(1 for delta in deltas if delta <= 0.0)
    monotonic = non_monotonic_steps == 0
    if not monotonic:
        raise ValueError(f"{log_path} contains non-monotonic frame timestamps")

    duration_s = timestamps[-1] - timestamps[0]
    mean_interval_s = statistics.mean(deltas)
    median_interval_s = statistics.median(deltas)
    stdev_interval_s = statistics.pstdev(deltas)
    min_interval_s = min(deltas)
    max_interval_s = max(deltas)
    measured_fps = 1.0 / mean_interval_s
    achieved_fps = (len(timestamps) - 1) / duration_s

    target_interval_s = None
    intervals_within_tolerance = None
    intervals_within_tolerance_pct = None
    suspected_dropped_frames = 0

    if target_fps is not None:
        target_interval_s = 1.0 / float(target_fps)
        if interval_tolerance_s is not None:
            intervals_within_tolerance = sum(
                1
                for delta in deltas
                if abs(delta - target_interval_s) <= interval_tolerance_s
            )
            intervals_within_tolerance_pct = (
                100.0 * intervals_within_tolerance / len(deltas)
            )

        for delta in deltas:
            multiple = delta / target_interval_s
            if multiple > 1.5:
                suspected_dropped_frames += max(0, int(round(multiple)) - 1)

    return FrameRateReport(
        log_path=log_path,
        target_fps=target_fps,
        frame_count=len(timestamps),
        interval_count=len(deltas),
        start_time_s=timestamps[0],
        end_time_s=timestamps[-1],
        duration_s=duration_s,
        mean_interval_s=mean_interval_s,
        median_interval_s=median_interval_s,
        stdev_interval_s=stdev_interval_s,
        min_interval_s=min_interval_s,
        max_interval_s=max_interval_s,
        measured_fps=measured_fps,
        achieved_fps=achieved_fps,
        monotonic=monotonic,
        non_monotonic_steps=non_monotonic_steps,
        suspected_dropped_frames=suspected_dropped_frames,
        target_interval_s=target_interval_s,
        interval_tolerance_s=interval_tolerance_s,
        intervals_within_tolerance=intervals_within_tolerance,
        intervals_within_tolerance_pct=intervals_within_tolerance_pct,
    )


def assert_frame_rate(
    log_path: str | Path,
    expected_fps: float,
    fps_abs_tolerance: float = 0.25,
    interval_tolerance_s: float = 0.002,
    min_intervals_within_tolerance_pct: float = 95.0,
) -> FrameRateReport:
    report = analyze_frame_log(
        log_path,
        target_fps=expected_fps,
        interval_tolerance_s=interval_tolerance_s,
    )

    failures: list[str] = []
    if abs(report.measured_fps - expected_fps) > fps_abs_tolerance:
        failures.append(
            f"measured_fps={report.measured_fps:.4f} outside +/- {fps_abs_tolerance:.4f} of {expected_fps:.4f}"
        )

    if abs(report.achieved_fps - expected_fps) > fps_abs_tolerance:
        failures.append(
            f"achieved_fps={report.achieved_fps:.4f} outside +/- {fps_abs_tolerance:.4f} of {expected_fps:.4f}"
        )

    if report.intervals_within_tolerance_pct is None:
        failures.append("interval tolerance analysis was not computed")
    elif report.intervals_within_tolerance_pct < min_intervals_within_tolerance_pct:
        failures.append(
            "intervals_within_tolerance_pct="
            f"{report.intervals_within_tolerance_pct:.2f} below required "
            f"{min_intervals_within_tolerance_pct:.2f}"
        )

    if report.suspected_dropped_frames != 0:
        failures.append(
            f"suspected_dropped_frames={report.suspected_dropped_frames} is not zero"
        )

    if failures:
        raise AssertionError(report.summary() + " | " + "; ".join(failures))

    return report
