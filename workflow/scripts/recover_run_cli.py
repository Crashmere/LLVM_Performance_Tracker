#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from workflow.lib.parse_results import filter_records, parse_results_directory, records_to_dataframe, write_records_table
from workflow.lib.reporting import aggregate_benchmark_records, generate_pure_plotly_report, write_table
from workflow.lib.run_manifest import discover_historical_experiments


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rebuild parsed data and reports from existing raw results.")
    parser.add_argument("--base-dir", required=True, help="Workflow base directory, such as auto/.")
    parser.add_argument("--run-label", help="Only recover experiments with this run_label.")
    parser.add_argument("--experiment-id", help="Only recover this experiment_id.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing parsed/report outputs.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    base_dir = Path(args.base_dir).expanduser().resolve()
    results_root = base_dir / "results"
    experiments = discover_historical_experiments(base_dir)
    if args.run_label:
        experiments = [experiment for experiment in experiments if experiment["run_label"] == args.run_label]
    if args.experiment_id:
        experiments = [experiment for experiment in experiments if experiment["experiment_id"] == args.experiment_id]

    if not experiments:
        raise FileNotFoundError("No matching historical experiments were found.")

    all_records = parse_results_directory(results_root)
    recovered = 0

    for experiment in experiments:
        experiment_id = experiment["experiment_id"]
        parsed_dir = base_dir / "parsed" / experiment_id
        reports_dir = base_dir / "reports" / experiment_id
        parsed_csv = parsed_dir / "benchmark_records.csv"
        aggregated_csv = parsed_dir / "benchmark_records_aggregated.csv"
        report_html = reports_dir / "benchmark_report.html"

        if not args.force and parsed_csv.exists() and aggregated_csv.exists() and report_html.exists():
            print(f"Skipping {experiment_id}: derived outputs already exist.")
            continue

        filtered_records = filter_records(
            all_records,
            compiler_version=experiment["llvm_tag"],
            run_label=experiment["run_label"],
            suite_versions={
                "official": experiment["official_tag"],
                "raja": experiment["raja_tag"],
            },
        )
        if not filtered_records:
            print(f"Skipping {experiment_id}: no raw records matched.")
            continue

        parsed_path = write_records_table(filtered_records, parsed_csv)
        aggregated_df = aggregate_benchmark_records(records_to_dataframe(filtered_records))
        aggregated_path = write_table(aggregated_df, aggregated_csv)
        report_path = generate_pure_plotly_report(aggregated_df, report_html)
        recovered += 1
        print(f"Recovered {experiment_id}")
        print(f"  parsed: {parsed_path}")
        print(f"  aggregated: {aggregated_path}")
        print(f"  report: {report_path}")

    print(f"Recovered {recovered} experiment(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
