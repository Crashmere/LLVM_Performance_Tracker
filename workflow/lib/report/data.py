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

