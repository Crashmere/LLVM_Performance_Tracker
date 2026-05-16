from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from workflow.lib.common import build_experiment_id, get_experiment_layout_paths


FAILURE_MARKERS = ("[ERROR]", "Traceback", "RuntimeError", "FileNotFoundError", "RuleException", "MissingInputException")
STAGE_SEQUENCE = (
    "checkout_llvm",
    "checkout_official",
    "checkout_raja",
    "build_llvm",
    "build_official",
    "build_raja",
    "run_official",
    "run_raja",
    "parse_results",
    "aggregate_results",
    "generate_report",
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def get_batch_paths(base_dir: Path, batch_id: str) -> dict[str, Path]:
    batch_dir = base_dir / "logs" / "_batches" / batch_id
    return {
        "batch_dir": batch_dir,
        "manifest_json": batch_dir / "manifest.json",
        "summary_csv": batch_dir / "summary.csv",
    }


def _existing_paths(paths: list[Path]) -> list[Path]:
    return [path for path in paths if path.exists()]


def _latest_mtime(paths: list[Path]) -> str | None:
    existing = _existing_paths(paths)
    if not existing:
        return None
    latest = max(path.stat().st_mtime for path in existing)
    return datetime.fromtimestamp(latest, tz=timezone.utc).replace(microsecond=0).isoformat()


def _earliest_mtime(paths: list[Path]) -> str | None:
    existing = _existing_paths(paths)
    if not existing:
        return None
    earliest = min(path.stat().st_mtime for path in existing)
    return datetime.fromtimestamp(earliest, tz=timezone.utc).replace(microsecond=0).isoformat()


def _read_failure_excerpt(log_path: Path) -> str | None:
    if not log_path.exists():
        return None

    try:
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None

    matched = [line.strip() for line in lines if any(marker in line for marker in FAILURE_MARKERS)]
    if matched:
        return matched[-1][:300]
    if lines:
        return lines[-1].strip()[:300]
    return None


def _stage_specs(base_dir: Path, experiment: dict[str, Any]) -> dict[str, dict[str, Any]]:
    layout = get_experiment_layout_paths(base_dir, experiment)
    experiment_id = str(experiment["experiment_id"])
    llvm_tag = str(experiment["llvm_tag"])
    official_tag = str(experiment["official_tag"])
    raja_tag = str(experiment["raja_tag"])
    run_label = str(experiment["run_label"])

    return {
        "checkout_llvm": {
            "outputs": [layout["llvm_source"] / ".checkout_complete"],
            "log": base_dir / "logs" / "_shared" / "checkout_llvm" / llvm_tag / "checkout_llvm.log",
        },
        "checkout_official": {
            "outputs": [layout["official_source"] / ".checkout_complete"],
            "log": base_dir / "logs" / "_shared" / "checkout_official" / official_tag / "checkout_official.log",
        },
        "checkout_raja": {
            "outputs": [layout["raja_source"] / ".checkout_complete"],
            "log": base_dir / "logs" / "_shared" / "checkout_raja" / raja_tag / "checkout_raja.log",
        },
        "build_llvm": {
            "outputs": [
                layout["llvm_build"] / ".build_complete",
                layout["llvm_install"] / "bin" / "clang++",
            ],
            "log": base_dir / "logs" / "_shared" / "build_llvm" / llvm_tag / "build_llvm.log",
        },
        "build_official": {
            "outputs": [
                layout["official_build"] / ".build_complete",
                layout["official_build"] / "CMakeCache.txt",
            ],
            "log": base_dir / "logs" / "_shared" / "build_official" / official_tag / f"llvm-{llvm_tag}" / "build_official.log",
        },
        "build_raja": {
            "outputs": [
                layout["raja_build"] / ".build_complete",
                layout["raja_build"] / "bin" / "raja-perf.exe",
            ],
            "log": base_dir / "logs" / "_shared" / "build_raja" / raja_tag / f"llvm-{llvm_tag}" / "build_raja.log",
        },
        "run_official": {
            "outputs": [
                layout["official_result"] / ".run_complete",
                layout["official_result"] / "baseline_results.json",
            ],
            "log": base_dir / "logs" / "_runs" / "official" / official_tag / llvm_tag / run_label / "run_official.log",
        },
        "run_raja": {
            "outputs": [
                layout["raja_result"] / ".run_complete",
                layout["raja_result"] / "RAJAPerf-kernel-run-data.csv",
            ],
            "log": base_dir / "logs" / "_runs" / "raja" / raja_tag / llvm_tag / run_label / "run_raja.log",
        },
        "parse_results": {
            "outputs": [layout["parsed_run_dir"] / "benchmark_records.csv"],
            "log": base_dir / "logs" / experiment_id / "parse_results.log",
        },
        "aggregate_results": {
            "outputs": [layout["parsed_run_dir"] / "benchmark_records_aggregated.csv"],
            "log": base_dir / "logs" / experiment_id / "aggregate_results.log",
        },
        "generate_report": {
            "outputs": [layout["reports_run_dir"] / "benchmark_report.html"],
            "log": base_dir / "logs" / experiment_id / "generate_report.log",
        },
    }


def collect_experiment_status(base_dir: Path, experiment: dict[str, Any]) -> dict[str, Any]:
    stage_specs = _stage_specs(base_dir, experiment)
    stage_states: dict[str, dict[str, Any]] = {}
    seen_activity = False
    overall_status = "pending"
    failed_stage: str | None = None

    for stage_name in STAGE_SEQUENCE:
        spec = stage_specs[stage_name]
        outputs = [Path(path) for path in spec["outputs"]]
        log_path = Path(spec["log"])
        outputs_exist = all(path.exists() for path in outputs)
        log_exists = log_path.exists()
        failure_excerpt = _read_failure_excerpt(log_path)

        if outputs_exist:
            stage_status = "succeeded"
            seen_activity = True
        elif log_exists and failure_excerpt:
            stage_status = "failed"
            seen_activity = True
            if failed_stage is None:
                failed_stage = stage_name
                overall_status = "failed"
        elif failed_stage is not None:
            stage_status = "skipped"
        elif log_exists:
            stage_status = "running"
            seen_activity = True
            if overall_status != "failed":
                overall_status = "running"
        elif seen_activity:
            stage_status = "pending"
        else:
            stage_status = "pending"

        stage_states[stage_name] = {
            "status": stage_status,
            "log_path": str(log_path),
            "outputs": [str(path) for path in outputs],
            "failure_excerpt": failure_excerpt if stage_status == "failed" else None,
        }

    if overall_status != "failed":
        if stage_states["generate_report"]["status"] == "succeeded":
            overall_status = "succeeded"
        elif any(stage["status"] == "running" for stage in stage_states.values()):
            overall_status = "running"
        elif any(stage["status"] == "succeeded" for stage in stage_states.values()):
            overall_status = "pending"

    all_paths: list[Path] = []
    for stage in stage_states.values():
        all_paths.extend(Path(path) for path in stage["outputs"])
        all_paths.append(Path(stage["log_path"]))

    return {
        "experiment_id": str(experiment["experiment_id"]),
        "name": experiment.get("name"),
        "llvm_tag": str(experiment["llvm_tag"]),
        "official_tag": str(experiment["official_tag"]),
        "raja_tag": str(experiment["raja_tag"]),
        "run_label": str(experiment["run_label"]),
        "platform": experiment.get("platform"),
        "build_profile": experiment.get("build_profile"),
        "status": overall_status,
        "failed_stage": failed_stage,
        "failure_excerpt": stage_states[failed_stage]["failure_excerpt"] if failed_stage else None,
        "started_at": _earliest_mtime(all_paths),
        "finished_at": _latest_mtime(all_paths),
        "stage_statuses": stage_states,
        "parsed_csv": stage_states["parse_results"]["outputs"][0],
        "aggregated_csv": stage_states["aggregate_results"]["outputs"][0],
        "report_html": stage_states["generate_report"]["outputs"][0],
    }


def build_batch_manifest(workflow_config: dict[str, Any], batch_status: str) -> dict[str, Any]:
    base_dir = Path(workflow_config["project"]["base_dir"]).expanduser().resolve()
    experiments = workflow_config["experiments"]
    experiment_rows = [collect_experiment_status(base_dir, experiment) for experiment in experiments]
    status_counts = Counter(row["status"] for row in experiment_rows)

    return {
        "schema_version": 1,
        "generated_at": utc_now_iso(),
        "batch_id": workflow_config["batch"]["batch_id"],
        "batch_status": batch_status,
        "experiment_mode": workflow_config["experiment_mode"],
        "experiment_count": len(experiment_rows),
        "status_counts": dict(status_counts),
        "experiments": experiment_rows,
    }


def write_batch_manifest(manifest: dict[str, Any], manifest_path: Path) -> Path:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest_path


def write_summary_csv(manifest: dict[str, Any], summary_path: Path) -> Path:
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "experiment_id",
        "name",
        "llvm_tag",
        "official_tag",
        "raja_tag",
        "run_label",
        "platform",
        "build_profile",
        "status",
        "failed_stage",
        "failure_excerpt",
        "started_at",
        "finished_at",
        "parsed_csv",
        "aggregated_csv",
        "report_html",
    ]

    with summary_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for experiment in manifest["experiments"]:
            writer.writerow({field: experiment.get(field) for field in fieldnames})
    return summary_path


