#!/usr/bin/env python3

import sys
from datetime import datetime
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from workflow.lib.command_runner import CommandRunner
from workflow.lib.common import prepare_git_repo


runner = CommandRunner.from_snakemake(snakemake)


target_dir = Path(snakemake.output.source_dir)
target_dir.parent.mkdir(parents=True, exist_ok=True)
recursive = bool(getattr(snakemake.params, "recursive", False))

success = prepare_git_repo(
    repo_url=str(snakemake.params.repo_url),
    target_dir=target_dir,
    tag_or_branch=str(snakemake.params.tag_or_branch),
    run_cmd=runner.run,
    status_callback=runner.log,
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
