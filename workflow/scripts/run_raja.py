#!/usr/bin/env python3

import subprocess
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


exe_path = Path(snakemake.params.exe)
result_dir = Path(snakemake.params.result_dir)
result_dir.mkdir(parents=True, exist_ok=True)
result_path = Path(snakemake.output.results)

success = run_cmd([str(exe_path)], cwd=result_dir)
if not success:
    raise RuntimeError(f"Failed to run RAJAPerf executable {exe_path}")

if not result_path.exists():
    raise FileNotFoundError(f"Expected RAJA benchmark result was not produced: {result_path}")

stamp_path = Path(snakemake.output.stamp)
with open(stamp_path, "w", encoding="utf-8") as f:
    f.write(f"executable={exe_path}\n")
    f.write(f"result_dir={result_dir}\n")
    f.write(f"results={result_path}\n")
    f.write(f"completed_at={datetime.now().isoformat()}\n")
