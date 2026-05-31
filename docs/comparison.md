# Historical Result Comparison

Stage 6A provides a lightweight comparison command for aggregated benchmark results. It identifies candidate performance changes without rerunning benchmarks.

The command reads `project.base_dir` from `config.yml` when resolving experiment IDs.

## Compare Historical Experiments

Use experiment IDs from `auto/parsed/`:

```bash
./run.sh compare \
  --baseline-experiment <baseline_experiment_id> \
  --candidate-experiment <candidate_experiment_id> \
  --output-dir auto/comparisons/<comparison_name>
```

You can also compare aggregated tables directly:

```bash
./run.sh compare \
  --baseline-file auto/parsed/<baseline_experiment_id>/benchmark_records_aggregated.csv \
  --candidate-file auto/parsed/<candidate_experiment_id>/benchmark_records_aggregated.csv \
  --output-dir auto/comparisons/<comparison_name>
```

## Thresholds

The default threshold is `5%`. Override it globally or for selected metrics:

```bash
./run.sh compare \
  --baseline-experiment <baseline_experiment_id> \
  --candidate-experiment <candidate_experiment_id> \
  --output-dir auto/comparisons/<comparison_name> \
  --threshold-percent 5 \
  --metric-threshold flops_gflops=3
```

Supported metrics:

- `exec_time`
- `compile_time`
- `binary_size`
- `bandwidth_gib`
- `flops_gflops`

The command understands metric direction. Lower execution time, compile time, and binary size are better. Higher bandwidth and GFLOP/s are better.

## Outputs

The output directory contains:

- `comparison.csv`: all matched metric comparisons.
- `regressions.csv`: candidate regressions above the configured threshold, ordered by magnitude.
- `improvements.csv`: candidate improvements above the configured threshold, ordered by magnitude.
- `comparison_summary.json`: source paths, matched and unmatched record counts, thresholds, and top changes.

## Interpretation

Stage 6A compares aggregated observations and reports candidate changes. It does not perform statistical significance testing. Use its regression and improvement lists to identify changes worth investigating, not as final evidence that a performance regression is statistically reliable.
