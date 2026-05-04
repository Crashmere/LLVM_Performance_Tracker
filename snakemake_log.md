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

## 阶段 3：重构目录布局与配置模型

### 目标

- 将配置 schema 从“单版本、扁平字段”升级为更接近 Snakemake 设计的结构
- 引入显式 `run_label`
- 将源码、构建、安装、结果、日志目录切换到 `sources/`、`builds/`、`installs/`、`results/`、`logs/` 约定
- 保留旧配置 schema 的兼容读取能力，避免迁移期中断

### 实际修改

- 修改 [`workflow/scripts/common.py`](/home/eidf018/eidf018/s2778911-aspp/msc/workflow/scripts/common.py)
  - 新增 `normalize_workflow_config()`
    - 支持读取新 schema
    - 支持将旧 schema 归一化为新 schema
  - 新增 `get_layout_paths()`
    - 统一生成以下目录路径
      - `sources/`
      - `builds/`
      - `installs/`
      - `results/`
      - `parsed/`
      - `reports/`
      - `logs/`
    - 以及按参数组合展开的具体目录
      - LLVM source/build/install
      - Official source/build/result
      - RAJA source/build/result
  - 新增内部工具
    - `_ensure_list()`
    - `_nested_get()`
- 修改 [`benchmark_pipeline.py`](/home/eidf018/eidf018/s2778911-aspp/msc/benchmark_pipeline.py)
  - 不再直接假定旧 `config.yml` 结构
  - 先读取原始配置，再通过 `normalize_workflow_config()` 归一化
  - 从 `runs.run_label` 读取显式 `RUN_LABEL`
  - 从 `llvm.tags[0]`、`test_suite.official.tags[0]`、`test_suite.raja.tags[0]` 读取当前单版本参数
  - 使用 `get_layout_paths()` 生成路径布局
  - 将以下路径切换到新目录结构
    - LLVM source：`sources/llvm-project/<llvm_tag>`
    - LLVM build：`builds/llvm/<llvm_tag>`
    - LLVM install：`installs/llvm/<llvm_tag>`
    - Official source：`sources/official/<official_tag>`
    - Official build：`builds/official/<official_tag>/llvm-<llvm_version>`
    - RAJA source：`sources/raja/<raja_tag>`
    - RAJA build：`builds/raja/<raja_tag>/llvm-<llvm_version>`
    - results：`results/<suite-tag>/<llvm_version>/<run_label>`
    - logs：`logs/<run_label>`
  - `setup_directories()` 改为初始化上述新布局目录
  - 保留旧顺序式 pipeline 主入口不变
- 修改 [`config.yml`](/home/eidf018/eidf018/s2778911-aspp/msc/config.yml)
  - 引入新 schema：
    - `runs.run_label`
    - `llvm.tags`
    - `test_suite.official`
    - `test_suite.raja`
  - 当前仍只使用每个 tag 列表中的第一个元素，作为阶段 3 的单版本实现

### 验证

- 运行语法检查：

```bash
python3 -m py_compile \
  benchmark_pipeline.py \
  parse_results.py \
  generate_report.py \
  workflow/scripts/common.py \
  workflow/scripts/parse_results_cli.py \
  workflow/scripts/generate_report_cli.py
```

- 验证新 schema 可被正确归一化并生成新布局路径：

```bash
python3 - <<'PY'
from pathlib import Path
from workflow.scripts.common import load_config, normalize_workflow_config, get_layout_paths, resolve_llvm_version
cfg = normalize_workflow_config(load_config(Path('config.yml')))
llvm_tag = cfg['llvm']['tags'][0]
official_tag = cfg['test_suite']['official']['tags'][0]
raja_tag = cfg['test_suite']['raja']['tags'][0]
run_label = cfg['runs']['run_label']
llvm_version = resolve_llvm_version(llvm_tag)
layout = get_layout_paths(Path(cfg['project']['base_dir']).expanduser(), llvm_tag, official_tag, raja_tag, llvm_version, run_label)
print(layout['llvm_source'])
print(layout['official_build'])
print(layout['official_result'])
print(layout['logs_run_dir'])
PY
```

- 验证旧 schema 仍可被兼容层读取：

```bash
python3 - <<'PY'
from workflow.scripts.common import normalize_workflow_config
old_cfg = {
  'project': {'base_dir': '~/msc/auto'},
  'llvm': {
    'tag': 'llvmorg-21.1.0',
    'repo_url': 'https://github.com/llvm/llvm-project.git',
    'build': {'c_compiler': 'gcc', 'cxx_compiler': 'g++', 'ninja_jobs': []},
  },
  'test_suite': {
    'official_repo_url': 'https://github.com/llvm/llvm-test-suite.git',
    'official_tag': 'llvmorg-21.1.0',
    'official_cxx_standard': '17',
    'raja_repo_url': 'https://github.com/LLNL/RAJAPerf.git',
    'raja_tag': 'v2025.12.0',
    'raja_cxx_standard': '17',
  },
}
print(normalize_workflow_config(old_cfg))
PY
```

- 结果：通过

