#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SNAKEFILE="$ROOT_DIR/workflow/Snakefile"
SNAKEMAKE_BIN="$ROOT_DIR/.venv/bin/snakemake"
PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
DEFAULT_JOBS=2
STRICT_MODE=0

if [[ ! -x "$SNAKEMAKE_BIN" ]]; then
  echo "Missing snakemake executable at $SNAKEMAKE_BIN" >&2
  echo "Create the virtual environment and install dependencies first." >&2
  exit 1
fi

run_snakemake() {
  local args=()
  if [[ "$STRICT_MODE" -eq 0 ]]; then
    args+=("--keep-going")
  fi
  args+=("$@")
  exec "$SNAKEMAKE_BIN" -s "$SNAKEFILE" -j "$DEFAULT_JOBS" "${args[@]}"
}

show_help() {
  cat <<'EOF'
Usage:
  ./run.sh                         Run the workflow with the default settings.
  ./run.sh dry-run                 Print the planned DAG without executing.
  ./run.sh resume                  Continue after an interrupted run.
  ./run.sh strict [command|args...] Run without --keep-going.
  ./run.sh inspect [args...]       Inspect existing outputs without changing state.
  ./run.sh disk [args...]          Show disk usage under the workflow base directory.
  ./run.sh compare [args...]       Compare two historical aggregated result tables.
  ./run.sh -- <args...>            Pass extra arguments through to snakemake.

Defaults:
  snakemake -s workflow/Snakefile -j 2 --keep-going
EOF
}

EXTRA_ARGS=()

if [[ "${1-}" == "strict" || "${1-}" == "--strict" ]]; then
  STRICT_MODE=1
  shift
fi

case "${1-}" in
  -h|--help)
    show_help
    exit 0
    ;;
  dry-run)
    EXTRA_ARGS+=("-n" "-p")
    shift
    ;;
  resume)
    shift
    EXTRA_ARGS+=("--rerun-incomplete")
    ;;
  inspect)
    shift
    if [[ ! -x "$PYTHON_BIN" ]]; then
      echo "Missing python executable at $PYTHON_BIN" >&2
      echo "Create the virtual environment and install dependencies first." >&2
      exit 1
    fi
    exec "$PYTHON_BIN" "$ROOT_DIR/tools/inspect_workflow_outputs.py" --base-dir "$ROOT_DIR/auto" "$@"
    ;;
  disk)
    shift
    if [[ ! -x "$PYTHON_BIN" ]]; then
      echo "Missing python executable at $PYTHON_BIN" >&2
      echo "Create the virtual environment and install dependencies first." >&2
      exit 1
    fi
    exec "$PYTHON_BIN" "$ROOT_DIR/tools/report_disk_usage.py" --config-file "$ROOT_DIR/config.yml" "$@"
    ;;
  compare)
    shift
    if [[ ! -x "$PYTHON_BIN" ]]; then
      echo "Missing python executable at $PYTHON_BIN" >&2
      echo "Create the virtual environment and install dependencies first." >&2
      exit 1
    fi
    exec "$PYTHON_BIN" "$ROOT_DIR/tools/compare_versions.py" --config-file "$ROOT_DIR/config.yml" "$@"
    ;;
  --)
    shift
    ;;
esac

if [[ $# -gt 0 ]]; then
  EXTRA_ARGS+=("$@")
fi

run_snakemake "${EXTRA_ARGS[@]}"
