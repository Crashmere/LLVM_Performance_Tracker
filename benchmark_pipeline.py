#!/usr/bin/env python3

import os
import sys
import subprocess
import venv
from datetime import datetime
from pathlib import Path

# ==========================================
# 0. Environment Bootstrapping
# ==========================================
SCRIPT_DIR = Path(__file__).resolve().parent
VENV_DIR = SCRIPT_DIR / ".venv"
VENV_PYTHON = VENV_DIR / "bin" / "python"

def bootstrap_env() -> None:
    timestamp = datetime.now().strftime('%H:%M:%S')
    print(f"[{timestamp}] >>> Verifying virtual environment...")
    
    if not VENV_DIR.exists():
        print(f"[{timestamp}] >>> Creating new virtual environment at {VENV_DIR}...")
        venv.create(VENV_DIR, with_pip=True)

    pip_exe = VENV_DIR / "bin" / "pip"
    subprocess.run([str(pip_exe), "install", "--upgrade", "pip", "-q"], check=True)
    subprocess.run([str(pip_exe), "install", "pyyaml", "lit", "-q"], check=True)

if Path(sys.executable).resolve() != VENV_PYTHON.resolve():
    bootstrap_env()
    print(f"[{datetime.now().strftime('%H:%M:%S')}] >>> Dependencies ready. Re-executing script within venv...")
    os.execv(str(VENV_PYTHON), [str(VENV_PYTHON)] + sys.argv)

from typing import Any

from workflow.scripts.common import (
    build_with_cmake,
    get_layout_paths,
    get_llvm_cmake_args,
    get_official_cmake_args,
    get_raja_cmake_args,
    load_config,
    normalize_workflow_config,
    normalize_ninja_jobs,
    prepare_git_repo,
    resolve_llvm_version,
)

# ==========================================
# 1. Configuration & Globals
# ==========================================
CONFIG_FILE = SCRIPT_DIR / "config.yml"

if not CONFIG_FILE.exists():
    print(f"Error: Configuration file not found at {CONFIG_FILE}")
    sys.exit(1)

raw_config: dict[str, Any] = load_config(CONFIG_FILE)
config: dict[str, Any] = normalize_workflow_config(raw_config)

BASE_DIR = Path(config["project"]["base_dir"]).expanduser().resolve()
RUN_LABEL = str(config["runs"]["run_label"])

LLVM_TAG = str(config["llvm"]["tags"][0])
LLVM_VERSION = resolve_llvm_version(LLVM_TAG)

LLVM_REPO_URL = config["llvm"]["repo_url"]
NINJA_JOBS = normalize_ninja_jobs(config["llvm"]["build"].get("ninja_jobs", []))
HOST_C_COMPILER = config["llvm"]["build"].get("c_compiler", "gcc")
HOST_CXX_COMPILER = config["llvm"]["build"].get("cxx_compiler", "g++")

OFFICIAL_REPO_URL = config["test_suite"]["official"]["repo_url"]
OFFICIAL_TAG = str(config["test_suite"]["official"]["tags"][0])
OFFICIAL_CXX_STD = str(config["test_suite"]["official"].get("cxx_standard", "17"))

RAJA_REPO_URL = config["test_suite"]["raja"]["repo_url"]
RAJA_TAG = str(config["test_suite"]["raja"]["tags"][0])
RAJA_CXX_STD = str(config["test_suite"]["raja"].get("cxx_standard", "17"))

LAYOUT = get_layout_paths(BASE_DIR, LLVM_TAG, OFFICIAL_TAG, RAJA_TAG, LLVM_VERSION, RUN_LABEL)
LLVM_CUSTOM_DIR = LAYOUT["llvm_install"]
CLANGXX_PATH = LLVM_CUSTOM_DIR / "bin" / "clang++"
CLANG_PATH = LLVM_CUSTOM_DIR / "bin" / "clang"

LOG_DIR = LAYOUT["logs_run_dir"]
LOG_DIR.mkdir(parents=True, exist_ok=True)
SUMMARY_LOG_FILE = LOG_DIR / "00_summary.log"
CURRENT_LOG_FILE: Path | None = None

