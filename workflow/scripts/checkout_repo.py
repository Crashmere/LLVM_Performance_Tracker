#!/usr/bin/env python3

from __future__ import annotations

import subprocess
import sys
from datetime import datetime
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from workflow.lib.common import prepare_git_repo


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


target_dir = Path(snakemake.output.source_dir)
target_dir.parent.mkdir(parents=True, exist_ok=True)
recursive = bool(getattr(snakemake.params, "recursive", False))

success = prepare_git_repo(
    repo_url=str(snakemake.params.repo_url),
    target_dir=target_dir,
    tag_or_branch=str(snakemake.params.tag_or_branch),
    run_cmd=run_cmd,
    status_callback=log_message,
    recursive=recursive,
)

if not success:
    raise RuntimeError(f"Failed to prepare repository at {target_dir}")

stamp_path = Path(snakemake.output.stamp)
stamp_path.parent.mkdir(parents=True, exist_ok=True)
with open(stamp_path, "w", encoding="utf-8") as f:
    f.write(f"repo_url={snakemake.params.repo_url}\n")
    f.write(f"tag_or_branch={snakemake.params.tag_or_branch}\n")
    f.write(f"recursive={recursive}\n")
    f.write(f"completed_at={datetime.now().isoformat()}\n")
