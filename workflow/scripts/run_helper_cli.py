#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from workflow.lib.common import load_config, normalize_workflow_config
from workflow.lib.run_manifest import get_batch_paths


def read_raw_config(config_path: Path) -> dict[str, Any]:
    with config_path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}
    if not isinstance(config, dict):
        raise ValueError(f"Configuration at {config_path} must be a mapping.")
    return config


def resolve_base_dir(config_path: Path) -> Path:
    config = read_raw_config(config_path)
    project = config.get("project", {})
    base_dir = project.get("base_dir", "~/msc/auto")
    return Path(base_dir).expanduser().resolve()


def resolve_run_label_override(config_path: Path) -> str:
    config = load_config(config_path)
    runs = config.get("runs", {})
    experiments = config.get("experiments", [])

    has_global_label = bool(runs.get("labels")) or bool(runs.get("run_label"))
    needs_explicit_default = False
    for experiment in experiments:
        if not isinstance(experiment, dict):
            continue
        if not experiment.get("run_label") and not experiment.get("run_labels"):
            needs_explicit_default = True
            break

    if has_global_label or (experiments and not needs_explicit_default):
        return ""
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def find_latest_batch_file(base_dir: Path, filename: str) -> Path | None:
    batch_root = base_dir / "logs" / "_batches"
    if not batch_root.exists():
        return None

    candidates = [path / filename for path in batch_root.iterdir() if path.is_dir() and (path / filename).exists()]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def show_size(base_dir: Path) -> int:
    parts = ("sources", "builds", "installs", "results", "parsed", "reports", "logs")
    print(f"Base directory: {base_dir}")
    print()
    for part in parts:
        target = base_dir / part
        if target.exists():
            result = subprocess.run(["du", "-sh", str(target)], check=True, text=True, capture_output=True)
            print(result.stdout.strip())
        else:
            print(f"0\t{target} (missing)")
    return 0


def clean_runs(base_dir: Path) -> int:
    targets = (
        base_dir / "results",
        base_dir / "parsed",
        base_dir / "reports",
        base_dir / "logs" / "_runs",
    )

    for target in targets:
        shutil.rmtree(target, ignore_errors=True)
        target.mkdir(parents=True, exist_ok=True)

    logs_root = base_dir / "logs"
    if logs_root.exists():
        for child in logs_root.iterdir():
            if child.name in {"_shared", "_runs"}:
                continue
            if child.is_dir():
                shutil.rmtree(child)

    print(f"Removed run outputs under {base_dir}")
    print("Kept sources/, builds/, installs/, and logs/_shared/")
    return 0


def show_cached_sources(base_dir: Path) -> int:
    sources_dir = base_dir / "sources"
    groups = (
        ("llvm-project", "llvm"),
        ("official", "official"),
        ("raja", "raja"),
    )

    print(f"Base directory: {base_dir}")
    print()

    if not sources_dir.exists():
        print("No source cache found.")
        return 0

    for dir_name, label in groups:
        target_dir = sources_dir / dir_name
        print(f"{label}:")
        if not target_dir.exists():
            print("  - (missing)")
            continue

        entries = sorted(path.name for path in target_dir.iterdir() if path.is_dir())
        if not entries:
            print("  - (none)")
            continue
        for entry in entries:
            print(f"  - {entry}")
    return 0


def show_batch_status(base_dir: Path) -> int:
    summary_csv = find_latest_batch_file(base_dir, "summary.csv")
    manifest_json = find_latest_batch_file(base_dir, "manifest.json")

    if not summary_csv or not manifest_json:
        print("No batch summary found for the current config.")
        return 1

    manifest = json.loads(manifest_json.read_text(encoding="utf-8"))
    with summary_csv.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    counts = Counter(row.get("status", "unknown") for row in rows)
    print(f"Batch ID: {manifest['batch_id']}")
    print(f"Batch status: {manifest['batch_status']}")
    print(f"Manifest: {manifest_json}")
    print(f"Summary: {summary_csv}")
    print()
    for key in sorted(counts):
        print(f"{key}: {counts[key]}")
    return 0


