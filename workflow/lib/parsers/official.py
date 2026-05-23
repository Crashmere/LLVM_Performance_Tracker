import json
import logging
from pathlib import Path
from typing import Any

from workflow.lib.parsers.base import ResultParser
from workflow.lib.result_schema import BenchmarkMetrics, BenchmarkRecord, safe_float, safe_int


class OfficialJsonAdapter(ResultParser):
    adapter_name = "official_json"
    result_filename = "baseline_results.json"

    def can_parse(self, path: Path) -> bool:
        return path.is_file() and path.name == self.result_filename

    def parse(
        self,
        path: Path,
        suite_version: str,
        compiler_ver: str,
        run_label: str,
    ) -> list[BenchmarkRecord]:
        raw_tests = parse_llvm_json(path)
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
                    compiler_tag=compiler_ver,
                    run_label=run_label,
                    test_name=test.get("name", "Unknown_Test"),
                    status=test.get("code", "UNKNOWN"),
                    metrics=metrics,
                    source_file=str(path),
                    parser_adapter=self.adapter_name,
                )
            )
        return records


def parse_llvm_json(file_path: Path) -> list[dict[str, Any]]:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("tests", [])
    except (json.JSONDecodeError, OSError) as e:
        logging.error("Failed to parse JSON %s: %s", file_path, e)
        return []
