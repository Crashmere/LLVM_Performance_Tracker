#!/usr/bin/env python3

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


ROOT_DIR = Path(__file__).resolve().parent
INCLUDE_PATHS = [
    "run.sh",
    "config.yml",
    "workflow",
    "tools",
    "docs",
]
EXCLUDED_DIRS = {
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}
EXCLUDED_SUFFIXES = {
    ".pyc",
    ".pyo",
}
EXCLUDED_NAMES = {
    ".DS_Store",
}


def parse_args() -> argparse.Namespace:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    parser = argparse.ArgumentParser(
        description="Package selected project files into a zip archive."
    )
    parser.add_argument(
        "-o",
        "--output",
        default=f"msc_project_{timestamp}.zip",
        help="Output zip path. Defaults to msc_project_<timestamp>.zip in the repository root.",
    )
    return parser.parse_args()


def should_exclude(path: Path) -> bool:
    if any(part in EXCLUDED_DIRS for part in path.parts):
        return True
    if path.name in EXCLUDED_NAMES:
        return True
    return path.suffix in EXCLUDED_SUFFIXES


def collect_files(output_path: Path) -> list[Path]:
    files: list[Path] = []
    for relative in INCLUDE_PATHS:
        path = ROOT_DIR / relative
        if not path.exists():
            raise FileNotFoundError(f"Required path does not exist: {path}")

        if path.is_file():
            if path.resolve() != output_path.resolve() and not should_exclude(path):
                files.append(path)
            continue

        for child in sorted(path.rglob("*")):
            if child.is_file() and child.resolve() != output_path.resolve() and not should_exclude(child):
                files.append(child)
    return files


def main() -> int:
    args = parse_args()
    output_path = Path(args.output).expanduser()
    if not output_path.is_absolute():
        output_path = ROOT_DIR / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)

    files = collect_files(output_path)
    with ZipFile(output_path, "w", compression=ZIP_DEFLATED) as archive:
        for file_path in files:
            archive.write(file_path, file_path.relative_to(ROOT_DIR))

    print(f"Wrote {output_path}")
    print(f"Included {len(files)} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
