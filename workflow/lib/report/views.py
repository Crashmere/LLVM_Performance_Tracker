from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
from jinja2 import Environment, FileSystemLoader, select_autoescape

from workflow.lib.report.data import AnalysisReportData, top_cv_rows, top_rows
from workflow.lib.report.figures import build_figures, render_figure_html
from workflow.lib.report.tables import (
    COMPARISON_COLUMNS,
    DETAIL_COLUMNS,
    SAMPLE_COLUMNS,
    TOP_CHANGE_COLUMNS,
    build_table,
    classification_class,
)


WORKFLOW_DIR = Path(__file__).resolve().parents[2]
TEMPLATE_DIR = WORKFLOW_DIR / "templates"
STATIC_DIR = WORKFLOW_DIR / "static"


@dataclass(frozen=True)
class FigureView:
    key: str
    title: str
    description: str
    html: str


def render_analysis_report(data: AnalysisReportData, output_path: Path | str) -> str:
    output = Path(output_path)
    environment = _template_environment()
    template = environment.get_template("analysis_report.html.j2")
    return template.render(**_build_context(data, output))


def _build_context(data: AnalysisReportData, output: Path) -> dict[str, Any]:
    figure_views = _figure_views(data)
    return {
        "css": _read_static("report.css"),
        "javascript": _read_static("report.js"),
        "csv_links": _csv_links(data.analysis_dir, output.parent),
        "nav_items": [
            {"href": "#overview", "label": "Overview"},
            {"href": "#trends", "label": "Trends"},
            {"href": "#suites", "label": "Suites"},
            {"href": "#top-changes", "label": "Top Changes"},
            {"href": "#noise", "label": "Noise"},
            {"href": "#data", "label": "Data"},
        ],
        "overview": _overview(data),
        "classification_figure": figure_views["classification_counts"],
        "compiler_pair_figure": figure_views["compiler_pair_matrix"],
        "suite_contribution_figure": figure_views["suite_metric_matrix"],
        "largest_changes_figure": figure_views["largest_changes"],
        "sample_noise_figure": figure_views["sample_noise"],
        "suite_cards": _suite_cards(data),
        "top_regressions_table": build_table(
            top_rows(data.top_regressions, 50),
            TOP_CHANGE_COLUMNS,
            "top-regressions",
            search=True,
            filters=["suite_name", "metric", "classification", "evidence"],
        ),
        "top_improvements_table": build_table(
            top_rows(data.top_improvements, 50),
            TOP_CHANGE_COLUMNS,
            "top-improvements",
            search=True,
            filters=["suite_name", "metric", "classification", "evidence"],
        ),
        "comparison_table": build_table(
            _comparison_preview(data),
            COMPARISON_COLUMNS,
            "metric-comparisons",
            search=True,
            filters=[
                "suite_name",
                "metric",
                "baseline_compiler_version",
                "candidate_compiler_version",
                "classification",
                "evidence",
            ],
        ),
        "sample_table": build_table(
            top_cv_rows(data.sample_statistics, 100),
            SAMPLE_COLUMNS,
            "sample-statistics",
            search=True,
            filters=["suite_name", "compiler_version", "metric"],
        ),
        "detail_table": build_table(
            data.analysis_records.head(200),
            DETAIL_COLUMNS,
            "analysis-records",
            search=True,
            filters=["suite_name", "compiler_version", "label", "sample", "metric"],
        ),
    }


def _template_environment() -> Environment:
    return Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(["html", "j2"]),
    )


def _read_static(filename: str) -> str:
    return (STATIC_DIR / filename).read_text(encoding="utf-8")


def _csv_links(analysis_dir: Path, output_dir: Path) -> dict[str, str]:
    links: dict[str, str] = {}
    for filename in [
        "analysis_records.csv",
        "sample_statistics.csv",
        "metric_comparisons.csv",
        "top_regressions.csv",
        "top_improvements.csv",
        "analysis_summary.json",
    ]:
        target = analysis_dir / filename
        links[filename] = os.path.relpath(target, output_dir)
    return links


