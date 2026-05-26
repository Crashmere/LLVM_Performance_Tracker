#!/usr/bin/env python3

import logging
from pathlib import Path

from workflow.lib.parsers.base import ParseError
from workflow.lib.parsers.official import OfficialJsonAdapter
from workflow.lib.parsers.raja import parse_raja_result_directory
from workflow.lib.result_schema import BenchmarkRecord, records_to_dataframe


logging.basicConfig(level=logging.WARNING, format="[%(levelname)s] %(message)s")


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
                            OfficialJsonAdapter().parse(
                                target_file,
                                suite_version,
                                compiler_ver,
                                current_run_label,
                            )
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
