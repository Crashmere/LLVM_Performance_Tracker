from parse_results import parse_results_directory
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path


def records_to_dataframe(records: list) -> pd.DataFrame:
    data = [{
        "suite_name": r.suite_name,
        "suite_version": r.suite_version,
        "compiler_version": r.compiler_version,
        "test_name": r.test_name,
        "exec_time": r.metrics.exec_time,
        "compile_time": r.metrics.compile_time,
        "binary_size": r.metrics.binary_size,
        "flops_gflops": r.metrics.flops_gflops,
        "bandwidth_gib": r.metrics.bandwidth_gib,
    } for r in records]
    return pd.DataFrame(data)

def aggregate_benchmark_records(df: pd.DataFrame) -> pd.DataFrame:
    group_keys = ["suite_name", "suite_version", "compiler_version", "test_name"]

    agg_rules = {
        "exec_time": ["mean", "std", "count"],
        "compile_time": ["mean"],
        "binary_size": ["first"],
        "flops_gflops": ["mean", "std"],
        "bandwidth_gib": ["mean", "std"],
    }

    valid_agg_rules = {k: v for k, v in agg_rules.items() if k in df.columns}

    aggregated_df = df.groupby(group_keys, dropna=False).agg(valid_agg_rules).reset_index()

    new_columns = []
    for col in aggregated_df.columns:
        if col[1] == "":
            new_columns.append(col[0])
        else:
            new_columns.append(f"{col[0]}_{col[1]}")

    aggregated_df.columns = new_columns

    return aggregated_df

def generate_pure_plotly_report(df: pd.DataFrame, output_file: Path | str) -> None:
    fig = make_subplots(
        rows=2, cols=1,
        subplot_titles=(
            "LLVM TSVC Vectorization: Execution Time (Lower is Better)",
            "RAJA Base_Seq: Computational Throughput (Higher is Better)"
        ),
        vertical_spacing=0.15
    )

    compiler_versions = sorted(df["compiler_version"].unique())

    df_tsvc = df[
        (df["suite_name"] == "official") &
        (df["test_name"].str.contains("TSVC", na=False)) &
        (df["exec_time_mean"] > 0.1)
    ]

    if not df_tsvc.empty:
        for version in compiler_versions:
            version_data = df_tsvc[df_tsvc["compiler_version"] == version]
            if not version_data.empty:
                fig.add_trace(
                    go.Box(
                        y=version_data["exec_time_mean"],
                        name=version,
                        boxpoints="all",
                        jitter=0.3,
                        pointpos=-1.8,
                        legend="legend",
                        showlegend=True
                    ),
                    row=1, col=1
                )

    df_raja = df[
        (df["suite_name"] == "raja") &
        (df["test_name"].str.contains("_Base_Seq_default", na=False))
    ]

    if not df_raja.empty:
        for version in compiler_versions:
            version_data = df_raja[df_raja["compiler_version"] == version]
            if not version_data.empty:
                fig.add_trace(
                    go.Bar(
                        x=version_data["test_name"],
                        y=version_data["flops_gflops_mean"],
                        error_y=dict(type='data', array=version_data.get("flops_gflops_std", None)),
                        name=version,
                        legend="legend2",
                        showlegend=True
                    ),
                    row=2, col=1
                )
    fig.update_layout(
        title_text="Automated Compiler Benchmark Report",
        height=1000,
        boxmode="group",
        barmode="group",
        template="plotly_white",
        hovermode="closest",
        legend=dict(
            title="TSVC Versions",
            x=1.02, y=1.0, xanchor="left", yanchor="top",
            tracegroupgap=0
        ),
        legend2=dict(
            title="RAJA Versions",
            x=1.02, y=0.45, xanchor="left", yanchor="top",
            tracegroupgap=0
        )
    )

    fig.update_yaxes(title_text="Execution Time Mean (s)", row=1, col=1)
    fig.update_yaxes(title_text="Throughput Mean (GFLOP/s)", row=2, col=1)
    fig.update_xaxes(title_text="Compiler Version", row=1, col=1)
    fig.update_xaxes(title_text="Kernel Name", tickangle=45, row=2, col=1)

    output_path = Path(output_file)
    fig.write_html(str(output_path), include_plotlyjs="cdn")
    print(f"Report generated successfully at: {output_path.resolve()}")


if __name__ == "__main__":
    RESULTS_DIR = Path("~/auto/results").expanduser()
    parsed_records = parse_results_directory(RESULTS_DIR)
    print(f"Successfully parsed {len(parsed_records)} benchmark records.")

    raw_df = records_to_dataframe(parsed_records)

    processed_df = aggregate_benchmark_records(raw_df)

    generate_pure_plotly_report(processed_df, "benchmark_report.html")
