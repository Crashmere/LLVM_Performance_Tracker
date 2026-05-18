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

build:
  ninja_jobs:
    - "-j"
    - "6"

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

当前实现支持两种配置模式：

- 简单矩阵模式：对 `llvm.tags`、`test_suite.*.tags` 以及可选的 `runs.labels` 做笛卡尔展开。
- 显式实验模式：通过 `experiments[]` 明确定义每个组合，并可对单个实验设置 `repeat_count`。

如果 `runs.labels` 未配置，系统会在运行时自动生成时间戳 `run_label`。这也是推荐的默认用法。只有在你需要手动命名某次运行或做一组固定命名的重复实验时，才需要显式写 `runs.labels`。

## 运行工作流

查看计划：

```bash
.venv/bin/snakemake -s workflow/Snakefile -n -j 2 -p
```

执行完整流程：

```bash
.venv/bin/snakemake -s workflow/Snakefile -j 2
```

或者直接使用根目录脚本：

```bash
./run.sh
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

[`auto/reports/<experiment_id>/benchmark_report.html`](/home/eidf018/eidf018/s2778911-aspp/msc/auto/reports/llvm_llvmorg-21.1.0__official_llvmorg-21.1.0__raja_v2025.12.0__run_20260504_120000/benchmark_report.html)

`run_official` 和 `run_raja` 被配置为独占所有可用 cores，因此 Snakemake 调度时不会并行执行 benchmark 运行任务，也不会让其它 CPU 密集型 job 与其并发。
`build.ninja_jobs` 是所有 CMake/Ninja 构建步骤共享的并行度设置，当前推荐值为 `-j 6`。

## 常用命令

打印 DAG：

```bash
.venv/bin/snakemake -s workflow/Snakefile --dag
```

只执行解析和报告前提是上游结果已经存在：

```bash
.venv/bin/snakemake -s workflow/Snakefile auto/reports/<experiment_id>/benchmark_report.html
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
  `auto/results/official-<official_tag>/<llvm_tag>/<run_label>/baseline_results.json`
- RAJA 结果：
  `auto/results/raja-<raja_tag>/<llvm_tag>/<run_label>/RAJAPerf-kernel-run-data.csv`
- 解析结果：
  `auto/parsed/<experiment_id>/benchmark_records.csv`
- 聚合结果：
  `auto/parsed/<experiment_id>/benchmark_records_aggregated.csv`
- 报告：
  `auto/reports/<experiment_id>/benchmark_report.html`
- 日志：
  `auto/logs/<experiment_id>/`

## 当前状态

- 旧顺序式 Python workflow 已移除
- 根目录不再保留旧版 `benchmark_pipeline.py`、`parse_results.py`、`generate_report.py`
- 当前仓库只保留 Snakemake 工作流代码，且共享依赖模块已整理到 `workflow/lib/`

## 开发记录

### 阶段一：配置模型升级与多版本矩阵执行

这一阶段的目标，是把原先“配置里看起来支持多个 tag，但执行时只实际使用 `tags[0]`”的状态，升级为真正可展开的多实验工作流。同时，这一阶段也顺手把运行方式、构建并行配置和 benchmark 独占执行策略一起收敛到了更稳定的默认行为上。

#### 背景与问题

- 旧版 `Snakefile` 在顶层直接读取 `llvm.tags[0]`、`official.tags[0]`、`raja.tags[0]`，所以配置中的 tag 列表只是表面支持。
- 原有路径布局主要围绕单个 `run_label` 设计，无法稳定区分多版本、多组合、多轮次实验。
- `parse_results` 会扫描整个 `auto/results/`，如果后续进入矩阵实验，单靠 `run_label` 过滤不够精确。
- 构建并行参数原先挂在 `llvm.build.ninja_jobs` 下，但实际上会同时影响 LLVM、official 和 RAJA 三类构建，语义不够清楚。
- benchmark 运行任务本身适合独占资源，不适合和其它 benchmark 任务并行。

#### 主要设计决策

