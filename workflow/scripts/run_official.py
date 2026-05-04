#!/usr/bin/env python3

import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path


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


def resolve_lit_executable() -> str:
    lit_path = shutil.which("lit")
    if lit_path:
        return lit_path

    candidate = Path(sys.executable).resolve().parent / "lit"
    if candidate.exists():
        return str(candidate)

    raise FileNotFoundError("Could not locate lit executable in PATH or current Python environment.")


build_dir = Path(snakemake.params.build_dir)
result_path = Path(snakemake.output.results)
result_path.parent.mkdir(parents=True, exist_ok=True)

lit_exe = resolve_lit_executable()
lit_cmd = [
    lit_exe,
    "-v",
    "-o",
    str(result_path),
    str(build_dir),
]

success = run_cmd(lit_cmd, cwd=build_dir.parent)
if not success:
    raise RuntimeError(f"Failed to run Official Test Suite from {build_dir}")

if not result_path.exists():
    raise FileNotFoundError(f"Expected Official benchmark result was not produced: {result_path}")

stamp_path = Path(snakemake.output.stamp)
with open(stamp_path, "w", encoding="utf-8") as f:
    f.write(f"build_dir={build_dir}\n")
    f.write(f"results={result_path}\n")
    f.write(f"completed_at={datetime.now().isoformat()}\n")
