# Agent Handoff

This document is a compact project memory for future development sessions. It is intentionally written for an AI assistant or a developer who needs to recover context after changing machines or losing the original chat.

## Current Status

The repository is a Snakemake workflow for LLVM performance tracking. It can checkout, build, run, parse, aggregate, and report benchmark results for:

- LLVM
- LLVM Official test-suite
- RAJAPerf

The active workflow code lives under `workflow/`. The default outputs live under `auto/`.

The project is currently at the end of Stage 5A.

## High-Level Architecture

- `workflow/Snakefile`
  - Defines the DAG.
  - Expands normalized experiments.
  - Keeps checkout/build targets shared by version tags.
  - Keeps run results and run logs isolated by global `label`.
  - Keeps parsed, aggregated, report, metadata, and experiment logs isolated by `experiment_id`.

- `workflow/lib/common.py`
  - Loads and normalizes config.
  - Builds experiment lists.
  - Normalizes `test_selection`.
  - Generates the single global `label`.
  - Contains shared small helpers such as `as_string_list()`.

- `workflow/lib/layout.py`
  - Defines path layout for one experiment.

- `workflow/lib/command_runner.py`
  - Shared command execution and logging.

- `workflow/lib/cmake_build.py`
  - Shared CMake/Ninja build behavior.

- `workflow/lib/build_configs.py`
  - Suite-specific CMake argument generation.

- `workflow/lib/parse_results.py`
  - Result directory dispatcher and table writer.
  - Does not contain suite-specific parsing details.

- `workflow/lib/parsers/`
  - Parser adapters for Official and RAJA.

- `workflow/lib/result_schema.py`
  - Unified parsed record and metric model.

- `workflow/lib/reporting.py`
  - Aggregation and Plotly report generation.

- `workflow/scripts/`
  - Rule scripts and CLI wrappers used by Snakemake.

- `tools/`
  - Read-only helper tools such as inspect and disk usage reporting.

## Configuration Model

The current config intentionally does not support old config shapes.

Shared config includes:

- `project.base_dir`
- optional `project.default_platform`
- optional top-level `label`
- `build.ninja_jobs`
- `build.clean_build`
- `build.reconfigure`
- `repositories`
- `compilers`
- `suite_defaults`
- optional `test_selection`

Simple matrix mode uses:

- `llvm.tags`
- `test_suite.official.tags`
- `test_suite.raja.tags`

Explicit experiment mode uses:

- `experiments[]`
  - each item defines `llvm_tag`, `official_tag`, `raja_tag`, optional `platform`

If `experiments` exists and is non-empty, explicit mode wins.

## Label Model

There is exactly one label field:

```yaml
# label: "baseline"
```

If omitted, the workflow generates a timestamp like:

```text
YYYYMMDD_HHMMSS
```

The single `label` is used for:

- Official result directory
- RAJA result directory
- run log directory
- `experiment_id` generation
- parsed record column
- inspect summary column

Do not reintroduce:

- `run_label`
- `run-label`
- `run_labels`
- `runs.labels`
- `repeat_count`
- `profile`
- experiment `name`

Repeated experiments and statistical samples should be redesigned later with a separate repeat/sample model. Do not overload `label` with multiple meanings.

## Test Selection Model

Stage 5A added direct argument pass-through:

```yaml
test_selection:
  official:
    lit_args: []
  raja:
    extra_args: []
```

The whole `test_selection` block is optional. Each suite sub-block is optional.

Equivalent defaults:

```yaml
test_selection:
  official:
    lit_args: []
  raja:
    extra_args: []
```

Only configuring RAJA is valid:

```yaml
test_selection:
  raja:
    extra_args:
      - "--kernels"
      - "Basic_DAXPY"
```

The values must be YAML lists. Do not split shell strings in code.

Current behavior:

- Official command becomes `lit -v -o <result> <lit_args...> <build_dir>`.
- RAJA command becomes `raja-perf.exe <extra_args...>`.
- `.run_complete` records the arguments actually used.
- `experiment.json` records normalized `test_selection`.

Changing selection with the same `label` reuses or overwrites the same result paths. For formal experiments, use a distinct `label` when changing selection.

## Stage History

### Stage 1: Experiment Matrix

Main outcome:

- Replaced single-tag execution with experiment-driven DAG expansion.
- Added simple matrix mode and explicit experiment mode.
- Introduced `experiment_id`.
- Shared checkout/build/install by version tags.
- Isolated parsed/report/log/metadata outputs by experiment.
- Set benchmark run jobs to exclusive scheduling through high `threads`.

