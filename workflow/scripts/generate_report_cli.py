#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from workflow.lib.reporting import (
    ensure_aggregated_records,
    generate_pure_plotly_report,
    read_table,
    write_table,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate an HTML report from parsed benchmark records.")
    parser.add_argument("--input-file", required=True, help="Input .csv or .parquet benchmark table.")
    parser.add_argument("--output-html", required=True, help="Output HTML report path.")
    parser.add_argument(
        "--aggregated-output",
        help="Optional .csv or .parquet path for writing aggregated benchmark data.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = Path(args.input_file)
    if not input_path.exists():
        raise FileNotFoundError(f"Expected aggregated benchmark table does not exist: {input_path}")

    input_df = read_table(args.input_file)
    aggregated_df = ensure_aggregated_records(input_df)

    if args.aggregated_output:
        aggregated_path = write_table(aggregated_df, args.aggregated_output)
        print(f"Wrote aggregated benchmark data to {aggregated_path.resolve()}")

    report_path = generate_pure_plotly_report(aggregated_df, args.output_html)
    print(f"Report generated successfully at: {report_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