### 当前状态说明

- 阶段 3 的目标已基本完成
- 新配置模型和新目录布局都已经落地到代码中
- 兼容层允许迁移期同时接受旧 schema 与新 schema
- 当前限制
  - 虽然 schema 已支持列表形式的 `tags`，但 `benchmark_pipeline.py` 目前仍只消费每个列表的第一个元素
  - 这符合“设计上支持矩阵，实施上先跑通单版本”的阶段目标
  - 旧 `parse_results.py` 不依赖配置文件，因此无需为目录布局调整额外改动

## 阶段 4：搭建最小可运行 Snakemake 工作流

### 目标

- 建立最小但真实可运行的 `workflow/Snakefile`
- 先跑通 LLVM 的 checkout + build 两条规则
- 为 `build_llvm` 提供强完成信号，而不是只依赖目录存在
- 验证 Snakemake 能正确解析最小 DAG，并支持重复执行时跳过已完成产物

### 实际修改

- 新增 [`workflow/Snakefile`](/home/eidf018/eidf018/s2778911-aspp/msc/workflow/Snakefile)
  - 使用根目录 [`config.yml`](/home/eidf018/eidf018/s2778911-aspp/msc/config.yml) 作为工作流配置输入
  - 在解析阶段通过 `normalize_workflow_config()` 归一化配置
  - 使用 `get_layout_paths()` 计算 LLVM source/build/install/log 路径
  - 定义最小规则集：
    - `rule checkout_llvm`
    - `rule build_llvm`
    - `rule all`
- 新增 [`workflow/scripts/checkout_repo.py`](/home/eidf018/eidf018/s2778911-aspp/msc/workflow/scripts/checkout_repo.py)
  - 作为 `checkout_llvm` 的执行脚本
  - 复用 `prepare_git_repo()`
  - 生成 checkout 完成标记：
    - `.checkout_complete`
  - 为该 rule 写独立日志文件
- 新增 [`workflow/scripts/build_llvm.py`](/home/eidf018/eidf018/s2778911-aspp/msc/workflow/scripts/build_llvm.py)
  - 作为 `build_llvm` 的执行脚本
  - 复用 `build_with_cmake()` 与 `get_llvm_cmake_args()`
  - 生成 build 完成标记：
    - `.build_complete`
  - 显式检查关键产物：
    - `installs/llvm/<llvm_tag>/bin/clang++`
  - 为该 rule 写独立日志文件
- 修改 [`workflow/scripts/common.py`](/home/eidf018/eidf018/s2778911-aspp/msc/workflow/scripts/common.py)
  - 修正 LLVM / Official / RAJA 的 CMake 源码路径参数
  - 使 helper 能兼容“build 目录与 source 目录分离”的新布局
- 修改 [`benchmark_pipeline.py`](/home/eidf018/eidf018/s2778911-aspp/msc/benchmark_pipeline.py)
  - 更新对 `get_llvm_cmake_args()`、`get_official_cmake_args()`、`get_raja_cmake_args()` 的调用
  - 修复阶段 3 新目录布局下旧 pipeline 的 CMake 源码路径问题

### 规则设计说明

- `checkout_llvm`
  - 输出：
    - `directory(sources/llvm-project/<llvm_tag>)`
    - `sources/llvm-project/<llvm_tag>/.checkout_complete`
- `build_llvm`
  - 输入：
    - `sources/llvm-project/<llvm_tag>/.checkout_complete`
  - 输出：
    - `installs/llvm/<llvm_tag>/bin/clang++`
    - `builds/llvm/<llvm_tag>/.build_complete`
- `all`
  - 默认目标指向 LLVM 关键产物与 build stamp

### 验证

- 运行语法检查：

```bash
python3 -m py_compile \
  benchmark_pipeline.py \
  parse_results.py \
  generate_report.py \
  workflow/scripts/common.py \
  workflow/scripts/parse_results_cli.py \
  workflow/scripts/generate_report_cli.py \
  workflow/scripts/checkout_repo.py \
  workflow/scripts/build_llvm.py
```

- 为项目 `.venv` 安装 `snakemake`

- 运行 Snakemake dry-run：

```bash
.venv/bin/snakemake -s workflow/Snakefile -n -p
```

- 运行 DAG 可视化文本输出：

```bash
.venv/bin/snakemake -s workflow/Snakefile --dag
```

- 验证结果
  - Snakemake 成功解析最小工作流
  - `dry-run` 显示正确的依赖链：
    - `checkout_llvm -> build_llvm -> all`
  - `build_llvm` 同时依赖：
    - 关键产物 `bin/clang++`
    - 完成标记 `.build_complete`
  - 规则日志路径已独立配置：
    - `logs/<run_label>/checkout_llvm.log`
    - `logs/<run_label>/build_llvm.log`

### 环境说明

- 本阶段为项目 `.venv` 补装了：
  - `snakemake`
- 这是运行环境变更，不属于 git 文件修改

### 当前状态说明

