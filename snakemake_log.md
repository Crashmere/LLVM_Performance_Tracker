# Snakemake 迁移实施记录

本文档用于记录 Snakemake 迁移过程中每个阶段已经完成的实际修改、验证方式与当前状态。后续阶段继续在此文件追加。

## 阶段 1：抽取公共逻辑，降低 `benchmark_pipeline.py` 耦合

### 目标

- 将可复用 helper 从 `benchmark_pipeline.py` 抽出，为后续 rule 化做准备
- 保持旧 `benchmark_pipeline.py` 仍可运行，不改变当前用户入口

### 实际修改

- 新增 [`workflow/scripts/common.py`](/home/eidf018/eidf018/s2778911-aspp/msc/workflow/scripts/common.py)
- 将以下逻辑从 [`benchmark_pipeline.py`](/home/eidf018/eidf018/s2778911-aspp/msc/benchmark_pipeline.py) 抽取到 `common.py`
  - 配置读取：`load_config()`
  - LLVM 版本解析：`resolve_llvm_version()`
  - `ninja_jobs` 规范化：`normalize_ninja_jobs()`
  - 目录清理：`clear_directory()`
  - `latest` tag 解析：`get_resolved_tag()`
  - git checkout / fetch / clone / submodule 准备：`prepare_git_repo()`
  - CMake + Ninja 构建封装：`build_with_cmake()`
  - Clang 主版本探测：`get_actual_clang_major_version()`
  - `libomp.so` 查找：`find_omp_library()`
  - LLVM / Official / RAJA 构建参数拼装：
    - `get_llvm_cmake_args()`
    - `get_official_cmake_args()`
    - `get_raja_cmake_args()`
- 修改 [`benchmark_pipeline.py`](/home/eidf018/eidf018/s2778911-aspp/msc/benchmark_pipeline.py)
  - 通过 `load_config()` 读取配置
  - 通过 `resolve_llvm_version()` 解析 `LLVM_VERSION`
  - 通过 `normalize_ninja_jobs()` 统一 `NINJA_JOBS`
  - 各阶段 build 改为调用 `common.py` 中的 helper
  - 保留原有 `.venv` 自举、日志写法、顺序式 orchestration 和旧入口

### 验证

- 运行语法检查：

```bash
python3 -m py_compile benchmark_pipeline.py workflow/scripts/common.py parse_results.py generate_report.py
```

- 结果：通过

### 提交记录

- Git commit: `0ae6c2a`
- 提交消息：`Refactor pipeline helpers for Snakemake migration`

### 当前状态说明

- 阶段 1 的目标已完成
- 旧 pipeline 仍可作为当前主入口继续运行
- 本阶段有意保留旧行为中的两个点，避免过早引入迁移风险
  - 仍由 `benchmark_pipeline.py` 自举 `.venv`
  - 仍在构建前清空 build 目录

## 阶段 2：重构结果处理脚本为“库 + CLI”

### 目标

- 让结果解析与报告生成可以脱离 `config.yml` 独立调用
- 为后续 Snakemake `script:` / `shell:` 提供清晰稳定的 CLI 接口

### 实际修改

- 重构 [`parse_results.py`](/home/eidf018/eidf018/s2778911-aspp/msc/parse_results.py) 为纯库模块
  - 移除直接从 `config.yml` 推导结果目录的入口行为
  - 保留 `BenchmarkRecord` / `BenchmarkMetrics` 数据结构
  - 保留 Official JSON 与 RAJA CSV 的解析逻辑
  - 将 `run_id` 语义明确为 `run_label`
  - 新增标准化表格能力：
    - `records_to_dataframe()`
    - `filter_records()`
    - `write_records_table()`
  - 支持输出 `.csv` 与 `.parquet`
- 重构 [`generate_report.py`](/home/eidf018/eidf018/s2778911-aspp/msc/generate_report.py) 为纯库模块
  - 新增 `read_table()` 读取 `.csv` / `.parquet`
  - 保留 `aggregate_benchmark_records()` 聚合逻辑
  - 保留 `generate_pure_plotly_report()` 报告生成逻辑
  - 新增 `write_table()` 用于输出聚合结果
- 新增 CLI 入口 [`workflow/scripts/parse_results_cli.py`](/home/eidf018/eidf018/s2778911-aspp/msc/workflow/scripts/parse_results_cli.py)
  - 参数：
    - `--input-dir`
    - `--output-file`
    - `--suite-name`
    - `--compiler-version`
    - `--run-label`
- 新增 CLI 入口 [`workflow/scripts/generate_report_cli.py`](/home/eidf018/eidf018/s2778911-aspp/msc/workflow/scripts/generate_report_cli.py)
  - 参数：
    - `--input-file`
    - `--output-html`
    - `--aggregated-output`

### 验证

- 运行语法检查：

```bash
.venv/bin/python -m py_compile \
  benchmark_pipeline.py \
  parse_results.py \
  generate_report.py \
  workflow/scripts/common.py \
  workflow/scripts/parse_results_cli.py \
  workflow/scripts/generate_report_cli.py
```

- 验证 CLI 帮助信息：

```bash
.venv/bin/python workflow/scripts/parse_results_cli.py --help
.venv/bin/python workflow/scripts/generate_report_cli.py --help
```

- 使用仓库内现有 `auto/results` 样本做端到端验证：

```bash
.venv/bin/python workflow/scripts/parse_results_cli.py \
  --input-dir auto/results \
  --output-file auto/parsed/stage2_validation/benchmark_records.csv

.venv/bin/python workflow/scripts/generate_report_cli.py \
  --input-file auto/parsed/stage2_validation/benchmark_records.csv \
  --aggregated-output auto/parsed/stage2_validation/benchmark_records_aggregated.csv \
  --output-html auto/reports/stage2_validation/benchmark_report.html
```

- 验证结果
  - 成功解析并输出标准化记录表
  - 成功输出聚合结果文件
  - 成功生成 HTML 报告
  - 期间出现一条已有样本数据告警：
    - `auto/results/raja-v2025.03.0/21.1.0/20260503_212930` 下缺少预期 CSV
    - 该告警来自已有历史数据，不是本阶段代码错误

### 环境说明

- 验证阶段为项目 `.venv` 补装了依赖：
  - `pandas`
  - `plotly`
  - `pyarrow`
- 这是运行环境变更，不属于 git 文件修改，但会影响 CLI 的本地可执行性

### 当前状态说明

- 阶段 2 的目标已完成
- 结果解析与报告生成现在都已经具备“库 + CLI”结构
- 后续可直接作为 Snakemake 规则中的脚本入口复用

## 后续追加约定

- 每完成一个迁移阶段，就在本文件追加一节
- 每节至少记录：
  - 目标
  - 实际修改
  - 验证方式
  - 当前状态或遗留问题
