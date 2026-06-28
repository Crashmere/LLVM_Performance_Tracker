# Run Records

## 2026-06-28: LLVM 22.1.0 Official Test-Suite Build Failed

Failed combination:

```text
LLVM: llvmorg-22.1.0
Official test-suite: llvmorg-21.1.0
RAJAPerf: v2025.12.0
```

Failed rule:

```text
build_official
```

Failure log:

```text
auto/logs/_shared/build_official/llvmorg-21.1.0/llvm-llvmorg-22.1.0/build_official.log
```

Core error:

```text
MultiSource/Applications/ClamAV/libclamav_cvd.c
error: incompatible pointer types assigning to 'gzFile *' from 'gzFile'
error: incompatible pointer types passing 'gzFile *' to parameter of type 'gzFile'
```