- 保留 `run_label` 概念，但默认不要求在配置中手写；如果未配置 `runs.labels`，系统会在运行时自动生成时间戳。
- 在配置层支持两种实验定义方式：
  - 简单矩阵模式：对 `llvm.tags`、`test_suite.*.tags` 和可选的 `runs.labels` 做展开。
  - 显式实验模式：使用 `experiments[]` 精确列出需要的组合。
- 为每个实验生成稳定的 `experiment_id`，让 `parsed/`、`reports/` 和实验级日志目录都按实验唯一隔离。
- 构建缓存按 tag 复用，运行结果按 `run_label` 隔离。
- benchmark 运行 rule 通过 `threads` 独占当前可用 cores，避免并行运行 benchmark。

#### 具体修改

- `workflow/lib/common.py`
  - 新增 `run_label` 归一化逻辑，支持自动时间戳、`runs.labels`、`repeat_count`。
  - 新增简单矩阵展开和显式实验展开逻辑。
  - 新增 `experiment_id` 生成与重复组合校验逻辑。
  - 将配置归一化结果升级为统一的 `experiments` 列表。
  - 将构建并行参数提升到新的全局字段 `build.ninja_jobs`，并在归一化阶段统一读取。
  - 更新路径布局：
    - build 和 result 路径按 `llvm_tag` 组织。
    - parsed、reports 和实验级 logs 按 `experiment_id` 组织。

- `workflow/Snakefile`
  - 重写为 experiment-driven DAG，不再依赖单一顶层 `LLVM_TAG` / `RUN_LABEL` 常量。
  - `rule all` 现在以所有实验的最终报告为目标。
  - checkout/build rule 改为按 tag 维度复用。
  - run/parse/report rule 改为按实验展开。
  - `run_official` 和 `run_raja` 被设置为独占执行，不与其他 benchmark 运行并行。

- `workflow/lib/parse_results.py`
  - 为记录过滤逻辑加入 suite version 过滤能力。
  - 目的不是兼容旧目录，而是保证矩阵实验下只保留当前 experiment 对应的 official / RAJA 版本数据。

- `workflow/scripts/parse_results_cli.py`
  - 新增 `--suite-version suite=value` 参数。
  - 将 suite version 条件传递到 `filter_records()`，使 `parse_results` 在扫描整个 `results/` 树后仍能精确筛选当前 experiment。

- `config.yml`
  - 默认切换为简洁配置：
    - 使用新的 `build.ninja_jobs`
    - 不再默认手写 `runs.labels`
  - 保留注释示例，说明如何显式指定 `runs` 或 `experiments[]`。

- 根目录新增 `run.sh`
  - 默认执行 `snakemake -s workflow/Snakefile -j 2`
  - 支持 `./run.sh dry-run`
  - 支持通过 `./run.sh -- ...` 透传额外 Snakemake 参数

- `README.md`
  - 同步更新配置说明、输出布局和推荐运行方式。
  - 明确说明 `build.ninja_jobs` 是所有构建步骤共享的并行设置。
  - 明确说明 benchmark 运行任务采用独占调度策略。

#### 关于配置模式的结论

- 当前默认 `config.yml` 使用的是简单矩阵模式。
- 只要配置里出现 `experiments:`，工作流就会切换到显式实验模式。
- 两者不会同时并列展开；显式实验模式优先。
- 简单模式字段在显式模式下只作为默认值来源，不再作为矩阵展开源。

#### 关于 `run_label` 和 `repeat_count`

- `run_label` 仍然有必要保留，因为它承担“单次运行标识”和“结果目录隔离”的作用。
- 但现在推荐的主路径是不在配置中手写 `runs.labels`，让系统自动生成时间戳。
- `repeat_count` 在配置归一化阶段生效，它不是在某个 rule 内部循环，而是先把一次实验展开成多个不同 `run_label` 的独立 experiment，例如：
  - `baseline_repeat_01`
  - `baseline_repeat_02`
  - `baseline_repeat_03`
- 不同 repeat 会复用源码和构建缓存，但会生成独立的 benchmark 结果、解析表和报告。

#### 关于资源与调度的结论

- 当前机器资源大致为：
  - `16` CPU cores
  - `31 GiB` memory
  - `51 GiB` free disk
