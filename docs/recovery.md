# Snakemake Recovery Notes

This workflow keeps Snakemake as the only scheduler. Recovery should normally be done by asking Snakemake for the target you want, not by running workflow stages manually.

## Common Recovery Commands

Continue after an interrupted run:

```bash
./run.sh -- --rerun-incomplete
```

Continue independent jobs after a failure in a batch:

```bash
./run.sh -- --keep-going
```

Rebuild one experiment report and any missing prerequisites:

```bash
./run.sh -- auto/reports/<experiment_id>/benchmark_report.html
```

Force one rule to rerun on the path to a report:

```bash
./run.sh -- --forcerun run_raja auto/reports/<experiment_id>/benchmark_report.html
```

If raw benchmark results already exist and only derived outputs are missing, target the derived output directly. Snakemake will reuse existing raw results when their expected files and stamps are present:

```bash
./run.sh -- auto/parsed/<experiment_id>/benchmark_records_aggregated.csv
./run.sh -- auto/reports/<experiment_id>/benchmark_report.html
```

## Output Summary

The summary helper is read-only. It scans existing workflow outputs and suggests which artifact is missing:

```bash
.venv/bin/python workflow/scripts/summarize_outputs_cli.py --base-dir auto
```

Machine-readable formats are also available:

```bash
.venv/bin/python workflow/scripts/summarize_outputs_cli.py --base-dir auto --format csv
.venv/bin/python workflow/scripts/summarize_outputs_cli.py --base-dir auto --format json
```

## Metadata

Each experiment report depends on:

```text
auto/metadata/<experiment_id>/experiment.json
```

This file records the normalized experiment, expected output paths, log paths, a config snapshot, and lightweight environment information. It is provenance data, not a mutable job-state database.

## Design Boundary

Do not add a second scheduler around Snakemake. Helper scripts should inspect existing files or write explicit DAG outputs only. They should not silently retry jobs, mutate global status, or call multiple workflow stages behind Snakemake's back.
