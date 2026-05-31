#!/usr/bin/env python3

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from workflow.lib.common import load_config
from workflow.lib.regression_analysis import (
    METRICS,
    build_comparison_summary,
    compare_aggregated_records,
)
from workflow.lib.reporting import read_table, write_table


AGGREGATED_FILENAME = "benchmark_records_aggregated.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare two aggregated benchmark result tables and identify candidate performance changes."
    )
    parser.add_argument("--config-file", default=str(REPO_ROOT / "config.yml"), help="Workflow config file.")
    baseline = parser.add_mutually_exclusive_group(required=True)
    baseline.add_argument("--baseline-file", help="Baseline aggregated .csv or .parquet table.")
    baseline.add_argument("--baseline-experiment", help="Baseline experiment_id under <project.base_dir>/parsed.")
    candidate = parser.add_mutually_exclusive_group(required=True)
    candidate.add_argument("--candidate-file", help="Candidate aggregated .csv or .parquet table.")
    candidate.add_argument("--candidate-experiment", help="Candidate experiment_id under <project.base_dir>/parsed.")
    parser.add_argument("--output-dir", required=True, help="Directory for stage 6A analysis outputs.")
    parser.add_argument(
        "--threshold-percent",
        type=float,
        default=5.0,
        help="Default absolute percentage threshold for reporting regressions and improvements.",
    )
    parser.add_argument(
        "--metric-threshold",
        action="append",
        default=[],
        metavar="METRIC=PERCENT",
        help="Override the threshold for one metric. May be repeated.",
    )
    return parser.parse_args()


def _resolve_base_dir(config_file: Path) -> Path:
    config = load_config(config_file)
    return Path(config["project"]["base_dir"]).expanduser().resolve()


def _resolve_input_path(
    base_dir: Path,
    input_file: str | None,
    experiment_id: str | None,
    role: str,
) -> Path:
    if input_file:
        path = Path(input_file).expanduser()
    elif experiment_id:
        path = base_dir / "parsed" / experiment_id / AGGREGATED_FILENAME
    else:
        raise ValueError(f"Missing {role} input.")

    path = path.resolve()
    if not path.exists():
        raise FileNotFoundError(f"Expected {role} aggregated table does not exist: {path}")
    return path


def _parse_metric_thresholds(raw_thresholds: list[str]) -> dict[str, float]:
    thresholds: dict[str, float] = {}
    for raw_threshold in raw_thresholds:
        metric, separator, raw_value = raw_threshold.partition("=")
        if not separator or not metric or not raw_value:
            raise ValueError(f"Expected --metric-threshold METRIC=PERCENT, got: {raw_threshold}")
        if metric not in METRICS:
            raise ValueError(f"Unknown metric {metric!r}. Choose from: {', '.join(sorted(METRICS))}")
        value = float(raw_value)
        if value < 0:
            raise ValueError(f"Threshold for {metric} must be zero or greater.")
        thresholds[metric] = value
    return thresholds


def _rank_changes(comparisons, classification: str):
    selected = comparisons[comparisons["classification"] == classification].copy()
    selected["magnitude_percent"] = selected["relative_delta_percent"].abs()
    return selected.sort_values("magnitude_percent", ascending=False).drop(columns=["magnitude_percent"])


def main() -> int:
    args = parse_args()
    config_file = Path(args.config_file).expanduser().resolve()
    base_dir = _resolve_base_dir(config_file)
    baseline_path = _resolve_input_path(base_dir, args.baseline_file, args.baseline_experiment, "baseline")
    candidate_path = _resolve_input_path(base_dir, args.candidate_file, args.candidate_experiment, "candidate")
    metric_thresholds = _parse_metric_thresholds(args.metric_threshold)

    baseline_df = read_table(baseline_path)
    candidate_df = read_table(candidate_path)
    comparisons = compare_aggregated_records(
        baseline_df,
        candidate_df,
        threshold_percent=args.threshold_percent,
        metric_thresholds=metric_thresholds,
    )

    output_dir = Path(args.output_dir).expanduser().resolve()
    comparison_path = write_table(comparisons, output_dir / "comparison.csv")
    regression_path = write_table(
        _rank_changes(comparisons, "regression"),
        output_dir / "regressions.csv",
    )
    improvement_path = write_table(
        _rank_changes(comparisons, "improvement"),
        output_dir / "improvements.csv",
    )
    summary = build_comparison_summary(
        comparisons,
        baseline_df=baseline_df,
        candidate_df=candidate_df,
        baseline_source=str(baseline_path),
        candidate_source=str(candidate_path),
    )
    summary["config_file"] = str(config_file)
    summary["base_dir"] = str(base_dir)
    summary["default_threshold_percent"] = args.threshold_percent
    summary["metric_thresholds"] = metric_thresholds
    summary_path = output_dir / "comparison_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"Wrote full comparison table to {comparison_path}")
    print(f"Wrote candidate regressions to {regression_path}")
    print(f"Wrote candidate improvements to {improvement_path}")
    print(f"Wrote comparison summary to {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
