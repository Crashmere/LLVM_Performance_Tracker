# LLVM Benchmark Workflow

本仓库现在以 Snakemake 作为唯一工作流入口。

## 目录结构

- `config.yml`
  当前工作流配置
- `workflow/Snakefile`
  Snakemake 主入口
- `workflow/lib/`
  工作流共享库模块
- `workflow/scripts/`
  各 rule 的执行脚本和 CLI
- `snakemake_design.md`
  迁移设计文档
- `snakemake_log.md`
  分阶段实施记录

## 系统依赖

需要 Linux x86-64 环境，并预先安装：

```bash
sudo apt-get update
sudo apt-get install -y \
  git \
  gcc g++ \
  cmake \
  ninja-build \
  python3 python3-pip python3-venv
```

## Python 环境

建议使用项目本地虚拟环境：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install pyyaml lit pandas plotly pyarrow snakemake
```

## 配置

编辑 [`config.yml`](/home/eidf018/eidf018/s2778911-aspp/msc/config.yml)。

关键字段：

```yaml
project:
  base_dir: "~/msc/auto"

runs:
  run_label: "20260504_120000"

llvm:
  repo_url: "https://github.com/llvm/llvm-project.git"
  tags:
    - "llvmorg-21.1.0"

test_suite:
  official:
    repo_url: "https://github.com/llvm/llvm-test-suite.git"
    tags:
      - "llvmorg-21.1.0"

  raja:
    repo_url: "https://github.com/LLNL/RAJAPerf.git"
    tags:
      - "v2025.12.0"
```

当前实现已经支持新 schema，但实际执行仍默认消费每个 `tags` 列表中的第一个元素。

## 运行工作流

查看计划：

```bash
.venv/bin/snakemake -s workflow/Snakefile -n -j 2 -p
```

执行完整流程：

```bash
.venv/bin/snakemake -s workflow/Snakefile -j 2
```

当前完整 DAG 包含：

1. `checkout_llvm`
2. `build_llvm`
3. `checkout_official`
4. `build_official`
5. `checkout_raja`
6. `build_raja`
7. `run_official`
8. `run_raja`
9. `parse_results`
10. `aggregate_results`
11. `generate_report`

默认目标是最终 HTML 报告：

[`auto/reports/<run_label>/benchmark_report.html`](/home/eidf018/eidf018/s2778911-aspp/msc/auto/reports/20260504_120000/benchmark_report.html)

## 常用命令

打印 DAG：

```bash
.venv/bin/snakemake -s workflow/Snakefile --dag
```

只执行解析和报告前提是上游结果已经存在：

```bash
.venv/bin/snakemake -s workflow/Snakefile auto/reports/20260504_120000/benchmark_report.html
```

## 输出布局

- LLVM 源码：
  `auto/sources/llvm-project/<llvm_tag>/`
- Official 源码：
  `auto/sources/official/<official_tag>/`
- RAJA 源码：
  `auto/sources/raja/<raja_tag>/`
- LLVM install：
  `auto/installs/llvm/<llvm_tag>/`
- Official 结果：
  `auto/results/official-<official_tag>/<llvm_version>/<run_label>/baseline_results.json`
- RAJA 结果：
  `auto/results/raja-<raja_tag>/<llvm_version>/<run_label>/RAJAPerf-kernel-run-data.csv`
- 解析结果：
  `auto/parsed/<run_label>/benchmark_records.csv`
- 聚合结果：
  `auto/parsed/<run_label>/benchmark_records_aggregated.csv`
- 报告：
  `auto/reports/<run_label>/benchmark_report.html`
- 日志：
  `auto/logs/<run_label>/`

## 当前状态

- 旧顺序式 Python workflow 已移除
- 根目录不再保留旧版 `benchmark_pipeline.py`、`parse_results.py`、`generate_report.py`
- 当前仓库只保留 Snakemake 工作流代码，且共享依赖模块已整理到 `workflow/lib/`