- 当前推荐默认设置：
  - Snakemake：`-j 2`
  - `build.ninja_jobs`：`-j 6`
- benchmark 运行 rule 当前通过高 `threads` 值独占当前 `-j` 所提供的全部 cores，因此在 `-j 2`、`-j 4` 这类配置下，都不会并行执行多个 benchmark 运行任务。

#### 关于当前实现边界的结论

- 这一阶段不再兼容旧结果目录布局，后续默认按新布局重新开始运行。
- 当前系统可以正常接受 tag 名作为版本标识；如果把 tag 字段写成某个可 checkout 的 commit hash，checkout 和路径命名大体上也能工作，但现阶段仍然更推荐使用正式 tag。
- 当前 `build_llvm.py`、`build_official.py`、`build_raja.py` 中的 `run_cmd()` 实现逻辑基本一致，差别主要不在执行器本身，而在各自传给 `build_with_cmake()` 的 CMake 参数和构建目标。

#### 验证与结果

- 已对配置归一化逻辑做过最小验证，确认 simple mode 和 explicit mode 都可以生成正确的 `experiments` 列表。
- 已多次执行 `snakemake -n` / `./run.sh dry-run` 验证 DAG 展开逻辑。
- 已验证矩阵配置下，多个 LLVM / RAJA / repeat 会被展开成多个独立 experiment。
- 已验证 benchmark 运行 rule 在 dry-run 中被调度为独占执行。

#### 讨论结论摘要

- `default_platform` 当前只是预留字段，尚未真正参与平台切换逻辑。
- 简单矩阵模式适合早期批量扫面；显式实验模式更适合后期精确实验设计和论文分析。
- 默认自动时间戳比强制手写 label 更适合当前项目阶段。

#### Commit Message

Enable experiment matrix execution and clean up workflow defaults.
Add experiment normalization, repeat expansion, experiment-scoped outputs, shared build concurrency settings, exclusive benchmark runs, and a simple run wrapper script.

#### Weekly Update

- This week I completed the first workflow upgrade for multi-version experiment support.
- I updated the config normalization layer so the workflow now expands real experiment matrices instead of only using the first tag in each list.
- I added support for repeated runs by expanding `repeat_count` into separate run labels and experiment IDs.
- I updated result parsing so `parse_results` can filter by suite version, which makes matrix runs safer and avoids mixing data from different experiment combinations.
- I moved the shared Ninja parallelism setting into a global build config and added a small `run.sh` wrapper to simplify normal execution and dry runs.
- I also constrained benchmark execution rules so benchmark jobs do not run in parallel and compete for the same machine resources.

### 阶段二：Snakemake 内聚的恢复、元数据与结构整理

这一阶段最初的目标是做“错误处理、状态恢复与运行清单”。但在重新评估后，我没有继续实现一套独立的 manifest 状态机或 retry 调度器。原因是这些能力会和 Snakemake 自身的 DAG、目标文件、日志和状态管理机制重叠，使入口变复杂，也容易产生“Snakemake 认为失败，但外部 manifest 认为成功”这类状态不一致问题。

因此阶段二的设计收敛为：继续让 Snakemake / `run.sh` 作为唯一主入口，只增强可观测性、恢复体验和 provenance。辅助脚本只做只读检查，不调度、不重跑、不修改 workflow 状态。

#### 主要设计决策

- 不实现全局 mutable manifest。
- 不实现独立 retry CLI。
- 不让 helper 脚本绕过 Snakemake 调用多个 workflow stage。
- 恢复操作优先映射为 Snakemake 原生能力：
  - `--keep-going`
  - `--rerun-incomplete`
  - 指定具体 target
  - 必要时通过 pass-through 使用 `--forcerun`
- 每个 experiment 生成一份稳定 metadata，作为 DAG 产物，而不是外部状态数据库。
- 人工诊断工具放入 `tools/`，不和 Snakemake rule 使用的 `workflow/scripts/` 混在一起。

#### 具体修改

