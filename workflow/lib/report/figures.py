from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import plotly.graph_objects as go

from workflow.lib.report.data import (
    AnalysisReportData,
    compiler_pair_metric_summary,
    compiler_pair_suite_metric_summary,
    noise_plot_rows,
    top_change_rows_with_context,
)
from workflow.lib.report.tables import classification_color


@dataclass(frozen=True)
class FigureSpec:
    key: str
    title: str
    description: str
    figure: go.Figure
    compiler_pair: str = ""


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
            "LLVM Version Pair Trend Matrix",
            "Color and cell text show median normalized change: green is improvement, red is regression. Hover shows changed row count.",
            _compiler_pair_trend_heatmap(data),
        ),
        FigureSpec(
            "largest_changes",
            "Largest Normalized Changes",
            "Improvement bars point right; regression bars point left. Labels and hover include the suite.",
            _top_change_figure(data),
        ),
        FigureSpec(
            "sample_noise",
            "Noisiest Sample Groups",
            "Coefficient of variation highlights unstable measurements. The x-axis is zoomed to distinguish close top values.",
            _sample_noise_figure(data),
        ),
    ]


def build_suite_drilldown_figures(data: AnalysisReportData) -> list[FigureSpec]:
    summary = compiler_pair_suite_metric_summary(data.metric_comparisons)
    if summary.empty:
        return []

    figures = []
    for compiler_pair in sorted(summary["compiler_pair"].dropna().astype(str).unique()):
        pair_summary = summary[summary["compiler_pair"].astype(str) == compiler_pair]
        figures.append(
            FigureSpec(
                key=f"suite_drilldown_{_slugify(compiler_pair)}",
                title=f"Suite Contribution For {compiler_pair}",
                description=(
                    "This drilldown keeps the selected LLVM version pair fixed and shows which suite/metric "
                    "contributes to the trend."
                ),
                figure=_suite_contribution_heatmap(pair_summary),
                compiler_pair=compiler_pair,
            )
        )
    return figures


def render_figure_html(figure: go.Figure, *, include_plotly: bool, div_id: str | None = None) -> str:
    kwargs: dict[str, object] = {}
    if div_id:
        kwargs["div_id"] = div_id
    return figure.to_html(full_html=False, include_plotlyjs=include_plotly, **kwargs)


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
    combined = top_change_rows_with_context(data.top_regressions, data.top_improvements, limit_each=10)
    if combined.empty:
        return go.Figure()

    colors = [
        "rgba(26, 127, 80, 0.85)" if value > 0 else "rgba(184, 69, 56, 0.85)"
        for value in combined["normalized_change_percent"].fillna(0)
    ]
    fig = go.Figure(
        go.Bar(
            x=combined["normalized_change_percent"],
            y=combined["plot_position"],
            orientation="h",
            marker_color=colors,
            customdata=combined[
                [
                    "suite_aware_label",
                    "suite_name",
                    "test_name",
                    "metric",
                    "metric_display_name",
                    "baseline_compiler_version",
                    "candidate_compiler_version",
                    "baseline_suite_version",
                    "candidate_suite_version",
                    "classification",
                    "evidence",
                ]
            ],
            hovertemplate=(
                "%{customdata[0]}<br>"
                "suite=%{customdata[1]}<br>"
                "test=%{customdata[2]}<br>"
                "metric=%{customdata[3]} (%{customdata[4]})<br>"
                "normalized change=%{x:+.2f}%<br>"
                "LLVM %{customdata[5]} -> %{customdata[6]}<br>"
                "suite version %{customdata[7]} -> %{customdata[8]}<br>"
                "%{customdata[9]} / %{customdata[10]}<extra></extra>"
            ),
        )
    )
    fig.update_layout(template="plotly_white", height=660, margin=dict(l=300, r=40, t=30, b=50))
    fig.update_xaxes(title_text="Normalized change (%; positive is improvement)")
    fig.update_yaxes(
        autorange="reversed",
        tickmode="array",
        tickvals=combined["plot_position"],
        ticktext=combined["suite_aware_label"],
    )
    fig.add_vline(x=0, line_width=1, line_color="rgba(96, 113, 128, 0.65)")
    return fig


