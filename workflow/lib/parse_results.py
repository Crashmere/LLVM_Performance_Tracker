#!/usr/bin/env python3

import logging
from pathlib import Path

from workflow.lib.parsers.base import ParseError
from workflow.lib.parsers.official import OfficialJsonAdapter, parse_llvm_json
from workflow.lib.parsers.raja import (
    KernelRunDataAdapter,
    parse_kernel_run_data,
    parse_raja_result_directory,
)
from workflow.lib.result_schema import (
    BenchmarkMetrics,
    BenchmarkRecord,
    records_to_dataframe,
    safe_float,
    safe_int,
)


logging.basicConfig(level=logging.WARNING, format="[%(levelname)s] %(message)s")


def parse_raja_csv(file_path: Path) -> list[dict[str, str]]:
    return parse_kernel_run_data(file_path)


def extract_official_records(
    file_path: Path,
    suite_version: str,
    compiler_ver: str,
    run_label: str,
) -> list[BenchmarkRecord]:
    return OfficialJsonAdapter().parse(file_path, suite_version, compiler_ver, run_label)


def extract_raja_records(
    file_path: Path,
    suite_version: str,
    compiler_ver: str,
    run_label: str,
) -> list[BenchmarkRecord]:
    return KernelRunDataAdapter().parse(file_path, suite_version, compiler_ver, run_label)


def parse_results_directory(
    base_dir: Path | str,
    suite_name: str | None = None,
    compiler_version: str | None = None,
    run_label: str | None = None,
    suite_versions: dict[str, str] | None = None,
) -> list[BenchmarkRecord]:
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
        current_suite_name, suite_version = parts[0], parts[1]
        if suite_name and current_suite_name != suite_name:
            continue
        if suite_versions and current_suite_name in suite_versions and suite_version != suite_versions[current_suite_name]:
            continue

        for compiler_dir in suite_dir.iterdir():
            if not compiler_dir.is_dir():
                continue
            compiler_ver = compiler_dir.name
            if compiler_version and compiler_ver != compiler_version:
                continue

            for run_dir in compiler_dir.iterdir():
                if not run_dir.is_dir():
                    continue
                current_run_label = run_dir.name
                if run_label and current_run_label != run_label:
                    continue

                if not any(run_dir.iterdir()):
                    logging.info("Skipping empty run directory: %s", run_dir)
                    continue

                if current_suite_name == "official":
                    target_file = run_dir / "baseline_results.json"
                    if target_file.exists():
                        all_records.extend(
                            extract_official_records(target_file, suite_version, compiler_ver, current_run_label)
                        )
                    else:
                        logging.warning("Expected JSON not found in %s", run_dir)
                elif current_suite_name == "raja":
                    try:
                        all_records.extend(
                            parse_raja_result_directory(run_dir, suite_version, compiler_ver, current_run_label)
                        )
                    except ParseError as exc:
                        raise ParseError(str(exc)) from exc
                else:
                    logging.warning("Unknown suite type: %s", current_suite_name)

    return all_records


def filter_records(
    records: list[BenchmarkRecord],
    suite_name: str | None = None,
    compiler_version: str | None = None,
    run_label: str | None = None,
    suite_versions: dict[str, str] | None = None,
) -> list[BenchmarkRecord]:
    filtered = records
    if suite_name:
        filtered = [record for record in filtered if record.suite_name == suite_name]
    if compiler_version:
        filtered = [record for record in filtered if record.compiler_version == compiler_version]
    if run_label:
        filtered = [record for record in filtered if record.run_label == run_label]
    if suite_versions:
        filtered = [
            record
            for record in filtered
            if record.suite_name not in suite_versions or record.suite_version == suite_versions[record.suite_name]
        ]
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


__all__ = [
    "BenchmarkMetrics",
    "BenchmarkRecord",
    "extract_official_records",
    "extract_raja_records",
    "filter_records",
    "parse_llvm_json",
    "parse_raja_csv",
    "parse_results_directory",
    "records_to_dataframe",
    "safe_float",
    "safe_int",
    "write_records_table",
]
