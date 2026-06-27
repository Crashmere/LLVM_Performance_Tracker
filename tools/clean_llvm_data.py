#!/usr/bin/env python3

import argparse
import shutil
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from workflow.lib.common import load_config


LLVM_DIRS = [
    ("source", Path("sources") / "llvm-project"),
    ("build", Path("builds") / "llvm"),
    ("install", Path("installs") / "llvm"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Remove downloaded, built, and installed LLVM data without touching suite data."
    )
    parser.add_argument("--config-file", default=str(REPO_ROOT / "config.yml"), help="Workflow config file.")
    parser.add_argument("--base-dir", help="Override the workflow base directory from the config file.")
    parser.add_argument(
        "--tag",
        action="append",
        dest="tags",
        help="LLVM tag to remove. Can be passed multiple times. If omitted, all LLVM tag directories are selected.",
    )
    parser.add_argument(
        "--run",
        action="store_true",
        help="Actually delete selected directories. Without this flag, only print what would be removed.",
    )
    return parser.parse_args()


def directory_size(path: Path) -> int:
    total = 0
    if not path.exists():
        return total

    for child in path.rglob("*"):
        try:
            if child.is_file() or child.is_symlink():
                total += child.lstat().st_size
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


def resolve_base_dir(args: argparse.Namespace) -> Path:
    config = load_config(Path(args.config_file))
    return Path(args.base_dir or config["project"]["base_dir"]).expanduser().resolve()


def collect_targets(base_dir: Path, tags: list[str] | None) -> list[tuple[str, Path]]:
    requested_tags = set(tags or [])
    targets: list[tuple[str, Path]] = []

    for kind, relative_parent in LLVM_DIRS:
        parent = base_dir / relative_parent
        if not parent.exists():
            continue

        if requested_tags:
            children = [parent / tag for tag in sorted(requested_tags)]
        else:
            children = sorted(child for child in parent.iterdir() if child.is_dir())

        for child in children:
            if child.exists() and child.is_dir():
                targets.append((kind, child))

    return targets


def print_targets(targets: list[tuple[str, Path]]) -> None:
    if not targets:
        print("No LLVM source/build/install directories matched.")
        return

    kind_width = max(len(kind) for kind, _ in targets)
    total_size = 0
    for kind, path in targets:
        size = directory_size(path)
        total_size += size
        print(f"{kind:<{kind_width}}  {format_size(size):>10}  {path}")
    print(f"Total selected: {format_size(total_size)}")


def main() -> int:
    args = parse_args()
    base_dir = resolve_base_dir(args)
    targets = collect_targets(base_dir, args.tags)

    print(f"Base directory: {base_dir}")
    print_targets(targets)

    if not targets:
        return 0

    if not args.run:
        print()
        print("Dry run only. Re-run with --run to delete these directories.")
        return 0

    print()
    for kind, path in targets:
        print(f"Removing {kind}: {path}")
        shutil.rmtree(path)

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
