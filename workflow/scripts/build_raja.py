#!/usr/bin/env python3

import sys
from datetime import datetime
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from workflow.lib.command_runner import CommandRunner
from workflow.lib.build_configs import get_raja_cmake_args
from workflow.lib.cmake_build import build_with_cmake, normalize_ninja_jobs


runner = CommandRunner.from_snakemake(snakemake)


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
    run_cmd=runner.run,
    status_callback=runner.log,
    clean_build=bool(snakemake.params.clean_build),
    reconfigure=bool(snakemake.params.reconfigure),
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
