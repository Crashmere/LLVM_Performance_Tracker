#!/usr/bin/env python3

import argparse
import os
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from workflow.lib.common import load_config


TOP_LEVEL_DIRS = [
    "sources",
    "builds",
    "installs",
    "results",
    "parsed",
    "reports",
    "metadata",
    "logs",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Report disk usage for workflow output directories without changing any files."
    )
    parser.add_argument("--config-file", default=str(REPO_ROOT / "config.yml"), help="Workflow config file.")
    parser.add_argument("--base-dir", help="Override the workflow base directory from the config file.")
    parser.add_argument(
        "--top",
        type=int,
        default=8,
        help="Number of largest immediate children to show for large directories.",
    )
    return parser.parse_args()


def directory_size(path: Path) -> int:
    total = 0
    if not path.exists():
        return total

    for root, dirs, files in os.walk(path, onerror=lambda error: None):
        root_path = Path(root)
        for name in files:
            file_path = root_path / name
            try:
                total += file_path.stat().st_size
            except OSError:
                continue
        for name in dirs:
            dir_path = root_path / name
            try:
                if dir_path.is_symlink():
                    total += dir_path.lstat().st_size
            except OSError:
                continue

    return total


def format_size(size: int) -> str:
    units = ["B", "KiB", "MiB", "GiB", "TiB"]
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TiB"


def immediate_children(path: Path) -> list[tuple[Path, int]]:
    if not path.exists() or not path.is_dir():
        return []

    children: list[tuple[Path, int]] = []
    for child in path.iterdir():
        try:
            if child.is_dir():
                size = directory_size(child)
            else:
                size = child.stat().st_size
        except OSError:
            continue
        children.append((child, size))

    return sorted(children, key=lambda item: item[1], reverse=True)


def print_table(rows: list[tuple[str, int]]) -> None:
    if not rows:
        print("(none)")
        return

    name_width = max(len(name) for name, _ in rows)
    for name, size in rows:
        print(f"{name:<{name_width}}  {format_size(size):>10}")


def main() -> int:
    args = parse_args()
    config = load_config(Path(args.config_file))
    base_dir = Path(args.base_dir or config["project"]["base_dir"]).expanduser().resolve()

    print(f"Base directory: {base_dir}")
    print()

    top_level_rows = [(name + "/", directory_size(base_dir / name)) for name in TOP_LEVEL_DIRS]
    print("Top-level workflow directories")
    print_table(top_level_rows)

    print()
    print(f"Largest immediate children per directory (top {args.top})")
    for name in TOP_LEVEL_DIRS:
        parent = base_dir / name
        children = immediate_children(parent)[: args.top]
        if not children:
            continue

        print()
        print(f"{name}/")
        rows = [(child.name + ("/" if child.is_dir() else ""), size) for child, size in children]
        print_table(rows)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
