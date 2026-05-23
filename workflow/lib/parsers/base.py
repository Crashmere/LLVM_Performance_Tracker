from abc import ABC, abstractmethod
from pathlib import Path

from workflow.lib.result_schema import BenchmarkRecord


class ParseError(RuntimeError):
    pass


class ResultParser(ABC):
    adapter_name: str

    @abstractmethod
    def can_parse(self, path: Path) -> bool:
        raise NotImplementedError

    @abstractmethod
    def parse(
        self,
        path: Path,
        suite_version: str,
        compiler_ver: str,
        run_label: str,
    ) -> list[BenchmarkRecord]:
        raise NotImplementedError