def discover_historical_experiments(base_dir: Path) -> list[dict[str, Any]]:
    results_root = base_dir / "results"
    experiments: dict[tuple[str, str, str, str], dict[str, Any]] = {}

    if not results_root.exists():
        return []

    for suite_dir in results_root.iterdir():
        if not suite_dir.is_dir() or "-" not in suite_dir.name:
            continue
        suite_name, suite_version = suite_dir.name.split("-", 1)

        for compiler_dir in suite_dir.iterdir():
            if not compiler_dir.is_dir():
                continue
            llvm_tag = compiler_dir.name

            for run_dir in compiler_dir.iterdir():
                if not run_dir.is_dir():
                    continue
                run_label = run_dir.name
                key = (llvm_tag, run_label)
                record = experiments.setdefault(
                    key,
                    {
                        "llvm_tag": llvm_tag,
                        "run_label": run_label,
                        "official_tag": None,
                        "raja_tag": None,
                    },
                )
                if suite_name == "official":
                    record["official_tag"] = suite_version
                elif suite_name == "raja":
                    record["raja_tag"] = suite_version

    discovered: list[dict[str, Any]] = []
    for record in experiments.values():
        official_tag = record.get("official_tag")
        raja_tag = record.get("raja_tag")
        if not official_tag or not raja_tag:
            continue
        experiment_id = build_experiment_id(
            record["llvm_tag"],
            official_tag,
            raja_tag,
            record["run_label"],
        )
        discovered.append(
            {
                "experiment_id": experiment_id,
                "llvm_tag": record["llvm_tag"],
                "official_tag": official_tag,
                "raja_tag": raja_tag,
                "run_label": record["run_label"],
                "llvm_version": record["llvm_tag"],
            }
        )

    return sorted(discovered, key=lambda item: (item["run_label"], item["llvm_tag"], item["official_tag"], item["raja_tag"]))


def summarize_historical_runs(base_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for experiment in discover_historical_experiments(base_dir):
        status_row = collect_experiment_status(base_dir, experiment)
        rows.append(status_row)
    return rows
