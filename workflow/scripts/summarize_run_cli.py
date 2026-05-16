#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from workflow.lib.common import load_config, normalize_workflow_config
from workflow.lib.run_manifest import build_batch_manifest, get_batch_paths, write_batch_manifest, write_summary_csv


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write a batch manifest and summary for the current workflow config.")
    parser.add_argument("--config", required=True, help="Path to config.yml.")
    parser.add_argument(
        "--batch-status",
        required=True,
        choices=["started", "completed", "failed"],
        help="High-level status to record for this batch snapshot.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    workflow_config = normalize_workflow_config(load_config(Path(args.config)))
    base_dir = Path(workflow_config["project"]["base_dir"]).expanduser().resolve()
    batch_paths = get_batch_paths(base_dir, workflow_config["batch"]["batch_id"])

    manifest = build_batch_manifest(workflow_config, args.batch_status)
    manifest_path = write_batch_manifest(manifest, batch_paths["manifest_json"])
    summary_path = write_summary_csv(manifest, batch_paths["summary_csv"])

    print(f"Wrote batch manifest to {manifest_path}")
    print(f"Wrote batch summary to {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
