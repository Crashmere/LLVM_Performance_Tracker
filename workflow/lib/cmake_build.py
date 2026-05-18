import shutil
from pathlib import Path
from typing import Callable


RunCommand = Callable[[list[str], Path | None, dict[str, str] | None], bool]
StatusCallback = Callable[[str], None]


def normalize_ninja_jobs(ninja_jobs: int) -> list[str]:
    if not isinstance(ninja_jobs, int):
        raise TypeError(f"build.ninja_jobs must be an integer, got {type(ninja_jobs).__name__}.")
    if ninja_jobs < 1:
        raise ValueError(f"build.ninja_jobs must be >= 1, got {ninja_jobs}.")
    return ["-j", str(ninja_jobs)]


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
    clean_build: bool = False,
    reconfigure: bool = True,
) -> bool:
    if clean_build:
        if status_callback:
            status_callback(f"Cleaning build directory before configure: {build_dir}")
        clear_directory(build_dir)
    build_dir.mkdir(parents=True, exist_ok=True)

    cmake_cache = build_dir / "CMakeCache.txt"
    should_configure = reconfigure or not cmake_cache.exists()
    if should_configure:
        if status_callback:
            status_callback("Configuring with CMake...")
        if not run_cmd(["cmake", "-G", "Ninja"] + cmake_args, build_dir, None):
            return False
    elif status_callback:
        status_callback(f"Skipping CMake configure because {cmake_cache} already exists.")

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
