#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from workflow.lib.analysis import (
    build_analysis_records,
    build_analysis_summary,
    build_metric_comparisons,
    build_sample_statistics,
    discover_parsed_tables,
    load_parsed_tables,
    split_top_changes,
    write_json,
    write_table,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build analysis tables from parsed benchmark results.")
    parser.add_argument("--base-dir", required=True, help="Workflow base directory containing parsed results.")
    parser.add_argument(
        "--input-file",
        action="append",
        default=[],
        help="Parsed benchmark CSV to include. May be repeated.",
    )
    parser.add_argument("--output-dir", required=True, help="Directory for analysis outputs.")
    parser.add_argument(
        "--threshold-percent",
        type=float,
        required=True,
        help="Minimum normalized percent change before a comparison is marked as changed.",
    )
    parser.add_argument(
        "--min-samples",
        type=int,
        required=True,
        help="Minimum observations per side before a change can be marked reliable.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    base_dir = Path(args.base_dir).expanduser().resolve()
    output_dir = Path(args.output_dir)

    input_files = [Path(path) for path in args.input_file]
    if not input_files:
        input_files = discover_parsed_tables(base_dir)

    parsed_df, skipped_inputs = load_parsed_tables(input_files)
    analysis_records = build_analysis_records(parsed_df)
    sample_statistics = build_sample_statistics(analysis_records)
    metric_comparisons = build_metric_comparisons(
        sample_statistics,
        threshold_percent=args.threshold_percent,
        min_samples=args.min_samples,
    )
    top_regressions, top_improvements = split_top_changes(metric_comparisons)

    summary = build_analysis_summary(
        input_files=input_files,
        skipped_inputs=skipped_inputs,
        analysis_records=analysis_records,
        sample_statistics=sample_statistics,
        metric_comparisons=metric_comparisons,
        top_regressions=top_regressions,
        top_improvements=top_improvements,
        threshold_percent=args.threshold_percent,
        min_samples=args.min_samples,
    )

    write_table(analysis_records, output_dir / "analysis_records.csv")
    write_table(sample_statistics, output_dir / "sample_statistics.csv")
    write_table(metric_comparisons, output_dir / "metric_comparisons.csv")
    write_table(top_regressions, output_dir / "top_regressions.csv")
    write_table(top_improvements, output_dir / "top_improvements.csv")
    write_json(summary, output_dir / "analysis_summary.json")

    print(f"Wrote analysis dataset to {output_dir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