- `workflow/Snakefile`
  - 新增 `write_experiment_metadata` rule。
  - `generate_report` 现在依赖：
    - `benchmark_records_aggregated.csv`
    - `auto/metadata/<experiment_id>/experiment.json`
  - 这样每个最终报告都能追溯到对应实验配置、路径和环境摘要。

- `workflow/scripts/write_experiment_metadata.py`
  - 新增 experiment metadata 生成脚本。
  - metadata 中记录：
    - normalized experiment
    - experiment mode
    - config snapshot
    - expected outputs
    - log paths
    - hostname、kernel、Python version、Snakemake version 等轻量环境信息
  - 为了避免自动时间戳 run label 在脚本内二次归一化时变化，metadata 脚本直接接收 `Snakefile` 传入的 normalized experiment JSON。

- `tools/inspect_workflow_outputs.py`
  - 新增只读检查工具。
  - 扫描 `auto/metadata/*/experiment.json`，检查 raw results、parsed CSV、aggregated CSV、report HTML 是否存在。
  - 支持 `table`、`csv`、`json` 输出。
  - 当前只以 metadata 为入口，不再扫描没有 metadata 的旧 report。
  - 该工具不修改任何文件，也不触发 Snakemake。

- `docs/recovery.md`
  - 新增恢复说明文档。
  - 记录常用恢复方式：
    - `./run.sh resume`
    - `./run.sh strict`
    - `./run.sh inspect`
    - `./run.sh -- <snakemake args...>`
  - 明确 helper scripts 不能成为第二套调度系统。

- `run.sh`
  - 默认执行 Snakemake 时加入 `--keep-going`，使批量实验中互不依赖的 job 可以继续运行。
  - 新增 `strict` 模式，用于失败时立即停止：
    - `./run.sh strict`
    - `./run.sh strict resume`
  - 新增 `inspect` 子命令，调用只读检查工具：
    - `./run.sh inspect`
    - `./run.sh inspect --format json`
  - 保留 `./run.sh -- <args...>` 作为 Snakemake pass-through。
  - 曾短暂考虑过 `report`、`aggregate`、`force` 子命令，但最后移除，因为这些快捷入口不够通用，直接使用 Snakemake target 更清楚。

- `workflow/lib/command_runner.py`
  - 新增共享命令执行器。
  - 把 `checkout_repo.py`、`build_llvm.py`、`build_official.py`、`build_raja.py`、`run_official.py`、`run_raja.py` 中重复的 `run_cmd()` 和 `log_message()` 收敛为 `CommandRunner`。
  - 各脚本现在通过：
    - `runner.run`
    - `runner.log`
    传入 `prepare_git_repo()` 或 `build_with_cmake()`。

- `workflow/lib/layout.py`
  - 从 `common.py` 中拆出路径布局函数：
    - `get_layout_paths()`
    - `get_experiment_layout_paths()`
  - 目的在于让路径约定成为独立模块，而不是继续堆在 `common.py` 中。

- `workflow/lib/cmake_build.py`
  - 从 `common.py` 中拆出通用 CMake/Ninja 构建流程：
    - `normalize_ninja_jobs()`
    - `clear_directory()`
    - `build_with_cmake()`
  - 保留 `build_with_cmake()` 的执行器注入设计，不把日志逻辑硬写进去。

- `config.yml`
  - 将配置整理为真正的三段式结构：
    - 共享配置：`project`、`build`、`repositories`、`compilers`、`suite_defaults`
    - simple mode：`runs`、`llvm.tags`、`test_suite.*.tags`
    - explicit mode：注释掉的 `experiments`
  - `build.ninja_jobs` 从 `["-j", "6"]` 改为数字 `6`。
  - `suite_defaults` 改为按 suite 分别配置：
    - `suite_defaults.official.cxx_standard`
    - `suite_defaults.raja.cxx_standard`
  - explicit mode 现在可以只依赖共享配置和 `experiments`，不再需要保留 simple mode 的 tags 块。

- `workflow/lib/common.py`
  - 更新配置归一化逻辑，读取新的共享配置字段：
    - `repositories.llvm`
    - `repositories.official`
    - `repositories.raja`
    - `compilers.host.c`
    - `compilers.host.cxx`
    - `suite_defaults.<suite>.cxx_standard`
  - 后续清理中移除了旧格式兼容，配置解析现在只接受当前推荐结构。

