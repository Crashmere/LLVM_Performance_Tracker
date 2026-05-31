#!/usr/bin/env python3

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any


SUMMARY_FIELDS = [
    "experiment_id",
    "label",
    "sample",
    "llvm_tag",
    "official_tag",
    "raja_tag",
    "metadata",
    "shared_deps",
    "raw_results",
    "parsed",
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
                    "label": "",
                    "sample": "",
                    "llvm_tag": "",
                    "official_tag": "",
                    "raja_tag": "",
                    "metadata": "invalid",
                    "shared_deps": "missing",
                    "raw_results": "missing",
                    "parsed": "missing",
                    "report": "missing",
                    "next_step": f"metadata invalid: {exc}",
                }
            )
            continue

        experiment = metadata.get("experiment", {})
        outputs = metadata.get("expected_outputs", {})
        paths = metadata.get("paths", {})
        shared_status = get_shared_dependency_status(outputs, paths)
        shared_ok = all(shared_status.values())
        official_ok = exists(outputs.get("official_results"))
        raja_ok = exists(outputs.get("raja_run_stamp"))
        parsed_ok = exists(outputs.get("parsed_csv"))
        report_ok = exists(outputs.get("report_html"))

        records.append(
            {
                "experiment_id": experiment.get("experiment_id", metadata_file.parent.name),
                "label": experiment.get("label", ""),
                "sample": experiment.get("sample", ""),
                "llvm_tag": experiment.get("llvm_tag", ""),
                "official_tag": experiment.get("official_tag", ""),
                "raja_tag": experiment.get("raja_tag", ""),
                "metadata": "present",
                "shared_deps": "present" if shared_ok else "missing",
                "raw_results": "present" if official_ok and raja_ok else "missing",
                "parsed": "present" if parsed_ok else "missing",
                "report": "present" if report_ok else "missing",
                "next_step": suggest_next_step(
                    shared_status,
                    official_ok,
                    raja_ok,
                    parsed_ok,
                    report_ok,
                ),
            }
        )
    return records


def get_shared_dependency_status(outputs: dict[str, Any], paths: dict[str, Any]) -> dict[str, bool]:
    expected_paths = {
        "llvm checkout": outputs.get("llvm_checkout_stamp") or _join_path(paths.get("llvm_source"), ".checkout_complete"),
        "official checkout": outputs.get("official_checkout_stamp")
        or _join_path(paths.get("official_source"), ".checkout_complete"),
        "RAJA checkout": outputs.get("raja_checkout_stamp") or _join_path(paths.get("raja_source"), ".checkout_complete"),
        "LLVM build": outputs.get("llvm_build_stamp") or _join_path(paths.get("llvm_build"), ".build_complete"),
        "official build": outputs.get("official_build_stamp") or _join_path(paths.get("official_build"), ".build_complete"),
        "RAJA build": outputs.get("raja_build_stamp") or _join_path(paths.get("raja_build"), ".build_complete"),
    }
    return {name: exists(path) for name, path in expected_paths.items()}


def _join_path(parent: str | None, child: str) -> str | None:
    if not parent:
        return None
    return str(Path(parent) / child)


def suggest_next_step(
    shared_status: dict[str, bool],
    official_ok: bool,
    raja_ok: bool,
    parsed_ok: bool,
    report_ok: bool,
) -> str:
    missing_shared = [name for name, ok in shared_status.items() if not ok]
    if missing_shared:
        return "rebuild shared dependency; missing " + " and ".join(missing_shared)
    if not official_ok or not raja_ok:
        missing = []
        if not official_ok:
            missing.append("official raw result")
        if not raja_ok:
            missing.append("RAJA raw result")
        return "run benchmark stage; missing " + " and ".join(missing)
    if not parsed_ok:
        return "rebuild parsed CSV target"
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
