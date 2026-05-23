from dataclasses import dataclass, field
from typing import Any

import pandas as pd


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
    compiler_tag: str | None = None
    compiler_commit: str | None = None
    platform: str | None = None
    hostname: str | None = None
    source_file: str | None = None
    parser_adapter: str | None = None
    status_detail: str | None = None


def safe_float(value: Any) -> float | None:
    try:
        return float(value) if value is not None and value != "" else None
    except (TypeError, ValueError):
        return None


def safe_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None and value != "" else None
    except (TypeError, ValueError):
        return None


def records_to_dataframe(records: list[BenchmarkRecord]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for record in records:
        row: dict[str, Any] = {
            "suite_name": record.suite_name,
            "suite_version": record.suite_version,
            "compiler_tag": record.compiler_tag,
            "compiler_version": record.compiler_version,
            "compiler_commit": record.compiler_commit,
            "run_label": record.run_label,
            "platform": record.platform,
            "hostname": record.hostname,
            "test_name": record.test_name,
            "status": record.status,
            "status_detail": record.status_detail,
            "source_file": record.source_file,
            "parser_adapter": record.parser_adapter,
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