def _sample_noise_figure(data: AnalysisReportData) -> go.Figure:
    noisy = noise_plot_rows(data.sample_statistics, 20)
    if noisy.empty:
        return go.Figure()

    fig = go.Figure(
        go.Scatter(
            x=noisy["cv"],
            y=noisy["display_name"],
            mode="markers",
            marker=dict(
                color="rgba(70, 111, 171, 0.88)",
                line=dict(color="rgba(31, 43, 37, 0.38)", width=1),
                size=12,
            ),
            customdata=noisy[
                [
                    "rank",
                    "suite_name",
                    "suite_version",
                    "compiler_version",
                    "metric",
                    "cv_percent",
                    "observations",
                    "mean",
                    "std",
                    "test_name",
                ]
            ],
            hovertemplate=(
                "rank=%{customdata[0]}<br>"
                "%{customdata[9]}<br>"
                "LLVM=%{customdata[3]}<br>"
                "suite=%{customdata[1]} %{customdata[2]}<br>"
                "metric=%{customdata[4]}<br>"
                "CV=%{x:.6g} (%{customdata[5]:.4f}%)<br>"
                "mean=%{customdata[7]:.6g}, std=%{customdata[8]:.6g}<br>"
                "observations=%{customdata[6]}<extra></extra>"
            ),
        )
    )
    xmin, xmax = _zoomed_axis_range(noisy["cv"])
    fig.update_layout(template="plotly_white", height=620, margin=dict(l=300, r=40, t=30, b=50))
    fig.update_xaxes(title_text="Coefficient of variation")
    if xmin is not None and xmax is not None:
        fig.update_xaxes(range=[xmin, xmax])
    fig.update_yaxes(autorange="reversed")
    return fig


def _compiler_pair_trend_heatmap(data: AnalysisReportData) -> go.Figure:
    summary = compiler_pair_metric_summary(data.metric_comparisons)
    if summary.empty:
        return go.Figure()

    pivot = summary.pivot_table(
        index="compiler_pair",
        columns="metric",
        values="median_normalized_change_percent",
        aggfunc="first",
    )
    text, customdata = _heatmap_text_and_customdata(summary, list(pivot.index), list(pivot.columns), include_suite=False)
    zmin, zmax = _symmetric_color_bounds(pivot.values)
    fig = go.Figure(
        go.Heatmap(
            z=pivot.values,
            x=list(pivot.columns),
            y=list(pivot.index),
            text=text,
            texttemplate="%{text}",
            customdata=customdata,
            colorscale=_trend_colorscale(),
            zmid=0,
            zmin=zmin,
            zmax=zmax,
            colorbar=dict(title="Median<br>change %"),
            hovertemplate=(
                "LLVM pair=%{y}<br>"
                "metric=%{x}<br>"
                "median change=%{z:+.2f}%<br>"
                "mean change=%{customdata[0]:+.2f}%<br>"
                "changed rows=%{customdata[1]} of %{customdata[2]}<br>"
                "improvements=%{customdata[3]}, regressions=%{customdata[4]}, stable=%{customdata[5]}<br>"
                "reliable changes=%{customdata[6]}, candidate changes=%{customdata[7]}<extra></extra>"
            ),
        )
    )
    fig.update_layout(template="plotly_white", height=380, margin=dict(l=180, r=40, t=30, b=80))
    return fig


def _suite_contribution_heatmap(summary: pd.DataFrame) -> go.Figure:
    if summary.empty:
        return go.Figure()

    summary = summary.copy()
    pivot = summary.pivot_table(
        index="suite_name",
        columns="metric",
        values="median_normalized_change_percent",
        aggfunc="first",
    )
    text, customdata = _heatmap_text_and_customdata(
        summary,
        list(pivot.index),
        list(pivot.columns),
        include_suite=True,
        row_key="suite_name",
    )
    zmin, zmax = _symmetric_color_bounds(pivot.values)
    height = max(320, min(520, 220 + len(pivot.index) * 58))
    fig = go.Figure(
        go.Heatmap(
            z=pivot.values,
            x=list(pivot.columns),
            y=list(pivot.index),
            text=text,
            texttemplate="%{text}",
            customdata=customdata,
            colorscale=_trend_colorscale(),
            zmid=0,
            zmin=zmin,
            zmax=zmax,
            colorbar=dict(title="Median<br>change %"),
            hovertemplate=(
                "LLVM pair=%{customdata[8]}<br>"
                "suite=%{y}<br>"
                "metric=%{x}<br>"
                "median change=%{z:+.2f}%<br>"
                "mean change=%{customdata[0]:+.2f}%<br>"
                "changed rows=%{customdata[1]} of %{customdata[2]}<br>"
                "improvements=%{customdata[3]}, regressions=%{customdata[4]}, stable=%{customdata[5]}<br>"
                "reliable changes=%{customdata[6]}, candidate changes=%{customdata[7]}<extra></extra>"
            ),
        )
    )
    fig.update_layout(template="plotly_white", height=height, margin=dict(l=110, r=40, t=30, b=80))
    return fig


