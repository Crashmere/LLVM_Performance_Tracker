# LLVM Release Monitoring

The workflow can be driven by a small monitoring script that checks the LLVM repository for new stable release tags and then runs the existing Snakemake pipeline with a runtime LLVM tag override.

The monitor only handles LLVM tags that match this format:

```text
llvmorg-X.Y.Z
```

It ignores release candidates, arbitrary commits, and RAJA or llvm-test-suite tags.

## Commands

Check the remote repository without writing state or starting the workflow:

```bash
.venv/bin/python tools/check_llvm_releases.py --config-file config.yml
```

Initialize the current latest LLVM release as the baseline:

```bash
.venv/bin/python tools/check_llvm_releases.py --config-file config.yml --initialize
```

Run the monitor and trigger the workflow if a newer latest release tag appears:

```bash
.venv/bin/python tools/check_llvm_releases.py --config-file config.yml --run
```

On the first `--run`, if no state file exists yet, the script records the current latest release as the baseline and does not start the workflow. This avoids accidentally launching a long historical run when deploying the monitor for the first time.

## State Files

By default, the monitor stores state under:

```text
auto/monitor/
```

The main files are:

```text
auto/monitor/seen_llvm_tags.txt
auto/monitor/last_triggered.json
```

These files are runtime state and are not intended to be committed.

## Cron Example

A minimal cron entry can run the monitor periodically:

```cron
0 3 * * * cd /path/to/project && .venv/bin/python tools/check_llvm_releases.py --config-file config.yml --run >> auto/monitor/cron.log 2>&1
```

Adjust the project path, Python environment, schedule, and output location for the target machine. The project does not install or manage crontab entries.
