#!/usr/bin/env python3

import argparse
import csv
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from workflow.lib.run_manifest import summarize_historical_runs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="List historical experiment runs discovered from the results directory.")
    parser.add_argument("--base-dir", required=True, help="Workflow base directory, such as auto/.")
    parser.add_argument(
        "--format",
        choices=["table", "csv"],
        default="table",
        help="Output format.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows = summarize_historical_runs(Path(args.base_dir).expanduser().resolve())

    if args.format == "csv":
        writer = csv.DictWriter(
            sys.stdout,
            fieldnames=[
                "experiment_id",
                "llvm_tag",
                "official_tag",
                "raja_tag",
                "run_label",
                "status",
                "failed_stage",
                "started_at",
                "finished_at",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field) for field in writer.fieldnames})
        return 0

    if not rows:
        print("No historical runs found.")
        return 0

    print(f"{'run_label':<24} {'llvm_tag':<18} {'official_tag':<18} {'raja_tag':<14} {'status':<10} failed_stage")
    for row in rows:
        print(
            f"{row['run_label']:<24} {row['llvm_tag']:<18} {row['official_tag']:<18} "
            f"{row['raja_tag']:<14} {row['status']:<10} {row.get('failed_stage') or '-'}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
