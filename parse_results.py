#!/usr/bin/env python3

from __future__ import annotations

import csv
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd


logging.basicConfig(level=logging.WARNING, format="[%(levelname)s] %(message)s")


@dataclass
class BenchmarkMetrics:
    exec_time: float | None = None
    compile_time: float | None = None
    link_time: float | None = None
    binary_size: int | None = None
    text_size: int | None = None
    executable_hash: str | None = None
    bandwidth_gib: float | None = None
    flops_gflops: float | None = None
    extra_metrics: dict[str, float | str | int] = field(default_factory=dict)


@dataclass
class BenchmarkRecord:
    suite_name: str
    suite_version: str
    compiler_version: str
    run_label: str
    test_name: str
    status: str
    metrics: BenchmarkMetrics


def safe_float(value: Any) -> float | None:
    try:
        return float(value) if value is not None and value != "" else None
    except ValueError:
        return None


def safe_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None and value != "" else None
    except ValueError:
        return None


def parse_llvm_json(file_path: Path) -> list[dict[str, Any]]:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("tests", [])
    except (json.JSONDecodeError, OSError) as e:
        logging.error("Failed to parse JSON %s: %s", file_path, e)
        return []


def parse_raja_csv(file_path: Path) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader, None)
            header_row = next(reader, None)

            if not header_row:
                return []

            headers = [h.strip() for h in header_row]
            for row in reader:
                if not row:
                    continue
                row_dict = {headers[i]: col.strip() for i, col in enumerate(row) if i < len(headers)}
                results.append(row_dict)
    except OSError as e:
        logging.error("Failed to parse CSV %s: %s", file_path, e)
    return results


def extract_official_records(
    file_path: Path,
    suite_version: str,
    compiler_ver: str,
    run_label: str,
) -> list[BenchmarkRecord]:
    raw_tests = parse_llvm_json(file_path)
    records: list[BenchmarkRecord] = []
    for test in raw_tests:
        metrics_data = test.get("metrics", {})
        metrics = BenchmarkMetrics(
            exec_time=safe_float(metrics_data.get("exec_time")),
            compile_time=safe_float(metrics_data.get("compile_time")),
            link_time=safe_float(metrics_data.get("link_time")),
            binary_size=safe_int(metrics_data.get("size")),
            text_size=safe_int(metrics_data.get("size..text")),
            executable_hash=metrics_data.get("hash"),
        )

        for key, value in metrics_data.items():
            if key not in {"exec_time", "compile_time", "link_time", "size", "size..text", "hash"}:
                metrics.extra_metrics[key] = value

        records.append(
            BenchmarkRecord(
                suite_name="official",
                suite_version=suite_version,
                compiler_version=compiler_ver,
                run_label=run_label,
                test_name=test.get("name", "Unknown_Test"),
                status=test.get("code", "UNKNOWN"),
                metrics=metrics,
            )
        )
    return records


def extract_raja_records(
    file_path: Path,
    suite_version: str,
    compiler_ver: str,
    run_label: str,
) -> list[BenchmarkRecord]:
    raw_rows = parse_raja_csv(file_path)
    records: list[BenchmarkRecord] = []
    for row in raw_rows:
        kernel = row.get("Kernel", "Unknown")
        variant = row.get("Variant", "Unknown")
        tuning = row.get("Tuning", "Unknown")
        test_name = f"{kernel}_{variant}_{tuning}"

        records.append(
            BenchmarkRecord(
                suite_name="raja",
                suite_version=suite_version,
                compiler_version=compiler_ver,
                run_label=run_label,
                test_name=test_name,
                status=row.get("Checksum", "UNKNOWN"),
                metrics=BenchmarkMetrics(
                    exec_time=safe_float(row.get("Mean time per rep (sec.)")),
                    bandwidth_gib=safe_float(row.get("Mean Bandwidth (GiB per sec.)")),
                    flops_gflops=safe_float(row.get("Mean flops (gigaFLOP per sec.)")),
                ),
            )
        )
    return records


def parse_results_directory(base_dir: Path | str) -> list[BenchmarkRecord]:
    base_path = Path(base_dir)
    all_records: list[BenchmarkRecord] = []

    if not base_path.exists() or not base_path.is_dir():
        logging.error("Base directory %s does not exist.", base_path)
        return all_records

    for suite_dir in base_path.iterdir():
        if not suite_dir.is_dir():
            continue

        parts = suite_dir.name.split("-", 1)
        if len(parts) != 2:
            logging.warning("Skipping incorrectly formatted suite dir: %s", suite_dir.name)
            continue
        suite_name, suite_version = parts[0], parts[1]

        for compiler_dir in suite_dir.iterdir():
            if not compiler_dir.is_dir():
                continue
            compiler_ver = compiler_dir.name

            for run_dir in compiler_dir.iterdir():
                if not run_dir.is_dir():
                    continue
                run_label = run_dir.name

                if not any(run_dir.iterdir()):
                    logging.info("Skipping empty run directory: %s", run_dir)
                    continue

                if suite_name == "official":
                    target_file = run_dir / "baseline_results.json"
                    if target_file.exists():
                        all_records.extend(
                            extract_official_records(target_file, suite_version, compiler_ver, run_label)
                        )
                    else:
                        logging.warning("Expected JSON not found in %s", run_dir)
                elif suite_name == "raja":
                    target_file = run_dir / "RAJAPerf-kernel-run-data.csv"
                    if target_file.exists():
                        all_records.extend(
                            extract_raja_records(target_file, suite_version, compiler_ver, run_label)
                        )
                    else:
                        logging.warning("Expected CSV not found in %s", run_dir)
                else:
                    logging.warning("Unknown suite type: %s", suite_name)

    return all_records


def records_to_dataframe(records: list[BenchmarkRecord]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for record in records:
        row: dict[str, Any] = {
            "suite_name": record.suite_name,
            "suite_version": record.suite_version,
            "compiler_version": record.compiler_version,
            "run_label": record.run_label,
            "test_name": record.test_name,
            "status": record.status,
            "exec_time": record.metrics.exec_time,
            "compile_time": record.metrics.compile_time,
            "link_time": record.metrics.link_time,
            "binary_size": record.metrics.binary_size,
            "text_size": record.metrics.text_size,
            "executable_hash": record.metrics.executable_hash,
            "bandwidth_gib": record.metrics.bandwidth_gib,
            "flops_gflops": record.metrics.flops_gflops,
        }
        row.update(record.metrics.extra_metrics)
        rows.append(row)
    return pd.DataFrame(rows)


def filter_records(
    records: list[BenchmarkRecord],
    suite_name: str | None = None,
    compiler_version: str | None = None,
    run_label: str | None = None,
) -> list[BenchmarkRecord]:
    filtered = records
    if suite_name:
        filtered = [record for record in filtered if record.suite_name == suite_name]
    if compiler_version:
        filtered = [record for record in filtered if record.compiler_version == compiler_version]
    if run_label:
        filtered = [record for record in filtered if record.run_label == run_label]
    return filtered


def write_records_table(records: list[BenchmarkRecord], output_file: Path | str) -> Path:
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    df = records_to_dataframe(records)
    suffix = output_path.suffix.lower()
    if suffix == ".csv":
        df.to_csv(output_path, index=False)
    elif suffix == ".parquet":
        df.to_parquet(output_path, index=False)
    else:
        raise ValueError(f"Unsupported output format for {output_path}. Use .csv or .parquet.")

    return output_path
