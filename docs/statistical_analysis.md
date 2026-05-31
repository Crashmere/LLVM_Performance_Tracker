# Statistical Sample Group Comparison

Stage 6C compares groups of repeated samples. It builds on the sample dimension introduced in Stage 6B.

## Inputs

Pass multiple baseline and candidate sample experiments:

```bash
./run.sh compare-samples \
  --baseline-experiment <baseline_sample_1_experiment_id> \
  --baseline-experiment <baseline_sample_2_experiment_id> \
  --baseline-experiment <baseline_sample_3_experiment_id> \
  --candidate-experiment <candidate_sample_1_experiment_id> \
  --candidate-experiment <candidate_sample_2_experiment_id> \
  --candidate-experiment <candidate_sample_3_experiment_id> \
  --output-dir auto/comparisons/<comparison_name>
```

You can also pass aggregated files directly:

```bash
./run.sh compare-samples \
  --baseline-file <baseline_sample_1_aggregated.csv> \
  --baseline-file <baseline_sample_2_aggregated.csv> \
  --candidate-file <candidate_sample_1_aggregated.csv> \
  --candidate-file <candidate_sample_2_aggregated.csv> \
  --output-dir auto/comparisons/<comparison_name>
```

## Thresholds

The default change threshold is `5%`. Override it globally or per metric:

```bash
./run.sh compare-samples \
  --baseline-experiment <baseline_sample_1_experiment_id> \
  --baseline-experiment <baseline_sample_2_experiment_id> \
  --baseline-experiment <baseline_sample_3_experiment_id> \
  --candidate-experiment <candidate_sample_1_experiment_id> \
  --candidate-experiment <candidate_sample_2_experiment_id> \
  --candidate-experiment <candidate_sample_3_experiment_id> \
  --output-dir auto/comparisons/<comparison_name> \
  --threshold-percent 5 \
  --metric-threshold flops_gflops=3 \
  --alpha 0.05
```

By default, a change needs at least three samples in each group before it can be marked `reliable_*`. Use `--min-samples` to change that threshold.

## Outputs

The output directory contains:

- `sample_observations.csv`: one row per sample observation and metric.
- `sample_statistics.csv`: per-group mean, standard deviation, coefficient of variation, and 95% confidence interval.
- `statistical_comparison.csv`: baseline/candidate group comparison with p-value and classification.
- `reliable_regressions.csv`: statistically supported regressions above the configured threshold.
- `reliable_improvements.csv`: statistically supported improvements above the configured threshold.
- `candidate_regressions.csv`: changes above the threshold that do not yet have enough statistical evidence.
- `candidate_improvements.csv`: improvements above the threshold that do not yet have enough statistical evidence.
- `statistical_summary.json`: source paths, settings, classification counts, and top changes.

## Interpretation

Classifications use both metric direction and the configured threshold:

- `reliable_regression`
- `reliable_improvement`
- `candidate_regression`
- `candidate_improvement`
- `within_threshold`
- `unchanged`
- `unclassified`

The current implementation reports a Welch-style p-value using a normal approximation. This is suitable as a lightweight screening tool, but small sample sizes should still be interpreted cautiously.
