#!/usr/bin/env python3

from __future__ import annotations

import subprocess
import sys
from datetime import datetime
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from workflow.scripts.common import build_with_cmake, get_raja_cmake_args, normalize_ninja_jobs


log_path = Path(snakemake.log[0])
log_path.parent.mkdir(parents=True, exist_ok=True)


def log_message(message: str) -> None:
    timestamp = datetime.now().strftime("%H:%M:%S")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")


def run_cmd(cmd: list[str], cwd: Path | None = None, env: dict[str, str] | None = None) -> bool:
    cmd_str = [str(part) for part in cmd if part]
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"\n[{datetime.now().strftime('%H:%M:%S')}] Executing: {' '.join(cmd_str)}\n")
        f.write(f"Working Directory: {cwd or Path.cwd()}\n")
        f.write("-" * 40 + "\n")
        f.flush()
        try:
            subprocess.run(cmd_str, cwd=cwd, env=env, stdout=f, stderr=subprocess.STDOUT, check=True)
            return True
        except subprocess.CalledProcessError as e:
            log_message(f"[ERROR] Command failed with exit code {e.returncode}.")
            return False


source_dir = Path(snakemake.params.source_dir)
build_dir = Path(snakemake.params.build_dir)
llvm_install_dir = Path(snakemake.params.llvm_install_dir)
ninja_jobs = normalize_ninja_jobs(snakemake.params.ninja_jobs)

clang_path = llvm_install_dir / "bin" / "clang"
clangxx_path = llvm_install_dir / "bin" / "clang++"

build_dir.parent.mkdir(parents=True, exist_ok=True)

cmake_args = get_raja_cmake_args(
    source_dir=source_dir,
    clang_path=clang_path,
    clangxx_path=clangxx_path,
    llvm_install_dir=llvm_install_dir,
    cxx_standard=str(snakemake.params.cxx_standard),
)

success = build_with_cmake(
    build_dir=build_dir,
    cmake_args=cmake_args,
    ninja_jobs=ninja_jobs,
    run_cmd=run_cmd,
    status_callback=log_message,
)

if not success:
    raise RuntimeError(f"Failed to build RAJAPerf in {build_dir}")

exe_path = Path(snakemake.output.exe)
if not exe_path.exists():
    raise FileNotFoundError(f"Expected RAJA build artifact was not produced: {exe_path}")

stamp_path = Path(snakemake.output.stamp)
stamp_path.parent.mkdir(parents=True, exist_ok=True)
with open(stamp_path, "w", encoding="utf-8") as f:
    f.write(f"raja_source={source_dir}\n")
    f.write(f"llvm_install={llvm_install_dir}\n")
    f.write(f"completed_at={datetime.now().isoformat()}\n")
