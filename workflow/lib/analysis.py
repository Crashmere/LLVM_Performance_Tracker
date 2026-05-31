from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import combinations
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class MetricDefinition:
    column: str
    name: str
    display_name: str
    direction: str


METRICS: tuple[MetricDefinition, ...] = (
    MetricDefinition("exec_time_mean", "exec_time", "Execution time", "lower"),
    MetricDefinition("compile_time_mean", "compile_time", "Compile time", "lower"),
    MetricDefinition("binary_size_first", "binary_size", "Binary size", "lower"),
    MetricDefinition("flops_gflops_mean", "flops_gflops", "Throughput", "higher"),
    MetricDefinition("bandwidth_gib_mean", "bandwidth_gib", "Memory bandwidth", "higher"),
)

ANALYSIS_RECORD_COLUMNS = [
    "experiment_id",
    "source_file",
    "suite_name",
    "suite_version",
    "compiler_version",
    "label",
    "sample",
    "test_name",
    "metric",
    "metric_display_name",
    "metric_source_column",
    "direction",
    "value",
]

SAMPLE_STATISTIC_COLUMNS = [
    "suite_name",
    "suite_version",
    "compiler_version",
    "test_name",
    "metric",
    "metric_display_name",
    "direction",
    "observations",
    "labels",
    "samples",
    "mean",
    "std",
    "cv",
    "ci95_low",
    "ci95_high",
]

COMPARISON_COLUMNS = [
    "suite_name",
    "test_name",
    "metric",
    "metric_display_name",
    "direction",
    "baseline_compiler_version",
    "baseline_suite_version",
    "candidate_compiler_version",
    "candidate_suite_version",
    "baseline_observations",
    "candidate_observations",
    "baseline_mean",
    "candidate_mean",
    "raw_change_percent",
    "normalized_change_percent",
    "classification",
    "evidence",
]


def discover_aggregated_tables(base_dir: Path | str) -> list[Path]:
    return sorted(Path(base_dir).expanduser().resolve().glob("parsed/*/benchmark_records_aggregated.csv"))


def write_table(df: pd.DataFrame, output_file: Path | str) -> Path:
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    return output_path


def write_json(data: dict[str, Any], output_file: Path | str) -> Path:
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _unique_paths(paths: list[Path | str]) -> list[Path]:
    unique: dict[str, Path] = {}
    for path in paths:
        resolved = Path(path).expanduser().resolve()
        unique[str(resolved)] = resolved
    return [unique[key] for key in sorted(unique)]


