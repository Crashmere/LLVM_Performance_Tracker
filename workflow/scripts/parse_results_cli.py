#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from workflow.lib.parse_results import filter_records, parse_results_directory, write_records_table


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Parse benchmark result directories into a tabular file.")
    parser.add_argument("--input-dir", required=True, help="Root results directory to parse.")
    parser.add_argument("--output-file", required=True, help="Output .csv or .parquet file path.")
    parser.add_argument("--suite-name", help="Optional suite filter, such as official or raja.")
    parser.add_argument("--compiler-version", help="Optional compiler version filter.")
    parser.add_argument("--run-label", help="Optional run label filter.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    records = parse_results_directory(args.input_dir)
    filtered_records = filter_records(
        records,
        suite_name=args.suite_name,
        compiler_version=args.compiler_version,
        run_label=args.run_label,
    )
    output_path = write_records_table(filtered_records, args.output_file)
    print(f"Wrote {len(filtered_records)} benchmark records to {output_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
