#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from workflow.lib.report_data import load_analysis_report_data
from workflow.lib.report_views import render_analysis_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate an HTML report from workflow analysis outputs.")
    parser.add_argument("--analysis-dir", required=True, help="Directory containing analysis CSV/JSON files.")
    parser.add_argument("--output-html", required=True, help="Output HTML report path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    data = load_analysis_report_data(args.analysis_dir)
    report_path = Path(args.output_html)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render_analysis_report(data, report_path), encoding="utf-8")
    print(f"Report generated successfully at: {report_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
