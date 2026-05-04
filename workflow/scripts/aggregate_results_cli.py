#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from workflow.lib.reporting import aggregate_benchmark_records, read_table, write_table


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Aggregate parsed benchmark records into summary tables.")
    parser.add_argument("--input-file", required=True, help="Input .csv or .parquet benchmark table.")
    parser.add_argument("--output-file", required=True, help="Output .csv or .parquet aggregated table.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    raw_df = read_table(args.input_file)
    aggregated_df = aggregate_benchmark_records(raw_df)
    output_path = write_table(aggregated_df, args.output_file)
    print(f"Wrote aggregated benchmark data to {output_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