def latest_summary_run_label(summary_csv: Path) -> str:
    with summary_csv.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        return ""
    return rows[0].get("run_label", "")


def retry_failed(base_dir: Path, snakemake_bin: Path, snakefile: Path, default_jobs: int, default_args: list[str]) -> int:
    summary_csv = find_latest_batch_file(base_dir, "summary.csv")
    if not summary_csv:
        print(f"No batch summary found under {base_dir / 'logs' / '_batches'}", file=sys.stderr)
        return 1

    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "workflow" / "scripts" / "retry_failed_cli.py"),
            "--summary-csv",
            str(summary_csv),
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    failed_targets = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if not failed_targets:
        print(f"No failed experiments found in {summary_csv}")
        return 0

    env = os.environ.copy()
    run_label = latest_summary_run_label(summary_csv)
    if run_label:
        env["MSC_RUN_LABEL_OVERRIDE"] = run_label

    completed = subprocess.run(
        [str(snakemake_bin), "-s", str(snakefile), "-j", str(default_jobs), *default_args, *failed_targets],
        env=env,
        check=False,
    )
    return completed.returncode


def list_history(base_dir: Path) -> int:
    completed = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "workflow" / "scripts" / "history_runs_cli.py"),
            "--base-dir",
            str(base_dir),
        ],
        check=False,
    )
    return completed.returncode


def recover(base_dir: Path, target_id: str, extra_args: list[str]) -> int:
    command = [
        sys.executable,
        str(REPO_ROOT / "workflow" / "scripts" / "recover_run_cli.py"),
        "--base-dir",
        str(base_dir),
    ]
    if target_id.startswith("llvm_") and "__official_" in target_id and "__raja_" in target_id and "__run_" in target_id:
        command.extend(["--experiment-id", target_id])
    else:
        command.extend(["--run-label", target_id])
    command.extend(extra_args)
    completed = subprocess.run(command, check=False)
    return completed.returncode


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Helper actions for the workflow run wrapper.")
    parser.add_argument("command", choices=["base-dir", "run-label-override", "clean", "size", "src", "status", "retry", "hist", "recover"])
    parser.add_argument("--config", default="config.yml", help="Path to config.yml.")
    parser.add_argument("--snakemake-bin", help="Path to snakemake executable.")
    parser.add_argument("--snakefile", help="Path to Snakefile.")
    parser.add_argument("--default-jobs", type=int, default=2, help="Default Snakemake jobs.")
    parser.add_argument("--default-arg", action="append", default=[], help="Default Snakemake arg, repeat as needed.")
    parser.add_argument("--target-id", help="run_label or experiment_id for recover.")
    parser.add_argument("extra", nargs="*", help="Extra arguments for the helper command.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config_path = Path(args.config).resolve()
    base_dir = resolve_base_dir(config_path)

    if args.command == "base-dir":
        print(base_dir)
        return 0
    if args.command == "run-label-override":
        print(resolve_run_label_override(config_path))
        return 0
    if args.command == "clean":
        return clean_runs(base_dir)
    if args.command == "size":
        return show_size(base_dir)
    if args.command == "src":
        return show_cached_sources(base_dir)
    if args.command == "status":
        return show_batch_status(base_dir)
    if args.command == "retry":
        if not args.snakemake_bin or not args.snakefile:
            raise ValueError("retry requires --snakemake-bin and --snakefile")
        return retry_failed(
            base_dir,
            Path(args.snakemake_bin),
            Path(args.snakefile),
            args.default_jobs,
            list(args.default_arg),
        )
    if args.command == "hist":
        return list_history(base_dir)
    if args.command == "recover":
        if not args.target_id:
            raise ValueError("recover requires --target-id")
        return recover(base_dir, args.target_id, list(args.extra))
    raise ValueError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
