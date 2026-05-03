#!/usr/bin/env python3

import json
import csv
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any

logging.basicConfig(level=logging.WARNING, format='[%(levelname)s] %(message)s')

# ==========================================
# 1. Unified Data Structure
# ==========================================
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
    run_id: str
    test_name: str
    status: str
    metrics: BenchmarkMetrics

# ==========================================
# 2. Generic Parsers
# ==========================================
def safe_float(value: Any) -> float | None:
    try:
        return float(value) if value is not None and value != '' else None
    except ValueError:
        return None

def safe_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None and value != '' else None
    except ValueError:
        return None

def parse_llvm_json(file_path: Path) -> list[dict[str, Any]]:
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get("tests", [])
    except (json.JSONDecodeError, IOError) as e:
        logging.error(f"Failed to parse JSON {file_path}: {e}")
        return []

def parse_raja_csv(file_path: Path) -> list[dict[str, str]]:
    results = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader, None) 
            header_row = next(reader, None)
            
            if not header_row:
                return []
            
            headers = [h.strip() for h in header_row]
            
            for row in reader:
                if not row: continue
                row_dict = {headers[i]: col.strip() for i, col in enumerate(row) if i < len(headers)}
                results.append(row_dict)
    except Exception as e:
        logging.error(f"Failed to parse CSV {file_path}: {e}")
    return results

# ==========================================
# 3. Traversal & Mapping Logic
# ==========================================
def extract_official_records(file_path: Path, suite_version: str, compiler_ver: str, run_id: str) -> list[BenchmarkRecord]:
    raw_tests = parse_llvm_json(file_path)
    records = []
    for test in raw_tests:
        metrics_data = test.get("metrics", {})
        
        metrics = BenchmarkMetrics(
            exec_time=safe_float(metrics_data.get("exec_time")),
            compile_time=safe_float(metrics_data.get("compile_time")),
            link_time=safe_float(metrics_data.get("link_time")),
            binary_size=safe_int(metrics_data.get("size")),
            text_size=safe_int(metrics_data.get("size..text")),
            executable_hash=metrics_data.get("hash")
        )
        
        for k, v in metrics_data.items():
            if k not in ["exec_time", "compile_time", "link_time", "size", "size..text", "hash"]:
                metrics.extra_metrics[k] = v

        record = BenchmarkRecord(
            suite_name="official",
            suite_version=suite_version,
            compiler_version=compiler_ver,
            run_id=run_id,
            test_name=test.get("name", "Unknown_Test"),
            status=test.get("code", "UNKNOWN"),
            metrics=metrics
        )
        records.append(record)
    return records

def extract_raja_records(file_path: Path, suite_version: str, compiler_ver: str, run_id: str) -> list[BenchmarkRecord]:
    raw_rows = parse_raja_csv(file_path)
    records = []
    for row in raw_rows:
        kernel = row.get("Kernel", "Unknown")
        variant = row.get("Variant", "Unknown")
        tuning = row.get("Tuning", "Unknown")
        test_name = f"{kernel}_{variant}_{tuning}"

        metrics = BenchmarkMetrics(
            exec_time=safe_float(row.get("Mean time per rep (sec.)")),
            bandwidth_gib=safe_float(row.get("Mean Bandwidth (GiB per sec.)")),
            flops_gflops=safe_float(row.get("Mean flops (gigaFLOP per sec.)"))
        )

        record = BenchmarkRecord(
            suite_name="raja",
            suite_version=suite_version,
            compiler_version=compiler_ver,
            run_id=run_id,
            test_name=test_name,
            status=row.get("Checksum", "UNKNOWN"),
            metrics=metrics
        )
        records.append(record)
    return records

def parse_results_directory(base_dir: Path | str) -> list[BenchmarkRecord]:
    base_path = Path(base_dir)
    all_records: list[BenchmarkRecord] = []

    if not base_path.exists() or not base_path.is_dir():
        logging.error(f"Base directory {base_path} does not exist.")
        return all_records

    # Level 1: Suite and Tag (e.g., official-llvmorg-21.1.0)
    for suite_dir in base_path.iterdir():
        if not suite_dir.is_dir(): continue
        
        parts = suite_dir.name.split("-", 1)
        if len(parts) != 2:
            logging.warning(f"Skipping incorrectly formatted suite dir: {suite_dir.name}")
            continue
        suite_name, suite_version = parts[0], parts[1]

        # Level 2: Compiler Version (e.g., llvmorg-20.1.0)
        for compiler_dir in suite_dir.iterdir():
            if not compiler_dir.is_dir(): continue
            compiler_ver = compiler_dir.name

            # Level 3: Run ID (e.g., 20260317_205430)
            for run_dir in compiler_dir.iterdir():
                if not run_dir.is_dir(): continue
                run_id = run_dir.name

                if not any(run_dir.iterdir()):
                    logging.info(f"Skipping empty run directory (likely build failed): {run_dir}")
                    continue

                if suite_name == "official":
                    target_file = run_dir / "baseline_results.json"
                    if target_file.exists():
                        all_records.extend(extract_official_records(target_file, suite_version, compiler_ver, run_id))
                    else:
                        logging.warning(f"Expected JSON not found in {run_dir}")
                
                elif suite_name == "raja":
                    target_file = run_dir / "RAJAPerf-kernel-run-data.csv"
                    if target_file.exists():
                        all_records.extend(extract_raja_records(target_file, suite_version, compiler_ver, run_id))
                    else:
                        logging.warning(f"Expected CSV not found in {run_dir}")
                
                else:
                    logging.warning(f"Unknown suite type: {suite_name}")

    return all_records

if __name__ == "__main__":
    RESULTS_DIR = Path("~/auto/results").expanduser()
    
    parsed_records = parse_results_directory(RESULTS_DIR)
    
    print(f"Successfully parsed {len(parsed_records)} benchmark records.")

    official = 0
    raja = 0
    for record in parsed_records:
        if record.suite_name == "official":
            official += 1
        elif record.suite_name == "raja":
            raja += 1
    print(f"Records from official suite: {official}")
    print(f"Records from RAJA suite: {raja}")

    high = 0
    low = 0
    for record in parsed_records:
        if record.metrics.exec_time is not None:
            if record.metrics.exec_time > 0.1:
                high += 1
            else:
                low += 1
    
    print(f"Records with exec_time > 0.1s: {high}")
    print(f"Records with exec_time <= 0.1s: {low}")

    # for record in parsed_records:
    #     if record.suite_name == "raja":
    #         print(record)
    #         break