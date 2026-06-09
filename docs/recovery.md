# Snakemake Recovery Notes

## Common Recovery Commands

`run.sh` passes `--keep-going` to Snakemake by default, so independent jobs can continue after a failure.

Run the workflow in strict mode when you want Snakemake to stop as soon as a job fails:

```bash
./run.sh strict
```

Continue after an interrupted run:

```bash
./run.sh resume
```

Continue after an interrupted run, but stop immediately on the next failure:

```bash
./run.sh strict resume
```

For less common recovery targets, use the pass-through form. Snakemake will still receive `--keep-going` unless `strict` is used:

```bash
./run.sh -- auto/reports/analysis_report.html
./run.sh strict -- auto/reports/analysis_report.html
```

If raw benchmark results already exist and only derived outputs are missing, target the derived output directly. Snakemake will reuse existing raw results when their expected files and stamps are present:

```bash
./run.sh -- auto/parsed/<experiment_id>/benchmark_records.csv
./run.sh -- auto/analysis/analysis_summary.json
./run.sh -- auto/reports/analysis_report.html
```

To force a specific rule, use Snakemake pass-through arguments:

```bash
./run.sh -- --forcerun run_raja auto/reports/analysis_report.html
```

## Output Summary

The inspection helper is read-only. It scans existing workflow outputs and suggests which artifact is missing:

```bash
./run.sh inspect
```

Machine-readable formats are also available:

```bash
./run.sh inspect --format csv
./run.sh inspect --format json
```

## Metadata

Each experiment metadata file is written under:

```text
auto/metadata/<experiment_id>/experiment.json
```

This file records the normalized experiment, expected output paths, log paths, a config snapshot, and lightweight environment information.