Important later correction:

- Stage 1 originally experimented with repeated labels and repeat expansion.
- That model was later removed. The current system has one global `label`.

### Stage 2: Metadata, Recovery, and Code Cleanup

Main outcome:

- Added `auto/metadata/<experiment_id>/experiment.json`.
- Added `workflow/scripts/write_experiment_metadata.py`.
- Added `tools/inspect_workflow_outputs.py`.
- Added `docs/recovery.md`.
- Added `run.sh` commands:
  - normal run with `--keep-going`
  - `resume`
  - `strict`
  - `inspect`
- Kept recovery Snakemake-first.
- Removed the idea of a separate manifest/state-machine scheduler.
- Consolidated repeated command-running logic into `workflow/lib/command_runner.py`.
- Split path layout into `workflow/lib/layout.py`.
- Split CMake/Ninja build behavior into `workflow/lib/cmake_build.py`.
- Cleaned old config compatibility paths.

Important design decision:

- `inspect` is read-only.
- Metadata is provenance, not mutable state.

### Stage 3: Build Cache and Storage Observability

Main outcome:

- Changed builds to reuse CMake build directories by default.
- Added `build.clean_build`.
- Added `build.reconfigure`.
- Removed an unnecessary `build_slot` resource setting; Snakemake `-j` is sufficient.
- Added disk usage reporting through `tools/report_disk_usage.py` and `./run.sh disk`.
- Clarified shared logs:
  - checkout/build logs go under `auto/logs/_shared/...`
  - run logs go under `auto/logs/_runs/.../<label>/...`
  - parse/aggregate/report/metadata logs go under `auto/logs/<experiment_id>/...`
- Updated `docs/storage.md` to be user-facing English documentation.

Important design decision:

- Shared logs may be overwritten by later reuse of shared build/checkouts.
- Full run reconstruction should also consult `.snakemake/log/<timestamp>.snakemake.log`.

### Stage 4: Parser Adapters and RAJA Multi-Format Support

Main outcome:

- Found a real failure mode: RAJAPerf versions can output different schemas.
- Moved RAJA run success away from requiring `RAJAPerf-kernel-run-data.csv`.
- `run_raja` now succeeds if RAJAPerf runs and produces RAJAPerf output files, then writes `.run_complete`.
- Parser layer decides which RAJA files are supported.
- Added parser adapter structure:
  - `workflow/lib/parsers/base.py`
  - `workflow/lib/parsers/official.py`
  - `workflow/lib/parsers/raja.py`
- Added unified schema:
  - `workflow/lib/result_schema.py`
- Supported RAJA formats:
  - `RAJAPerf-kernel-run-data.csv`
  - `RAJAPerf-timing-Average.csv`
- Removed backward-compatible parser wrapper functions.

Important design decision:

- A benchmark run completing is not the same as the parser supporting every output schema.
- Add adapters for new formats rather than hard-coding file names in `Snakefile` or `run_raja.py`.

### Stage 5A: Direct Test Selection, Single Label, Self-Contained Reports

Main outcome:

- Added `test_selection.official.lit_args`.
- Added `test_selection.raja.extra_args`.
- Passed these args through Snakemake params into run scripts.
- Recorded args in `.run_complete`.
- Recorded normalized test selection in metadata.
- Unified label-like config to one global `label`.
- Removed old label/repeat fields from active code.
- Changed parser CLI and schema from `run_label` to `label`.
- Changed inspect summary from `run_label` to `label`.
- Changed report generation to self-contained Plotly HTML:
  - `fig.write_html(..., include_plotlyjs=True)`

Important design decision:

- Report files should be offline-viewable. CDN-based Plotly caused blank reports in remote/IDE preview environments.

## Current User-Facing Commands

Normal run:

```bash
./run.sh
```

Dry-run:

```bash
./run.sh dry-run
```

Strict run:

```bash
./run.sh strict
```

Resume:

```bash
./run.sh resume
```

Inspect:

```bash
./run.sh inspect
```

Disk usage:

```bash
./run.sh disk
```

Force-regenerate only one report:

```bash
./run.sh -- --forcerun generate_report \
  auto/reports/<experiment_id>/benchmark_report.html
```

Example from a real run:

