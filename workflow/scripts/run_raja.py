#!/usr/bin/env python3

import sys
from datetime import datetime
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from workflow.lib.command_runner import CommandRunner


runner = CommandRunner.from_snakemake(snakemake)


exe_path = Path(snakemake.params.exe)
result_dir = Path(snakemake.params.result_dir)
result_dir.mkdir(parents=True, exist_ok=True)
result_path = Path(snakemake.output.results)

success = runner.run([str(exe_path)], cwd=result_dir)
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
