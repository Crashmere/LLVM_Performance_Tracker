from __future__ import annotations

from html import escape
import os
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.graph_objects as go

from workflow.lib.report_data import AnalysisReportData, suite_metric_summary, top_cv_rows, top_rows


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


def render_analysis_report(data: AnalysisReportData, output_path: Path | str) -> str:
    output = Path(output_path)
    csv_links = _csv_links(data.analysis_dir, output.parent)
    figures = _build_figures(data)

    figure_sections: list[str] = []
    include_plotly = True
    for title, description, figure in figures:
        figure_sections.append(_figure_section(title, description, figure, include_plotly))
        include_plotly = False

    body = "\n".join(
        [
            _hero_section(data),
            _summary_section(data),
            _top_changes_section(data, csv_links),
            "\n".join(figure_sections),
            _comparison_section(data, csv_links),
            _sample_section(data, csv_links),
            _suite_section(data),
            _detail_section(data, csv_links),
        ]
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>LLVM Performance Analysis Report</title>
  <style>{_css()}</style>
</head>
<body>
  <main>
    {body}
  </main>
  <script>{_javascript()}</script>
</body>
</html>
"""


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


def _hero_section(data: AnalysisReportData) -> str:
    generated_at = data.summary.get("generated_at", "unknown")
    return f"""
<section class="hero">
  <p class="eyebrow">Snakemake analysis report</p>
  <h1>LLVM Performance Analysis</h1>
  <p>
    This report summarizes all retained parsed benchmark results under <code>auto/parsed</code>.
    To exclude an old result from analysis, remove the unwanted output from <code>auto/</code> and rerun the workflow.
  </p>
  <p class="muted">Generated at {escape(str(generated_at))}</p>
</section>
"""


def _summary_section(data: AnalysisReportData) -> str:
    records = data.summary.get("records", {})
    inputs = data.summary.get("inputs", {})
    coverage = data.summary.get("coverage", {})
    settings = data.summary.get("settings", {})
    counts = data.summary.get("classification_counts", {})

    cards = [
        ("Input files", inputs.get("count", 0), "Parsed CSV files included"),
        ("Analysis records", records.get("analysis_records", len(data.analysis_records)), "Metric observations"),
        ("Sample groups", records.get("sample_statistics", len(data.sample_statistics)), "Grouped statistics"),
        ("LLVM comparisons", records.get("metric_comparisons", len(data.metric_comparisons)), "Compiler version pairs"),
        ("Suites", len(coverage.get("suites", [])), ", ".join(map(str, coverage.get("suites", []))) or "none"),
        ("Samples", len(coverage.get("samples", [])), ", ".join(map(str, coverage.get("samples", []))) or "none"),
    ]
    card_html = "\n".join(_card(title, value, detail) for title, value, detail in cards)

    counts_html = _classification_pills(counts)
    settings_html = (
        f"Threshold: <strong>{escape(str(settings.get('change_threshold_percent', 'unknown')))}%</strong>. "
        f"Minimum observations for reliable evidence: <strong>{escape(str(settings.get('min_samples', 'unknown')))}</strong>."
    )

    versions = ", ".join(map(str, coverage.get("compiler_versions", []))) or "none"
    suite_versions = ", ".join(map(str, coverage.get("suite_versions", []))) or "none"
    labels = ", ".join(map(str, coverage.get("labels", [])[:8])) or "none"
    if len(coverage.get("labels", [])) > 8:
        labels += ", ..."

    return f"""
<section class="panel" id="overview">
  <div class="section-heading">
    <p class="eyebrow">Overview</p>
    <h2>Analysis Coverage</h2>
  </div>
  <div class="cards">{card_html}</div>
  <div class="note">
    <p>{settings_html}</p>
    <p>Comparison scope: LLVM/compiler versions are compared only within the same suite, suite version, test, and metric.</p>
    <p>Compiler versions: {escape(versions)}</p>
    <p>Suite versions: {escape(suite_versions)}</p>
    <p>Labels: {escape(labels)}</p>
  </div>
  <div class="pill-row">{counts_html}</div>
</section>
"""


def _top_changes_section(data: AnalysisReportData, csv_links: dict[str, str]) -> str:
    regressions = top_rows(data.top_regressions, 50)
    improvements = top_rows(data.top_improvements, 50)
    return f"""
<section class="panel" id="top-changes">
  <div class="section-heading">
    <p class="eyebrow">Priority list</p>
    <h2>Top LLVM Version Regressions And Improvements</h2>
    <p class="muted">Positive normalized change means the candidate LLVM version is better; negative means regression. Suite versions are fixed within each comparison.</p>
  </div>
  <div class="split">
    <div>
      <h3>Top Regressions</h3>
      <p><a href="{escape(csv_links['top_regressions.csv'])}">Open CSV</a></p>
      {_table(regressions, TOP_CHANGE_COLUMNS, "top-regressions", search=True)}
    </div>
    <div>
      <h3>Top Improvements</h3>
      <p><a href="{escape(csv_links['top_improvements.csv'])}">Open CSV</a></p>
      {_table(improvements, TOP_CHANGE_COLUMNS, "top-improvements", search=True)}
    </div>
  </div>
</section>
"""


def _comparison_section(data: AnalysisReportData, csv_links: dict[str, str]) -> str:
    comparisons = data.metric_comparisons.copy()
    if "normalized_change_percent" in comparisons.columns:
        comparisons["abs_change"] = pd.to_numeric(comparisons["normalized_change_percent"], errors="coerce").abs()
        comparisons = comparisons.sort_values("abs_change", ascending=False).drop(columns=["abs_change"])
    comparisons = comparisons.head(500)

    return f"""
<section class="panel" id="comparisons">
  <div class="section-heading">
    <p class="eyebrow">Full LLVM comparison table</p>
    <h2>Metric Comparisons Across LLVM Versions</h2>
    <p class="muted">Use filters to narrow the comparison table. Comparisons keep suite version fixed and vary LLVM/compiler version. The table is capped at 500 highest-change rows in HTML; the full CSV remains available.</p>
  </div>
  <p><a href="{escape(csv_links['metric_comparisons.csv'])}">Open full CSV</a></p>
  {_table(
      comparisons,
      COMPARISON_COLUMNS,
      "metric-comparisons",
      search=True,
      filters=["suite_name", "metric", "classification"],
  )}
</section>
"""


def _sample_section(data: AnalysisReportData, csv_links: dict[str, str]) -> str:
    noisy = top_cv_rows(data.sample_statistics, 100)
    return f"""
<section class="panel" id="samples">
  <div class="section-heading">
    <p class="eyebrow">Noise and confidence</p>
    <h2>Sample Statistics</h2>
    <p class="muted">High CV values identify noisy tests. Low observation counts explain many candidate rather than reliable classifications.</p>
  </div>
  <p><a href="{escape(csv_links['sample_statistics.csv'])}">Open full CSV</a></p>
  {_table(noisy, SAMPLE_COLUMNS, "sample-statistics", search=True, filters=["suite_name", "metric"])}
</section>
"""


def _suite_section(data: AnalysisReportData) -> str:
    pieces = []
    for suite in sorted(data.metric_comparisons["suite_name"].dropna().astype(str).unique()):
        comparisons = data.metric_comparisons[data.metric_comparisons["suite_name"].astype(str) == suite]
        samples = data.sample_statistics[data.sample_statistics["suite_name"].astype(str) == suite]
        regressions = comparisons[comparisons["classification"].astype(str).str.endswith("regression", na=False)]
        improvements = comparisons[comparisons["classification"].astype(str).str.endswith("improvement", na=False)]
        metrics = ", ".join(sorted(comparisons["metric"].dropna().astype(str).unique())) or "none"
        pieces.append(
            f"""
    <article class="suite-card">
      <h3>{escape(suite)}</h3>
      <p class="muted">Metrics: {escape(metrics)}</p>
      <div class="mini-cards">
        {_card("Comparisons", len(comparisons), "comparison rows")}
        {_card("Regressions", len(regressions), "candidate or reliable")}
        {_card("Improvements", len(improvements), "candidate or reliable")}
        {_card("Sample groups", len(samples), "statistical groups")}
      </div>
    </article>
"""
        )

    return f"""
<section class="panel" id="suites">
  <div class="section-heading">
    <p class="eyebrow">Suite views</p>
    <h2>Official And RAJA Summary</h2>
  </div>
  <div class="suite-grid">{''.join(pieces) if pieces else '<p class="muted">No suite data available.</p>'}</div>
</section>
"""


def _detail_section(data: AnalysisReportData, csv_links: dict[str, str]) -> str:
    details = data.analysis_records.head(200)
    return f"""
<section class="panel" id="details">
  <div class="section-heading">
    <p class="eyebrow">Provenance</p>
    <h2>Analysis Record Preview</h2>
    <p class="muted">Only the first 200 rows are embedded to keep the HTML manageable.</p>
  </div>
  <p><a href="{escape(csv_links['analysis_records.csv'])}">Open full CSV</a></p>
  {_table(details, DETAIL_COLUMNS, "analysis-records", search=True, filters=["suite_name", "metric"])}
</section>
"""


def _build_figures(data: AnalysisReportData) -> list[tuple[str, str, go.Figure]]:
    return [
        (
            "Classification Counts",
            "How many comparison rows are stable, candidate changes, or reliable changes.",
            _classification_counts_figure(data),
        ),
        (
            "Largest Normalized Changes",
            "Improvement bars point right; regression bars point left.",
            _top_change_figure(data),
        ),
        (
            "LLVM Version Pair Change Matrix",
            "Changed rows grouped by baseline/candidate LLVM version pair and metric.",
            _compiler_pair_heatmap(data),
        ),
        (
            "Noisiest Sample Groups",
            "Coefficient of variation highlights tests with unstable measurements.",
            _sample_noise_figure(data),
        ),
        (
            "Suite And Metric Change Matrix",
            "Counts of changed rows by suite and metric.",
            _suite_metric_heatmap(data),
        ),
    ]


def _classification_counts_figure(data: AnalysisReportData) -> go.Figure:
    counts = data.summary.get("classification_counts", {})
    labels = list(counts.keys())
    values = [counts[label] for label in labels]
    colors = [_classification_color(label) for label in labels]
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
    combined["short_name"] = combined["test_name"].astype(str).map(_shorten)
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
    test_name = _shorten(str(row.get("test_name", "unknown")), 72)
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


def _figure_section(title: str, description: str, figure: go.Figure, include_plotly: bool) -> str:
    figure_html = figure.to_html(full_html=False, include_plotlyjs=include_plotly)
    return f"""
<section class="panel chart-panel">
  <div class="section-heading">
    <p class="eyebrow">Chart</p>
    <h2>{escape(title)}</h2>
    <p class="muted">{escape(description)}</p>
  </div>
  {figure_html}
</section>
"""


def _table(
    df: pd.DataFrame,
    columns: list[str],
    table_id: str,
    *,
    search: bool = False,
    filters: list[str] | None = None,
) -> str:
    available = [column for column in columns if column in df.columns]
    filters = [column for column in (filters or []) if column in available]
    controls = _table_controls(df, available, table_id, search, filters)

    if df.empty or not available:
        return controls + '<p class="muted">No rows available.</p>'

    header = "".join(f"<th>{escape(column)}</th>" for column in available)
    rows = []
    for _, row in df[available].iterrows():
        cells = []
        for column in available:
            value = row[column]
            cells.append(f"<td>{_format_cell(column, value)}</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")

    return f"""
{controls}
<div class="table-wrap">
  <table id="{escape(table_id)}" class="data-table">
    <thead><tr>{header}</tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
</div>
"""


def _table_controls(
    df: pd.DataFrame,
    columns: list[str],
    table_id: str,
    search: bool,
    filters: list[str],
) -> str:
    parts = []
    if search:
        parts.append(
            f'<input class="table-search" data-search="{escape(table_id)}" '
            f'placeholder="Search {escape(table_id.replace("-", " "))}...">'
        )
    for column in filters:
        values = sorted(str(value) for value in df[column].dropna().unique())
        options = '<option value="">All</option>' + "".join(
            f'<option value="{escape(value)}">{escape(value)}</option>' for value in values
        )
        column_index = columns.index(column)
        parts.append(
            f'<label class="filter-label">{escape(column)} '
            f'<select data-filter="{escape(table_id)}" data-column="{column_index}">{options}</select></label>'
        )
    if not parts:
        return ""
    return f'<div class="table-controls">{"".join(parts)}</div>'


def _format_cell(column: str, value: Any) -> str:
    if pd.isna(value):
        return ""
    if column == "normalized_change_percent":
        text = f"{float(value):+.2f}%"
        klass = "improvement" if float(value) > 0 else "regression" if float(value) < 0 else "stable"
        return f'<span class="change {klass}">{escape(text)}</span>'
    if column == "raw_change_percent":
        return escape(f"{float(value):+.2f}%")
    if column in {"baseline_mean", "candidate_mean", "mean", "std", "cv", "ci95_low", "ci95_high", "value"}:
        try:
            return escape(f"{float(value):.6g}")
        except (TypeError, ValueError):
            return escape(str(value))
    if column == "classification":
        klass = _classification_class(str(value))
        return f'<span class="badge {klass}">{escape(str(value))}</span>'
    if column == "test_name":
        return f'<span title="{escape(str(value))}">{escape(_shorten(str(value), 90))}</span>'
    return escape(str(value))


def _card(title: str, value: Any, detail: str) -> str:
    return f"""
<div class="card">
  <span>{escape(title)}</span>
  <strong>{escape(str(value))}</strong>
  <em>{escape(str(detail))}</em>
</div>
"""


def _classification_pills(counts: dict[str, Any]) -> str:
    if not counts:
        return '<span class="pill">No classifications</span>'
    return "".join(
        f'<span class="pill {_classification_class(name)}">{escape(str(name))}: {escape(str(value))}</span>'
        for name, value in sorted(counts.items())
    )


def _classification_color(name: str) -> str:
    if "regression" in name:
        return "rgba(184, 69, 56, 0.85)"
    if "improvement" in name:
        return "rgba(26, 127, 80, 0.85)"
    return "rgba(96, 113, 128, 0.75)"


def _classification_class(name: str) -> str:
    if "regression" in name:
        return "regression"
    if "improvement" in name:
        return "improvement"
    if "stable" in name:
        return "stable"
    return "neutral"


def _shorten(value: str, limit: int = 64) -> str:
    if len(value) <= limit:
        return value
    return "..." + value[-(limit - 3) :]


def _css() -> str:
    return """
:root {
  --ink: #1e2b25;
  --muted: #66746f;
  --paper: #fffaf0;
  --panel: rgba(255, 252, 244, 0.92);
  --line: #dfd4bf;
  --green: #1a7f50;
  --red: #b84538;
  --blue: #466fab;
  --gold: #b58027;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  color: var(--ink);
  background:
    radial-gradient(circle at top left, rgba(181, 128, 39, 0.18), transparent 32rem),
    radial-gradient(circle at top right, rgba(70, 111, 171, 0.18), transparent 28rem),
    linear-gradient(135deg, #f6efe0 0%, #eef3ec 100%);
  font-family: "Iowan Old Style", "Palatino Linotype", Georgia, serif;
}
main { width: min(1520px, calc(100% - 48px)); margin: 0 auto; padding: 36px 0 56px; }
.hero, .panel {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 24px;
  box-shadow: 0 18px 50px rgba(31, 43, 37, 0.09);
  margin-bottom: 24px;
  padding: 28px;
}
.hero { padding: 42px; }
.eyebrow {
  color: var(--gold);
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0.14em;
  margin: 0 0 8px;
  text-transform: uppercase;
}
h1, h2, h3 { margin: 0 0 12px; line-height: 1.05; }
h1 { font-size: clamp(2.4rem, 6vw, 5.8rem); max-width: 980px; }
h2 { font-size: clamp(1.8rem, 3vw, 3rem); }
h3 { font-size: 1.35rem; }
p { line-height: 1.55; }
a { color: #255f8f; font-weight: 700; }
code { background: #efe5d2; border-radius: 6px; padding: 2px 6px; }
.muted { color: var(--muted); }
.section-heading { margin-bottom: 18px; max-width: 980px; }
.cards, .mini-cards {
  display: grid;
  gap: 14px;
  grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
}
.card {
  background: #213b33;
  border-radius: 18px;
  color: #fffaf0;
  min-height: 116px;
  padding: 18px;
}
.card span, .card em { display: block; opacity: 0.76; }
.card strong { display: block; font-size: 2rem; margin: 8px 0; }
.card em { font-size: 0.86rem; font-style: normal; }
.note {
  background: rgba(255,255,255,0.55);
  border: 1px solid var(--line);
  border-radius: 16px;
  margin: 18px 0;
  padding: 16px 18px;
}
.pill-row { display: flex; flex-wrap: wrap; gap: 8px; }
.pill, .badge, .change {
  border-radius: 999px;
  display: inline-block;
  font-weight: 700;
  padding: 4px 9px;
  white-space: nowrap;
}
.pill { background: #ece3d3; }
.badge { font-size: 0.82rem; }
.regression { background: rgba(184, 69, 56, 0.15); color: var(--red); }
.improvement { background: rgba(26, 127, 80, 0.15); color: var(--green); }
.stable { background: rgba(96, 113, 128, 0.15); color: #53616a; }
.neutral { background: rgba(70, 111, 171, 0.14); color: var(--blue); }
.split {
  display: grid;
  gap: 22px;
  grid-template-columns: repeat(auto-fit, minmax(420px, 1fr));
}
.suite-grid {
  display: grid;
  gap: 18px;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
}
.suite-card {
  background: rgba(255,255,255,0.55);
  border: 1px solid var(--line);
  border-radius: 18px;
  padding: 18px;
}
.table-controls {
  align-items: center;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin: 12px 0;
}
.table-search, select {
  background: white;
  border: 1px solid var(--line);
  border-radius: 10px;
  color: var(--ink);
  font: inherit;
  padding: 8px 10px;
}
.table-search { min-width: min(420px, 100%); }
.filter-label { color: var(--muted); font-size: 0.92rem; }
.table-wrap {
  border: 1px solid var(--line);
  border-radius: 16px;
  max-height: 560px;
  overflow: auto;
}
.data-table {
  background: rgba(255,255,255,0.72);
  border-collapse: collapse;
  font-size: 0.86rem;
  width: 100%;
}
.data-table th, .data-table td {
  border-bottom: 1px solid #eadfca;
  padding: 8px 10px;
  text-align: left;
  vertical-align: top;
}
.data-table th {
  background: #eadfca;
  position: sticky;
  top: 0;
  z-index: 1;
}
.chart-panel .plotly-graph-div { width: 100% !important; }
@media (max-width: 760px) {
  main { width: min(100% - 24px, 1520px); padding-top: 18px; }
  .hero, .panel { border-radius: 18px; padding: 18px; }
  .split { grid-template-columns: 1fr; }
}
"""


def _javascript() -> str:
    return """
function applyTableFilters(tableId) {
  const table = document.getElementById(tableId);
  if (!table || !table.tBodies.length) return;
  const search = document.querySelector(`[data-search="${tableId}"]`);
  const query = search ? search.value.toLowerCase() : "";
  const filters = Array.from(document.querySelectorAll(`[data-filter="${tableId}"]`));
  for (const row of table.tBodies[0].rows) {
    let visible = row.innerText.toLowerCase().includes(query);
    for (const filter of filters) {
      const value = filter.value;
      if (!value) continue;
      const column = Number(filter.dataset.column);
      const cellText = row.cells[column] ? row.cells[column].innerText : "";
      if (cellText !== value) visible = false;
    }
    row.style.display = visible ? "" : "none";
  }
}
document.addEventListener("input", (event) => {
  const tableId = event.target.dataset.search || event.target.dataset.filter;
  if (tableId) applyTableFilters(tableId);
});
"""
