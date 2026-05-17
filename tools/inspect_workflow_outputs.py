#!/usr/bin/env python3

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any


SUMMARY_FIELDS = [
    "experiment_id",
    "run_label",
    "llvm_tag",
    "official_tag",
    "raja_tag",
    "metadata",
    "raw_results",
    "parsed",
    "aggregated",
    "report",
    "next_step",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect existing workflow outputs without changing Snakemake state."
    )
    parser.add_argument("--base-dir", default="auto", help="Workflow base directory to scan.")
    parser.add_argument(
        "--format",
        choices=["table", "csv", "json"],
        default="table",
        help="Output format for the summary.",
    )
    return parser.parse_args()


def exists(path: str | None) -> bool:
    return bool(path) and Path(path).exists()


def load_metadata_records(base_dir: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    metadata_root = base_dir / "metadata"
    if not metadata_root.exists():
        return records

    for metadata_file in sorted(metadata_root.glob("*/experiment.json")):
        try:
            metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            records.append(
                {
                    "experiment_id": metadata_file.parent.name,
                    "run_label": "",
                    "llvm_tag": "",
                    "official_tag": "",
                    "raja_tag": "",
                    "metadata": "invalid",
                    "raw_results": "missing",
                    "parsed": "missing",
                    "aggregated": "missing",
                    "report": "missing",
                    "next_step": f"metadata invalid: {exc}",
                }
            )
            continue

        experiment = metadata.get("experiment", {})
        outputs = metadata.get("expected_outputs", {})
        official_ok = exists(outputs.get("official_results"))
        raja_ok = exists(outputs.get("raja_results"))
        parsed_ok = exists(outputs.get("parsed_csv"))
        aggregated_ok = exists(outputs.get("aggregated_csv"))
        report_ok = exists(outputs.get("report_html"))

        records.append(
            {
                "experiment_id": experiment.get("experiment_id", metadata_file.parent.name),
                "run_label": experiment.get("run_label", ""),
                "llvm_tag": experiment.get("llvm_tag", ""),
                "official_tag": experiment.get("official_tag", ""),
                "raja_tag": experiment.get("raja_tag", ""),
                "metadata": "present",
                "raw_results": "present" if official_ok and raja_ok else "missing",
                "parsed": "present" if parsed_ok else "missing",
                "aggregated": "present" if aggregated_ok else "missing",
                "report": "present" if report_ok else "missing",
                "next_step": suggest_next_step(official_ok, raja_ok, parsed_ok, aggregated_ok, report_ok),
            }
        )
    return records


def suggest_next_step(
    official_ok: bool,
    raja_ok: bool,
    parsed_ok: bool,
    aggregated_ok: bool,
    report_ok: bool,
) -> str:
    if not official_ok or not raja_ok:
        missing = []
        if not official_ok:
            missing.append("official raw result")
        if not raja_ok:
            missing.append("RAJA raw result")
        return "run benchmark stage; missing " + " and ".join(missing)
    if not parsed_ok:
        return "rebuild parsed CSV target"
    if not aggregated_ok:
        return "rebuild aggregated CSV target"
    if not report_ok:
        return "rebuild report target"
    return "complete"


def write_table(records: list[dict[str, Any]]) -> None:
    if not records:
        print("No metadata outputs found.")
        return

    widths = {field: len(field) for field in SUMMARY_FIELDS}
    for record in records:
        for field in SUMMARY_FIELDS:
            widths[field] = max(widths[field], len(str(record.get(field, ""))))

    print("  ".join(field.ljust(widths[field]) for field in SUMMARY_FIELDS))
    print("  ".join("-" * widths[field] for field in SUMMARY_FIELDS))
    for record in records:
        print("  ".join(str(record.get(field, "")).ljust(widths[field]) for field in SUMMARY_FIELDS))


def main() -> int:
    args = parse_args()
    base_dir = Path(args.base_dir).expanduser().resolve()
    records = load_metadata_records(base_dir)

    if args.format == "json":
        print(json.dumps(records, indent=2, sort_keys=True))
    elif args.format == "csv":
        writer = csv.DictWriter(sys.stdout, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        writer.writerows(records)
    else:
        write_table(records)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
