#!/usr/bin/env python3

import argparse
import csv
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="List report targets for failed experiments in a batch summary.")
    parser.add_argument("--summary-csv", required=True, help="Path to the batch summary.csv file.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary_path = Path(args.summary_csv)
    if not summary_path.exists():
        raise FileNotFoundError(f"Summary file not found: {summary_path}")

    failed_targets: list[str] = []
    with summary_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if row.get("status") == "failed" and row.get("report_html"):
                failed_targets.append(row["report_html"])

    for target in failed_targets:
        print(target)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
