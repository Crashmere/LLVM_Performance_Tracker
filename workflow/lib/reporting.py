from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def aggregate_benchmark_records(df: pd.DataFrame) -> pd.DataFrame:
    group_keys = ["suite_name", "suite_version", "compiler_version", "label", "sample", "test_name"]

    agg_rules = {
        "exec_time": ["mean", "std", "count"],
        "compile_time": ["mean"],
        "binary_size": ["first"],
        "flops_gflops": ["mean", "std"],
        "bandwidth_gib": ["mean", "std"],
    }

    valid_agg_rules = {key: value for key, value in agg_rules.items() if key in df.columns}
    aggregated_df = df.groupby(group_keys, dropna=False).agg(valid_agg_rules).reset_index()

    new_columns = []
    for col in aggregated_df.columns:
        if col[1] == "":
            new_columns.append(col[0])
        else:
            new_columns.append(f"{col[0]}_{col[1]}")

    aggregated_df.columns = new_columns
    return aggregated_df


def read_table(input_file: Path | str) -> pd.DataFrame:
    input_path = Path(input_file)
    suffix = input_path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(input_path)
    if suffix == ".parquet":
        return pd.read_parquet(input_path)
    raise ValueError(f"Unsupported input format for {input_path}. Use .csv or .parquet.")


def write_table(df: pd.DataFrame, output_file: Path | str) -> Path:
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    suffix = output_path.suffix.lower()

    if suffix == ".csv":
        df.to_csv(output_path, index=False)
    elif suffix == ".parquet":
        df.to_parquet(output_path, index=False)
    else:
        raise ValueError(f"Unsupported output format for {output_path}. Use .csv or .parquet.")

    return output_path


def ensure_aggregated_records(df: pd.DataFrame) -> pd.DataFrame:
    if "exec_time_mean" in df.columns or "flops_gflops_mean" in df.columns:
        return df
    return aggregate_benchmark_records(df)


def generate_pure_plotly_report(df: pd.DataFrame, output_file: Path | str) -> Path:
    fig = make_subplots(
        rows=2,
        cols=1,
        subplot_titles=(
            "LLVM TSVC Vectorization: Execution Time (Lower is Better)",
            "RAJA Base_Seq: Computational Throughput (Higher is Better)",
        ),
        vertical_spacing=0.15,
    )

    compiler_versions = sorted(df["compiler_version"].dropna().unique())

    df_tsvc = df[
        (df["suite_name"] == "official")
        & (df["test_name"].str.contains("TSVC", na=False))
        & (df["exec_time_mean"] > 0.1)
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
                        showlegend=True,
                    ),
                    row=1,
                    col=1,
                )

    df_raja = df[
        (df["suite_name"] == "raja")
        & (df["test_name"].str.contains("_Base_Seq_default", na=False))
    ]

    if not df_raja.empty:
        for version in compiler_versions:
            version_data = df_raja[df_raja["compiler_version"] == version]
            if not version_data.empty:
                fig.add_trace(
                    go.Bar(
                        x=version_data["test_name"],
                        y=version_data["flops_gflops_mean"],
                        error_y=dict(type="data", array=version_data.get("flops_gflops_std", None)),
                        name=version,
                        legend="legend2",
                        showlegend=True,
                    ),
                    row=2,
                    col=1,
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
            x=1.02,
            y=1.0,
            xanchor="left",
            yanchor="top",
            tracegroupgap=0,
        ),
        legend2=dict(
            title="RAJA Versions",
            x=1.02,
            y=0.45,
            xanchor="left",
            yanchor="top",
            tracegroupgap=0,
        ),
    )

    fig.update_yaxes(title_text="Execution Time Mean (s)", row=1, col=1)
    fig.update_yaxes(title_text="Throughput Mean (GFLOP/s)", row=2, col=1)
    fig.update_xaxes(title_text="Compiler Version", row=1, col=1)
    fig.update_xaxes(title_text="Kernel Name", tickangle=45, row=2, col=1)

    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(str(output_path), include_plotlyjs=True)
    return output_path