- `workflow/scripts/aggregate_results_cli.py` 和 `workflow/scripts/generate_report_cli.py`
  - 增加输入文件缺失时的明确错误信息，减少调试时看到底层 pandas/IO 报错的概率。

- `work_plan.md`
  - 重写阶段二规划，明确“不做第二套 scheduler”的边界。
  - 记录后续模块边界整理方向：
    - parser adapter 拆分
    - reporting / analysis 解耦
    - suite-specific CMake 参数未来拆出
    - `common.py` 未来继续收敛

#### 关于当前恢复模型的结论

- 当前系统没有引入独立恢复状态数据库。
- Snakemake 仍然是唯一调度器。
- `auto/metadata/<experiment_id>/experiment.json` 是 provenance 产物，不是 mutable run state。
- `inspect` 只告诉用户当前产物缺什么，不负责决定或执行重跑。
- 如果用户要重建某个 report 或强制某个 rule，仍然应该通过 Snakemake target 或 pass-through 参数表达。

#### 关于配置结构的结论

- simple mode 现在只保留真正和矩阵展开有关的字段。
- explicit mode 可以通过取消注释 `experiments` 切换。
- repo URL、host compiler、suite 默认 C++ 标准都属于共享配置，不再混入 simple mode。
- `name` 只存在于 explicit experiment 中，作为人工可读标签，不参与唯一性或路径生成。
- `run_label` 仍然是结果目录隔离和重复实验标识的核心字段。

#### 关于代码结构的结论

- `command_runner.py`、`layout.py`、`cmake_build.py` 已从原先的重复脚本和 `common.py` 中拆出。
- `common.py` 当前仍保留配置归一化、git 辅助和 suite-specific CMake 参数生成。
- 后续阶段如果继续扩展 parser、reporting、build profile 或平台支持，应优先拆分：
  - `workflow/lib/parsers/`
  - `workflow/lib/result_schema.py`
  - `workflow/lib/analysis.py`
  - `workflow/lib/build_configs.py`

#### 验证与结果

- 已执行 `py_compile` 检查受影响 Python 模块。
- 已多次执行 `./run.sh dry-run` 验证 DAG 展开。
- 已验证当前 simple mode 配置可以正常归一化。
- 已用模拟配置验证 explicit mode 在不保留 simple tags 块时仍可归一化。
- 已验证 `suite_defaults.official.cxx_standard` 和 `suite_defaults.raja.cxx_standard` 可以分别生效。
- 已移除旧的 `suite_defaults.cxx_standard` 全局写法 fallback。
- 已验证 `run.sh inspect` 能正常执行只读检查。

#### Commit Message

Add Snakemake-native recovery metadata and simplify workflow support code.
Introduce experiment metadata outputs, a read-only output inspection tool, recovery documentation, shared command execution, clearer library boundaries, and a cleaner shared/simple/explicit config structure.

#### Weekly Update

- This week I refined the recovery design so the workflow continues to rely on Snakemake rather than a separate retry or manifest scheduler.
- I added experiment metadata generation as a normal DAG output, so each report can be traced back to its normalized experiment, expected outputs, logs, config snapshot, and environment summary.
- I added a read-only inspection tool and connected it through `run.sh inspect`, while keeping all actual reruns and recovery actions expressed through Snakemake targets or options.
- I simplified repeated command logging code by introducing a shared `CommandRunner`, then updated the checkout, build, and benchmark run scripts to use it.
- I split path layout and generic CMake/Ninja execution helpers out of `common.py`, which makes the library structure easier to extend in later stages.
- I also reorganized `config.yml` into shared settings plus simple and explicit mode sections, including numeric Ninja jobs and per-suite C++ standard defaults.

### 阶段三：构建缓存、磁盘可观测性与失败诊断增强

这一阶段的目标，是让已有构建产物更好地复用，避免每次执行 build rule 都清空 CMake/Ninja build 目录。同时补充只读磁盘占用检查工具，并改进阶段二的 inspect 诊断能力，让失败时更容易判断问题发生在 shared checkout/build 阶段，还是 run/parse/report 阶段。

