#!/usr/bin/env python3

import argparse
import json
import platform
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from workflow.lib.common import load_config
from workflow.lib.layout import get_experiment_layout_paths


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write a provenance metadata file for one experiment.")
    parser.add_argument("--config-file", required=True, help="Workflow config file used to define experiments.")
    parser.add_argument("--base-dir", required=True, help="Resolved workflow base directory.")
    parser.add_argument("--experiment-json", required=True, help="Normalized experiment JSON from the Snakefile.")
    parser.add_argument("--experiment-mode", required=True, help="Normalized experiment mode from the Snakefile.")
    parser.add_argument("--output-file", required=True, help="Output experiment metadata JSON file.")
    return parser.parse_args()


def _path_map_to_strings(paths: dict[str, Path]) -> dict[str, str]:
    return {key: str(value) for key, value in sorted(paths.items())}


def _command_output(cmd: list[str]) -> str | None:
    try:
        return subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def collect_environment() -> dict[str, Any]:
    cpu_model = None
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.exists():
        for line in cpuinfo.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("model name"):
                _, value = line.split(":", 1)
                cpu_model = value.strip()
                break

    return {
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "kernel": platform.release(),
        "machine": platform.machine(),
        "cpu_model": cpu_model,
        "python_version": platform.python_version(),
        "snakemake_version": _command_output([sys.executable, "-m", "snakemake", "--version"]),
    }


def build_metadata(
    config_file: Path,
    base_dir: Path,
    experiment: dict[str, Any],
    experiment_mode: str,
) -> dict[str, Any]:
    raw_config = load_config(config_file)
    layout = get_experiment_layout_paths(base_dir, experiment)

    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "experiment": experiment,
        "experiment_mode": experiment_mode,
        "workflow": {
            "config_file": str(config_file.resolve()),
            "base_dir": str(base_dir.resolve()),
        },
        "paths": _path_map_to_strings(layout),
        "expected_outputs": {
            "llvm_checkout_stamp": str(layout["llvm_source"] / ".checkout_complete"),
            "official_checkout_stamp": str(layout["official_source"] / ".checkout_complete"),
            "raja_checkout_stamp": str(layout["raja_source"] / ".checkout_complete"),
            "llvm_build_stamp": str(layout["llvm_build"] / ".build_complete"),
            "official_build_stamp": str(layout["official_build"] / ".build_complete"),
            "raja_build_stamp": str(layout["raja_build"] / ".build_complete"),
            "official_results": str(layout["official_result"] / "baseline_results.json"),
            "raja_results": str(layout["raja_result"] / "RAJAPerf-kernel-run-data.csv"),
            "parsed_csv": str(layout["parsed_run_dir"] / "benchmark_records.csv"),
            "aggregated_csv": str(layout["parsed_run_dir"] / "benchmark_records_aggregated.csv"),
            "report_html": str(layout["reports_run_dir"] / "benchmark_report.html"),
            "metadata_json": str(layout["metadata_run_dir"] / "experiment.json"),
        },
        "logs": {
            "parse_results": str(layout["logs_run_dir"] / "parse_results.log"),
            "aggregate_results": str(layout["logs_run_dir"] / "aggregate_results.log"),
            "generate_report": str(layout["logs_run_dir"] / "generate_report.log"),
            "run_official": str(
                base_dir
                / "logs"
                / "_runs"
                / "official"
                / str(experiment["official_tag"])
                / str(experiment["llvm_tag"])
                / str(experiment["run_label"])
                / "run_official.log"
            ),
            "run_raja": str(
                base_dir
                / "logs"
                / "_runs"
                / "raja"
                / str(experiment["raja_tag"])
                / str(experiment["llvm_tag"])
                / str(experiment["run_label"])
                / "run_raja.log"
            ),
        },
        "shared_logs": {
            "checkout_llvm": str(
                base_dir
                / "logs"
                / "_shared"
                / "checkout_llvm"
                / str(experiment["llvm_tag"])
                / "checkout_llvm.log"
            ),
            "checkout_official": str(
                base_dir
                / "logs"
                / "_shared"
                / "checkout_official"
                / str(experiment["official_tag"])
                / "checkout_official.log"
            ),
            "checkout_raja": str(
                base_dir
                / "logs"
                / "_shared"
                / "checkout_raja"
                / str(experiment["raja_tag"])
                / "checkout_raja.log"
            ),
            "build_llvm": str(
                base_dir
                / "logs"
                / "_shared"
                / "build_llvm"
                / str(experiment["llvm_tag"])
                / "build_llvm.log"
            ),
            "build_official": str(
                base_dir
                / "logs"
                / "_shared"
                / "build_official"
                / str(experiment["official_tag"])
                / f"llvm-{experiment['llvm_tag']}"
                / "build_official.log"
            ),
            "build_raja": str(
                base_dir
                / "logs"
                / "_shared"
                / "build_raja"
                / str(experiment["raja_tag"])
                / f"llvm-{experiment['llvm_tag']}"
                / "build_raja.log"
            ),
        },
        "environment": collect_environment(),
        "config_snapshot": raw_config,
    }


def main() -> int:
    args = parse_args()
    output_file = Path(args.output_file)
    experiment = json.loads(args.experiment_json)
    metadata = build_metadata(
        config_file=Path(args.config_file),
        base_dir=Path(args.base_dir).expanduser().resolve(),
        experiment=experiment,
        experiment_mode=args.experiment_mode,
    )

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote experiment metadata to {output_file.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
