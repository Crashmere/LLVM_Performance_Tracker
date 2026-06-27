#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SNAKEFILE="$ROOT_DIR/workflow/Snakefile"
SNAKEMAKE_BIN="$ROOT_DIR/.venv/bin/snakemake"
PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
DEFAULT_JOBS=2
STRICT_MODE=0
LLVM_TAG_OVERRIDE=""

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
  if [[ -n "$LLVM_TAG_OVERRIDE" ]]; then
    args+=("--config" "llvm_tag_override=$LLVM_TAG_OVERRIDE")
  fi
  args+=("$@")
  exec "$SNAKEMAKE_BIN" -s "$SNAKEFILE" -j "$DEFAULT_JOBS" "${args[@]}"
}

set_llvm_tag_override() {
  if [[ $# -ne 1 || -z "$1" ]]; then
    echo "Missing value for --llvm-tag" >&2
    exit 1
  fi
  LLVM_TAG_OVERRIDE="$1"
}

collect_workflow_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --llvm-tag|-L)
        shift
        if [[ $# -eq 0 ]]; then
          echo "Missing value for --llvm-tag" >&2
          exit 1
        fi
        set_llvm_tag_override "$1"
        ;;
      --llvm-tag=*)
        set_llvm_tag_override "${1#*=}"
        ;;
      --)
        shift
        EXTRA_ARGS+=("$@")
        return
        ;;
      *)
        EXTRA_ARGS+=("$1")
        ;;
    esac
    shift
  done
}

show_help() {
  cat <<'EOF'
Usage:
  ./run.sh                         Run the workflow with the default settings.
  ./run.sh --llvm-tag <tag>        Run only the specified LLVM tag for this invocation.
  ./run.sh dry-run                 Print the planned DAG without executing.
  ./run.sh dry-run --llvm-tag <tag> Print the planned DAG for one LLVM tag.
  ./run.sh resume                  Continue after an interrupted run.
  ./run.sh strict [command|args...] Run without --keep-going.
  ./run.sh report                  Regenerate the HTML report from current analysis data.
  ./run.sh inspect [args...]       Inspect existing outputs without changing state.
  ./run.sh disk [args...]          Show disk usage under the workflow base directory.
  ./run.sh -- <args...>            Pass extra arguments through to snakemake.

Defaults:
  snakemake -s workflow/Snakefile -j 2 --keep-going
EOF
}

EXTRA_ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    strict|--strict)
      STRICT_MODE=1
      shift
      ;;
    --llvm-tag|-L)
      shift
      if [[ $# -eq 0 ]]; then
        echo "Missing value for --llvm-tag" >&2
        exit 1
      fi
      set_llvm_tag_override "$1"
      shift
      ;;
    --llvm-tag=*)
      set_llvm_tag_override "${1#*=}"
      shift
      ;;
    *)
      break
      ;;
  esac
done

case "${1-}" in
  -h|--help)
    show_help
    exit 0
    ;;
  dry-run)
    EXTRA_ARGS+=("-n" "-p")
    shift
    collect_workflow_args "$@"
    set --
    ;;
  resume)
    shift
    EXTRA_ARGS+=("--rerun-incomplete")
    collect_workflow_args "$@"
    set --
    ;;
  report)
    shift
    if [[ ! -x "$PYTHON_BIN" ]]; then
      echo "Missing python executable at $PYTHON_BIN" >&2
      echo "Create the virtual environment and install dependencies first." >&2
      exit 1
    fi
    exec "$PYTHON_BIN" "$ROOT_DIR/workflow/scripts/generate_report_cli.py" \
      --analysis-dir "$ROOT_DIR/auto/analysis" \
      --output-html "$ROOT_DIR/auto/reports/analysis_report.html" "$@"
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
  --)
    shift
    EXTRA_ARGS+=("$@")
    set --
    ;;
esac

if [[ $# -gt 0 ]]; then
  collect_workflow_args "$@"
fi

run_snakemake "${EXTRA_ARGS[@]}"
