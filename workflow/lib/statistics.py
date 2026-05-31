from math import erfc, sqrt
from typing import Any

import pandas as pd

from workflow.lib.regression_analysis import MATCH_KEYS, METRICS, MetricDefinition


STAT_KEYS = [*MATCH_KEYS, "metric"]
CONFIDENCE_Z = 1.96


def _metric_thresholds_with_default(
    threshold_percent: float,
    metric_thresholds: dict[str, float] | None,
) -> dict[str, float]:
    if threshold_percent < 0:
        raise ValueError("threshold_percent must be zero or greater.")
    metric_thresholds = metric_thresholds or {}
    unknown_metrics = sorted(set(metric_thresholds) - set(METRICS))
    if unknown_metrics:
        raise ValueError(f"Unknown metrics in threshold configuration: {', '.join(unknown_metrics)}")
    if any(value < 0 for value in metric_thresholds.values()):
        raise ValueError("Metric thresholds must be zero or greater.")
    return {metric_name: metric_thresholds.get(metric_name, threshold_percent) for metric_name in METRICS}


def _unique_join(values: pd.Series) -> str:
    unique_values = sorted(str(value) for value in values.dropna().unique())
    return ",".join(unique_values)


def _to_observations(df: pd.DataFrame, group_name: str, source_name: str) -> pd.DataFrame:
    required_columns = [*MATCH_KEYS, "compiler_version"]
    missing = [column for column in required_columns if column not in df.columns]
    if missing:
        raise ValueError(f"{source_name} is missing required columns: {', '.join(missing)}")

    rows: list[dict[str, Any]] = []
    for record in df.to_dict(orient="records"):
        for metric in METRICS.values():
            if metric.column not in record:
                continue
            value = record[metric.column]
            if pd.isna(value):
                continue
            rows.append(
                {
                    **{key: record[key] for key in MATCH_KEYS},
                    "metric": metric.name,
                    "group": group_name,
                    "source": source_name,
                    "compiler_version": record["compiler_version"],
                    "label": record.get("label", ""),
                    "sample": record.get("sample", ""),
                    "value": float(value),
                }
            )

    return pd.DataFrame(
        rows,
        columns=[
            *STAT_KEYS,
            "group",
            "source",
            "compiler_version",
            "label",
            "sample",
            "value",
        ],
    )


def build_sample_observations(
    sources: list[tuple[str, pd.DataFrame]],
    group_name: str,
) -> pd.DataFrame:
    observations = [_to_observations(df, group_name, source_name) for source_name, df in sources]
    if not observations:
        return pd.DataFrame()
    return pd.concat(observations, ignore_index=True)


def summarize_sample_group(observations: pd.DataFrame, group_name: str) -> pd.DataFrame:
    columns = [
        "group",
        "suite_name",
        "suite_version",
        "test_name",
        "metric",
        "compiler_versions",
        "labels",
        "samples",
        "n",
        "mean",
        "std",
        "cv_percent",
        "ci95_low",
        "ci95_high",
    ]
    if observations.empty:
        return pd.DataFrame(columns=columns)

    rows: list[dict[str, Any]] = []
    for keys, data in observations.groupby(STAT_KEYS, dropna=False):
        suite_name, suite_version, test_name, metric_name = keys
        values = data["value"].dropna()
        n = int(values.count())
        mean = float(values.mean()) if n else None
        std = float(values.std(ddof=1)) if n > 1 else None
        sem = std / sqrt(n) if std is not None and n > 0 else None
        ci_half_width = CONFIDENCE_Z * sem if sem is not None else None
        cv_percent = abs(std / mean * 100) if std is not None and mean not in (None, 0) else None

        rows.append(
            {
                "group": group_name,
                "suite_name": suite_name,
                "suite_version": suite_version,
                "test_name": test_name,
                "metric": metric_name,
                "compiler_versions": _unique_join(data["compiler_version"]),
                "labels": _unique_join(data["label"]),
                "samples": _unique_join(data["sample"]),
                "n": n,
                "mean": mean,
                "std": std,
                "cv_percent": cv_percent,
                "ci95_low": mean - ci_half_width if mean is not None and ci_half_width is not None else None,
                "ci95_high": mean + ci_half_width if mean is not None and ci_half_width is not None else None,
            }
        )

    return pd.DataFrame(rows, columns=columns)


