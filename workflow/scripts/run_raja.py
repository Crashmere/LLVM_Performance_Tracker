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

success = runner.run([str(exe_path)], cwd=result_dir)
if not success:
    raise RuntimeError(f"Failed to run RAJAPerf executable {exe_path}")

result_files = sorted(path for path in result_dir.glob("RAJAPerf*") if path.is_file())
if not result_files:
    raise FileNotFoundError(f"RAJAPerf did not produce any RAJAPerf* files in {result_dir}")

stamp_path = Path(snakemake.output.stamp)
with open(stamp_path, "w", encoding="utf-8") as f:
    f.write(f"executable={exe_path}\n")
    f.write(f"result_dir={result_dir}\n")
    for result_file in result_files:
        f.write(f"result_file={result_file}\n")
    f.write(f"completed_at={datetime.now().isoformat()}\n")
