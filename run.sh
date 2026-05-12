#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SNAKEFILE="$ROOT_DIR/workflow/Snakefile"
SNAKEMAKE_BIN="$ROOT_DIR/.venv/bin/snakemake"
DEFAULT_JOBS=2

if [[ ! -x "$SNAKEMAKE_BIN" ]]; then
  echo "Missing snakemake executable at $SNAKEMAKE_BIN" >&2
  echo "Create the virtual environment and install dependencies first." >&2
  exit 1
fi

show_help() {
  cat <<'EOF'
Usage:
  ./run.sh                 Run the workflow with the default settings.
  ./run.sh dry-run         Print the planned DAG without executing.
  ./run.sh -- <args...>    Pass extra arguments through to snakemake.

Defaults:
  snakemake -s workflow/Snakefile -j 2
EOF
}

EXTRA_ARGS=()

case "${1-}" in
  -h|--help)
    show_help
    exit 0
    ;;
  dry-run)
    EXTRA_ARGS+=("-n" "-p")
    shift
    ;;
  --)
    shift
    ;;
esac

if [[ $# -gt 0 ]]; then
  EXTRA_ARGS+=("$@")
fi

exec "$SNAKEMAKE_BIN" -s "$SNAKEFILE" -j "$DEFAULT_JOBS" "${EXTRA_ARGS[@]}"