def _welch_p_value(
    baseline_mean: float,
    baseline_std: float | None,
    baseline_n: int,
    candidate_mean: float,
    candidate_std: float | None,
    candidate_n: int,
) -> float | None:
    if (
        baseline_n < 2
        or candidate_n < 2
        or baseline_std is None
        or candidate_std is None
        or pd.isna(baseline_std)
        or pd.isna(candidate_std)
    ):
        return None

    baseline_var = baseline_std**2
    candidate_var = candidate_std**2
    standard_error = sqrt(baseline_var / baseline_n + candidate_var / candidate_n)
    difference = candidate_mean - baseline_mean

    if standard_error == 0:
        return 1.0 if difference == 0 else 0.0

    z_score = abs(difference) / standard_error
    return erfc(z_score / sqrt(2))


def _directional_classification(
    baseline_mean: float,
    candidate_mean: float,
    relative_delta_percent: float | None,
    metric: MetricDefinition,
    threshold_percent: float,
    p_value: float | None,
    alpha: float,
    min_samples: int,
    baseline_n: int,
    candidate_n: int,
) -> tuple[str, str]:
    if candidate_mean == baseline_mean:
        return "unchanged", "unchanged"
    if relative_delta_percent is None:
        return "unclassified", "zero_baseline"
    if abs(relative_delta_percent) < threshold_percent:
        return "within_threshold", "below_threshold"

    candidate_increased = relative_delta_percent > 0
    improved = candidate_increased if metric.better_when == "higher" else not candidate_increased
    direction = "improvement" if improved else "regression"

    if baseline_n < min_samples or candidate_n < min_samples or p_value is None:
        return f"candidate_{direction}", "insufficient_samples"
    if p_value <= alpha:
        return f"reliable_{direction}", "significant"
    return f"candidate_{direction}", "not_significant"