def _parse_experiment_id(experiment_id: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for part in experiment_id.split("__"):
        if part.startswith("label_"):
            values["label"] = part.removeprefix("label_")
        elif part.startswith("run_"):
            values["label"] = part.removeprefix("run_")
        elif part.startswith("sample_"):
            values["sample"] = part
    return values


def _ensure_context_columns(df: pd.DataFrame, source_file: Path) -> pd.DataFrame:
    result = df.copy()
    experiment_id = source_file.parent.name
    inferred = _parse_experiment_id(experiment_id)

    result["experiment_id"] = experiment_id
    result["source_file"] = str(source_file)

    if "label" not in result.columns:
        result["label"] = inferred.get("label", "unknown")
    else:
        result["label"] = result["label"].fillna(inferred.get("label", "unknown")).astype(str)

    if "sample" not in result.columns:
        result["sample"] = inferred.get("sample", "sample_1")
    else:
        result["sample"] = result["sample"].fillna(inferred.get("sample", "sample_1")).astype(str)

    return result


def load_aggregated_tables(input_files: list[Path | str]) -> tuple[pd.DataFrame, list[str]]:
    frames: list[pd.DataFrame] = []
    skipped: list[str] = []

    for input_file in _unique_paths(input_files):
        if not input_file.exists():
            skipped.append(f"{input_file}: missing")
            continue
        try:
            df = pd.read_csv(input_file)
        except Exception as exc:
            skipped.append(f"{input_file}: {exc}")
            continue
        if df.empty:
            skipped.append(f"{input_file}: empty")
            continue
        frames.append(_ensure_context_columns(df, input_file))

    if not frames:
        return pd.DataFrame(), skipped
    return pd.concat(frames, ignore_index=True, sort=False), skipped


def build_analysis_records(aggregated_df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if aggregated_df.empty:
        return pd.DataFrame(columns=ANALYSIS_RECORD_COLUMNS)

    base_columns = [
        "experiment_id",
        "source_file",
        "suite_name",
        "suite_version",
        "compiler_version",
        "label",
        "sample",
        "test_name",
    ]

    for metric in METRICS:
        if metric.column not in aggregated_df.columns:
            continue
        metric_df = aggregated_df[base_columns + [metric.column]].copy()
        metric_df[metric.column] = pd.to_numeric(metric_df[metric.column], errors="coerce")
        metric_df = metric_df.dropna(subset=[metric.column])
        for record in metric_df.to_dict("records"):
            rows.append(
                {
                    **{key: record.get(key) for key in base_columns},
                    "metric": metric.name,
                    "metric_display_name": metric.display_name,
                    "metric_source_column": metric.column,
                    "direction": metric.direction,
                    "value": record[metric.column],
                }
            )

    if not rows:
        return pd.DataFrame(columns=ANALYSIS_RECORD_COLUMNS)
    return pd.DataFrame(rows, columns=ANALYSIS_RECORD_COLUMNS)


def _joined_unique(values: pd.Series) -> str:
    return ",".join(sorted({str(value) for value in values.dropna()}))


def build_sample_statistics(analysis_records: pd.DataFrame) -> pd.DataFrame:
    if analysis_records.empty:
        return pd.DataFrame(columns=SAMPLE_STATISTIC_COLUMNS)

    rows: list[dict[str, Any]] = []
    group_keys = ["suite_name", "suite_version", "compiler_version", "test_name", "metric"]

    for keys, group in analysis_records.groupby(group_keys, dropna=False):
        values = pd.to_numeric(group["value"], errors="coerce").dropna()
        observations = int(values.count())
        mean = float(values.mean()) if observations else math.nan
        std = float(values.std(ddof=1)) if observations > 1 else math.nan
        cv = float(std / abs(mean)) if observations > 1 and mean != 0 and not math.isnan(std) else math.nan
        ci_half_width = float(1.96 * std / math.sqrt(observations)) if observations > 1 else math.nan

        rows.append(
            {
                "suite_name": keys[0],
                "suite_version": keys[1],
                "compiler_version": keys[2],
                "test_name": keys[3],
                "metric": keys[4],
                "metric_display_name": str(group["metric_display_name"].iloc[0]),
                "direction": str(group["direction"].iloc[0]),
                "observations": observations,
                "labels": _joined_unique(group["label"]),
                "samples": _joined_unique(group["sample"]),
                "mean": mean,
                "std": std,
                "cv": cv,
                "ci95_low": mean - ci_half_width if not math.isnan(ci_half_width) else math.nan,
                "ci95_high": mean + ci_half_width if not math.isnan(ci_half_width) else math.nan,
            }
        )

    return pd.DataFrame(rows, columns=SAMPLE_STATISTIC_COLUMNS)


def _ci_overlap(left: pd.Series, right: pd.Series) -> bool | None:
    left_low = left.get("ci95_low")
    left_high = left.get("ci95_high")
    right_low = right.get("ci95_low")
    right_high = right.get("ci95_high")
    if any(pd.isna(value) for value in [left_low, left_high, right_low, right_high]):
        return None
    return not (float(left_high) < float(right_low) or float(right_high) < float(left_low))


def _classify_change(
    normalized_change_percent: float,
    ci_overlap: bool | None,
    baseline_n: int,
    candidate_n: int,
    *,
    threshold_percent: float,
    min_samples: int,
) -> tuple[str, str]:
    if abs(normalized_change_percent) < threshold_percent:
        return "stable", "below_threshold"

    direction = "regression" if normalized_change_percent > 0 else "improvement"
    if baseline_n < min_samples or candidate_n < min_samples:
        return f"candidate_{direction}", "insufficient_samples"
    if ci_overlap is False:
        return f"reliable_{direction}", "ci95_non_overlapping"
    if ci_overlap is True:
        return f"candidate_{direction}", "ci95_overlapping"
    return f"candidate_{direction}", "missing_ci"


def build_metric_comparisons(
    sample_statistics: pd.DataFrame,
    *,
    threshold_percent: float,
    min_samples: int,
) -> pd.DataFrame:
    if sample_statistics.empty:
        return pd.DataFrame(columns=COMPARISON_COLUMNS)

    rows: list[dict[str, Any]] = []
    group_keys = ["suite_name", "test_name", "metric"]

    for _, group in sample_statistics.groupby(group_keys, dropna=False):
        variants = group.sort_values(["compiler_version", "suite_version"]).reset_index(drop=True)
        if len(variants) < 2:
            continue

        for baseline_index, candidate_index in combinations(range(len(variants)), 2):
            baseline = variants.iloc[baseline_index]
            candidate = variants.iloc[candidate_index]
            baseline_mean = float(baseline["mean"])
            candidate_mean = float(candidate["mean"])
            if baseline_mean == 0 or pd.isna(baseline_mean) or pd.isna(candidate_mean):
                continue

            raw_change_percent = ((candidate_mean - baseline_mean) / abs(baseline_mean)) * 100.0
            normalized_change_percent = (
                raw_change_percent if baseline["direction"] == "lower" else -raw_change_percent
            )
            overlap = _ci_overlap(baseline, candidate)
            classification, evidence = _classify_change(
                normalized_change_percent,
                overlap,
                int(baseline["observations"]),
                int(candidate["observations"]),
                threshold_percent=threshold_percent,
                min_samples=min_samples,
            )

            rows.append(
                {
                    "suite_name": baseline["suite_name"],
                    "test_name": baseline["test_name"],
                    "metric": baseline["metric"],
                    "metric_display_name": baseline["metric_display_name"],
                    "direction": baseline["direction"],
                    "baseline_compiler_version": baseline["compiler_version"],
                    "baseline_suite_version": baseline["suite_version"],
                    "candidate_compiler_version": candidate["compiler_version"],
                    "candidate_suite_version": candidate["suite_version"],
                    "baseline_observations": int(baseline["observations"]),
                    "candidate_observations": int(candidate["observations"]),
                    "baseline_mean": baseline_mean,
                    "candidate_mean": candidate_mean,
                    "raw_change_percent": raw_change_percent,
                    "normalized_change_percent": normalized_change_percent,
                    "classification": classification,
                    "evidence": evidence,
                }
            )

    return pd.DataFrame(rows, columns=COMPARISON_COLUMNS)


def split_top_changes(metric_comparisons: pd.DataFrame, *, limit: int = 50) -> tuple[pd.DataFrame, pd.DataFrame]:
    if metric_comparisons.empty:
        empty = pd.DataFrame(columns=COMPARISON_COLUMNS)
        return empty.copy(), empty.copy()

    regressions = metric_comparisons[
        metric_comparisons["classification"].str.endswith("regression", na=False)
    ].sort_values("normalized_change_percent", ascending=False)
    improvements = metric_comparisons[
        metric_comparisons["classification"].str.endswith("improvement", na=False)
    ].sort_values("normalized_change_percent", ascending=True)
    return regressions.head(limit).copy(), improvements.head(limit).copy()


def build_analysis_summary(
    *,
    input_files: list[Path | str],
    skipped_inputs: list[str],
    analysis_records: pd.DataFrame,
    sample_statistics: pd.DataFrame,
    metric_comparisons: pd.DataFrame,
    top_regressions: pd.DataFrame,
    top_improvements: pd.DataFrame,
    threshold_percent: float,
    min_samples: int,
) -> dict[str, Any]:
    classification_counts = (
        metric_comparisons["classification"].value_counts().sort_index().to_dict()
        if not metric_comparisons.empty
        else {}
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "analysis_scope": "all retained aggregated benchmark results under auto/parsed",
        "settings": {
            "change_threshold_percent": threshold_percent,
            "min_samples": min_samples,
        },
        "inputs": {
            "count": len(_unique_paths(input_files)),
            "skipped": skipped_inputs,
        },
        "records": {
            "analysis_records": int(len(analysis_records)),
            "sample_statistics": int(len(sample_statistics)),
            "metric_comparisons": int(len(metric_comparisons)),
            "top_regressions": int(len(top_regressions)),
            "top_improvements": int(len(top_improvements)),
        },
        "coverage": {
            "suites": sorted(analysis_records["suite_name"].dropna().astype(str).unique().tolist())
            if not analysis_records.empty
            else [],
            "compiler_versions": sorted(
                analysis_records["compiler_version"].dropna().astype(str).unique().tolist()
            )
            if not analysis_records.empty
            else [],
            "labels": sorted(analysis_records["label"].dropna().astype(str).unique().tolist())
            if not analysis_records.empty
            else [],
            "samples": sorted(analysis_records["sample"].dropna().astype(str).unique().tolist())
            if not analysis_records.empty
            else [],
        },
        "classification_counts": classification_counts,
    }

