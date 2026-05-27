import csv
import logging
from pathlib import Path

from workflow.lib.parsers.base import ParseError, ResultParser
from workflow.lib.result_schema import BenchmarkMetrics, BenchmarkRecord, safe_float


KERNEL_RUN_DATA = "RAJAPerf-kernel-run-data.csv"
TIMING_AVERAGE = "RAJAPerf-timing-Average.csv"
SUPPORTED_RAJA_RESULT_FILES = (KERNEL_RUN_DATA, TIMING_AVERAGE)


class KernelRunDataAdapter(ResultParser):
    adapter_name = "raja_kernel_run_data"
    result_filename = KERNEL_RUN_DATA

    def can_parse(self, path: Path) -> bool:
        return path.is_file() and path.name == self.result_filename and _looks_like_kernel_run_data(path)

    def parse(
        self,
        path: Path,
        suite_version: str,
        compiler_ver: str,
        label: str,
    ) -> list[BenchmarkRecord]:
        raw_rows = parse_kernel_run_data(path)
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
                    compiler_tag=compiler_ver,
                    label=label,
                    test_name=test_name,
                    status=row.get("Checksum", "UNKNOWN"),
                    metrics=BenchmarkMetrics(
                        exec_time=safe_float(row.get("Mean time per rep (sec.)")),
                        bandwidth_gib=safe_float(row.get("Mean Bandwidth (GiB per sec.)")),
                        flops_gflops=safe_float(row.get("Mean flops (gigaFLOP per sec.)")),
                    ),
                    source_file=str(path),
                    parser_adapter=self.adapter_name,
                )
            )
        return records


class TimingAverageAdapter(ResultParser):
    adapter_name = "raja_timing_average"
    result_filename = TIMING_AVERAGE

    def can_parse(self, path: Path) -> bool:
        return path.is_file() and path.name == self.result_filename and _looks_like_timing_average(path)

    def parse(
        self,
        path: Path,
        suite_version: str,
        compiler_ver: str,
        label: str,
    ) -> list[BenchmarkRecord]:
        rows = parse_timing_average(path)
        records: list[BenchmarkRecord] = []
        for row in rows:
            test_name = f"{row['kernel']}_{row['variant']}_{row['tuning']}"
            records.append(
                BenchmarkRecord(
                    suite_name="raja",
                    suite_version=suite_version,
                    compiler_version=compiler_ver,
                    compiler_tag=compiler_ver,
                    label=label,
                    test_name=test_name,
                    status="COMPLETED",
                    status_detail="Parsed from RAJAPerf timing average matrix; checksum is unavailable.",
                    metrics=BenchmarkMetrics(exec_time=row["exec_time"]),
                    source_file=str(path),
                    parser_adapter=self.adapter_name,
                )
            )
        return records


def parse_raja_result_directory(
    run_dir: Path,
    suite_version: str,
    compiler_ver: str,
    label: str,
) -> list[BenchmarkRecord]:
    adapters: list[ResultParser] = [KernelRunDataAdapter(), TimingAverageAdapter()]
    discovered = sorted(path.name for path in run_dir.glob("RAJAPerf*") if path.is_file())
    for filename in SUPPORTED_RAJA_RESULT_FILES:
        candidate = run_dir / filename
        for adapter in adapters:
            if adapter.can_parse(candidate):
                return adapter.parse(candidate, suite_version, compiler_ver, label)

    raise ParseError(
        "No supported RAJA result schema found in "
        f"{run_dir}. Found files: {', '.join(discovered) if discovered else 'none'}. "
        "Supported files: " + ", ".join(SUPPORTED_RAJA_RESULT_FILES)
    )


def parse_kernel_run_data(file_path: Path) -> list[dict[str, str]]:
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


def parse_timing_average(file_path: Path) -> list[dict[str, str | float]]:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader, None)
            variants = _strip_row(next(reader, []))
            tunings = _strip_row(next(reader, []))
            if not variants or not tunings:
                return []

            records: list[dict[str, str | float]] = []
            for row in reader:
                stripped = _strip_row(row)
                if not stripped or not stripped[0]:
                    continue
                kernel = stripped[0]
                for index in range(1, min(len(stripped), len(variants), len(tunings))):
                    exec_time = safe_float(stripped[index])
                    if exec_time is None:
                        continue
                    variant = variants[index]
                    tuning = tunings[index]
                    if not variant or not tuning:
                        continue
                    records.append(
                        {
                            "kernel": kernel,
                            "variant": variant,
                            "tuning": tuning,
                            "exec_time": exec_time,
                        }
                    )
            return records
    except OSError as e:
        logging.error("Failed to parse CSV %s: %s", file_path, e)
        return []


def _strip_row(row: list[str]) -> list[str]:
    return [value.strip() for value in row]


def _looks_like_kernel_run_data(path: Path) -> bool:
    try:
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader, None)
            headers = [value.strip() for value in next(reader, [])]
    except OSError:
        return False
    return {"Kernel", "Variant", "Tuning"}.issubset(set(headers))


def _looks_like_timing_average(path: Path) -> bool:
    try:
        first_line = path.read_text(encoding="utf-8", errors="replace").splitlines()[0]
    except (OSError, IndexError):
        return False
    return first_line.startswith("Mean Runtime Report")
