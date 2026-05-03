#!/usr/bin/env python3

import os
import sys
import shutil
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

import yaml
from typing import Any

# ==========================================
# 1. Configuration & Globals
# ==========================================
CONFIG_FILE = SCRIPT_DIR / "config.yml"

if not CONFIG_FILE.exists():
    print(f"Error: Configuration file not found at {CONFIG_FILE}")
    sys.exit(1)

with open(CONFIG_FILE, "r", encoding="utf-8") as f:
    config: dict[str, Any] = yaml.safe_load(f)

BASE_DIR = Path(config["project"]["base_dir"]).expanduser().resolve()
RUN_ID = datetime.now().strftime("%Y%m%d_%H%M%S")

LLVM_TAG = str(config["llvm"].get("tag", "latest"))

if "-" in LLVM_TAG:
    LLVM_VERSION = LLVM_TAG.split("-", 1)[1]
else:
    LLVM_VERSION = LLVM_TAG

LLVM_REPO_URL = config["llvm"]["repo_url"]
NINJA_JOBS = config["llvm"]["build"].get("ninja_jobs", [])
HOST_C_COMPILER = config["llvm"]["build"].get("c_compiler", "gcc")
HOST_CXX_COMPILER = config["llvm"]["build"].get("cxx_compiler", "g++")

OFFICIAL_REPO_URL = config["test_suite"]["official_repo_url"]
OFFICIAL_TAG = str(config["test_suite"].get("official_tag", "latest"))
OFFICIAL_CXX_STD = str(config["test_suite"].get("official_cxx_standard", "17"))

RAJA_REPO_URL = config["test_suite"]["raja_repo_url"]
RAJA_TAG = str(config["test_suite"].get("raja_tag", "latest"))
RAJA_CXX_STD = str(config["test_suite"].get("raja_cxx_standard", "17"))

LLVM_CUSTOM_DIR = BASE_DIR / f"compiler/llvm-{LLVM_VERSION}-custom"
CLANGXX_PATH = LLVM_CUSTOM_DIR / "bin" / "clang++"
CLANG_PATH = LLVM_CUSTOM_DIR / "bin" / "clang"

LOG_DIR = BASE_DIR / f"logs/{LLVM_VERSION}/{RUN_ID}"
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

def clear_directory(dir_path: Path) -> None:
    if not dir_path.exists():
        return
    for item in dir_path.iterdir():
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()

def get_resolved_tag(repo_url: str, configured_tag: str) -> str:
    if configured_tag.lower() != "latest":
        return configured_tag
    
    print_step(f"Resolving 'latest' commit hash for {repo_url}...")
    try:
        output = subprocess.check_output(["git", "ls-remote", repo_url, "HEAD"], text=True)
        if output:
            short_hash = output.split()[0][:7]
            print_step(f"Resolved to short hash: {short_hash}")
            return short_hash
    except Exception as e:
        print_step(f"[WARNING] Failed to resolve remote hash. Using fallback 'latest'. Error: {e}")
    
    return "latest"

def prepare_git_repo(repo_url: str, target_dir: Path, tag_or_branch: str | None = None, 
                     recursive: bool = False) -> bool:
    if not (target_dir / ".git").exists():
        print_step(f"Cloning {repo_url} into {target_dir}...")
        cmd = ["git", "clone"]
        if recursive:
            cmd.append("--recursive")
        cmd.extend([repo_url, str(target_dir)])
        if not run_cmd(cmd, cwd=target_dir.parent):
            return False
    
    if tag_or_branch:
        if tag_or_branch.lower() == "latest":
            if not run_cmd(["git", "fetch", "origin"], cwd=target_dir): return False
            if not run_cmd(["git", "remote", "set-head", "origin", "-a"], cwd=target_dir): return False
            if not run_cmd(["git", "reset", "--hard", "origin/HEAD"], cwd=target_dir): return False
        else:
            if not run_cmd(["git", "fetch", "--tags"], cwd=target_dir): return False
            if not run_cmd(["git", "checkout", tag_or_branch], cwd=target_dir): return False
        
        if recursive:
            if not run_cmd(["git", "submodule", "update", "--init", "--recursive"], cwd=target_dir): return False
            
    try:
        current_hash = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=target_dir, text=True).strip()
        print_step(f"Repository {target_dir.name} successfully set to commit hash: {current_hash}")
    except subprocess.CalledProcessError:
        print_step(f"[WARNING] Failed to retrieve current commit hash for {target_dir.name}")

    return True

