#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SNAKEFILE="$ROOT_DIR/workflow/Snakefile"
SNAKEMAKE_BIN="$ROOT_DIR/.venv/bin/snakemake"
PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
HELPER="$ROOT_DIR/workflow/scripts/run_helper_cli.py"
CONFIG_FILE="$ROOT_DIR/config.yml"
DEFAULT_JOBS=2
DEFAULT_SNAKEMAKE_ARGS=(--keep-going)

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
  ./run.sh status          Show the current batch summary status.
  ./run.sh retry           Re-run only the failed experiments from the current batch.
  ./run.sh hist            List historical experiments discovered from results/.
  ./run.sh recover <id>    Rebuild parsed/report outputs from existing raw results.
  ./run.sh -- <args...>    Pass extra arguments through to snakemake.

Defaults:
  snakemake -s workflow/Snakefile -j 2 --keep-going
EOF
}

helper() {
  "$PYTHON_BIN" "$HELPER" --config "$CONFIG_FILE" "$@"
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
  clean)
    helper clean
    exit $?
    ;;
  size)
    helper size
    exit $?
    ;;
  src)
    helper src
    exit $?
    ;;
  status)
    helper status
    exit $?
    ;;
  retry)
    helper retry \
      --snakemake-bin "$SNAKEMAKE_BIN" \
      --snakefile "$SNAKEFILE" \
      --default-jobs "$DEFAULT_JOBS" \
      --default-arg="${DEFAULT_SNAKEMAKE_ARGS[0]}"
    exit $?
    ;;
  hist)
    helper hist
    exit $?
    ;;
  recover)
    if [[ $# -lt 2 ]]; then
      echo "Usage: ./run.sh recover <run_label|experiment_id>" >&2
      exit 1
    fi
    target_id="$2"
    shift 2
    helper recover --target-id "$target_id" "$@"
    exit $?
    ;;
  --)
    shift
    ;;
esac

if [[ $# -gt 0 ]]; then
  EXTRA_ARGS+=("$@")
fi

RUN_LABEL_OVERRIDE="$(helper run-label-override)"
if [[ -n "$RUN_LABEL_OVERRIDE" ]]; then
  export MSC_RUN_LABEL_OVERRIDE="$RUN_LABEL_OVERRIDE"
fi

exec "$SNAKEMAKE_BIN" -s "$SNAKEFILE" -j "$DEFAULT_JOBS" "${DEFAULT_SNAKEMAKE_ARGS[@]}" "${EXTRA_ARGS[@]}"
