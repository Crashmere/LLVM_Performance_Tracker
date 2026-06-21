from __future__ import annotations

from dataclasses import dataclass
from html import escape
from typing import Any

import pandas as pd


TOP_CHANGE_COLUMNS = [
    "suite_name",
    "metric",
    "baseline_compiler_version",
    "candidate_compiler_version",
    "baseline_mean",
    "candidate_mean",
    "normalized_change_percent",
    "classification",
    "evidence",
    "baseline_suite_version",
    "candidate_suite_version",
    "test_name",
]

COMPARISON_COLUMNS = [
    "suite_name",
    "metric",
    "baseline_compiler_version",
    "candidate_compiler_version",
    "baseline_observations",
    "candidate_observations",
    "baseline_mean",
    "candidate_mean",
    "normalized_change_percent",
    "classification",
    "evidence",
    "baseline_suite_version",
    "candidate_suite_version",
    "test_name",
]

SAMPLE_COLUMNS = [
    "suite_name",
    "suite_version",
    "compiler_version",
    "metric",
    "observations",
    "mean",
    "std",
    "cv",
    "ci95_low",
    "ci95_high",
    "test_name",
]

DETAIL_COLUMNS = [
    "experiment_id",
    "suite_name",
    "suite_version",
    "compiler_version",
    "label",
    "sample",
    "metric",
    "value",
    "source_observations",
    "test_name",
]


@dataclass(frozen=True)
class FilterControl:
    label: str
    column_index: int
    options: list[str]


@dataclass(frozen=True)
class TableView:
    table_id: str
    columns: list[str]
    rows: list[list[str]]
    search: bool
    filters: list[FilterControl]
    empty_message: str = "No rows available."

    @property
    def has_controls(self) -> bool:
        return self.search or bool(self.filters)


def build_table(
    df: pd.DataFrame,
    columns: list[str],
    table_id: str,
    *,
    search: bool = False,
    filters: list[str] | None = None,
) -> TableView:
    available = [column for column in columns if column in df.columns]
    filter_columns = [column for column in (filters or []) if column in available]
    controls = _build_filter_controls(df, available, filter_columns)
    rows = _build_rows(df, available)

    return TableView(
        table_id=table_id,
        columns=available,
        rows=rows,
        search=search,
        filters=controls,
    )


def classification_class(name: str) -> str:
    if "regression" in name:
        return "regression"
    if "improvement" in name:
        return "improvement"
    if "stable" in name:
        return "stable"
    return "neutral"


def classification_color(name: str) -> str:
    if "regression" in name:
        return "rgba(184, 69, 56, 0.85)"
    if "improvement" in name:
        return "rgba(26, 127, 80, 0.85)"
    return "rgba(96, 113, 128, 0.75)"


def shorten(value: str, limit: int = 64) -> str:
    if len(value) <= limit:
        return value
    return "..." + value[-(limit - 3) :]


def _build_filter_controls(
    df: pd.DataFrame,
    available_columns: list[str],
    filter_columns: list[str],
) -> list[FilterControl]:
    controls = []
    for column in filter_columns:
        values = sorted(str(value) for value in df[column].dropna().unique())
        controls.append(
            FilterControl(
                label=column,
                column_index=available_columns.index(column),
                options=values,
            )
        )
    return controls


def _build_rows(df: pd.DataFrame, columns: list[str]) -> list[list[str]]:
    if df.empty or not columns:
        return []

    rows = []
    for _, row in df[columns].iterrows():
        rows.append([_format_cell(column, row[column]) for column in columns])
    return rows


def _format_cell(column: str, value: Any) -> str:
    if pd.isna(value):
        return ""
    if column == "normalized_change_percent":
        text = f"{float(value):+.2f}%"
        klass = "improvement" if float(value) > 0 else "regression" if float(value) < 0 else "stable"
        return f'<span class="change {klass}">{escape(text)}</span>'
    if column == "raw_change_percent":
        return escape(f"{float(value):+.2f}%")
    if column == "cv":
        try:
            return escape(f"{float(value):.8g}")
        except (TypeError, ValueError):
            return escape(str(value))
    if column in {"baseline_mean", "candidate_mean", "mean", "std", "ci95_low", "ci95_high", "value"}:
        try:
            return escape(f"{float(value):.6g}")
        except (TypeError, ValueError):
            return escape(str(value))
    if column == "classification":
        klass = classification_class(str(value))
        return f'<span class="badge {klass}">{escape(str(value))}</span>'
    if column == "test_name":
        return f'<span title="{escape(str(value))}">{escape(shorten(str(value), 90))}</span>'
    return escape(str(value))