def build_with_cmake(build_dir: Path, cmake_args: list[str], install: bool = False) -> bool:
    clear_directory(build_dir)
    build_dir.mkdir(parents=True, exist_ok=True)
    
    print_step("Configuring with CMake...")
    if not run_cmd(["cmake", "-G", "Ninja"] + cmake_args, cwd=build_dir): return False
    
    print_step("Compiling...")
    if not run_cmd(["ninja"] + NINJA_JOBS, cwd=build_dir): return False
    
    if install:
        print_step("Installing...")
        if not run_cmd(["ninja", "install"], cwd=build_dir): return False
        
    return True

def get_actual_clang_major_version() -> str:
    try:
        output = subprocess.check_output([str(CLANGXX_PATH), "-dumpversion"], text=True)
        return output.strip().split(".")[0]
    except subprocess.CalledProcessError:
        print_step("[ERROR] Failed to probe Clang version.")
        sys.exit(1)

def find_omp_library() -> Path | None:
    lib_base_dir = LLVM_CUSTOM_DIR / "lib"
    if not lib_base_dir.exists():
        return None
    
    for path in lib_base_dir.rglob("libomp.so"):
        return path
        
    return None

# ==========================================
# 3. Core Phase Functions
# ==========================================
def setup_directories() -> tuple[Path, Path]:
    set_current_log("01_init_directories")
    print_step("Phase 1: Initializing directory structure...")
    
    resolved_official_tag = get_resolved_tag(OFFICIAL_REPO_URL, OFFICIAL_TAG)
    resolved_raja_tag = get_resolved_tag(RAJA_REPO_URL, RAJA_TAG)
    
    RESULTS_BASE_DIR = BASE_DIR / "results"
    
    official_result_dir = RESULTS_BASE_DIR / f"official-{resolved_official_tag}/{LLVM_VERSION}/{RUN_ID}"
    raja_result_dir = RESULTS_BASE_DIR / f"raja-{resolved_raja_tag}/{LLVM_VERSION}/{RUN_ID}"

    dirs_to_create = [
        BASE_DIR / "official" / "source",
        BASE_DIR / "official" / "build",
        BASE_DIR / "raja" / "source",
        BASE_DIR / "raja" / "build",
        BASE_DIR / "compiler",
        official_result_dir,
        raja_result_dir
    ]

    for d in dirs_to_create:
        d.mkdir(parents=True, exist_ok=True)
        
    return official_result_dir, raja_result_dir

def build_llvm() -> bool:
    set_current_log("02_build_llvm")
    
    if CLANGXX_PATH.exists() and os.access(CLANGXX_PATH, os.X_OK):
        print_step(f"LLVM compiler already exists at {LLVM_CUSTOM_DIR}.")
        print_step("Skipping LLVM build phase to save time.")
        return True

    print_step(f"Phase 2: Building and installing LLVM (Tag: {LLVM_TAG})...")
    llvm_project_dir = BASE_DIR / "compiler/llvm-project"
    llvm_build_dir = llvm_project_dir / "build"

    if not prepare_git_repo(LLVM_REPO_URL, llvm_project_dir, tag_or_branch=LLVM_TAG):
        return False

    cmake_args = [
        "../llvm",
        f"-DCMAKE_C_COMPILER={HOST_C_COMPILER}",
        f"-DCMAKE_CXX_COMPILER={HOST_CXX_COMPILER}",
        "-DCMAKE_BUILD_TYPE=Release",
        "-DLLVM_ENABLE_PROJECTS=clang;lld",
        "-DLLVM_ENABLE_RUNTIMES=openmp",
        "-DLLVM_TARGETS_TO_BUILD=X86",
        "-DLLVM_INCLUDE_TESTS=OFF",
        "-DLLVM_INCLUDE_BENCHMARKS=OFF",
        "-DLLVM_ENABLE_WARNINGS=OFF",
        f"-DCMAKE_INSTALL_PREFIX={LLVM_CUSTOM_DIR}"
    ]
    if build_with_cmake(llvm_build_dir, cmake_args, install=True):
        print_step("LLVM built and installed successfully.")
        return True
    return False

