import subprocess
from pathlib import Path


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
    llvm_source_dir: Path,
    host_c_compiler: str,
    host_cxx_compiler: str,
    llvm_install_dir: Path,
) -> list[str]:
    return [
        str(llvm_source_dir / "llvm"),
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
    source_dir: Path,
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
        str(source_dir),
    ]


def get_raja_cmake_args(
    source_dir: Path,
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
        str(source_dir),
    ]
