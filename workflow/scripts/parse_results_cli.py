#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from workflow.lib.parse_results import parse_results_directory, write_records_table


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Parse benchmark result directories into a tabular file.")
    parser.add_argument("--input-dir", required=True, help="Root results directory to parse.")
    parser.add_argument("--output-file", required=True, help="Output .csv or .parquet file path.")
    parser.add_argument("--suite-name", help="Optional suite filter, such as official or raja.")
    parser.add_argument("--compiler-version", help="Optional compiler version filter.")
    parser.add_argument("--label", help="Optional label filter.")
    parser.add_argument(
        "--suite-version",
        action="append",
        default=[],
        help="Optional suite version filters in the form suite=value, for example official=llvmorg-21.1.0.",
    )
    return parser.parse_args()


def parse_suite_versions(entries: list[str]) -> dict[str, str]:
    suite_versions: dict[str, str] = {}
    for entry in entries:
        if "=" not in entry:
            raise ValueError(f"Invalid --suite-version value {entry!r}. Expected suite=value.")
        suite_name, suite_version = entry.split("=", 1)
        suite_name = suite_name.strip()
        suite_version = suite_version.strip()
        if not suite_name or not suite_version:
            raise ValueError(f"Invalid --suite-version value {entry!r}. Expected suite=value.")
        suite_versions[suite_name] = suite_version
    return suite_versions


def main() -> int:
    args = parse_args()
    suite_versions = parse_suite_versions(args.suite_version)
    records = parse_results_directory(
        args.input_dir,
        suite_name=args.suite_name,
        compiler_version=args.compiler_version,
        label=args.label,
        suite_versions=suite_versions,
    )
    output_path = write_records_table(records, args.output_file)
    print(f"Wrote {len(records)} benchmark records to {output_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