with open(SUMMARY_LOG_FILE, "w", encoding="utf-8") as f:
    f.write(f"--- Automated Benchmark Summary | Initiated: {datetime.now()} ---\n")

# ==========================================
# 2. Utility Functions
# ==========================================
def set_current_log(step_name: str) -> None:
    global CURRENT_LOG_FILE
    CURRENT_LOG_FILE = LOG_DIR / f"{step_name}.log"
    with open(CURRENT_LOG_FILE, "w", encoding="utf-8") as f:
        f.write(f"--- {step_name} Initiated: {datetime.now()} ---\n")

def print_step(msg: str) -> None:
    timestamp = datetime.now().strftime('%H:%M:%S')
    console_msg = f"[{timestamp}] >>> {msg}"
    print(f"\n{console_msg}")
    
    with open(SUMMARY_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{console_msg}\n")
    
    if CURRENT_LOG_FILE and CURRENT_LOG_FILE.exists():
        with open(CURRENT_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"\n{console_msg}\n")

def run_cmd(cmd: list[str], cwd: Path | None = None, env: dict[str, str] | None = None) -> bool:
    if not CURRENT_LOG_FILE:
        print_step("[ERROR] Log file not set before running command.")
        return False

    cmd_str_list = [str(c) for c in cmd if c]
    with open(CURRENT_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"\n[{datetime.now().strftime('%H:%M:%S')}] Executing: {' '.join(cmd_str_list)}\n")
        f.write(f"Working Directory: {cwd or os.getcwd()}\n")
        f.write("-" * 40 + "\n")
        f.flush()
        try:
            subprocess.run(cmd_str_list, cwd=cwd, env=env, stdout=f, stderr=subprocess.STDOUT, check=True)
            return True
        except subprocess.CalledProcessError as e:
            print_step(f"[ERROR] Command failed with exit code {e.returncode}. Check {CURRENT_LOG_FILE.name} for details.")
            return False

# ==========================================
# 3. Core Phase Functions
# ==========================================
def setup_directories() -> tuple[Path, Path]:
    set_current_log("01_init_directories")
    print_step("Phase 1: Initializing directory structure...")

    dirs_to_create = [
        LAYOUT["sources_root"],
        LAYOUT["builds_root"],
        LAYOUT["installs_root"],
        LAYOUT["results_root"],
        LAYOUT["parsed_root"],
        LAYOUT["reports_root"],
        LAYOUT["logs_root"],
        LAYOUT["llvm_source"].parent,
        LAYOUT["official_source"].parent,
        LAYOUT["raja_source"].parent,
        LAYOUT["llvm_build"].parent,
        LAYOUT["official_build"].parent,
        LAYOUT["raja_build"].parent,
        LAYOUT["llvm_install"].parent,
        LAYOUT["official_result"],
        LAYOUT["raja_result"],
    ]

    for d in dirs_to_create:
        d.mkdir(parents=True, exist_ok=True)

    print_step(f"Using run_label: {RUN_LABEL}")
    print_step(f"LLVM source/build/install directories: {LAYOUT['llvm_source']} | {LAYOUT['llvm_build']} | {LAYOUT['llvm_install']}")
    return LAYOUT["official_result"], LAYOUT["raja_result"]

def build_llvm() -> bool:
    set_current_log("02_build_llvm")
    
    if CLANGXX_PATH.exists() and os.access(CLANGXX_PATH, os.X_OK):
        print_step(f"LLVM compiler already exists at {LLVM_CUSTOM_DIR}.")
        print_step("Skipping LLVM build phase to save time.")
        return True

    print_step(f"Phase 2: Building and installing LLVM (Tag: {LLVM_TAG})...")
    llvm_project_dir = LAYOUT["llvm_source"]
    llvm_build_dir = LAYOUT["llvm_build"]

    if not prepare_git_repo(LLVM_REPO_URL, llvm_project_dir, LLVM_TAG, run_cmd, print_step):
        return False

    cmake_args = get_llvm_cmake_args(HOST_C_COMPILER, HOST_CXX_COMPILER, LLVM_CUSTOM_DIR)
    if build_with_cmake(llvm_build_dir, cmake_args, NINJA_JOBS, run_cmd, print_step, install=True):
        print_step("LLVM built and installed successfully.")
        return True
    return False

def build_official_suite() -> bool:
    set_current_log("03_build_official_suite")
    print_step(f"Phase 3: Building LLVM Official Test Suite (Tag: {OFFICIAL_TAG}, C++{OFFICIAL_CXX_STD})...")
    official_src_dir = LAYOUT["official_source"]
    official_build_dir = LAYOUT["official_build"]

    if not prepare_git_repo(OFFICIAL_REPO_URL, official_src_dir, OFFICIAL_TAG, run_cmd, print_step):
        return False

    cmake_args = get_official_cmake_args(CLANG_PATH, CLANGXX_PATH, OFFICIAL_CXX_STD)
    if build_with_cmake(official_build_dir, cmake_args, NINJA_JOBS, run_cmd, print_step):
        print_step("Official Test Suite built successfully.")
        return True
    return False

def build_raja_suite() -> bool:
    set_current_log("04_build_raja_suite")
    print_step(f"Phase 4: Building RAJA Performance Suite (Tag: {RAJA_TAG}, C++{RAJA_CXX_STD})...")
    raja_src_dir = LAYOUT["raja_source"]
    raja_build_dir = LAYOUT["raja_build"]

    if not prepare_git_repo(RAJA_REPO_URL, raja_src_dir, RAJA_TAG, run_cmd, print_step, recursive=True):
        return False

    try:
        cmake_args = get_raja_cmake_args(CLANG_PATH, CLANGXX_PATH, LLVM_CUSTOM_DIR, RAJA_CXX_STD)
    except (FileNotFoundError, RuntimeError) as e:
        print_step(f"[ERROR] {e}")
        return False

    if build_with_cmake(raja_build_dir, cmake_args, NINJA_JOBS, run_cmd, print_step):
        print_step("RAJA Performance Suite built successfully.")
        return True
    return False

def run_benchmarks(official_result_dir: Path, raja_result_dir: Path, 
                   run_official: bool, run_raja: bool) -> None:
    if run_official:
        set_current_log("05_run_official_benchmark")
        print_step("Phase 5.1: Executing LLVM Official Test Suite...")
        lit_exe = Path(sys.prefix) / "bin" / "lit"
        official_build_dir = LAYOUT["official_build"]
        lit_cmd = [
            str(lit_exe), "-v", "-o",
            str(official_result_dir / "baseline_results.json"),
            str(official_build_dir)
        ]
        if run_cmd(lit_cmd, cwd=official_build_dir.parent):
            print_step("Official Test Suite executed successfully.")
        else:
            print_step("[WARNING] Official Test Suite execution encountered errors.")

    if run_raja:
        set_current_log("06_run_raja_benchmark")
        print_step("Phase 5.2: Executing RAJA Performance Suite...")
        raja_build_dir = LAYOUT["raja_build"]
        raja_exe = raja_build_dir / "bin/raja-perf.exe"
        if run_cmd([str(raja_exe)], cwd=raja_result_dir):
            print_step("RAJA Performance Suite executed successfully.")
        else:
            print_step("[WARNING] RAJA Performance Suite execution encountered errors.")

# ==========================================
# 4. Main Orchestrator
# ==========================================
def main() -> None:
    print_step("Starting automated benchmark script.")
    print_step(f"Detailed logs will be saved to: {LOG_DIR}")

    official_result_dir, raja_result_dir = setup_directories()
    
    if not build_llvm():
        print_step("[FATAL] LLVM build failed. Aborting all subsequent benchmark tasks.")
        sys.exit(1)

    official_build_success = build_official_suite()
    if not official_build_success:
        print_step("[WARNING] Official Test Suite build failed. Skipping its execution phase.")

    raja_build_success = build_raja_suite()
    if not raja_build_success:
        print_step("[WARNING] RAJA Performance Suite build failed. Skipping its execution phase.")
    
    run_benchmarks(official_result_dir, raja_result_dir, official_build_success, raja_build_success)

    global CURRENT_LOG_FILE
    CURRENT_LOG_FILE = None
    print_step("Script execution finished. Check 00_summary.log and fragment logs for detailed status.")

if __name__ == "__main__":
    main()