```bash
./run.sh -- --forcerun generate_report \
  auto/reports/llvm_llvmorg-21.1.0__official_llvmorg-21.1.0__raja_v2025.12.0__label_20260527_022025/benchmark_report.html
```

## Known Useful Real Outputs

Existing real outputs have been used for validation:

- `auto/results/raja-v2025.12.0/llvmorg-21.1.0/20260518_212526/RAJAPerf-kernel-run-data.csv`
- `auto/results/raja-v2025.03.0/llvmorg-21.1.0/20260518_220116/RAJAPerf-timing-Average.csv`
- `auto/results/raja-v2025.12.0/llvmorg-21.1.0/20260527_022025/RAJAPerf-kernel-run-data.csv`
- `auto/results/official-llvmorg-21.1.0/llvmorg-21.1.0/20260527_022025/baseline_results.json`

The `20260527_022025` run produced:

- `42` parsed benchmark records
- `42` aggregated benchmark records
- an HTML report that originally appeared blank when Plotly was CDN-loaded

## Validation Commands Used Recently

Compile checks:

```bash
.venv/bin/python -m py_compile workflow/lib/common.py workflow/lib/layout.py workflow/lib/parse_results.py workflow/lib/result_schema.py workflow/lib/parsers/base.py workflow/lib/parsers/official.py workflow/lib/parsers/raja.py workflow/scripts/parse_results_cli.py workflow/scripts/write_experiment_metadata.py tools/inspect_workflow_outputs.py workflow/lib/reporting.py workflow/scripts/generate_report_cli.py
```

Config normalization:

```bash
.venv/bin/python - <<'PY'
from pathlib import Path
from workflow.lib.common import load_config, normalize_workflow_config
cfg = normalize_workflow_config(load_config(Path("config.yml")))
print("label=", cfg["label"])
print("mode=", cfg["experiment_mode"])
print("experiments=", len(cfg["experiments"]))
print(cfg["experiments"][0])
PY
```

Dry-run:

```bash
./run.sh dry-run
```

Parse existing results with label:

```bash
.venv/bin/python workflow/scripts/parse_results_cli.py \
  --input-dir auto/results \
  --label 20260518_220116 \
  --compiler-version llvmorg-21.1.0 \
  --suite-version official=llvmorg-21.1.0 \
  --suite-version raja=v2025.03.0 \
  --output-file /tmp/label_parse.csv
```

Generate self-contained report from an existing aggregated CSV:

```bash
.venv/bin/python workflow/scripts/generate_report_cli.py \
  --input-file auto/parsed/llvm_llvmorg-21.1.0__official_llvmorg-21.1.0__raja_v2025.12.0__label_20260527_022025/benchmark_records_aggregated.csv \
  --output-html /tmp/self_contained_report.html
```

Format check:

```bash
git diff --check
```

Search for removed old label fields:

```bash
rg -n "run_label|run-label|runs\\.labels|repeat_count|run_labels|repeat_labels|\\bprofile\\b" config.yml workflow tools --glob '!*.pyc'
```

## Next Likely Work

Continue from `work_plan.md`, probably Stage 5B or Stage 6 depending on project priorities.

Stage 5B likely means:

- Add structured selection helpers only after direct `lit_args` and `extra_args` prove stable.
- Consider `workflow/lib/test_selection.py`.
- Avoid hard-coding suite-specific selection logic in run scripts.

Stage 6 likely means:

- Version-to-version comparison.
- Regression and improvement tables.
- Threshold filtering.
- Analysis outputs suitable for the dissertation.

Stage 7 likely means:

- Better report views.
- Interactive filtering.
- Historical experiment comparison reports.

Stage 8 likely means:

- Redesign repeated runs and statistical significance.
- Do not revive old `repeat_count` directly.

## Development Risks

- Long benchmark runs are expensive; use existing `auto/results` for parser/report validation.
- Labels are global; changing selection under the same label can overwrite or reuse paths.
- Shared build logs are not immutable per-experiment evidence.
- Reports are now larger because Plotly is embedded.
- Current reporting is still simple and demo-like; blank reports from empty filtered views should be handled better in a later stage.
- Automated tests are still sparse or absent.

## Conversation Preservation

Full chat history is not automatically stored in this repository. If the chat UI supports export, export the raw conversation to:

```text
docs/conversations/<date>-<topic>.md
```

This handoff document should be updated after each major stage so future agents do not need to read the full raw chat to recover context.