- 阶段 4 的目标已完成
- 当前已经具备最小可运行 Snakemake 工作流
- 已验证 DAG 解析与依赖关系正确
- 尚未执行真实 LLVM 构建
  - 原因是完整构建成本较高，本阶段先验证工作流结构与规则契约
- 后续阶段可以在此基础上继续接入：
  - `checkout_official` / `build_official`
  - `checkout_raja` / `build_raja`
  - benchmark 运行与解析报告规则

## 阶段 5：接入 Official 和 RAJA 构建规则

### 目标

- 将 Official 和 RAJA 的 checkout/build 流程接入现有 Snakemake DAG
- 让两个 suite 的 build 依赖 LLVM install，而不是依赖旧脚本中的全局状态
- 为 `build_official` 和 `build_raja` 提供稳定的完成判定
- 验证在 `snakemake -j 2` 下，Official 和 RAJA build 具备并行执行条件

### 实际修改

- 修改 [`workflow/Snakefile`](/home/eidf018/eidf018/s2778911-aspp/msc/workflow/Snakefile)
  - 新增 `checkout_official`
  - 新增 `checkout_raja`
  - 新增 `build_official`
  - 新增 `build_raja`
  - 更新 `rule all`
    - 默认目标现在包含：
      - LLVM build 完成
      - Official build 完成
      - RAJA build 完成
- 新增 [`workflow/scripts/build_official.py`](/home/eidf018/eidf018/s2778911-aspp/msc/workflow/scripts/build_official.py)
  - 复用 `get_official_cmake_args()`
  - 复用 `build_with_cmake()`
  - 输出 `CMakeCache.txt` 与 `.build_complete`
- 新增 [`workflow/scripts/build_raja.py`](/home/eidf018/eidf018/s2778911-aspp/msc/workflow/scripts/build_raja.py)
  - 复用 `get_raja_cmake_args()`
  - 复用 `build_with_cmake()`
  - 输出 `bin/raja-perf.exe` 与 `.build_complete`
- 修改 [`workflow/scripts/checkout_repo.py`](/home/eidf018/eidf018/s2778911-aspp/msc/workflow/scripts/checkout_repo.py)
  - 增加 `recursive` 参数支持
  - 使 `checkout_raja` 可以按 submodule 方式准备源码
  - 将 `recursive` 状态写入 stamp 文件

### 规则设计说明

- `checkout_official`
  - 输出：
    - `directory(sources/official/<official_tag>)`
    - `sources/official/<official_tag>/.checkout_complete`
- `checkout_raja`
  - 输出：
    - `directory(sources/raja/<raja_tag>)`
    - `sources/raja/<raja_tag>/.checkout_complete`
  - 使用递归 submodule checkout
- `build_official`
  - 输入：
    - Official checkout stamp
    - LLVM `bin/clang++`
    - LLVM `.build_complete`
  - 输出：
    - `builds/official/<official_tag>/llvm-<llvm_version>/CMakeCache.txt`
    - `builds/official/<official_tag>/llvm-<llvm_version>/.build_complete`
- `build_raja`
  - 输入：
    - RAJA checkout stamp
    - LLVM `bin/clang++`
    - LLVM `.build_complete`
  - 输出：
    - `builds/raja/<raja_tag>/llvm-<llvm_version>/bin/raja-perf.exe`
    - `builds/raja/<raja_tag>/llvm-<llvm_version>/.build_complete`

### 验证

- 运行语法检查：

```bash
python3 -m py_compile \
  workflow/scripts/checkout_repo.py \
  workflow/scripts/build_llvm.py \
  workflow/scripts/build_official.py \
  workflow/scripts/build_raja.py \
  workflow/scripts/common.py \
  benchmark_pipeline.py
```

- 运行 Snakemake dry-run：

```bash
.venv/bin/snakemake -s workflow/Snakefile -n -j 2 -p
```

- 运行 DAG 可视化文本输出：

```bash
.venv/bin/snakemake -s workflow/Snakefile --dag
```

- 验证结果
  - Snakemake 成功解析包含 7 个 job 的 DAG：
    - `checkout_llvm`
    - `checkout_official`
    - `checkout_raja`
    - `build_llvm`
    - `build_official`
    - `build_raja`
    - `all`
  - `build_official` 与 `build_raja` 都显式依赖 LLVM build 产物与各自的 checkout stamp
  - DAG 中 `build_official` 与 `build_raja` 位于并行分支
  - 在 `-j 2` dry-run 下，规则依赖关系已满足并行执行条件
  - 每个新增 rule 都配置了独立日志文件：
    - `checkout_official.log`
    - `checkout_raja.log`
    - `build_official.log`
    - `build_raja.log`

### 当前状态说明

- 阶段 5 的目标已完成
- Official 与 RAJA 的 checkout/build 已接入 Snakemake DAG
- build 完成判定不再依赖“目录存在”这种弱信号
- 尚未执行真实 suite 构建
  - 本阶段重点是规则契约、依赖表达和并行结构验证

## 后续追加约定

- 每完成一个迁移阶段，就在本文件追加一节
- 每节至少记录：
  - 目标
  - 实际修改
  - 验证方式
  - 当前状态或遗留问题