def _heatmap_text_and_customdata(
    summary: pd.DataFrame,
    rows: list[str],
    columns: list[str],
    *,
    include_suite: bool,
    row_key: str = "compiler_pair",
) -> tuple[list[list[str]], list[list[list[object]]]]:
    lookup = {(str(row[row_key]), str(row["metric"])): row for _, row in summary.iterrows()}
    text_grid: list[list[str]] = []
    custom_grid: list[list[list[object]]] = []
    for row_name in rows:
        text_row: list[str] = []
        custom_row: list[list[object]] = []
        for column in columns:
            record = lookup.get((str(row_name), str(column)))
            if record is None:
                text_row.append("")
                custom_row.append([0.0, 0, 0, 0, 0, 0, 0, 0, "", ""])
                continue
            changed_count = int(record.get("changed_count", 0))
            text_row.append(_heatmap_cell_text(record.get("median_normalized_change_percent")))
            custom_row.append(
                [
                    float(record.get("mean_normalized_change_percent", 0) or 0),
                    changed_count,
                    int(record.get("row_count", 0)),
                    int(record.get("improvement_count", 0)),
                    int(record.get("regression_count", 0)),
                    int(record.get("stable_count", 0)),
                    int(record.get("reliable_change_count", 0)),
                    int(record.get("candidate_change_count", 0)),
                    str(record.get("compiler_pair", "")) if include_suite else "",
                    str(record.get("suite_name", "")) if include_suite else "",
                ]
            )
        text_grid.append(text_row)
        custom_grid.append(custom_row)
    return text_grid, custom_grid


def _heatmap_cell_text(value: object) -> str:
    if pd.isna(value):
        return ""
    return f"{float(value):+.2f}%"


def _symmetric_color_bounds(values: object) -> tuple[float, float]:
    if hasattr(values, "ravel"):
        flat_values = values.ravel()
    else:
        flat_values = []
        for row in values:
            if isinstance(row, (list, tuple)):
                flat_values.extend(row)
            else:
                flat_values.append(row)

    numeric = pd.Series(flat_values)
    numeric = pd.to_numeric(numeric, errors="coerce").dropna().abs()
    if numeric.empty:
        return -1.0, 1.0

    robust_max = float(numeric.quantile(0.95))
    absolute_max = float(numeric.max())
    bound = min(absolute_max, robust_max) if robust_max > 0 else absolute_max
    bound = max(bound, 0.01)
    return -bound, bound


def _trend_colorscale() -> list[list[object]]:
    return [
        [0.0, "rgba(184, 69, 56, 0.92)"],
        [0.5, "rgba(247, 241, 228, 0.96)"],
        [1.0, "rgba(26, 127, 80, 0.92)"],
    ]


def _zoomed_axis_range(values: pd.Series) -> tuple[float | None, float | None]:
    numeric = pd.to_numeric(values, errors="coerce").dropna()
    if numeric.empty:
        return None, None
    minimum = float(numeric.min())
    maximum = float(numeric.max())
    if minimum == maximum:
        padding = max(abs(maximum) * 0.05, 0.000001)
        return minimum - padding, maximum + padding
    padding = (maximum - minimum) * 0.12
    return max(0.0, minimum - padding), maximum + padding


def _slugify(value: str) -> str:
    slug = []
    for character in value.lower():
        if character.isalnum():
            slug.append(character)
        elif slug and slug[-1] != "_":
            slug.append("_")
    return "".join(slug).strip("_") or "item"
