#!/usr/bin/env python3

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from workflow.lib.command_runner import CommandRunner
from workflow.lib.common import as_string_list


runner = CommandRunner.from_snakemake(snakemake)


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
lit_args = as_string_list(snakemake.params.lit_args)

lit_exe = resolve_lit_executable()
lit_cmd = [
    lit_exe,
    "-v",
    "-o",
    str(result_path),
    *lit_args,
    str(build_dir),
]

success = runner.run(lit_cmd, cwd=build_dir.parent)
if not success:
    raise RuntimeError(f"Failed to run Official Test Suite from {build_dir}")

if not result_path.exists():
    raise FileNotFoundError(f"Expected Official benchmark result was not produced: {result_path}")

stamp_path = Path(snakemake.output.stamp)
with open(stamp_path, "w", encoding="utf-8") as f:
    f.write(f"build_dir={build_dir}\n")
    f.write(f"results={result_path}\n")
    f.write(f"lit_args={json.dumps(lit_args)}\n")
    f.write(f"completed_at={datetime.now().isoformat()}\n")
