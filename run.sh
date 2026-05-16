#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SNAKEFILE="$ROOT_DIR/workflow/Snakefile"
SNAKEMAKE_BIN="$ROOT_DIR/.venv/bin/snakemake"
PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
CONFIG_FILE="$ROOT_DIR/config.yml"
DEFAULT_JOBS=2

if [[ ! -x "$SNAKEMAKE_BIN" ]]; then
  echo "Missing snakemake executable at $SNAKEMAKE_BIN" >&2
  echo "Create the virtual environment and install dependencies first." >&2
  exit 1
fi

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Missing python executable at $PYTHON_BIN" >&2
  echo "Create the virtual environment and install dependencies first." >&2
  exit 1
fi

show_help() {
  cat <<'EOF'
Usage:
  ./run.sh                 Run the workflow with the default settings.
  ./run.sh dry-run         Print the planned DAG without executing.
  ./run.sh clean           Remove run outputs while keeping sources/builds/installs.
  ./run.sh size            Show storage usage for the workflow directories.
  ./run.sh src             List cached source versions.
  ./run.sh -- <args...>    Pass extra arguments through to snakemake.

Defaults:
  snakemake -s workflow/Snakefile -j 2
EOF
}

resolve_base_dir() {
  "$PYTHON_BIN" - <<'PY'
from pathlib import Path
import yaml

config_path = Path("config.yml")
with config_path.open("r", encoding="utf-8") as handle:
    config = yaml.safe_load(handle) or {}

project = config.get("project", {})
base_dir = project.get("base_dir", "~/msc/auto")
print(Path(base_dir).expanduser())
PY
}

show_size() {
  local base_dir="$1"
  local parts=(
    "sources"
    "builds"
    "installs"
    "results"
    "parsed"
    "reports"
    "logs"
  )

  echo "Base directory: $base_dir"
  echo
  for part in "${parts[@]}"; do
    if [[ -e "$base_dir/$part" ]]; then
      du -sh "$base_dir/$part"
    else
      echo "0\t$base_dir/$part (missing)"
    fi
  done
}

clean_runs() {
  local base_dir="$1"
  local targets=(
    "$base_dir/results"
    "$base_dir/parsed"
    "$base_dir/reports"
    "$base_dir/logs/_runs"
  )

  for target in "${targets[@]}"; do
    rm -rf "$target"
    mkdir -p "$target"
  done

  if [[ -d "$base_dir/logs" ]]; then
    find "$base_dir/logs" -mindepth 1 -maxdepth 1 -type d ! -name "_shared" ! -name "_runs" -exec rm -rf {} +
  fi

  echo "Removed run outputs under $base_dir"
  echo "Kept sources/, builds/, installs/, and logs/_shared/"
}

show_cached_sources() {
  local base_dir="$1"
  local sources_dir="$base_dir/sources"
  local groups=(
    "llvm-project:llvm"
    "official:official"
    "raja:raja"
  )

  echo "Base directory: $base_dir"
  echo

  if [[ ! -d "$sources_dir" ]]; then
    echo "No source cache found."
    return 0
  fi

  for group in "${groups[@]}"; do
    local dir_name="${group%%:*}"
    local label="${group##*:}"
    local target_dir="$sources_dir/$dir_name"

    echo "$label:"
    if [[ -d "$target_dir" ]]; then
      local found=0
      for path in "$target_dir"/*; do
        if [[ -d "$path" ]]; then
          found=1
          echo "  - $(basename "$path")"
        fi
      done
      if [[ "$found" -eq 0 ]]; then
        echo "  - (none)"
      fi
    else
      echo "  - (missing)"
    fi
  done
}

EXTRA_ARGS=()
BASE_DIR="$(cd "$ROOT_DIR" && resolve_base_dir)"

case "${1-}" in
  -h|--help)
    show_help
    exit 0
    ;;
  dry-run)
    EXTRA_ARGS+=("-n" "-p")
    shift
    ;;
  clean)
    clean_runs "$BASE_DIR"
    exit 0
    ;;
  size)
    show_size "$BASE_DIR"
    exit 0
    ;;
  src)
    show_cached_sources "$BASE_DIR"
    exit 0
    ;;
  --)
    shift
    ;;
esac

if [[ $# -gt 0 ]]; then
  EXTRA_ARGS+=("$@")
fi

exec "$SNAKEMAKE_BIN" -s "$SNAKEFILE" -j "$DEFAULT_JOBS" "${EXTRA_ARGS[@]}"