def compare_sample_groups(
    baseline_stats: pd.DataFrame,
    candidate_stats: pd.DataFrame,
    threshold_percent: float = 5.0,
    metric_thresholds: dict[str, float] | None = None,
    alpha: float = 0.05,
    min_samples: int = 2,
) -> pd.DataFrame:
    if not 0 < alpha < 1:
        raise ValueError("alpha must be greater than 0 and less than 1.")
    if min_samples < 1:
        raise ValueError("min_samples must be at least 1.")

    thresholds = _metric_thresholds_with_default(threshold_percent, metric_thresholds)
    joined = baseline_stats.merge(
        candidate_stats,
        on=STAT_KEYS,
        how="inner",
        suffixes=("_baseline", "_candidate"),
        validate="one_to_one",
    )

    columns = [
        *STAT_KEYS,
        "better_when",
        "baseline_compiler_versions",
        "candidate_compiler_versions",
        "baseline_labels",
        "candidate_labels",
        "baseline_samples",
        "candidate_samples",
        "baseline_n",
        "candidate_n",
        "baseline_mean",
        "candidate_mean",
        "baseline_std",
        "candidate_std",
        "baseline_cv_percent",
        "candidate_cv_percent",
        "baseline_ci95_low",
        "baseline_ci95_high",
        "candidate_ci95_low",
        "candidate_ci95_high",
        "absolute_delta",
        "relative_delta_percent",
        "threshold_percent",
        "alpha",
        "p_value",
        "statistical_evidence",
        "classification",
    ]
    rows: list[dict[str, Any]] = []
    for record in joined.to_dict(orient="records"):
        metric = METRICS[record["metric"]]
        baseline_mean = float(record["mean_baseline"])
        candidate_mean = float(record["mean_candidate"])
        absolute_delta = candidate_mean - baseline_mean
        relative_delta_percent = None
        if baseline_mean != 0:
            relative_delta_percent = absolute_delta / abs(baseline_mean) * 100

        p_value = _welch_p_value(
            baseline_mean=baseline_mean,
            baseline_std=record.get("std_baseline"),
            baseline_n=int(record["n_baseline"]),
            candidate_mean=candidate_mean,
            candidate_std=record.get("std_candidate"),
            candidate_n=int(record["n_candidate"]),
        )
        classification, statistical_evidence = _directional_classification(
            baseline_mean=baseline_mean,
            candidate_mean=candidate_mean,
            relative_delta_percent=relative_delta_percent,
            metric=metric,
            threshold_percent=thresholds[metric.name],
            p_value=p_value,
            alpha=alpha,
            min_samples=min_samples,
            baseline_n=int(record["n_baseline"]),
            candidate_n=int(record["n_candidate"]),
        )

        rows.append(
            {
                **{key: record[key] for key in STAT_KEYS},
                "better_when": metric.better_when,
                "baseline_compiler_versions": record["compiler_versions_baseline"],
                "candidate_compiler_versions": record["compiler_versions_candidate"],
                "baseline_labels": record["labels_baseline"],
                "candidate_labels": record["labels_candidate"],
                "baseline_samples": record["samples_baseline"],
                "candidate_samples": record["samples_candidate"],
                "baseline_n": int(record["n_baseline"]),
                "candidate_n": int(record["n_candidate"]),
                "baseline_mean": baseline_mean,
                "candidate_mean": candidate_mean,
                "baseline_std": record.get("std_baseline"),
                "candidate_std": record.get("std_candidate"),
                "baseline_cv_percent": record.get("cv_percent_baseline"),
                "candidate_cv_percent": record.get("cv_percent_candidate"),
                "baseline_ci95_low": record.get("ci95_low_baseline"),
                "baseline_ci95_high": record.get("ci95_high_baseline"),
                "candidate_ci95_low": record.get("ci95_low_candidate"),
                "candidate_ci95_high": record.get("ci95_high_candidate"),
                "absolute_delta": absolute_delta,
                "relative_delta_percent": relative_delta_percent,
                "threshold_percent": thresholds[metric.name],
                "alpha": alpha,
                "p_value": p_value,
                "statistical_evidence": statistical_evidence,
                "classification": classification,
            }
        )

    return pd.DataFrame(rows, columns=columns)


def build_statistical_summary(
    comparisons: pd.DataFrame,
    baseline_source_count: int,
    candidate_source_count: int,
    alpha: float,
    min_samples: int,
) -> dict[str, Any]:
    classifications = comparisons["classification"].value_counts().to_dict()

    def top_changes(classification: str) -> list[dict[str, Any]]:
        selected = comparisons[comparisons["classification"] == classification].copy()
        selected["magnitude_percent"] = selected["relative_delta_percent"].abs()
        ranked = selected.sort_values("magnitude_percent", ascending=False).head(10)
        return ranked[[*STAT_KEYS, "relative_delta_percent", "p_value"]].to_dict(orient="records")

    return {
        "analysis_stage": "6C",
        "analysis_scope": "sample group comparison with confidence intervals and significance evidence",
        "baseline_source_count": baseline_source_count,
        "candidate_source_count": candidate_source_count,
        "matched_metric_count": len(comparisons),
        "alpha": alpha,
        "min_samples": min_samples,
        "classification_counts": {
            classification: int(classifications.get(classification, 0))
            for classification in [
                "reliable_regression",
                "reliable_improvement",
                "candidate_regression",
                "candidate_improvement",
                "within_threshold",
                "unchanged",
                "unclassified",
            ]
        },
        "top_reliable_regressions": top_changes("reliable_regression"),
        "top_reliable_improvements": top_changes("reliable_improvement"),
        "top_candidate_regressions": top_changes("candidate_regression"),
        "top_candidate_improvements": top_changes("candidate_improvement"),
    }
