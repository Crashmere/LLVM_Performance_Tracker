# Run Records

## 2026-06-28 Run Failure: LLVM 22.1.0 Official Test-Suite Build

This run started at:

```text
2026-06-28 04:24:55 UTC
```

Main Snakemake log:

```text
.snakemake/log/2026-06-28T042455.389648.snakemake.log
```

The run used label:

```text
20260628_042455
```

The configured LLVM versions were:

```text
llvmorg-17.0.0
llvmorg-18.1.0
llvmorg-22.1.0
```

The suite versions were unchanged:

```text
Official test-suite: llvmorg-21.1.0
RAJAPerf: v2025.12.0
```

Each experiment was configured with five samples.

### What Completed

- `llvmorg-17.0.0` completed all five samples and produced parsed benchmark records.
- `llvmorg-18.1.0` completed all five samples and produced parsed benchmark records.
- RAJAPerf built successfully for `llvmorg-22.1.0`.

### Failure

The workflow failed in:

```text
rule build_official
```

for:

```text
Official test-suite llvmorg-21.1.0 + LLVM llvmorg-22.1.0
```

Failure log:

```text
auto/logs/_shared/build_official/llvmorg-21.1.0/llvm-llvmorg-22.1.0/build_official.log
```

The failing component was:

```text
MultiSource/Applications/ClamAV/libclamav_cvd.c
```

Clang 22.1.0 reported incompatible pointer type errors around `gzFile` usage, for example assigning `gzFile` to `gzFile *` and passing `gzFile *` where `gzFile` was expected.

### Interpretation

This was a source compatibility issue between LLVM 22.1.0's compiler diagnostics and the older ClamAV code included in `llvm-test-suite` `llvmorg-21.1.0`.

It was not caused by:

- Snakemake orchestration logic.
- Result parsing.
- Report generation.
- Disk exhaustion.

The filesystem was still tight, with roughly 4.4 GiB available, but the observed failure was a compiler error rather than `No space left on device`.

### Follow-Up Options

- For a stable project demonstration, avoid `llvmorg-22.1.0` with the current Official test-suite configuration.
- Use already validated LLVM versions such as `llvmorg-17.0.0` and `llvmorg-18.1.0`, or the earlier 19/20/21 set.
- If LLVM 22 support is needed later, consider excluding `MultiSource/Applications/ClamAV` from Official test-suite runs or adding a dedicated compatibility patch.
- Update `analysis.min_samples` to `3` when running five samples, if the goal is to require at least three valid observations per sample group.