def build_official_suite() -> bool:
    set_current_log("03_build_official_suite")
    print_step(f"Phase 3: Building LLVM Official Test Suite (Tag: {OFFICIAL_TAG}, C++{OFFICIAL_CXX_STD})...")
    official_src_dir = BASE_DIR / "official/source"
    official_build_dir = BASE_DIR / "official/build"

    if not prepare_git_repo(OFFICIAL_REPO_URL, official_src_dir, tag_or_branch=OFFICIAL_TAG):
        return False

    cmake_args = [
        f"-DCMAKE_C_COMPILER={CLANG_PATH}",
        f"-DCMAKE_CXX_COMPILER={CLANGXX_PATH}",
        "-DCMAKE_BUILD_TYPE=Release",
        "-DTEST_SUITE_BENCHMARKING_ONLY=ON",
        f"-DCMAKE_CXX_STANDARD={OFFICIAL_CXX_STD}",
        "../source"
    ]
    if build_with_cmake(official_build_dir, cmake_args):
        print_step("Official Test Suite built successfully.")
        return True
    return False

def build_raja_suite() -> bool:
    set_current_log("04_build_raja_suite")
    print_step(f"Phase 4: Building RAJA Performance Suite (Tag: {RAJA_TAG}, C++{RAJA_CXX_STD})...")
    raja_src_dir = BASE_DIR / "raja/source"
    raja_build_dir = BASE_DIR / "raja/build"

    if not prepare_git_repo(RAJA_REPO_URL, raja_src_dir, tag_or_branch=RAJA_TAG, recursive=True):
        return False

    # Dynamic OpenMP library discovery
    omp_lib_path = find_omp_library()
    if not omp_lib_path:
        print_step(f"[ERROR] Could not locate libomp.so within {LLVM_CUSTOM_DIR}/lib. OpenMP runtime might not be installed correctly.")
        return False
        
    omp_lib_dir = omp_lib_path.parent
    print_step(f"Dynamically resolved OpenMP library path: {omp_lib_path}")

    actual_major_version = get_actual_clang_major_version()
    clang_include_dir = LLVM_CUSTOM_DIR / f"lib/clang/{actual_major_version}/include"

    cmake_args = [
        f"-DCMAKE_CXX_COMPILER={CLANGXX_PATH}",
        f"-DCMAKE_C_COMPILER={CLANG_PATH}",
        "-DCMAKE_BUILD_TYPE=Release",
        "-DENABLE_OPENMP=On",
        "-DENABLE_CUDA=Off",
        "-DENABLE_HIP=Off",
        "-DENABLE_ALL_MISSING=On",
        f"-DCMAKE_CXX_STANDARD={RAJA_CXX_STD}",
        f"-DCMAKE_CXX_FLAGS=-I{clang_include_dir} -Wno-unused-command-line-argument",
        f"-DCMAKE_C_FLAGS=-I{clang_include_dir} -Wno-unused-command-line-argument",
        f"-DCMAKE_EXE_LINKER_FLAGS=-L{omp_lib_dir} -lomp -Wl,-rpath,{omp_lib_dir}",
        "-DOpenMP_CXX_FLAGS=-fopenmp=libomp",
        "-DOpenMP_C_FLAGS=-fopenmp=libomp",
        "-DOpenMP_CXX_LIB_NAMES=omp",
        "-DOpenMP_C_LIB_NAMES=omp",
        f"-DOpenMP_omp_LIBRARY={omp_lib_path}",
        "../source"
    ]
    if build_with_cmake(raja_build_dir, cmake_args):
        print_step("RAJA Performance Suite built successfully.")
        return True
    return False

def run_benchmarks(official_result_dir: Path, raja_result_dir: Path, 
                   run_official: bool, run_raja: bool) -> None:
    if run_official:
        set_current_log("05_run_official_benchmark")
        print_step("Phase 5.1: Executing LLVM Official Test Suite...")
        lit_exe = Path(sys.prefix) / "bin" / "lit"
        official_build_dir = BASE_DIR / "official/build"
        lit_cmd = [
            str(lit_exe), "-v", "-o",
            str(official_result_dir / "baseline_results.json"),
            str(official_build_dir)
        ]
        if run_cmd(lit_cmd, cwd=BASE_DIR / "official"):
            print_step("Official Test Suite executed successfully.")
        else:
            print_step("[WARNING] Official Test Suite execution encountered errors.")

    if run_raja:
        set_current_log("06_run_raja_benchmark")
        print_step("Phase 5.2: Executing RAJA Performance Suite...")
        raja_build_dir = BASE_DIR / "raja/build"
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