#!/usr/bin/env python3

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from re import compile as compile_regex
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from workflow.lib.common import load_config


LLVM_RELEASE_TAG = compile_regex(r"^llvmorg-(\d+)\.(\d+)\.(\d+)$")
SEEN_TAGS_FILE = "seen_llvm_tags.txt"
LAST_TRIGGERED_FILE = "last_triggered.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check LLVM release tags and optionally trigger the workflow for a new release."
    )
    parser.add_argument(
        "--config-file",
        default=str(REPO_ROOT / "config.yml"),
        help="Workflow config file. The LLVM repository URL and base directory are read from this file.",
    )
    parser.add_argument(
        "--state-dir",
        help="Directory for monitor state files. Defaults to <project.base_dir>/monitor.",
    )
    parser.add_argument(
        "--run-sh",
        default=str(REPO_ROOT / "run.sh"),
        help="Path to the workflow wrapper used when --run is set.",
    )
    parser.add_argument(
        "--initialize",
        action="store_true",
        help="Record the current latest release tag as the baseline without running the workflow.",
    )
    parser.add_argument(
        "--run",
        action="store_true",
        help="Run the workflow for the latest unseen release tag.",
    )
    return parser.parse_args()


def release_version_key(tag: str) -> tuple[int, int, int]:
    match = LLVM_RELEASE_TAG.fullmatch(tag)
    if match is None:
        raise ValueError(f"Not an LLVM stable release tag: {tag}")
    return tuple(int(part) for part in match.groups())


def list_remote_release_tags(repo_url: str) -> list[str]:
    result = subprocess.run(
        ["git", "ls-remote", "--tags", repo_url],
        check=True,
        capture_output=True,
        text=True,
    )

    release_tags: set[str] = set()
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) != 2:
            continue

        ref = parts[1]
        if ref.endswith("^{}") or not ref.startswith("refs/tags/"):
            continue

        tag = ref.removeprefix("refs/tags/")
        if LLVM_RELEASE_TAG.fullmatch(tag):
            release_tags.add(tag)

    return sorted(release_tags, key=release_version_key)


def read_seen_tags(path: Path) -> set[str]:
    if not path.exists():
        return set()

    tags: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        tag = line.strip()
        if not tag or tag.startswith("#"):
            continue
        tags.add(tag)
    return tags


def write_seen_tags(path: Path, tags: set[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(sorted(tags, key=release_version_key))
    if content:
        content += "\n"
    path.write_text(content, encoding="utf-8")


def write_last_triggered(state_dir: Path, payload: dict[str, Any]) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    path = state_dir / LAST_TRIGGERED_FILE
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def resolve_state_dir(config: dict[str, Any], state_dir_override: str | None) -> Path:
    if state_dir_override:
        return Path(state_dir_override).expanduser().resolve()
    return (Path(config["project"]["base_dir"]).expanduser().resolve() / "monitor")


def load_monitor_inputs(args: argparse.Namespace) -> tuple[str, Path, Path]:
    config = load_config(Path(args.config_file))
    repo_url = str(config["repositories"]["llvm"])
    state_dir = resolve_state_dir(config, args.state_dir)
    run_sh = Path(args.run_sh).expanduser().resolve()
    return repo_url, state_dir, run_sh


def initialize_baseline(state_dir: Path, latest_tag: str, seen_tags: set[str]) -> None:
    updated_seen_tags = set(seen_tags)
    updated_seen_tags.add(latest_tag)
    write_seen_tags(state_dir / SEEN_TAGS_FILE, updated_seen_tags)
    write_last_triggered(
        state_dir,
        {
            "action": "initialize",
            "tag": latest_tag,
            "timestamp_utc": utc_now(),
        },
    )


def trigger_workflow(run_sh: Path, tag: str) -> int:
    result = subprocess.run([str(run_sh), "--llvm-tag", tag], cwd=REPO_ROOT)
    return result.returncode


def print_status(repo_url: str, state_dir: Path, latest_tag: str, seen_tags: set[str]) -> None:
    print(f"LLVM repository: {repo_url}")
    print(f"State directory: {state_dir}")
    print(f"Latest stable release tag: {latest_tag}")
    if seen_tags:
        newest_seen = sorted(seen_tags, key=release_version_key)[-1]
        print(f"Seen tags: {len(seen_tags)} (newest: {newest_seen})")
    else:
        print("Seen tags: none")


def main() -> int:
    args = parse_args()
    repo_url, state_dir, run_sh = load_monitor_inputs(args)
    seen_path = state_dir / SEEN_TAGS_FILE

    release_tags = list_remote_release_tags(repo_url)
    if not release_tags:
        print("No LLVM stable release tags were found.", file=sys.stderr)
        return 1

    latest_tag = release_tags[-1]
    seen_tags = read_seen_tags(seen_path)
    print_status(repo_url, state_dir, latest_tag, seen_tags)

    if latest_tag in seen_tags:
        print("Decision: no new latest LLVM release tag to process.")
        return 0

    if not seen_tags:
        print("Decision: no baseline state exists yet.")
        if args.initialize or args.run:
            initialize_baseline(state_dir, latest_tag, seen_tags)
            print(f"Initialized baseline with {latest_tag}; workflow was not triggered.")
            return 0
        print("Dry run: would initialize this tag as the baseline. Use --initialize or --run to write state.")
        return 0

    print(f"Decision: latest tag {latest_tag} has not been processed.")
    if not args.run:
        print(f"Dry run: would run {run_sh} --llvm-tag {latest_tag}")
        return 0

    exit_code = trigger_workflow(run_sh, latest_tag)
    if exit_code != 0:
        write_last_triggered(
            state_dir,
            {
                "action": "run_failed",
                "tag": latest_tag,
                "exit_code": exit_code,
                "timestamp_utc": utc_now(),
            },
        )
        print(f"Workflow failed for {latest_tag}; tag was not marked as seen.", file=sys.stderr)
        return exit_code

    updated_seen_tags = set(seen_tags)
    updated_seen_tags.add(latest_tag)
    write_seen_tags(seen_path, updated_seen_tags)
    write_last_triggered(
        state_dir,
        {
            "action": "run_succeeded",
            "tag": latest_tag,
            "exit_code": exit_code,
            "timestamp_utc": utc_now(),
        },
    )
    print(f"Workflow succeeded for {latest_tag}; tag was marked as seen.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
