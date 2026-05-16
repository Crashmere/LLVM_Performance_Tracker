import shutil
from pathlib import Path
from typing import Any, Callable


RunCommand = Callable[[list[str], Path | None, dict[str, str] | None], bool]
StatusCallback = Callable[[str], None]


def normalize_ninja_jobs(ninja_jobs: list[Any] | int | str | None) -> list[str]:
    if ninja_jobs is None:
        return []
    if isinstance(ninja_jobs, int):
        return ["-j", str(ninja_jobs)]
    if isinstance(ninja_jobs, str):
        value = ninja_jobs.strip()
        if not value:
            return []
        if value.isdigit():
            return ["-j", value]
        return [value]
    return [str(job) for job in ninja_jobs]


def clear_directory(dir_path: Path) -> None:
    if not dir_path.exists():
        return

    for item in dir_path.iterdir():
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()


def build_with_cmake(
    build_dir: Path,
    cmake_args: list[str],
    ninja_jobs: list[str],
    run_cmd: RunCommand,
    status_callback: StatusCallback | None = None,
    install: bool = False,
    clear_first: bool = True,
) -> bool:
    if clear_first:
        clear_directory(build_dir)
    build_dir.mkdir(parents=True, exist_ok=True)

    if status_callback:
        status_callback("Configuring with CMake...")
    if not run_cmd(["cmake", "-G", "Ninja"] + cmake_args, build_dir, None):
        return False

    if status_callback:
        status_callback("Compiling...")
    if not run_cmd(["ninja"] + ninja_jobs, build_dir, None):
        return False

    if install:
        if status_callback:
            status_callback("Installing...")
        if not run_cmd(["ninja", "install"], build_dir, None):
            return False

    return True
