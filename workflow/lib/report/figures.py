from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import plotly.graph_objects as go

from workflow.lib.report.data import AnalysisReportData, suite_metric_summary, top_cv_rows
from workflow.lib.report.tables import classification_color, shorten


@dataclass(frozen=True)
class FigureSpec:
    key: str
    title: str
    description: str
    figure: go.Figure


def build_figures(data: AnalysisReportData) -> list[FigureSpec]:
    return [
        FigureSpec(
            "classification_counts",
            "Outcome Classification Counts",
            "How many comparison rows are stable, candidate changes, or reliable changes.",
            _classification_counts_figure(data),
        ),
        FigureSpec(
            "compiler_pair_matrix",
            "Change Distribution By LLVM Version Pair",
            "Changed rows grouped by baseline/candidate LLVM version pair and metric.",
            _compiler_pair_heatmap(data),
        ),
        FigureSpec(
            "suite_metric_matrix",
            "Change Distribution By Suite And Metric",
            "Counts of changed rows by suite and metric.",
            _suite_metric_heatmap(data),
        ),
        FigureSpec(
            "largest_changes",
            "Largest Normalized Changes",
            "Improvement bars point right; regression bars point left.",
            _top_change_figure(data),
        ),
        FigureSpec(
            "sample_noise",
            "Noisiest Sample Groups",
            "Coefficient of variation highlights tests with unstable measurements.",
            _sample_noise_figure(data),
        ),
    ]


def render_figure_html(figure: go.Figure, *, include_plotly: bool) -> str:
    return figure.to_html(full_html=False, include_plotlyjs=include_plotly)


def _classification_counts_figure(data: AnalysisReportData) -> go.Figure:
    counts = data.summary.get("classification_counts", {})
    labels = list(counts.keys())
    values = [counts[label] for label in labels]
    colors = [classification_color(label) for label in labels]
    fig = go.Figure(go.Bar(x=labels, y=values, marker_color=colors))
    fig.update_layout(template="plotly_white", height=360, margin=dict(l=40, r=20, t=40, b=80))
    fig.update_yaxes(title_text="Rows")
    return fig


def _top_change_figure(data: AnalysisReportData) -> go.Figure:
    regressions = data.top_regressions.head(10).copy()
    improvements = data.top_improvements.head(10).copy()
    combined = pd.concat([improvements, regressions], ignore_index=True)
    if combined.empty:
        return go.Figure()

    combined["normalized_change_percent"] = pd.to_numeric(combined["normalized_change_percent"], errors="coerce")
    combined["short_name"] = combined["test_name"].astype(str).map(shorten)
    colors = [
        "rgba(26, 127, 80, 0.85)" if value > 0 else "rgba(184, 69, 56, 0.85)"
        for value in combined["normalized_change_percent"].fillna(0)
    ]
    fig = go.Figure(
        go.Bar(
            x=combined["normalized_change_percent"],
            y=combined["short_name"],
            orientation="h",
            marker_color=colors,
            customdata=combined[
                [
                    "metric",
                    "baseline_compiler_version",
                    "candidate_compiler_version",
                    "classification",
                    "evidence",
                ]
            ],
            hovertemplate=(
                "%{y}<br>%{x:.2f}%<br>%{customdata[0]}<br>"
                "LLVM %{customdata[1]} -> %{customdata[2]}<br>"
                "%{customdata[3]} / %{customdata[4]}<extra></extra>"
            ),
        )
    )
    fig.update_layout(template="plotly_white", height=620, margin=dict(l=220, r=40, t=30, b=50))
    fig.update_xaxes(title_text="Normalized change (%; positive is improvement)")
    return fig


def _sample_noise_figure(data: AnalysisReportData) -> go.Figure:
    noisy = top_cv_rows(data.sample_statistics, 20)
    if noisy.empty:
        return go.Figure()

    noisy["display_name"] = noisy.apply(_sample_noise_label, axis=1)
    fig = go.Figure(
        go.Bar(
            x=noisy["cv"],
            y=noisy["display_name"],
            orientation="h",
            marker_color="rgba(70, 111, 171, 0.85)",
            customdata=noisy[
                [
                    "suite_name",
                    "suite_version",
                    "compiler_version",
                    "metric",
                    "observations",
                    "mean",
                    "std",
                    "test_name",
                ]
            ],
            hovertemplate=(
                "%{customdata[7]}<br>"
                "LLVM=%{customdata[2]}<br>"
                "suite=%{customdata[0]} %{customdata[1]}<br>"
                "metric=%{customdata[3]}<br>"
                "CV=%{x:.4f}<br>"
                "mean=%{customdata[5]:.6g}, std=%{customdata[6]:.6g}<br>"
                "observations=%{customdata[4]}<extra></extra>"
            ),
        )
    )
    fig.update_layout(template="plotly_white", height=620, margin=dict(l=280, r=40, t=30, b=50))
    fig.update_xaxes(title_text="Coefficient of variation")
    fig.update_yaxes(autorange="reversed")
    return fig


def _sample_noise_label(row: pd.Series) -> str:
    compiler = str(row.get("compiler_version", "unknown"))
    metric = str(row.get("metric", "metric"))
    test_name = shorten(str(row.get("test_name", "unknown")), 72)
    return f"{compiler} | {metric} | {test_name}"


def _compiler_pair_heatmap(data: AnalysisReportData) -> go.Figure:
    comparisons = data.metric_comparisons.copy()
    required = {
        "baseline_compiler_version",
        "candidate_compiler_version",
        "metric",
        "classification",
    }
    if comparisons.empty or not required.issubset(comparisons.columns):
        return go.Figure()

    changed = comparisons[comparisons["classification"].astype(str) != "stable"].copy()
    if changed.empty:
        changed = comparisons
    changed["compiler_pair"] = (
        changed["baseline_compiler_version"].astype(str)
        + " -> "
        + changed["candidate_compiler_version"].astype(str)
    )
    pivot = changed.pivot_table(
        index="compiler_pair",
        columns="metric",
        values="classification",
        aggfunc="count",
        fill_value=0,
    )
    fig = go.Figure(
        go.Heatmap(
            z=pivot.values,
            x=list(pivot.columns),
            y=list(pivot.index),
            colorscale="Blues",
            hovertemplate="LLVM pair=%{y}<br>metric=%{x}<br>rows=%{z}<extra></extra>",
        )
    )
    fig.update_layout(template="plotly_white", height=360, margin=dict(l=180, r=40, t=30, b=80))
    return fig


def _suite_metric_heatmap(data: AnalysisReportData) -> go.Figure:
    summary = suite_metric_summary(data.metric_comparisons)
    if summary.empty:
        return go.Figure()

    changed = summary[summary["classification"].astype(str) != "stable"]
    if changed.empty:
        changed = summary
    pivot = changed.pivot_table(index="suite_name", columns="metric", values="count", aggfunc="sum", fill_value=0)
    fig = go.Figure(
        go.Heatmap(
            z=pivot.values,
            x=list(pivot.columns),
            y=list(pivot.index),
            colorscale="YlOrRd",
            hovertemplate="suite=%{y}<br>metric=%{x}<br>rows=%{z}<extra></extra>",
        )
    )
    fig.update_layout(template="plotly_white", height=360, margin=dict(l=80, r=40, t=30, b=80))
    return fig

