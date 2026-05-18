# Build Cache and Disk Usage

The workflow keeps CMake/Ninja build directories by default. This lets repeated runs reuse existing build artifacts and avoids unnecessary full rebuilds.

## Build Settings

Build cache behavior is configured in `config.yml`:

```yaml
build:
  ninja_jobs: 6
  clean_build: false
  reconfigure: true
```

- `build.ninja_jobs` controls the number of Ninja jobs used inside one build task.
- `build.clean_build: false` keeps the existing build directory before building.
- `build.clean_build: true` clears the build directory before CMake is run.
- `build.reconfigure: true` runs CMake configure whenever a build task runs, but does not clear the build directory.
- `build.reconfigure: false` skips CMake configure when `CMakeCache.txt` already exists, and then runs Ninja directly.

The workflow-level job concurrency is controlled by Snakemake's `-j` option. The `run.sh` wrapper uses `-j 2` by default.

## When To Use A Clean Build

Keep `clean_build: false` for normal runs. This is the safest default for reusing existing builds.

Use `clean_build: true` only when you want to discard the existing CMake/Ninja state for the selected build target, for example after a failed or corrupted build directory.

## Checking Disk Usage

Use the disk report command to inspect output directory sizes:

```bash
./run.sh disk
```

Limit the number of child entries shown per directory with:

```bash
./run.sh disk --top 5
```

This command is read-only. It does not delete files, rebuild outputs, or modify Snakemake metadata.

## Cleaning Files

There is no automatic cleanup rule. Source checkouts, build directories, LLVM installs, raw results, parsed tables, reports, metadata, and logs may all be needed for reproducibility or for rebuilding downstream targets.

Before deleting anything, use `./run.sh disk` to identify where space is being used, then remove only the directories you intentionally want to discard.
