from __future__ import annotations

from datetime import datetime
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable

import yaml


RunCommand = Callable[[list[str], Path | None, dict[str, str] | None], bool]
StatusCallback = Callable[[str], None]


def load_config(config_file: Path) -> dict[str, Any]:
    with open(config_file, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    if not isinstance(config, dict):
        raise ValueError(f"Configuration at {config_file} must be a mapping.")

    return config


def _ensure_list(value: Any, *, default: list[str] | None = None) -> list[str]:
    if value is None:
        return list(default or [])
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def _nested_get(mapping: dict[str, Any], *keys: str, default: Any = None) -> Any:
    current: Any = mapping
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


def normalize_workflow_config(config: dict[str, Any]) -> dict[str, Any]:
    project = config.get("project", {})
    llvm = config.get("llvm", {})
    test_suite = config.get("test_suite", {})
    official = test_suite.get("official", {})
    raja = test_suite.get("raja", {})
    runs = config.get("runs", {})

    llvm_tags = _ensure_list(llvm.get("tags"))
    if not llvm_tags:
        llvm_tags = _ensure_list(llvm.get("tag"), default=["latest"])

    official_tags = _ensure_list(official.get("tags"))
    if not official_tags:
        official_tags = _ensure_list(test_suite.get("official_tag"), default=["latest"])

    raja_tags = _ensure_list(raja.get("tags"))
    if not raja_tags:
        raja_tags = _ensure_list(test_suite.get("raja_tag"), default=["latest"])

    run_label = runs.get("run_label")
    if not run_label:
        run_label = datetime.now().strftime("%Y%m%d_%H%M%S")

    return {
        "project": {
            "base_dir": project["base_dir"],
        },
        "runs": {
            "run_label": str(run_label),
        },
        "llvm": {
            "repo_url": llvm["repo_url"],
            "tags": llvm_tags,
            "build": {
                "c_compiler": _nested_get(llvm, "build", "c_compiler", default="gcc"),
                "cxx_compiler": _nested_get(llvm, "build", "cxx_compiler", default="g++"),
                "ninja_jobs": _nested_get(llvm, "build", "ninja_jobs", default=[]),
            },
        },
        "test_suite": {
            "official": {
                "repo_url": official.get("repo_url", test_suite.get("official_repo_url")),
                "tags": official_tags,
                "cxx_standard": str(
                    official.get("cxx_standard", test_suite.get("official_cxx_standard", "17"))
                ),
            },
            "raja": {
                "repo_url": raja.get("repo_url", test_suite.get("raja_repo_url")),
                "tags": raja_tags,
                "cxx_standard": str(
                    raja.get("cxx_standard", test_suite.get("raja_cxx_standard", "17"))
                ),
            },
        },
    }


def resolve_llvm_version(llvm_tag: str) -> str:
    if "-" in llvm_tag:
        return llvm_tag.split("-", 1)[1]
    return llvm_tag


def get_layout_paths(
    base_dir: Path,
    llvm_tag: str,
    official_tag: str,
    raja_tag: str,
    llvm_version: str,
    run_label: str,
) -> dict[str, Path]:
    return {
        "sources_root": base_dir / "sources",
        "builds_root": base_dir / "builds",
        "installs_root": base_dir / "installs",
        "results_root": base_dir / "results",
        "parsed_root": base_dir / "parsed",
        "reports_root": base_dir / "reports",
        "logs_root": base_dir / "logs",
        "llvm_source": base_dir / "sources" / "llvm-project" / llvm_tag,
        "official_source": base_dir / "sources" / "official" / official_tag,
        "raja_source": base_dir / "sources" / "raja" / raja_tag,
        "llvm_build": base_dir / "builds" / "llvm" / llvm_tag,
        "official_build": base_dir / "builds" / "official" / official_tag / f"llvm-{llvm_version}",
        "raja_build": base_dir / "builds" / "raja" / raja_tag / f"llvm-{llvm_version}",
        "llvm_install": base_dir / "installs" / "llvm" / llvm_tag,
        "official_result": base_dir / "results" / f"official-{official_tag}" / llvm_version / run_label,
        "raja_result": base_dir / "results" / f"raja-{raja_tag}" / llvm_version / run_label,
        "parsed_run_dir": base_dir / "parsed" / run_label,
        "reports_run_dir": base_dir / "reports" / run_label,
        "logs_run_dir": base_dir / "logs" / run_label,
    }


def normalize_ninja_jobs(ninja_jobs: list[Any] | int | str | None) -> list[str]:
    if ninja_jobs is None:
        return []
    if isinstance(ninja_jobs, int):
        return ["-j", str(ninja_jobs)]
    if isinstance(ninja_jobs, str):
        return [ninja_jobs] if ninja_jobs else []
    return [str(job) for job in ninja_jobs]


def clear_directory(dir_path: Path) -> None:
    if not dir_path.exists():
        return

    for item in dir_path.iterdir():
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()


def get_resolved_tag(
    repo_url: str,
    configured_tag: str,
    status_callback: StatusCallback | None = None,
) -> str:
    if configured_tag.lower() != "latest":
        return configured_tag

    if status_callback:
        status_callback(f"Resolving 'latest' commit hash for {repo_url}...")

    try:
        output = subprocess.check_output(["git", "ls-remote", repo_url, "HEAD"], text=True)
        if output:
            short_hash = output.split()[0][:7]
            if status_callback:
                status_callback(f"Resolved to short hash: {short_hash}")
            return short_hash
    except Exception as e:
        if status_callback:
            status_callback(f"[WARNING] Failed to resolve remote hash. Using fallback 'latest'. Error: {e}")

    return "latest"


def prepare_git_repo(
    repo_url: str,
    target_dir: Path,
    tag_or_branch: str | None,
    run_cmd: RunCommand,
    status_callback: StatusCallback | None = None,
    recursive: bool = False,
) -> bool:
    if not (target_dir / ".git").exists():
        if status_callback:
            status_callback(f"Cloning {repo_url} into {target_dir}...")
        clone_cmd = ["git", "clone"]
        if recursive:
            clone_cmd.append("--recursive")
        clone_cmd.extend([repo_url, str(target_dir)])
        if not run_cmd(clone_cmd, target_dir.parent, None):
            return False

    if tag_or_branch:
        if tag_or_branch.lower() == "latest":
            if not run_cmd(["git", "fetch", "origin"], target_dir, None):
                return False
            if not run_cmd(["git", "remote", "set-head", "origin", "-a"], target_dir, None):
                return False
            if not run_cmd(["git", "reset", "--hard", "origin/HEAD"], target_dir, None):
                return False
        else:
            if not run_cmd(["git", "fetch", "--tags"], target_dir, None):
                return False
            if not run_cmd(["git", "checkout", tag_or_branch], target_dir, None):
                return False

        if recursive and not run_cmd(["git", "submodule", "update", "--init", "--recursive"], target_dir, None):
            return False

    try:
        current_hash = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=target_dir,
            text=True,
        ).strip()
        if status_callback:
            status_callback(f"Repository {target_dir.name} successfully set to commit hash: {current_hash}")
    except subprocess.CalledProcessError:
        if status_callback:
            status_callback(f"[WARNING] Failed to retrieve current commit hash for {target_dir.name}")

    return True


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


