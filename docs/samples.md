# Repeated Samples

Stage 6B adds an explicit sample dimension to the workflow. A `label` identifies one experiment group, while `sample` identifies one independent observation inside that group.

## Configure Sample Count

Set the number of samples in `config.yml`:

```yaml
samples:
  count: 3
```

The workflow expands each experiment configuration into:

```text
sample_1
sample_2
sample_3
```

If `samples.count` is omitted, the default is one sample.

## Output Layout

Raw benchmark results are stored under both `label` and `sample`:

```text
auto/results/official-<official_tag>/<llvm_tag>/<label>/<sample>/
auto/results/raja-<raja_tag>/<llvm_tag>/<label>/<sample>/
```

Derived outputs still use `experiment_id`, and the generated ID includes the sample:

```text
auto/parsed/<experiment_id>/benchmark_records.csv
auto/metadata/<experiment_id>/experiment.json
auto/reports/<experiment_id>/benchmark_report.html
```

## Parsed Columns

Parsed and aggregated tables include both columns:

```text
label
sample
```

The normal aggregation step preserves the sample boundary. It does not merge multiple samples into one statistical result.

## Interpretation

Stage 6B creates and records independent samples. Stage 6C uses those samples for statistical aggregation, confidence intervals, and significance screening. See `docs/statistical_analysis.md`.