阶段三继续保持 Snakemake-first 的设计：不引入新的调度器，不做自动清理 rule，也不新增额外的 build slot 配置。整体并发仍然由 Snakemake `-j` 控制，单个 Ninja build 的内部并行度由 `build.ninja_jobs` 控制。

#### 主要设计决策

- 默认保留 build 目录，不再在每次 build 前自动清空。
- clean build 必须由配置显式开启，避免无意触发全量重编。
- CMake configure 和 clean build 分开控制：
  - `clean_build` 决定是否删除已有 build 目录内容。
  - `reconfigure` 决定是否重新运行 CMake configure。
- 不使用额外的 `build_slots` 配置；构建并发保持由 Snakemake `-j` 控制。
- 磁盘占用工具只读，不删除文件、不修改 Snakemake metadata。
- shared checkout/build 日志可以被多个 experiment 复用，因此只作为 shared log path 记录，不视为 experiment 私有日志快照。

#### 具体修改

- `workflow/lib/cmake_build.py`
  - `build_with_cmake()` 默认不再清空 build 目录。
  - 新增 `clean_build` 参数，只有为 `true` 时才调用 `clear_directory()`。
  - 新增 `reconfigure` 参数：
    - `true`：每次 build rule 执行时重新运行 CMake configure。
    - `false`：如果已有 `CMakeCache.txt`，跳过 configure，直接运行 Ninja。
  - 保留 CMake configure 与 Ninja build 的通用流程，继续不耦合 suite-specific 参数。

- `workflow/lib/build_configs.py`
  - 新增构建参数模块。
  - 从 `common.py` 中迁出：
    - `get_llvm_cmake_args()`
    - `get_official_cmake_args()`
    - `get_raja_cmake_args()`
    - `find_omp_library()`
    - `get_actual_clang_major_version()`
  - RAJA OpenMP 探测和 RAJA CMake 参数现在放在同一模块中，避免 `common.py` 继续承载 suite-specific 构建细节。

- `workflow/scripts/build_llvm.py`
  - 改为从 `workflow.lib.build_configs` 导入 LLVM CMake 参数生成函数。
  - 从 Snakemake params 接收 `clean_build` 和 `reconfigure`，并传给 `build_with_cmake()`。

- `workflow/scripts/build_official.py`
  - 改为从 `workflow.lib.build_configs` 导入 Official CMake 参数生成函数。
  - 接入 `clean_build` 和 `reconfigure`。

- `workflow/scripts/build_raja.py`
  - 改为从 `workflow.lib.build_configs` 导入 RAJA CMake 参数生成函数。
  - 接入 `clean_build` 和 `reconfigure`。

- `workflow/Snakefile`
  - build rule 的 params 中新增：
    - `clean_build=WORKFLOW_CONFIG["build"]["clean_build"]`
    - `reconfigure=WORKFLOW_CONFIG["build"]["reconfigure"]`
  - 没有引入 `resources.build_slots`；构建任务并发仍由 Snakemake `-j` 控制。

- `config.yml`
  - `build` 配置扩展为：
    - `ninja_jobs: 6`
    - `clean_build: false`
    - `reconfigure: true`
  - `clean_build: false` 是默认推荐设置。
  - `reconfigure: true` 让 CMake 参数、编译器路径、安装路径等变化能被重新检查，同时仍保留 Ninja 增量构建缓存。

- `tools/report_disk_usage.py`
  - 新增只读磁盘占用检查工具。
  - 扫描 workflow base directory 下的：
    - `sources/`
    - `builds/`
    - `installs/`
    - `results/`
    - `parsed/`
    - `reports/`
    - `metadata/`
    - `logs/`
  - 支持 `--top` 控制每类目录展示多少个最大子项。

- `run.sh`
  - 新增 `disk` 子命令：
    - `./run.sh disk`
    - `./run.sh disk --top 5`
  - 该命令调用 `tools/report_disk_usage.py`。
  - `run.sh` 没有新增自动清理入口。

