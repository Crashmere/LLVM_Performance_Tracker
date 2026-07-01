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

## 2026-06-29: LLVM 11/12/13 Build Failed

Failed LLVM versions:

```text
llvmorg-11.1.0
llvmorg-12.0.1
llvmorg-13.0.1
```

Failed rule:

```text
build_llvm
```

Failure logs:

```text
auto/logs/_shared/build_llvm/llvmorg-11.1.0/build_llvm.log
auto/logs/_shared/build_llvm/llvmorg-12.0.1/build_llvm.log
auto/logs/_shared/build_llvm/llvmorg-13.0.1/build_llvm.log
```

Core error:

```text
llvm/include/llvm/Support/Signals.h
error: 'uintptr_t' was not declared in this scope
note: 'uintptr_t' is defined in header '<cstdint>'
```

## 2026-07-01: LLVM 14.0.0 Build Failed

Failed LLVM version:

```text
llvmorg-14.0.0
```

Failed rule:

```text
build_llvm
```

Failure log:

```text
auto/logs/_shared/build_llvm/llvmorg-14.0.0/build_llvm.log
```

Core error:

```text
llvm/include/llvm/Support/Signals.h
error: 'uintptr_t' was not declared in this scope
note: 'uintptr_t' is defined in header '<cstdint>'
```
