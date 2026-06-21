from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class AnalysisReportData:
    analysis_dir: Path
    summary: dict[str, Any]
    analysis_records: pd.DataFrame
    sample_statistics: pd.DataFrame
    metric_comparisons: pd.DataFrame
    top_regressions: pd.DataFrame
    top_improvements: pd.DataFrame


REQUIRED_TABLES = {
    "analysis_records": "analysis_records.csv",
    "sample_statistics": "sample_statistics.csv",
    "metric_comparisons": "metric_comparisons.csv",
    "top_regressions": "top_regressions.csv",
    "top_improvements": "top_improvements.csv",
}


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Expected analysis table does not exist: {path}")
    return pd.read_csv(path)


def _read_summary(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Expected analysis summary does not exist: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_analysis_report_data(analysis_dir: Path | str) -> AnalysisReportData:
    base = Path(analysis_dir).expanduser().resolve()
    tables = {name: _read_csv(base / filename) for name, filename in REQUIRED_TABLES.items()}
    summary = _read_summary(base / "analysis_summary.json")

    return AnalysisReportData(
        analysis_dir=base,
        summary=summary,
        analysis_records=tables["analysis_records"],
        sample_statistics=tables["sample_statistics"],
        metric_comparisons=tables["metric_comparisons"],
        top_regressions=tables["top_regressions"],
        top_improvements=tables["top_improvements"],
    )


def count_unique(df: pd.DataFrame, column: str) -> int:
    if column not in df.columns:
        return 0
    return int(df[column].dropna().nunique())


def top_rows(df: pd.DataFrame, limit: int) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    return df.head(limit).copy()


def top_cv_rows(sample_statistics: pd.DataFrame, limit: int = 20) -> pd.DataFrame:
    if sample_statistics.empty or "cv" not in sample_statistics.columns:
        return sample_statistics.head(0).copy()

    data = sample_statistics.copy()
    data["cv"] = pd.to_numeric(data["cv"], errors="coerce")
    data = data.dropna(subset=["cv"])
    data = data[data["cv"] > 0]
    return data.sort_values("cv", ascending=False).head(limit).copy()


def compiler_pair_metric_summary(metric_comparisons: pd.DataFrame) -> pd.DataFrame:
    group_columns = [
        "baseline_compiler_version",
        "candidate_compiler_version",
        "metric",
        "metric_display_name",
    ]
    output_columns = [
        "compiler_pair",
        *group_columns,
        "row_count",
        "changed_count",
        "stable_count",
        "regression_count",
        "improvement_count",
        "candidate_change_count",
        "reliable_change_count",
        "median_normalized_change_percent",
        "mean_normalized_change_percent",
    ]
    if metric_comparisons.empty or not set(group_columns).issubset(metric_comparisons.columns):
        return pd.DataFrame(columns=output_columns)

    data = _comparison_rows_with_flags(metric_comparisons)
    summary = _summarize_comparison_groups(data, group_columns)
    return summary[output_columns].sort_values(["baseline_compiler_version", "candidate_compiler_version", "metric"])


def compiler_pair_suite_metric_summary(metric_comparisons: pd.DataFrame) -> pd.DataFrame:
    group_columns = [
        "baseline_compiler_version",
        "candidate_compiler_version",
        "suite_name",
        "metric",
        "metric_display_name",
    ]
    output_columns = [
        "compiler_pair",
        *group_columns,
        "row_count",
        "changed_count",
        "stable_count",
        "regression_count",
        "improvement_count",
        "candidate_change_count",
        "reliable_change_count",
        "median_normalized_change_percent",
        "mean_normalized_change_percent",
    ]
    if metric_comparisons.empty or not set(group_columns).issubset(metric_comparisons.columns):
        return pd.DataFrame(columns=output_columns)

    data = _comparison_rows_with_flags(metric_comparisons)
    summary = _summarize_comparison_groups(data, group_columns)
    return summary[output_columns].sort_values(
        ["baseline_compiler_version", "candidate_compiler_version", "suite_name", "metric"]
    )


def top_change_rows_with_context(
    top_regressions: pd.DataFrame,
    top_improvements: pd.DataFrame,
    *,
    limit_each: int = 10,
) -> pd.DataFrame:
    regressions = top_regressions.head(limit_each).copy()
    improvements = top_improvements.head(limit_each).copy()
    combined = pd.concat([improvements, regressions], ignore_index=True)
    if combined.empty:
        return combined

    if "normalized_change_percent" in combined.columns:
        combined["normalized_change_percent"] = pd.to_numeric(combined["normalized_change_percent"], errors="coerce")
        combined = combined.sort_values("normalized_change_percent", ascending=True)

    suite = combined.get("suite_name", pd.Series(["unknown"] * len(combined), index=combined.index)).astype(str)
    metric = combined.get("metric", pd.Series(["metric"] * len(combined), index=combined.index)).astype(str)
    test_names = combined.get("test_name", pd.Series(["unknown"] * len(combined), index=combined.index)).astype(str)
    combined["suite_aware_label"] = [
        f"{suite_name} | {metric_name} | {short_test_name(test_name, 68)}"
        for suite_name, metric_name, test_name in zip(suite, metric, test_names, strict=False)
    ]
    return combined


def noise_plot_rows(sample_statistics: pd.DataFrame, limit: int = 20) -> pd.DataFrame:
    rows = top_cv_rows(sample_statistics, limit)
    if rows.empty:
        return rows

    rows = rows.reset_index(drop=True)
    rows["rank"] = rows.index + 1
    rows["cv_percent"] = pd.to_numeric(rows["cv"], errors="coerce") * 100.0
    rows["display_name"] = rows.apply(_sample_noise_label, axis=1)
    return rows


def short_test_name(value: str, limit: int = 64) -> str:
    if len(value) <= limit:
        return value
    return "..." + value[-(limit - 3) :]


def suite_metric_summary(metric_comparisons: pd.DataFrame) -> pd.DataFrame:
    columns = ["suite_name", "metric", "classification", "count"]
    if metric_comparisons.empty:
        return pd.DataFrame(columns=columns)
    return (
        metric_comparisons.groupby(["suite_name", "metric", "classification"], dropna=False)
        .size()
        .reset_index(name="count")
        .sort_values(["suite_name", "metric", "classification"])
    )


def _comparison_rows_with_flags(metric_comparisons: pd.DataFrame) -> pd.DataFrame:
    data = metric_comparisons.copy()
    data["normalized_change_percent"] = pd.to_numeric(data["normalized_change_percent"], errors="coerce")
    data["classification"] = data["classification"].astype(str)
    data["compiler_pair"] = (
        data["baseline_compiler_version"].astype(str)
        + " -> "
        + data["candidate_compiler_version"].astype(str)
    )
    data["is_stable"] = data["classification"].eq("stable")
    data["is_regression"] = data["classification"].str.endswith("regression", na=False)
    data["is_improvement"] = data["classification"].str.endswith("improvement", na=False)
    data["is_candidate_change"] = data["classification"].str.startswith("candidate_", na=False)
    data["is_reliable_change"] = data["classification"].str.startswith("reliable_", na=False)
    data["is_changed"] = ~data["is_stable"]
    return data


def _summarize_comparison_groups(data: pd.DataFrame, group_columns: list[str]) -> pd.DataFrame:
    grouped = data.groupby(group_columns, dropna=False)
    summary = grouped.agg(
        compiler_pair=("compiler_pair", "first"),
        row_count=("classification", "size"),
        changed_count=("is_changed", "sum"),
        stable_count=("is_stable", "sum"),
        regression_count=("is_regression", "sum"),
        improvement_count=("is_improvement", "sum"),
        candidate_change_count=("is_candidate_change", "sum"),
        reliable_change_count=("is_reliable_change", "sum"),
        median_normalized_change_percent=("normalized_change_percent", "median"),
        mean_normalized_change_percent=("normalized_change_percent", "mean"),
    )
    return summary.reset_index()


def _sample_noise_label(row: pd.Series) -> str:
    compiler = str(row.get("compiler_version", "unknown"))
    suite = str(row.get("suite_name", "suite"))
    metric = str(row.get("metric", "metric"))
    test_name = short_test_name(str(row.get("test_name", "unknown")), 64)
    return f"{compiler} | {suite} | {metric} | {test_name}"