- `docs/storage.md`
  - 新增英文用户说明文档。
  - 只说明如何使用 build cache 配置和 `./run.sh disk`。
  - 不写开发记录，不面向开发者描述阶段历史。

- `workflow/scripts/write_experiment_metadata.py`
  - metadata 的 `expected_outputs` 中新增 shared dependency stamp：
    - checkout stamps
    - build stamps
  - 新增 `shared_logs` 字段，记录 checkout/build 这些共享日志路径。
  - `shared_logs` 明确表示“共享目标当前日志路径”，不表示某个 experiment 独占的日志快照。

- `tools/inspect_workflow_outputs.py`
  - 新增 `shared_deps` 列。
  - inspect 现在会先检查 shared checkout/build stamp，再检查 raw results、parsed、aggregated、report。
  - 对旧 metadata 兼容：如果 metadata 中没有新增的 stamp 字段，会从已有 `paths` 字段推断 stamp 路径。
  - 失败诊断更具体。例如 Official build 失败时，`next_step` 会显示：
    - `rebuild shared dependency; missing official build`
    而不是只显示：
    - `run benchmark stage; missing official raw result`

- `work_plan.md`
  - 阶段三已标记完成。
  - 后续近期优先级推进到阶段四。
  - 阶段三规划中移除了 `build_slots` 设计，明确继续使用 Snakemake `-j`。

#### 关于 clean_build 与 reconfigure 的结论

- `clean_build` 控制是否清空 build 目录。
- `reconfigure` 控制是否重新运行 CMake configure。
- 常规运行推荐：
  - `clean_build: false`
  - `reconfigure: true`
- 如果 build 目录损坏或需要彻底重建，可以临时设置：
  - `clean_build: true`
- 即使 `reconfigure: false`，只要 `CMakeCache.txt` 不存在，系统仍会自动运行 CMake configure。

#### 关于 shared logs 的结论

- `_shared` 日志路径由 `Snakefile` 中的 rule log 路径决定，是手写的目录约定，不是运行时自动推断。
- checkout/build 产物本身会被多个 experiment 共享，因此它们的日志也放在 `logs/_shared/`。
- run 日志包含 `run_label`，不是 shared。
- parse、aggregate、report、metadata 按 `experiment_id` 隔离，也不是 shared。
- shared log 后续重跑时可能被覆盖，因此不能当作某一次 experiment 的不可变日志快照。
- 真正需要追溯某次完整 Snakemake 执行时，应结合 `.snakemake/log/<timestamp>.snakemake.log`。

#### 验证与结果

- 已执行 `py_compile` 检查受影响 Python 模块。
- 已执行 `./run.sh dry-run` 验证 DAG 展开。
- 已执行 `./run.sh disk --top 1` 验证磁盘报告工具。
- 已执行 `./run.sh inspect` 验证 shared dependency 诊断。
- 使用故意失败的 Official test-suite commit 验证：
  - metadata 能先生成。
  - RAJA 独立分支可以继续运行。
  - Snakemake 能定位失败 rule 和 rule log。
  - inspect 能指出 `official build` 缺失，而不是只报告 raw result 缺失。

#### Commit Message

Improve build caching and workflow diagnostics.
Keep CMake build directories by default, add explicit clean/reconfigure controls, move suite-specific CMake arguments into a build config module, add a read-only disk usage tool, and improve inspect output for shared checkout/build dependencies.

#### Weekly Update

- This week I improved the build cache behavior so CMake/Ninja build directories are reused by default instead of being cleared on every build rule execution.
- I added explicit `clean_build` and `reconfigure` settings, keeping normal runs incremental while still allowing clean rebuilds when needed.
- I moved LLVM, Official test-suite, and RAJAPerf CMake argument generation into a dedicated build configuration module, reducing suite-specific logic in `common.py`.
- I added a read-only disk usage command through `./run.sh disk`, which helps identify where workflow storage is being used without modifying Snakemake state.
- I refined experiment inspection so shared checkout/build dependencies are checked before raw results, making failed build stages easier to identify.
- I also documented the shared log model: checkout/build logs are shared by reusable targets, while run and experiment-level logs remain run- or experiment-scoped.
