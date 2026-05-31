#!/usr/bin/env python3

import argparse
import json
import sys
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from workflow.lib.common import load_config
from workflow.lib.regression_analysis import METRICS
from workflow.lib.reporting import read_table, write_table
from workflow.lib.statistics import (
    build_sample_observations,
    build_statistical_summary,
    compare_sample_groups,
    summarize_sample_group,
)


AGGREGATED_FILENAME = "benchmark_records_aggregated.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare baseline and candidate sample groups with statistical summaries."
    )
    parser.add_argument("--config-file", default=str(REPO_ROOT / "config.yml"), help="Workflow config file.")
    parser.add_argument(
        "--baseline-experiment",
        action="append",
        default=[],
        help="Baseline experiment_id under <project.base_dir>/parsed. May be repeated.",
    )
    parser.add_argument(
        "--candidate-experiment",
        action="append",
        default=[],
        help="Candidate experiment_id under <project.base_dir>/parsed. May be repeated.",
    )
    parser.add_argument(
        "--baseline-file",
        action="append",
        default=[],
        help="Baseline aggregated .csv or .parquet file. May be repeated.",
    )
    parser.add_argument(
        "--candidate-file",
        action="append",
        default=[],
        help="Candidate aggregated .csv or .parquet file. May be repeated.",
    )
    parser.add_argument("--output-dir", required=True, help="Directory for stage 6C statistical outputs.")
    parser.add_argument(
        "--threshold-percent",
        type=float,
        default=5.0,
        help="Default absolute percentage threshold for reporting changes.",
    )
    parser.add_argument(
        "--metric-threshold",
        action="append",
        default=[],
        metavar="METRIC=PERCENT",
        help="Override the threshold for one metric. May be repeated.",
    )
    parser.add_argument("--alpha", type=float, default=0.05, help="Significance threshold for p-values.")
    parser.add_argument(
        "--min-samples",
        type=int,
        default=3,
        help="Minimum samples per group required before a change can be marked reliable.",
    )
    return parser.parse_args()


def _resolve_base_dir(config_file: Path) -> Path:
    config = load_config(config_file)
    return Path(config["project"]["base_dir"]).expanduser().resolve()


def _resolve_inputs(
    base_dir: Path,
    experiment_ids: list[str],
    input_files: list[str],
    role: str,
) -> list[Path]:
    paths = [base_dir / "parsed" / experiment_id / AGGREGATED_FILENAME for experiment_id in experiment_ids]
    paths.extend(Path(input_file).expanduser() for input_file in input_files)

    if not paths:
        raise ValueError(f"At least one {role} experiment or file is required.")

    resolved_paths = [path.resolve() for path in paths]
    missing = [str(path) for path in resolved_paths if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing {role} aggregated table(s): {', '.join(missing)}")
    return resolved_paths


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


def _read_sources(paths: list[Path]) -> list[tuple[str, pd.DataFrame]]:
    return [(str(path), read_table(path)) for path in paths]


def _rank_changes(comparisons, classification: str):
    selected = comparisons[comparisons["classification"] == classification].copy()
    selected["magnitude_percent"] = selected["relative_delta_percent"].abs()
    return selected.sort_values("magnitude_percent", ascending=False).drop(columns=["magnitude_percent"])


def main() -> int:
    args = parse_args()
    config_file = Path(args.config_file).expanduser().resolve()
    base_dir = _resolve_base_dir(config_file)
    metric_thresholds = _parse_metric_thresholds(args.metric_threshold)

    baseline_paths = _resolve_inputs(base_dir, args.baseline_experiment, args.baseline_file, "baseline")
    candidate_paths = _resolve_inputs(base_dir, args.candidate_experiment, args.candidate_file, "candidate")

    baseline_observations = build_sample_observations(_read_sources(baseline_paths), "baseline")
    candidate_observations = build_sample_observations(_read_sources(candidate_paths), "candidate")
    observations = pd.concat([baseline_observations, candidate_observations], ignore_index=True)

    baseline_stats = summarize_sample_group(baseline_observations, "baseline")
    candidate_stats = summarize_sample_group(candidate_observations, "candidate")
    sample_statistics = pd.concat([baseline_stats, candidate_stats], ignore_index=True)

    comparisons = compare_sample_groups(
        baseline_stats,
        candidate_stats,
        threshold_percent=args.threshold_percent,
        metric_thresholds=metric_thresholds,
        alpha=args.alpha,
        min_samples=args.min_samples,
    )

    output_dir = Path(args.output_dir).expanduser().resolve()
    observations_path = write_table(observations, output_dir / "sample_observations.csv")
    statistics_path = write_table(sample_statistics, output_dir / "sample_statistics.csv")
    comparison_path = write_table(comparisons, output_dir / "statistical_comparison.csv")
    reliable_regressions_path = write_table(
        _rank_changes(comparisons, "reliable_regression"),
        output_dir / "reliable_regressions.csv",
    )
    reliable_improvements_path = write_table(
        _rank_changes(comparisons, "reliable_improvement"),
        output_dir / "reliable_improvements.csv",
    )
    candidate_regressions_path = write_table(
        _rank_changes(comparisons, "candidate_regression"),
        output_dir / "candidate_regressions.csv",
    )
    candidate_improvements_path = write_table(
        _rank_changes(comparisons, "candidate_improvement"),
        output_dir / "candidate_improvements.csv",
    )

    summary = build_statistical_summary(
        comparisons,
        baseline_source_count=len(baseline_paths),
        candidate_source_count=len(candidate_paths),
        alpha=args.alpha,
        min_samples=args.min_samples,
    )
    summary["config_file"] = str(config_file)
    summary["base_dir"] = str(base_dir)
    summary["baseline_sources"] = [str(path) for path in baseline_paths]
    summary["candidate_sources"] = [str(path) for path in candidate_paths]
    summary["default_threshold_percent"] = args.threshold_percent
    summary["metric_thresholds"] = metric_thresholds
    summary_path = output_dir / "statistical_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(f"Wrote sample observations to {observations_path}")
    print(f"Wrote sample statistics to {statistics_path}")
    print(f"Wrote statistical comparison to {comparison_path}")
    print(f"Wrote reliable regressions to {reliable_regressions_path}")
    print(f"Wrote reliable improvements to {reliable_improvements_path}")
    print(f"Wrote candidate regressions to {candidate_regressions_path}")
    print(f"Wrote candidate improvements to {candidate_improvements_path}")
    print(f"Wrote statistical summary to {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