def get_actual_clang_major_version(clangxx_path: Path) -> str:
    try:
        output = subprocess.check_output([str(clangxx_path), "-dumpversion"], text=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to probe Clang version from {clangxx_path}") from e

    return output.strip().split(".")[0]


def find_omp_library(llvm_install_dir: Path) -> Path | None:
    lib_base_dir = llvm_install_dir / "lib"
    if not lib_base_dir.exists():
        return None

    for path in lib_base_dir.rglob("libomp.so"):
        return path

    return None


def get_llvm_cmake_args(
    host_c_compiler: str,
    host_cxx_compiler: str,
    llvm_install_dir: Path,
) -> list[str]:
    return [
        "../llvm",
        f"-DCMAKE_C_COMPILER={host_c_compiler}",
        f"-DCMAKE_CXX_COMPILER={host_cxx_compiler}",
        "-DCMAKE_BUILD_TYPE=Release",
        "-DLLVM_ENABLE_PROJECTS=clang;lld",
        "-DLLVM_ENABLE_RUNTIMES=openmp",
        "-DLLVM_TARGETS_TO_BUILD=X86",
        "-DLLVM_INCLUDE_TESTS=OFF",
        "-DLLVM_INCLUDE_BENCHMARKS=OFF",
        "-DLLVM_ENABLE_WARNINGS=OFF",
        f"-DCMAKE_INSTALL_PREFIX={llvm_install_dir}",
    ]


def get_official_cmake_args(
    clang_path: Path,
    clangxx_path: Path,
    cxx_standard: str,
) -> list[str]:
    return [
        f"-DCMAKE_C_COMPILER={clang_path}",
        f"-DCMAKE_CXX_COMPILER={clangxx_path}",
        "-DCMAKE_BUILD_TYPE=Release",
        "-DTEST_SUITE_BENCHMARKING_ONLY=ON",
        f"-DCMAKE_CXX_STANDARD={cxx_standard}",
        "../source",
    ]


def get_raja_cmake_args(
    clang_path: Path,
    clangxx_path: Path,
    llvm_install_dir: Path,
    cxx_standard: str,
) -> list[str]:
    omp_lib_path = find_omp_library(llvm_install_dir)
    if not omp_lib_path:
        raise FileNotFoundError(
            f"Could not locate libomp.so within {llvm_install_dir / 'lib'}."
        )

    omp_lib_dir = omp_lib_path.parent
    actual_major_version = get_actual_clang_major_version(clangxx_path)
    clang_include_dir = llvm_install_dir / f"lib/clang/{actual_major_version}/include"

    return [
        f"-DCMAKE_CXX_COMPILER={clangxx_path}",
        f"-DCMAKE_C_COMPILER={clang_path}",
        "-DCMAKE_BUILD_TYPE=Release",
        "-DENABLE_OPENMP=On",
        "-DENABLE_CUDA=Off",
        "-DENABLE_HIP=Off",
        "-DENABLE_ALL_MISSING=On",
        f"-DCMAKE_CXX_STANDARD={cxx_standard}",
        f"-DCMAKE_CXX_FLAGS=-I{clang_include_dir} -Wno-unused-command-line-argument",
        f"-DCMAKE_C_FLAGS=-I{clang_include_dir} -Wno-unused-command-line-argument",
        f"-DCMAKE_EXE_LINKER_FLAGS=-L{omp_lib_dir} -lomp -Wl,-rpath,{omp_lib_dir}",
        "-DOpenMP_CXX_FLAGS=-fopenmp=libomp",
        "-DOpenMP_C_FLAGS=-fopenmp=libomp",
        "-DOpenMP_CXX_LIB_NAMES=omp",
        "-DOpenMP_C_LIB_NAMES=omp",
        f"-DOpenMP_omp_LIBRARY={omp_lib_path}",
        "../source",
    ]
