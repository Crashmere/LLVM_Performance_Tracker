# AI Agent Guide

This file is the handoff entry point for future AI assistants working on this repository.

## Project Snapshot

This repository contains a Snakemake-based workflow for tracking LLVM compiler performance using:

- LLVM builds from `llvm-project`
- LLVM Official test-suite
- RAJAPerf
- parsing, aggregation, and Plotly HTML reporting

The current workflow entry point is:

```bash
./run.sh
```

The Snakemake entry point is:

```bash
.venv/bin/snakemake -s workflow/Snakefile
```

## Read First

Before making non-trivial changes, read these files in this order:

1. `docs/agent_handoff.md`
2. `work_plan.md`
3. `README.md`
4. `config.yml`
5. `workflow/Snakefile`

For recovery and storage behavior, also read:

- `docs/recovery.md`
- `docs/storage.md`

## Current Design Principles

- Snakemake is the only workflow scheduler. Do not add a second orchestration layer.
- New pipeline functionality should normally enter the Snakemake DAG, not a standalone driver script.
- Preserve raw benchmark outputs and metadata; derived CSV/report files can be rebuilt.
- Prefer explicit provenance over clever implicit state.
- `auto/metadata/<experiment_id>/experiment.json` is provenance, not a mutable run-state database.
- Helper tools under `tools/` should be read-only unless explicitly designed otherwise.
- The workflow does not provide backward compatibility for old config shapes.
- Do not reintroduce old label fields such as `run_label`, `run_labels`, `runs.labels`, `repeat_count`, `profile`, or experiment `name`.
- There is exactly one global `label` config field. If omitted, the workflow generates a timestamp label.
- Test selection currently uses direct argument pass-through, not a structured DSL.
- Reports should be self-contained HTML and must not depend on external Plotly CDN access.

## Common Commands

Dry-run:

```bash
./run.sh dry-run
```

Normal run, with `--keep-going` by default:

```bash
./run.sh
```

Stop immediately on first failure:

```bash
./run.sh strict
```

Resume incomplete work:

```bash
./run.sh resume
```

Inspect existing metadata-backed outputs:

```bash
./run.sh inspect
```

Report disk usage:

```bash
./run.sh disk
```

Force-regenerate one report without rerunning benchmarks:

```bash
./run.sh -- --forcerun generate_report \
  auto/reports/<experiment_id>/benchmark_report.html
```

## Coding Guidance

- Use `rg` for searching.
- Use `apply_patch` for manual edits.
- Keep Python scripts small and rule-specific.
- Put reusable logic in `workflow/lib/`.
- Keep parser format details in `workflow/lib/parsers/`.
- Keep shared result schema in `workflow/lib/result_schema.py`.
- Keep path layout conventions in `workflow/lib/layout.py`.
- Keep CMake/Ninja build behavior in `workflow/lib/cmake_build.py`.
- Keep command execution/logging in `workflow/lib/command_runner.py`.

## Validation Checklist

Use the smallest relevant subset of these checks after changes:

```bash
.venv/bin/python -m py_compile workflow/lib/*.py workflow/scripts/*.py tools/*.py
./run.sh dry-run
git diff --check
```

For parser/report changes, use existing outputs under `auto/results/` when possible instead of rerunning benchmarks.

For label/config changes, verify:

```bash
.venv/bin/python - <<'PY'
from pathlib import Path
from workflow.lib.common import load_config, normalize_workflow_config
cfg = normalize_workflow_config(load_config(Path("config.yml")))
print(cfg["label"])
print(cfg["experiment_mode"])
print(cfg["experiments"][0])
PY
```

## Important History

The project has moved through these major stages:

- Stage 1: experiment matrix and Snakemake-driven multi-version layout.
- Stage 2: metadata, recovery, inspect tooling, and code/module cleanup.
- Stage 3: build caching, disk usage reporting, and shared/run log distinction.
- Stage 4: parser adapters and multiple RAJAPerf output schemas.
- Stage 5A: direct test-selection argument pass-through, single global `label`, and self-contained reports.

See `docs/agent_handoff.md` for a fuller handoff.
