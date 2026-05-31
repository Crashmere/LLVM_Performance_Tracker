from dataclasses import dataclass
from typing import Any

import pandas as pd


MATCH_KEYS = ["suite_name", "suite_version", "test_name"]


@dataclass(frozen=True)
class MetricDefinition:
    name: str
    column: str
    better_when: str


METRICS = {
    "exec_time": MetricDefinition("exec_time", "exec_time_mean", "lower"),
    "compile_time": MetricDefinition("compile_time", "compile_time_mean", "lower"),
    "binary_size": MetricDefinition("binary_size", "binary_size_first", "lower"),
    "bandwidth_gib": MetricDefinition("bandwidth_gib", "bandwidth_gib_mean", "higher"),
    "flops_gflops": MetricDefinition("flops_gflops", "flops_gflops_mean", "higher"),
}


def _require_columns(df: pd.DataFrame, columns: list[str], source_name: str) -> None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise ValueError(f"{source_name} is missing required columns: {', '.join(missing)}")


def _validate_unique_records(df: pd.DataFrame, source_name: str) -> None:
    duplicates = df[df.duplicated(MATCH_KEYS, keep=False)]
    if duplicates.empty:
        return

    example = duplicates[MATCH_KEYS].iloc[0].to_dict()
    raise ValueError(
        f"{source_name} contains duplicate aggregated records for {example}. "
        "Aggregate repeated samples before running the stage 6A comparison."
    )


def _classify_change(
    baseline_value: float,
    candidate_value: float,
    relative_delta_percent: float | None,
    metric: MetricDefinition,
    threshold_percent: float,
) -> str:
    if candidate_value == baseline_value:
        return "unchanged"

    if relative_delta_percent is None:
        return "unclassified"

    if abs(relative_delta_percent) < threshold_percent:
        return "within_threshold"

    candidate_increased = relative_delta_percent > 0
    improved = candidate_increased if metric.better_when == "higher" else not candidate_increased
    return "improvement" if improved else "regression"


def compare_aggregated_records(
    baseline_df: pd.DataFrame,
    candidate_df: pd.DataFrame,
    threshold_percent: float = 5.0,
    metric_thresholds: dict[str, float] | None = None,
) -> pd.DataFrame:
    if threshold_percent < 0:
        raise ValueError("threshold_percent must be zero or greater.")

    metric_thresholds = metric_thresholds or {}
    unknown_metrics = sorted(set(metric_thresholds) - set(METRICS))
    if unknown_metrics:
        raise ValueError(f"Unknown metrics in threshold configuration: {', '.join(unknown_metrics)}")
    if any(value < 0 for value in metric_thresholds.values()):
        raise ValueError("Metric thresholds must be zero or greater.")

    required_columns = [*MATCH_KEYS, "compiler_version"]
    _require_columns(baseline_df, required_columns, "baseline input")
    _require_columns(candidate_df, required_columns, "candidate input")
    _validate_unique_records(baseline_df, "baseline input")
    _validate_unique_records(candidate_df, "candidate input")

    joined = baseline_df.merge(
        candidate_df,
        on=MATCH_KEYS,
        how="inner",
        suffixes=("_baseline", "_candidate"),
        validate="one_to_one",
    )

    rows: list[dict[str, Any]] = []
    for record in joined.to_dict(orient="records"):
        for metric in METRICS.values():
            baseline_column = f"{metric.column}_baseline"
            candidate_column = f"{metric.column}_candidate"
            if baseline_column not in record or candidate_column not in record:
                continue

            baseline_value = record[baseline_column]
            candidate_value = record[candidate_column]
            if pd.isna(baseline_value) or pd.isna(candidate_value):
                continue

            baseline_value = float(baseline_value)
            candidate_value = float(candidate_value)
            absolute_delta = candidate_value - baseline_value
            relative_delta_percent = None
            if baseline_value != 0:
                relative_delta_percent = absolute_delta / abs(baseline_value) * 100

            metric_threshold = metric_thresholds.get(metric.name, threshold_percent)
            rows.append(
                {
                    **{key: record[key] for key in MATCH_KEYS},
                    "metric": metric.name,
                    "better_when": metric.better_when,
                    "baseline_compiler_version": record["compiler_version_baseline"],
                    "candidate_compiler_version": record["compiler_version_candidate"],
                    "baseline_value": baseline_value,
                    "candidate_value": candidate_value,
                    "absolute_delta": absolute_delta,
                    "relative_delta_percent": relative_delta_percent,
                    "threshold_percent": metric_threshold,
                    "classification": _classify_change(
                        baseline_value,
                        candidate_value,
                        relative_delta_percent,
                        metric,
                        metric_threshold,
                    ),
                }
            )

    columns = [
        *MATCH_KEYS,
        "metric",
        "better_when",
        "baseline_compiler_version",
        "candidate_compiler_version",
        "baseline_value",
        "candidate_value",
        "absolute_delta",
        "relative_delta_percent",
        "threshold_percent",
        "classification",
    ]
    return pd.DataFrame(rows, columns=columns)


def build_comparison_summary(
    comparisons: pd.DataFrame,
    baseline_df: pd.DataFrame,
    candidate_df: pd.DataFrame,
    baseline_source: str,
    candidate_source: str,
) -> dict[str, Any]:
    classifications = comparisons["classification"].value_counts().to_dict()
    matched_records = comparisons[MATCH_KEYS].drop_duplicates()
    record_matches = baseline_df[MATCH_KEYS].merge(
        candidate_df[MATCH_KEYS],
        on=MATCH_KEYS,
        how="outer",
        indicator=True,
        validate="one_to_one",
    )
    ranked_columns = [
        *MATCH_KEYS,
        "metric",
        "relative_delta_percent",
    ]

    def top_changes(classification: str) -> list[dict[str, Any]]:
        selected = comparisons[comparisons["classification"] == classification].copy()
        selected["magnitude_percent"] = selected["relative_delta_percent"].abs()
        ranked = selected.sort_values("magnitude_percent", ascending=False).head(10)
        return ranked[ranked_columns].to_dict(orient="records")

    return {
        "analysis_stage": "6A",
        "analysis_scope": "candidate changes without statistical significance testing",
        "baseline_source": baseline_source,
        "candidate_source": candidate_source,
        "baseline_record_count": len(baseline_df),
        "candidate_record_count": len(candidate_df),
        "matched_record_count": len(matched_records),
        "baseline_only_record_count": int((record_matches["_merge"] == "left_only").sum()),
        "candidate_only_record_count": int((record_matches["_merge"] == "right_only").sum()),
        "matched_metric_count": len(comparisons),
        "classification_counts": {
            classification: int(classifications.get(classification, 0))
            for classification in [
                "regression",
                "improvement",
                "within_threshold",
                "unchanged",
                "unclassified",
            ]
        },
        "top_regressions": top_changes("regression"),
        "top_improvements": top_changes("improvement"),
    }