def _overview(data: AnalysisReportData) -> dict[str, Any]:
    records = data.summary.get("records", {})
    inputs = data.summary.get("inputs", {})
    coverage = data.summary.get("coverage", {})
    settings = data.summary.get("settings", {})

    return {
        "generated_at": data.summary.get("generated_at", "unknown"),
        "change_threshold_percent": settings.get("change_threshold_percent", "unknown"),
        "min_samples": settings.get("min_samples", "unknown"),
        "compiler_versions": _join_values(coverage.get("compiler_versions", [])),
        "suite_versions": _join_values(coverage.get("suite_versions", [])),
        "labels": _join_values(coverage.get("labels", []), limit=8),
        "classification_pills": _classification_pills(data.summary.get("classification_counts", {})),
        "cards": [
            _card("Input files", inputs.get("count", 0), "Parsed CSV files included"),
            _card("Analysis records", records.get("analysis_records", len(data.analysis_records)), "Metric observations"),
            _card("Sample groups", records.get("sample_statistics", len(data.sample_statistics)), "Grouped statistics"),
            _card("LLVM comparisons", records.get("metric_comparisons", len(data.metric_comparisons)), "Compiler version pairs"),
            _card("Suites", len(coverage.get("suites", [])), _join_values(coverage.get("suites", []))),
            _card("Samples", len(coverage.get("samples", [])), _join_values(coverage.get("samples", []))),
        ],
    }


def _figure_views(data: AnalysisReportData) -> dict[str, FigureView]:
    views: dict[str, FigureView] = {}
    include_plotly = True
    for spec in build_figures(data):
        views[spec.key] = FigureView(
            key=spec.key,
            title=spec.title,
            description=spec.description,
            html=render_figure_html(spec.figure, include_plotly=include_plotly),
        )
        include_plotly = False
    return views


def _suite_cards(data: AnalysisReportData) -> list[dict[str, Any]]:
    comparisons_df = data.metric_comparisons
    if comparisons_df.empty or "suite_name" not in comparisons_df.columns:
        return []

    cards = []
    for suite in sorted(comparisons_df["suite_name"].dropna().astype(str).unique()):
        comparisons = comparisons_df[comparisons_df["suite_name"].astype(str) == suite]
        samples = _sample_rows_for_suite(data.sample_statistics, suite)
        regressions = _classification_rows(comparisons, "regression")
        improvements = _classification_rows(comparisons, "improvement")
        metrics = _join_values(sorted(comparisons["metric"].dropna().astype(str).unique())) if "metric" in comparisons else "none"

        cards.append(
            {
                "name": suite,
                "metrics": metrics,
                "cards": [
                    _card("Comparisons", len(comparisons), "comparison rows"),
                    _card("Regressions", len(regressions), "candidate or reliable"),
                    _card("Improvements", len(improvements), "candidate or reliable"),
                    _card("Sample groups", len(samples), "statistical groups"),
                ],
            }
        )
    return cards


def _sample_rows_for_suite(sample_statistics: pd.DataFrame, suite: str) -> pd.DataFrame:
    if sample_statistics.empty or "suite_name" not in sample_statistics.columns:
        return sample_statistics.head(0)
    return sample_statistics[sample_statistics["suite_name"].astype(str) == suite]


def _classification_rows(comparisons: pd.DataFrame, suffix: str) -> pd.DataFrame:
    if comparisons.empty or "classification" not in comparisons.columns:
        return comparisons.head(0)
    return comparisons[comparisons["classification"].astype(str).str.endswith(suffix, na=False)]


def _comparison_preview(data: AnalysisReportData) -> pd.DataFrame:
    comparisons = data.metric_comparisons.copy()
    if "normalized_change_percent" in comparisons.columns:
        comparisons["abs_change"] = pd.to_numeric(comparisons["normalized_change_percent"], errors="coerce").abs()
        comparisons = comparisons.sort_values("abs_change", ascending=False).drop(columns=["abs_change"])
    return comparisons.head(500)


def _card(title: str, value: Any, detail: Any) -> dict[str, Any]:
    return {
        "title": title,
        "value": value,
        "detail": detail,
    }


def _classification_pills(counts: dict[str, Any]) -> list[dict[str, str]]:
    if not counts:
        return [{"label": "No classifications", "kind": "neutral"}]
    return [
        {
            "label": f"{name}: {value}",
            "kind": classification_class(str(name)),
        }
        for name, value in sorted(counts.items())
    ]


def _join_values(values: Any, *, limit: int | None = None) -> str:
    items = [str(value) for value in values]
    if not items:
        return "none"

    selected = items[:limit] if limit is not None else items
    text = ", ".join(selected)
    if limit is not None and len(items) > limit:
        text += ", ..."
    return text
