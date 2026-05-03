# Scripts

This directory contains the automation scripts for building LLVM, running benchmark suites, and generating performance reports.

---

## System Requirements

The scripts are designed for **Linux (x86-64)**. The following system packages must be installed before running anything:

```bash
sudo apt-get update
sudo apt-get install -y \
    git \
    gcc g++ \
    cmake \
    ninja-build \
    python3 python3-pip python3-venv
```

**Python version:** 3.10 or later is required (the scripts use `X | Y` union type hints and `match` expressions).

---

## Scripts

| File | Description |
|------|-------------|
| `benchmark_pipeline.py` | Main entry point. Runs the full pipeline: bootstraps a Python virtual environment, builds a custom LLVM compiler from source, builds the LLVM Official Test Suite and RAJA Performance Suite against it, and executes both benchmark suites. |
| `parse_results.py` | Parses raw benchmark output files (Official suite JSON, RAJA CSV) from the results directory tree into a unified `BenchmarkRecord` data structure. Can also be run standalone to print a summary of parsed records. |
| `generate_report.py` | Reads parsed benchmark records, aggregates results across runs, and produces an interactive HTML report (`benchmark_report.html`) using Plotly. |
| `config.yml` | Configuration file. Controls which LLVM version to build, which compiler to use for the build, the test suite repository URLs and tags, and the base working directory. |
| `benchmark_pipeline_legacy.sh` | The original Bash implementation of the pipeline (superseded by `benchmark_pipeline.py`). Kept for reference. |

---

## Configuration

Edit `config.yml` before running. Key fields:

```yaml
project:
  base_dir: "~/auto"          # All build artefacts and results go here

llvm:
  tag: "llvmorg-21.1.0"       # LLVM release tag to check out and build
  build:
    c_compiler: "gcc"
    cxx_compiler: "g++"
    ninja_jobs: []             # e.g. ["-j4"] to limit parallelism and avoid OOM

test_suite:
  official_tag: "llvmorg-21.1.0"
  raja_tag: "v2025.03.0"
```

---

## Running the Pipeline

### Step 1 — Full build and benchmark run

```bash
python3 benchmark_pipeline.py
```

The script will:
1. Create a Python virtual environment at `scripts/.venv` and install `pyyaml` and `lit` automatically.
2. Clone and build LLVM into `<base_dir>/compiler/llvm-<version>-custom/`.
3. Clone and build the LLVM Official Test Suite and the RAJA Performance Suite.
4. Execute both benchmark suites and save results under `<base_dir>/results/`.

If the LLVM compiler binary already exists, the build step is skipped to save time.

### Step 2 — Generate the HTML report

After one or more benchmark runs have completed:

```bash
python3 generate_report.py
```

This reads all results from `<base_dir>/results/` and writes `benchmark_report.html` to the current directory.

`parse_results.py` can be run on its own to verify that results have been parsed correctly:

```bash
python3 parse_results.py
```

---

## Python Dependencies

`benchmark_pipeline.py` installs its own dependencies automatically into `.venv`. For `generate_report.py` and `parse_results.py`, install manually if needed:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install pyyaml lit pandas plotly
```

---

## Output Locations

| Artefact | Path |
|----------|------|
| Custom LLVM install | `<base_dir>/compiler/llvm-<version>-custom/` |
| Official Test Suite results | `<base_dir>/results/official-<tag>/<llvm-version>/<run-id>/baseline_results.json` |
| RAJA results | `<base_dir>/results/raja-<tag>/<llvm-version>/<run-id>/RAJAPerf-kernel-run-data.csv` |
| Per-phase build logs | `<base_dir>/logs/<llvm-version>/<run-id>/` |
| HTML performance report | `benchmark_report.html` (project root) |

`<run-id>` is a timestamp in the format `YYYYMMDD_HHMMSS`, so each run produces an isolated result directory.
