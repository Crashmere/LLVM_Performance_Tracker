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
pip install pyyaml lit pandas plotly pyarrow jinja2 snakemake
```

## 配置

编辑 [`config.yml`](/home/eidf018/eidf018/s2778911-aspp/msc/config.yml)。

关键字段：

```yaml
project:
  base_dir: "~/msc/auto"

build:
  ninja_jobs: 6

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

- 简单矩阵模式：对 `llvm.tags` 和 `test_suite.*.tags` 做笛卡尔展开。
- 显式实验模式：通过 `experiments[]` 明确定义每个组合。

全局 `label` 用来标识本次运行，并参与结果目录和 `experiment_id` 生成。如果未配置，系统会在运行时自动生成时间戳；如果需要手动命名一次实验，可以在配置公共部分写 `label: "baseline"`。

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

[`auto/reports/<experiment_id>/benchmark_report.html`](/home/eidf018/eidf018/s2778911-aspp/msc/auto/reports/llvm_llvmorg-21.1.0__official_llvmorg-21.1.0__raja_v2025.12.0__label_20260504_120000/benchmark_report.html)

`run_official` 和 `run_raja` 被配置为独占所有可用 cores，因此 Snakemake 调度时不会并行执行 benchmark 运行任务，也不会让其它 CPU 密集型 job 与其并发。
`build.ninja_jobs` 是所有 CMake/Ninja 构建步骤共享的并行度设置，当前推荐值为 `6`，脚本会负责转换成 Ninja 的 `-j 6`。

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
  `auto/results/official-<official_tag>/<llvm_tag>/<label>/baseline_results.json`
- RAJA 结果：
  `auto/results/raja-<raja_tag>/<llvm_tag>/<label>/RAJAPerf*.csv`
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
- 原有路径布局主要围绕单个运行标识设计，无法稳定区分多版本、多组合实验。
- `parse_results` 会扫描整个 `auto/results/`，如果后续进入矩阵实验，必须结合 suite version、compiler version 和 `label` 精确过滤。
- 构建并行参数原先挂在 `llvm.build.ninja_jobs` 下，但实际上会同时影响 LLVM、official 和 RAJA 三类构建，语义不够清楚。
- benchmark 运行任务本身适合独占资源，不适合和其它 benchmark 任务并行。

#### 主要设计决策

- 后续已将运行标识统一收敛为全局 `label`，默认不要求在配置中手写；如果未配置，系统会在运行时自动生成时间戳。
- 在配置层支持两种实验定义方式：
  - 简单矩阵模式：对 `llvm.tags` 和 `test_suite.*.tags` 做展开。
  - 显式实验模式：使用 `experiments[]` 精确列出需要的组合。
- 为每个实验生成稳定的 `experiment_id`，让 `parsed/`、`reports/` 和实验级日志目录都按实验唯一隔离。
- 构建缓存按 tag 复用，运行结果按 `label` 隔离。
- benchmark 运行 rule 通过 `threads` 独占当前可用 cores，避免并行运行 benchmark。

#### 具体修改

- `workflow/lib/common.py`
  - 新增运行标识归一化逻辑，当前已收敛为单一全局 `label`，支持未配置时自动时间戳。
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
    - 不再默认手写 `label`
  - 保留注释示例，说明如何显式指定 `label` 或 `experiments[]`。

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

#### 关于 `label`

- 当前系统只保留一个全局 `label`，它承担“本次运行标识”和“结果目录隔离”的作用。
- 推荐默认不手写 `label`，让系统自动生成时间戳；正式实验如需固定命名，可以在配置公共部分写 `label: "baseline"`。
- 旧的 `runs.labels`、`run_label`、`run_labels`、`repeat_count` 已移除，不再做向前兼容。
- 如果未来要重新支持重复实验，应使用独立的 repeat/sample 模型，而不是重新引入多个 label 概念。

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
Add experiment normalization, experiment-scoped outputs, shared build concurrency settings, exclusive benchmark runs, and a simple run wrapper script.

#### Weekly Update

- This week I completed the first workflow upgrade for multi-version experiment support.
- I updated the config normalization layer so the workflow now expands real experiment matrices instead of only using the first tag in each list.
- I added experiment normalization so matrix combinations are expanded into stable experiment IDs.
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
  - 为了避免自动时间戳 `label` 在脚本内二次归一化时变化，metadata 脚本直接接收 `Snakefile` 传入的 normalized experiment JSON。

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
    - simple mode：`label`、`llvm.tags`、`test_suite.*.tags`
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
- `label` 是结果目录隔离和实验标识的唯一标签字段；旧的 `run_label`、`runs.labels` 和 `repeat_count` 已移除。

#### 关于代码结构的结论

- `command_runner.py`、`layout.py`、`cmake_build.py` 已从原先的重复脚本和 `common.py` 中拆出。
- `common.py` 当前仍保留配置归一化、git 辅助和 suite-specific CMake 参数生成。
- 后续阶段如果继续扩展 parser、reporting 或平台支持，应优先拆分：
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
- run 日志包含 `label`，不是 shared。
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

### 阶段四：数据解析层重构与 RAJA 多格式适配

这一阶段的直接背景，是在阶段三测试失败场景时发现 RAJAPerf 不同版本的原始输出并不完全一致。较新的 RAJA 结果会生成 `RAJAPerf-kernel-run-data.csv`，这是当前系统原先硬编码依赖的长表格式；但 `v2025.03.0` 能正常运行到 `DONE!!!`，实际只生成 `RAJAPerf-timing-Average.csv`、`RAJAPerf-speedup-Average.csv`、`RAJAPerf-fom.csv`、`RAJAPerf-kernels.csv` 等文件，没有 `RAJAPerf-kernel-run-data.csv`。

旧设计的问题在于：`run_raja` 把缺少某个固定 CSV 文件直接判定为 benchmark run 失败。实际上这不是 RAJAPerf 运行失败，而是解析层不支持该版本的输出 schema。阶段四因此把边界重新划清：run 阶段负责确认 benchmark 程序运行并产出原始文件；parse 阶段负责发现、识别和解析具体格式。

#### 主要设计决策

- 不再把 `RAJAPerf-kernel-run-data.csv` 作为 RAJA run 成功的唯一标志。
- RAJA run rule 的下游依赖改为 `.run_complete`，具体 CSV 文件由 parser adapter 在结果目录中发现。
- Official 和 RAJA 的解析逻辑拆成 adapter，`parse_results.py` 只保留目录扫描和表格输出两个当前入口。
- RAJA adapter 通过文件名和 header 内容识别格式，不依赖 tag 名称判断版本。
- 当多个 RAJA 格式同时存在时，优先使用 `RAJAPerf-kernel-run-data.csv`，因为它包含 checksum、runtime、bandwidth、GFLOP/s。
- 当只有 `RAJAPerf-timing-Average.csv` 时，降级解析 runtime；checksum、bandwidth、GFLOP/s 允许为空。
- 不保留面向旧代码调用方式的兼容包装函数；当前代码只支持阶段四后的新结构。

#### 具体修改

- `workflow/lib/result_schema.py`
  - 新增统一结果数据模型：
    - `BenchmarkMetrics`
    - `BenchmarkRecord`
  - 新增安全类型转换：
    - `safe_float()`
    - `safe_int()`
  - 新增 `records_to_dataframe()`，统一把解析结果展开成表格列。
  - 表格中新增 provenance / parser 相关列：
    - `compiler_tag`
    - `compiler_commit`
    - `platform`
    - `hostname`
    - `source_file`
    - `parser_adapter`
    - `status_detail`

- `workflow/lib/parsers/base.py`
  - 新增 parser adapter 基类 `ResultParser`。
  - 新增 `ParseError`，用于报告不支持的结果 schema 或无法解析的结果目录。

- `workflow/lib/parsers/official.py`
  - 新增 `OfficialJsonAdapter`。
  - Official test-suite 的 `baseline_results.json` 解析逻辑从 `parse_results.py` 中迁出。
  - 每条 Official 记录会写入 `source_file` 和 `parser_adapter=official_json`。

- `workflow/lib/parsers/raja.py`
  - 新增 `KernelRunDataAdapter`。
    - 识别并解析 `RAJAPerf-kernel-run-data.csv`。
    - 保留原有 runtime、bandwidth、GFLOP/s、checksum 信息。
    - 输出 `parser_adapter=raja_kernel_run_data`。
  - 新增 `TimingAverageAdapter`。
    - 识别并解析 `RAJAPerf-timing-Average.csv`。
    - 将矩阵格式拉平成统一记录：
      - `Kernel + Variant + Tuning -> test_name`
      - 单元格数值 -> `exec_time`
    - 跳过 `Not run`、空值和非数值单元格。
    - 将 `status` 设为 `COMPLETED`，并在 `status_detail` 中说明 checksum 不可用。
    - 输出 `parser_adapter=raja_timing_average`。
  - 新增 `parse_raja_result_directory()`。
    - 在 RAJA run 目录中自动选择可支持格式。
    - 如果没有受支持的格式，抛出包含目录、已发现文件和支持文件列表的清晰错误。

- `workflow/lib/parse_results.py`
  - 从“解析实现集合”收敛为解析调度层。
  - 保留当前真正使用的两个入口：
    - `parse_results_directory()`
    - `write_records_table()`
  - 删除阶段四过程中临时保留的旧兼容包装函数：
    - `parse_raja_csv()`
    - `extract_official_records()`
    - `extract_raja_records()`
    - `filter_records()`
  - 删除旧的 `__all__` 重导出。
  - 目录扫描时会按 suite、suite version、compiler version、label 预先过滤，避免不相关历史结果中的坏格式影响当前 experiment。

- `workflow/scripts/parse_results_cli.py`
  - CLI 继续作为 Snakemake 的解析入口。
  - 将 `--suite-version`、`--compiler-version`、`--label` 等过滤条件直接传给 `parse_results_directory()`。
  - 不再先全量扫描再二次过滤。

- `workflow/scripts/run_raja.py`
  - 不再读取 `snakemake.output.results` 中的固定 CSV 路径。
  - RAJAPerf 程序返回成功后，扫描结果目录中的 `RAJAPerf*` 文件。
  - 只要存在 RAJAPerf 原始输出文件，就写 `.run_complete`。
  - `.run_complete` 中记录本次发现的 `result_file=...` 列表。

- `workflow/Snakefile`
  - `run_raja` 的 output 删除固定的 `RAJAPerf-kernel-run-data.csv`。
  - `run_raja` 现在只声明 `.run_complete`。
  - `parse_results` 不再把固定 RAJA CSV 作为 input，只依赖 RAJA `.run_complete`，再由 parser adapter 发现具体文件。

- `workflow/scripts/write_experiment_metadata.py`
  - metadata 中 RAJA expected outputs 从单一 `raja_results` 扩展为：
    - `raja_result_dir`
    - `raja_run_stamp`
    - `raja_kernel_run_data`
    - `raja_timing_average`
  - 这样 metadata 能表达当前支持的两种 RAJA 原始格式。

- `tools/inspect_workflow_outputs.py`
  - RAJA raw result 是否存在的判断改为优先看 `raja_run_stamp`。
  - 对旧 metadata 中的 `raja_results` 保留读取能力，仅用于已有记录的检查。

#### 关于 RAJA 输出格式的结论

- `RAJAPerf-kernel-run-data.csv` 是当前信息最完整、最适合分析的 RAJA 格式。
- `RAJAPerf-timing-Average.csv` 可以作为降级格式支持 runtime 分析。
- `timing-Average` 不应伪造 checksum、bandwidth 或 GFLOP/s；这些字段保持为空更诚实。
- RAJA run 成功不等于某个特定 CSV 文件存在；run 成功和 parse schema 支持必须分开判断。
- 后续如果 RAJA 再出现新格式，应新增 adapter，而不是修改 `Snakefile` 或 `run_raja.py` 中的硬编码路径。

#### 关于解析层结构的结论

- `parse_results.py` 当前只负责：
  - 扫描 `auto/results` 目录。
  - 根据 suite/version/compiler/run 过滤目标目录。
  - 调用对应 adapter。
  - 写出统一表格。
- 具体文件格式细节属于 `workflow/lib/parsers/`。
- 统一数据模型属于 `workflow/lib/result_schema.py`。
- 这种结构比原先所有解析逻辑堆在 `parse_results.py` 中更适合后续加入新 suite、新格式或更严格 schema 检查。

#### 验证与结果

- 已执行 `py_compile` 检查受影响 Python 模块。
- 已验证较新 RAJA 格式可以解析：
  - `RAJAPerf-kernel-run-data.csv`
  - 输出 `parser_adapter=raja_kernel_run_data`
- 已验证 `v2025.03.0` RAJA timing 格式可以解析：
  - `RAJAPerf-timing-Average.csv`
  - 输出 `parser_adapter=raja_timing_average`
- 已验证旧格式解析结果可以继续 aggregate 并生成 report。
- 已执行 `./run.sh dry-run` 验证 Snakemake DAG 展开。
- 已执行 `git diff --check` 检查格式。
- 在删除旧兼容接口后再次验证：
  - 新 RAJA 格式解析成功。
  - 旧 RAJA timing 格式解析成功。

#### Commit Message

Refactor result parsing and support multiple RAJAPerf output formats.
Introduce parser adapters and a shared result schema, move Official and RAJA parsing out of the dispatcher, decouple RAJA run completion from a fixed CSV filename, and support both RAJAPerf kernel-run-data and timing-average outputs.

#### Weekly Update

- This week I refactored the result parsing layer so format-specific logic lives in parser adapters rather than in the main parsing dispatcher.
- I added a shared benchmark record schema, which keeps parsed Official and RAJA results in a consistent table while preserving parser provenance.
- I changed RAJA run handling so benchmark execution success no longer depends on one hard-coded CSV filename.
- I added RAJA support for both the newer `RAJAPerf-kernel-run-data.csv` format and the older matrix-style `RAJAPerf-timing-Average.csv` format.
- I verified both real RAJA output formats from existing workflow results.
- I also removed temporary backward-compatible parsing wrappers, keeping the codebase aligned with the current adapter-based design.

### 阶段五 A：测试子集参数透传与标签配置收敛

这一阶段的目标，是先用最小、直接、稳定的方式支持测试子集选择，而不是马上设计一套复杂的结构化 benchmark selection DSL。当前系统已经可以把用户在配置中写的 Official lit 参数和 RAJAPerf 参数直接传给对应 run 脚本，从而支持 smoke run、局部 kernel run 或其它 suite 原生命令行能力。

本阶段还顺手清理了一个配置语义问题：系统里原先同时出现过 `profile`、`name`、`run_label`、`runs.labels`、`repeat_count` 等多个类似“标签/运行标识”的概念。它们会让结果目录隔离、metadata provenance 和重复实验设计混在一起。因此阶段五 A 将当前系统收敛为唯一的全局 `label` 配置；如果用户不配置，系统自动使用时间戳。

阶段五 A 后续测试中还发现一个报告可用性问题：Plotly HTML 默认引用外部 CDN，在无外网环境或 IDE preview 中会出现空白页面。由于 report 是需要归档和离线查看的 workflow 产物，本阶段将报告生成改为内嵌 Plotly JS 的自包含 HTML。

#### 主要设计决策

- `test_selection` 第一版只做参数透传，不做复杂解释。
- Official 使用 `test_selection.official.lit_args`，这些参数插入到 `lit -v -o <result> ... <build_dir>` 中。
- RAJA 使用 `test_selection.raja.extra_args`，这些参数追加到 `raja-perf.exe` 后面。
- selection 参数必须写成 YAML list，不做字符串拆分，避免 shell quoting 歧义。
- run rule 的输出路径不自动根据 selection 参数变化；是否复用同一个 `label` 由用户负责。
- 正式实验切换 full/subset/smoke 参数时，建议显式设置不同 `label`，避免覆盖或混淆结果。
- 全系统只保留一个标签字段 `label`，不再支持多个 label 或旧的 `run_label` 写法。
- 重复实验暂不在当前配置模型里实现；未来如果需要，应设计独立的 repeat/sample 机制，而不是重新引入多个标签字段。
- 报告 HTML 应默认自包含，不依赖外部 CDN；文件体积变大可以接受，离线可读性更重要。

#### 具体修改

- `config.yml`
  - 新增公共配置示例：
    - `# label: "baseline"`
  - 新增当前启用的 full selection 配置：
    - `test_selection.official.lit_args: []`
    - `test_selection.raja.extra_args: []`
  - 新增注释掉的 subset/smoke 示例，方便通过切换注释快速测试。
  - 移除旧的 `runs` 配置块，不再保留 `runs.labels` 或 `repeat_count`。
  - explicit mode 示例中不再写单独的 `name`、`run_label` 或重复次数。

- `workflow/lib/common.py`
  - 新增 `normalize_test_selection()`，统一校验并归一化 selection 配置。
  - 新增 `as_string_list()`，供 run 脚本读取 Snakemake params 时复用。
  - 新增单一 `label` 归一化逻辑：
    - 配置存在时使用配置值。
    - 配置缺失时生成 `YYYYMMDD_HHMMSS` 时间戳。
    - 如果写成 list，则直接报错，因为当前只允许一个全局 label。
  - 删除旧的 `runs.labels`、`run_label`、`run_labels`、`repeat_count` 展开逻辑。
  - simple mode 和 explicit mode 都使用同一个全局 `label`。
  - `experiment_id` 中的运行标识段从 `run_<...>` 改为 `label_<...>`。

- `workflow/Snakefile`
  - `rule run_official` 新增 `lit_args` params。
  - `rule run_raja` 新增 `extra_args` params。
  - run 结果路径和 run 日志路径统一使用 `{label}` wildcard。
  - `parse_results` 调用从 `--run-label` 改为 `--label`。

- `workflow/scripts/run_official.py`
  - 从 `workflow.lib.common` 导入 `as_string_list()`。
  - 将 `lit_args` 插入 lit 命令。
  - `.run_complete` 中记录本次使用的 `lit_args`。

- `workflow/scripts/run_raja.py`
  - 从 `workflow.lib.common` 导入 `as_string_list()`。
  - 将 `extra_args` 追加到 `raja-perf.exe` 命令。
  - `.run_complete` 中记录本次使用的 `extra_args`。

- `workflow/scripts/write_experiment_metadata.py`
  - metadata 中写入 normalized `test_selection`。
  - run 日志路径使用 `experiment["label"]`。

- `workflow/scripts/parse_results_cli.py`
  - CLI 参数从 `--run-label` 改为 `--label`。

- `workflow/lib/parse_results.py`、`workflow/lib/result_schema.py`、`workflow/lib/parsers/`
  - 解析过滤参数和输出 schema 从 `run_label` 统一改为 `label`。
  - 输出表格列名现在是 `label`，不再生成 `run_label` 列。

- `workflow/lib/layout.py`
  - 结果目录布局使用 `label`：
    - `auto/results/official-<official_tag>/<llvm_tag>/<label>/`
    - `auto/results/raja-<raja_tag>/<llvm_tag>/<label>/`

- `tools/inspect_workflow_outputs.py`
  - 汇总表字段从 `run_label` 改为 `label`。
  - RAJA raw result 判断收敛为检查 `.run_complete`，与阶段四后的 RAJA 多格式解析边界一致。

- `workflow/lib/reporting.py`
  - `generate_pure_plotly_report()` 从 `include_plotlyjs="cdn"` 改为 `include_plotlyjs=True`。
  - 新生成的 report 会内嵌 Plotly JS，不再需要浏览器访问 `cdn.plot.ly`。
  - 代价是 HTML 文件明显变大；一次测试中自包含 report 约为 `4.8 MB`。

- `work_plan.md`
  - 更新阶段五 A 的当前设计。
  - 移除对旧标签/重复运行配置的当前能力描述。
  - 将重复实验和统计显著性保留为后续需要重新设计的功能。

#### 关于 `test_selection` 的结论

- 现阶段最稳妥的做法是保留 suite 原生命令行参数入口。
- `lit_args` 和 `extra_args` 足以支持第一批 smoke/subset 实验。
- 不应该在 run 脚本里硬编码 suite-specific 的复杂筛选规则。
- 如果后续常用筛选模式稳定下来，再进入阶段五 B，把它们封装成结构化配置和 `workflow/lib/test_selection.py`。

#### 关于 `label` 的结论

- 当前系统只有一个全局 `label`。
- `label` 同时用于结果目录隔离、run 日志路径和 `experiment_id` 生成。
- 不配置 `label` 时，系统自动生成时间戳，这是默认推荐路径。
- 配置 `label` 时，simple mode 和 explicit mode 中所有 experiment 共用这个 label。
- 旧的 `run_label`、`runs.labels`、`run_labels`、`repeat_count`、`profile`、`name` 相关标签逻辑已从当前代码路径移除。

#### 关于报告生成的结论

- report 是最终研究产物，应该能在离线环境中直接打开。
- 使用外部 Plotly CDN 会让服务器环境、IDE preview 或无外网浏览器出现白屏。
- 当前默认生成自包含 HTML，避免外部 JS 依赖。
- 如果只想重跑某次实验的报告，可以强制执行 `generate_report` rule，例如：

```bash
./run.sh -- --forcerun generate_report \
  auto/reports/llvm_llvmorg-21.1.0__official_llvmorg-21.1.0__raja_v2025.12.0__label_20260527_022025/benchmark_report.html
```

#### 验证与结果

- 已执行 `py_compile` 检查受影响 Python 模块。
- 已执行 `./run.sh dry-run` 验证 Snakemake DAG 能正确展开。
- 已验证配置归一化会生成单一全局 `label`。
- 已验证 explicit mode 下多个 experiment 会共享同一个全局 `label`。
- 已验证 metadata 生成脚本会写入 `experiment.label` 和 normalized `test_selection`。
- 已验证现有结果解析可以通过 `--label` 过滤，并输出 `label` 列而不是 `run_label` 列。
- 已使用 `label=20260527_022025` 的真实 aggregated CSV 重新生成临时自包含 report，确认 report 成功生成并包含 `Plotly.newPlot`。
- 已执行 `git diff --check` 检查格式。
- 已确认 `config.yml`、`workflow/` 和 `tools/` 中不再残留旧标签配置字段。

#### Commit Message

Add direct test selection parameters and unify workflow labels.
Pass Official lit arguments and RAJAPerf extra arguments through the Snakemake run rules, record normalized test selection in metadata and run stamps, replace the old run-label/repeat configuration with a single global label, and make Plotly reports self-contained for offline viewing.

#### Weekly Update

- This week I added the first test selection mechanism by passing user-defined Official lit arguments and RAJAPerf arguments directly from `config.yml` into the run scripts.
- I kept the design deliberately simple: arguments are configured as lists and passed through without shell parsing or extra suite-specific interpretation.
- I recorded the normalized test selection in experiment metadata and wrote the actual arguments used into each run stamp.
- I also simplified the workflow label model so the whole system now uses one global `label`, with timestamp generation when it is omitted.
- I removed the old run-label and repeat-count configuration paths, which keeps provenance clearer and avoids multiple competing label concepts.
- I changed report generation to embed Plotly directly in the HTML, so reports can be opened offline or in IDE previews without depending on the Plotly CDN.
- I verified the updated DAG, metadata generation, parser filtering, and self-contained report generation.

### 阶段五 B：常用测试选择参数结构化

这一阶段在保留阶段五 A 原生参数透传能力的基础上，为常用测试范围增加了更直观的结构化配置。

- Official 新增 `test_selection.official.filters` 和 `excluded`，归一化时转换为 lit 的 `--filter` 和 `--filter-out` 参数。
- RAJA 新增 `test_selection.raja.kernels` 和 `excluded`，归一化时转换为 RAJAPerf 的 `--kernels` 和 `--exclude-kernels` 参数。
- inclusion 和 `excluded` 可以同时配置，用于先选择较大的测试组，再排除其中少数不需要运行的测试。
- 原有 `official.lit_args` 和 `raja.extra_args` 继续保留，作为未结构化参数的直接透传入口。
- 新增 `workflow/lib/test_selection.py`，集中负责 selection 配置校验、归一化和最终参数拼装。
- metadata 同时记录结构化配置和最终传给工具的 resolved 参数，便于核对实际运行范围。
- 当前不根据 selection 自动修改结果目录；切换测试范围时仍建议使用不同的全局 `label`。

#### Commit Message

Add structured test selection configuration.
Introduce structured Official filters and RAJAPerf kernel selection and exclusion while preserving raw argument passthrough for advanced use cases.

#### Weekly Update

- This week I added structured configuration for common benchmark selection options.
- Official and RAJAPerf test selection now support direct inclusion and exclusion fields.
- Inclusion and exclusion can be combined to select a broad benchmark group while skipping individual tests or kernels.
- I kept the raw argument fields as escape hatches for options that do not yet need dedicated configuration.
- I moved selection normalization into a dedicated module and recorded both configured and resolved arguments in experiment metadata.

### 阶段六：全量分析数据层

这一阶段的目标，是在不增加第二套 report 命令、不引入独立 compare 工具的前提下，为后续可视化报告准备统一的分析数据层。系统现在仍然保持一条 Snakemake 主流水线，但在 parse 之后新增 `analyze` 步骤，默认扫描 `auto/parsed/` 中保留下来的全部可用 parsed 结果，并生成 `auto/analysis/` 下的结构化 CSV/JSON。

阶段六只负责生成分析后的数据，不负责 HTML 展示。HTML 如何读取这些数据、如何展示 regression / improvement、如何交互过滤，留到阶段七处理。

#### 主要设计决策

- 删除单独的 `aggregate_results` 中间步骤。
- `benchmark_records.csv` 成为 parsed 阶段唯一的事实表。
- `analyze` 直接读取所有 `auto/parsed/*/benchmark_records.csv`。
- 如果用户不希望某些历史结果进入分析，应删除对应 `auto/parsed/<experiment_id>/` 或相关结果目录，而不是传复杂筛选参数。
- `sample` 是重复实验的独立维度，和 `label` 不混用。
- `analysis.py` 会先在同一个 `experiment_id / label / sample / test / metric` 内归一为一个观测，避免同一个 sample 内的重复原始记录被误当成多个独立 sample。
- `generate_report` 暂时仍生成现有单 experiment HTML，但不读取 `auto/analysis/`。
- `rule all` 同时要求现有 report 和 `auto/analysis/analysis_summary.json`，所以正常运行主流水线会生成分析数据。

#### 具体修改

- `workflow/Snakefile`
  - 删除 `rule aggregate_results`。
  - 新增 `rule analyze`。
  - `generate_report` 改为直接读取 `benchmark_records.csv`。
  - 为当前配置展开出的 `experiment_id` 增加 wildcard 约束，避免 Snakemake 尝试重建历史 parsed 结果。

- `workflow/scripts/analyze.py`
  - 新增分析入口脚本。
  - 从 `config.yml` 归一化后的 analysis 参数接收变化阈值和最小样本数。
  - 读取 parsed CSV，写出 `auto/analysis/` 下的分析产物。

- `workflow/lib/analysis.py`
  - 新增全量分析逻辑。
  - 负责发现 parsed 表、构建 analysis records、样本统计、metric 对比、top regression/improvement 和 summary。

- `workflow/lib/reporting.py`
  - 保留 report 内部临时聚合逻辑，仅用于当前 Plotly 图表。
  - 移除文件级 aggregated 产物概念。

- `workflow/scripts/generate_report_cli.py`
  - 移除 `--aggregated-output`。
  - 输入说明从 aggregated table 收敛为普通 benchmark table。

- `workflow/scripts/write_experiment_metadata.py`
  - metadata 不再记录 `benchmark_records_aggregated.csv`。
  - metadata 中记录 analysis 输出路径和 `analyze` 日志路径。

- `tools/inspect_workflow_outputs.py`
  - inspect 输出不再包含 `aggregated` 列。
  - 当前只检查 metadata、shared deps、raw results、parsed 和 report。

- `docs/recovery.md`
  - 恢复命令示例改为 parsed、analysis summary 和 report target。

- `config.yml`
  - 新增 analysis 配置：

```yaml
analysis:
  change_threshold_percent: 5.0
  min_samples: 1
```

#### Analysis 产物总览

阶段六会在 `auto/analysis/` 下生成以下文件：

- `analysis_records.csv`
- `sample_statistics.csv`
- `metric_comparisons.csv`
- `top_regressions.csv`
- `top_improvements.csv`
- `analysis_summary.json`

数据流可以理解为：

```text
auto/parsed/*/benchmark_records.csv
  -> analysis_records.csv
  -> sample_statistics.csv
  -> metric_comparisons.csv
  -> top_regressions.csv / top_improvements.csv
  -> analysis_summary.json
```

#### `analysis_records.csv`

这是最底层的分析事实表。它把所有 parsed 结果中的可用指标展开成长表，一行表示某个 experiment/sample 中某个 test 的某个 metric。

字段说明：

- `experiment_id`：来源 experiment 的唯一 ID，来自 parsed 文件所在目录名。
- `source_file`：该行数据来自哪个 `benchmark_records.csv`。
- `suite_name`：测试套件名，当前主要是 `official` 或 `raja`。
- `suite_version`：测试套件版本，例如 `llvmorg-21.1.0`、`v2025.12.0` 或某个 commit hash。
- `compiler_version`：编译器版本或标签，例如 `llvmorg-21.1.0`。
- `label`：实验组标签。可能是自动时间戳，也可能是用户手写标签。
- `sample`：重复实验样本编号，例如 `sample_1`、`sample_2`、`sample_3`。
- `test_name`：测试名或 RAJA kernel 名。
- `metric`：标准化指标名，当前可能是 `exec_time`、`compile_time`、`binary_size`、`flops_gflops`、`bandwidth_gib`。
- `metric_display_name`：面向展示的指标名，例如 `Execution time`、`Compile time`、`Binary size`、`Throughput`、`Memory bandwidth`。
- `metric_source_column`：该指标来自 parsed 表中的哪一列。
- `direction`：指标方向。`lower` 表示越低越好，`higher` 表示越高越好。
- `value`：该 metric 的数值。
- `source_observations`：同一个 experiment/sample/test/metric 内有多少条原始记录被合成为这个值。通常是 `1`。

#### `sample_statistics.csv`

这是样本统计表。它基于 `analysis_records.csv`，按 `suite_name / suite_version / compiler_version / test_name / metric` 汇总多个 label/sample 观测。

字段说明：

- `suite_name`：测试套件名。
- `suite_version`：测试套件版本。
- `compiler_version`：编译器版本。
- `test_name`：测试名或 kernel 名。
- `metric`：指标名。
- `metric_display_name`：展示名。
- `direction`：指标方向，`lower` 或 `higher`。
- `observations`：参与统计的观测数量。
- `labels`：这些观测来自哪些 label，多个值用逗号连接。
- `samples`：这些观测来自哪些 sample，多个值用逗号连接。
- `mean`：观测值平均值。
- `std`：样本标准差。只有一个观测时通常为空。
- `cv`：变异系数，计算为 `std / abs(mean)`，用于粗略观察波动比例。
- `ci95_low`：95% 置信区间下界，当前使用轻量公式 `mean - 1.96 * std / sqrt(n)`。
- `ci95_high`：95% 置信区间上界，当前使用轻量公式 `mean + 1.96 * std / sqrt(n)`。

#### `metric_comparisons.csv`

这是变化对比表。它基于 `sample_statistics.csv`，在同一个 `suite_name / suite_version / test_name / metric` 内，对不同 LLVM/compiler version 组合做两两比较。

也就是说，当前系统的性能变化主轴是 LLVM/compiler version；suite version 是固定上下文，不作为变化对比轴。

字段说明：

- `suite_name`：测试套件名。
- `test_name`：测试名或 kernel 名。
- `metric`：指标名。
- `metric_display_name`：展示名。
- `direction`：指标方向。
- `baseline_compiler_version`：baseline 编译器版本。
- `baseline_suite_version`：baseline suite 版本。它用于约束比较上下文，正常应与 candidate suite version 相同。
- `candidate_compiler_version`：candidate 编译器版本。
- `candidate_suite_version`：candidate suite 版本。它用于约束比较上下文，正常应与 baseline suite version 相同。
- `baseline_observations`：baseline 侧观测数量。
- `candidate_observations`：candidate 侧观测数量。
- `baseline_mean`：baseline 平均值。
- `candidate_mean`：candidate 平均值。
- `raw_change_percent`：原始变化百分比，计算为 `(candidate - baseline) / abs(baseline) * 100`。
- `normalized_change_percent`：按指标方向归一后的变化。正数表示变好，负数表示变差。
- `classification`：变化分类。
- `evidence`：分类依据。

`classification` 的可能值：

- `stable`：变化幅度低于阈值。
- `candidate_regression`：超过阈值，且按指标方向看是变差，但证据还不够强。
- `candidate_improvement`：超过阈值，且按指标方向看是变好，但证据还不够强。
- `reliable_regression`：样本数足够，且 95% CI 不重叠，判断为相对可靠的变差。
- `reliable_improvement`：样本数足够，且 95% CI 不重叠，判断为相对可靠的变好。

`evidence` 的可能值：

- `below_threshold`：变化幅度低于 `analysis.change_threshold_percent`。
- `insufficient_samples`：某一侧观测数量低于 `analysis.min_samples`。
- `missing_ci`：缺少置信区间，通常因为某侧只有一个观测，无法计算标准差。
- `ci95_overlapping`：两侧 95% CI 重叠，不能认为变化可靠。
- `ci95_non_overlapping`：两侧 95% CI 不重叠，证据相对更强。

#### `top_regressions.csv`

这是从 `metric_comparisons.csv` 中筛选出的 top regression 表，字段与 `metric_comparisons.csv` 完全相同。

生成逻辑：

- 保留 `classification` 以 `regression` 结尾的行。
- 按 `normalized_change_percent` 从小到大排序。
- 默认保留前 50 行。

解释方式：

- 对 `lower` 指标，例如 `exec_time`，数值上升通常是 regression。
- 对 `higher` 指标，例如 `flops_gflops`，数值下降通常是 regression。
- `normalized_change_percent` 越小，表示退化越明显。

#### `top_improvements.csv`

这是从 `metric_comparisons.csv` 中筛选出的 top improvement 表，字段与 `metric_comparisons.csv` 完全相同。

生成逻辑：

- 保留 `classification` 以 `improvement` 结尾的行。
- 按 `normalized_change_percent` 从大到小排序。
- 默认保留前 50 行。

解释方式：

- 对 `lower` 指标，例如 `exec_time`，数值下降通常是 improvement。
- 对 `higher` 指标，例如 `flops_gflops`，数值上升通常是 improvement。
- `normalized_change_percent` 越大，表示改善越明显。

#### `analysis_summary.json`

这是整次 analysis 的摘要文件，适合后续阶段七作为报告首页、数据完整性检查或调试信息来源。

字段说明：

- `analysis_scope`：本次分析范围。当前含义是扫描 `auto/parsed` 下保留的 parsed benchmark 结果。
- `generated_at`：生成时间，UTC ISO 格式。
- `settings.change_threshold_percent`：变化阈值。低于该百分比的变化会归为 `stable`。
- `settings.min_samples`：可靠变化所需的最小观测数。
- `inputs.count`：纳入分析的 parsed CSV 文件数量。
- `inputs.skipped`：被跳过的输入及原因。
- `records.analysis_records`：`analysis_records.csv` 行数。
- `records.sample_statistics`：`sample_statistics.csv` 行数。
- `records.metric_comparisons`：`metric_comparisons.csv` 行数。
- `records.top_regressions`：`top_regressions.csv` 行数。
- `records.top_improvements`：`top_improvements.csv` 行数。
- `coverage.suites`：本次覆盖的 suite。
- `coverage.compiler_versions`：覆盖的编译器版本。
- `coverage.labels`：覆盖的实验标签。
- `coverage.samples`：覆盖的 sample 名。
- `classification_counts`：`metric_comparisons.csv` 中不同 `classification` 的数量统计。

#### 关于 aggregated 中间产物的结论

- 阶段六开发过程中确认，原先 `benchmark_records_aggregated.csv` 与 `benchmark_records.csv` 在当前数据形态下大多是一一对应的。
- 真正有意义的跨 sample / 跨历史结果聚合发生在 analysis 阶段。
- 因此当前代码删除了 `aggregate_results` rule 和 `workflow/scripts/aggregate_results_cli.py`。
- 如果 report 需要临时聚合，它会在内存中从 parsed 表生成，不再写出单独 aggregated 文件。
- 磁盘上已有的旧 `benchmark_records_aggregated.csv` 不会被新代码使用；如果不需要保留，可以由用户手动清理。

#### 验证与结果

- 已执行 `py_compile` 检查受影响 Python 模块。
- 已执行 `git diff --check` 检查格式。
- 已验证 `workflow/scripts/analyze.py` 可以基于现有 parsed 数据生成 `auto/analysis` 结构。
- 已验证 `generate_report_cli.py` 可以直接基于 `benchmark_records.csv` 生成 report。
- 已执行 `./run.sh dry-run` 验证 Snakemake DAG。
- 当前 DAG 不再包含 `aggregate_results`，而是包含 `analyze`。
- 已执行 `./run.sh inspect --format json`，确认 inspect 输出中不再包含 `aggregated` 字段。
- 已实际运行一次 workflow 并成功生成 `auto/analysis/` 结果。

#### Commit Message

Add workflow analysis data layer.
Introduce the Snakemake `analyze` stage to build report-ready analysis tables from retained parsed results, remove the redundant aggregated CSV stage, add sample statistics and metric comparison outputs, and keep HTML rendering separate for the next reporting phase.

#### Weekly Update

- This week I added the analysis data layer that scans retained parsed benchmark results and produces structured CSV/JSON outputs under `auto/analysis`.
- I removed the redundant aggregated CSV stage so `benchmark_records.csv` is now the single parsed fact table.
- I added sample-level statistics, normalized metric comparisons, and top regression/improvement tables.
- I kept the design Snakemake-first: users still run the normal pipeline, and analysis is generated as part of the DAG.
- I deliberately kept HTML consumption of the analysis data out of this stage, leaving visualization and report integration for the next phase.
- I updated metadata, recovery notes, and inspect output to match the simplified parse/analyze/report flow.

### 阶段七：全局 HTML 分析报告

这一阶段把阶段六生成的 `auto/analysis/` 数据真正接入 HTML 报告。报告不再围绕单个 experiment 的临时图表，而是默认读取当前保留下来的全部 parsed/analysis 结果，生成一个面向 LLVM 版本性能变化分析的全局静态页面：

```text
auto/analysis/*.csv + auto/analysis/analysis_summary.json
  -> workflow/lib/report/
  -> workflow/templates/
  -> workflow/static/
  -> auto/reports/analysis_report.html
```

阶段七仍然保持 Snakemake 主线：正常运行 workflow 时，`analyze` 生成分析数据，`generate_report` 再读取这些数据生成 HTML。为了开发和调试方便，也新增了 `./run.sh report`，可以在不重新运行 benchmark 的情况下，基于现有 `auto/analysis/` 快速重生成报告。

#### 主要设计决策

- 报告输入统一切换为阶段六的 `auto/analysis/` 产物。
- 最终报告目标统一为 `auto/reports/analysis_report.html`。
- 报告默认反映 `auto/parsed/` 中保留下来的全部可用结果。
- 如果用户不希望某些历史结果进入报告，应删除对应历史产物后重新运行主 workflow。
- HTML report 是静态单文件，Plotly、CSS 和 JavaScript 都内嵌，适合归档和离线查看。
- 页面中的 comparison 主轴是 LLVM/compiler version；suite version 固定为上下文，不作为性能变化对比轴。
- 复杂的筛选、服务端应用或独立 dashboard 暂不进入本阶段。

#### Report 代码结构

阶段七将原先混合在一个 Python 文件中的 report 逻辑拆成更清晰的模块：

- `workflow/lib/report/data.py`
  - 读取 `auto/analysis/` 下的 CSV/JSON。
  - 封装成 `AnalysisReportData`。
  - 提供少量展示前 helper，例如 top rows、top CV rows、suite/metric summary。

- `workflow/lib/report/figures.py`
  - 负责构造 Plotly 图表。
  - 当前包括 classification counts、LLVM version pair heatmap、suite/metric heatmap、largest normalized changes、noisiest sample groups。
  - 只第一张图内嵌 Plotly JS，后续图表复用同一份 Plotly runtime，避免 HTML 体积重复膨胀。

- `workflow/lib/report/tables.py`
  - 负责表格列选择、筛选器配置、单元格格式化和 badge/change 样式 class。
  - `build_table()` 不排序，只按调用方传入的 DataFrame 顺序生成 `TableView`。
  - `classification`、`normalized_change_percent` 和 `test_name` 有专门展示格式。

- `workflow/lib/report/views.py`
  - 作为 report 编排层。
  - 构造 Jinja2 context，组织 overview、figures、suite cards、tables 和 CSV links。
  - 不再直接拼接大量 HTML/CSS/JS 字符串。

- `workflow/templates/analysis_report.html.j2`
  - 主 HTML 模板。
  - 定义页面 section 顺序和整体结构。

- `workflow/templates/partials/table.html.j2`
  - 通用表格模板。
  - 支持搜索框、下拉筛选、空表提示和已格式化 cell 渲染。

- `workflow/static/report.css`
  - 报告页面样式。
  - 控制卡片、表格、badge、Plotly 面板和响应式布局。

- `workflow/static/report.js`
  - 轻量原生 JavaScript。
  - 当前负责表格搜索和下拉筛选。

#### 页面内容

生成的 `analysis_report.html` 当前包含以下主要区域：

- `LLVM Performance Analysis`
  - 报告标题、生成时间和分析范围说明。
  - 提醒用户报告默认总结保留在 `auto/parsed/` 下的全部 parsed 结果。

- `Analysis Coverage`
  - 展示输入文件数量、analysis records 数量、sample groups 数量、LLVM comparisons 数量、suite 数量和 sample 数量。
  - 展示变化阈值、可靠证据所需最小观测数、覆盖的 compiler versions、suite versions 和 labels。
  - 展示 `classification_counts`，例如 stable、candidate regression、reliable improvement 等。

- `Outcome Classification Counts`
  - 柱状图。
  - 展示 stable / regression / improvement 等分类数量。

- `Change Distribution By LLVM Version Pair`
  - 热力图。
  - 按 `baseline_compiler_version -> candidate_compiler_version` 和 `metric` 统计变化行数量。
  - 只基于 `metric_comparisons.csv`，不会把不同 suite version 之间的差异当成 compiler 性能变化。

- `Change Distribution By Suite And Metric`
  - 热力图。
  - 按 suite 和 metric 汇总变化数量。
  - 如果未来同一个 suite 下有多个 suite version，它们各自内部的 compiler comparison 会汇总到同一个 suite/metric 格子里，但不会跨 suite version 做 comparison。

- `Official And RAJA Summary`
  - 每个 suite 一个 summary card。
  - `Comparisons` 是该 suite 在 `metric_comparisons.csv` 中的行数。
  - `Sample groups` 是该 suite 在 `sample_statistics.csv` 中的行数。
  - 如果每个 test/metric 正好有两个 compiler version，comparison 数量通常接近 sample groups 的一半；若存在缺失 metric、单边结果、超过两个 compiler version 或被跳过的无效数值，则比例不会严格相等。

- `Largest Normalized Changes`
  - 横向条形图。
  - 展示 top regression 和 top improvement 中变化幅度最大的项目。
  - `normalized_change_percent > 0` 表示 candidate 变好，`< 0` 表示 candidate 变差。

- `Top LLVM Version Regressions And Improvements`
  - 左右两张表。
  - 分别展示 top regressions 和 top improvements。
  - 提供对应 CSV 链接。

- `Metric Comparisons Across LLVM Versions`
  - 完整 comparison 预览表。
  - HTML 中按 `abs(normalized_change_percent)` 从大到小展示前 500 行。
  - 支持搜索，并支持按 suite、metric、classification 筛选。
  - 完整数据仍通过 `metric_comparisons.csv` 链接查看。

- `Noisiest Sample Groups`
  - 横向条形图。
  - 按 CV 从高到低展示最 noisy 的 sample groups。
  - 用于解释哪些测试更容易产生 candidate 而不是 reliable 结论。

- `Sample Statistics`
  - 样本统计表。
  - HTML 中按 CV 从高到低展示前 100 行。
  - 展示 observations、mean、std、cv、ci95_low/high。

- `Analysis Record Preview`
  - provenance/debug 表。
  - 展示 `analysis_records.csv` 前 200 行。
  - 完整数据仍通过 CSV 链接查看。

#### 表格排序与交互

`tables.py` 本身不改变行顺序。每张表的排序由 `views.py` 在调用 `build_table()` 前决定：

- `Top Regressions`：阶段六已按 `normalized_change_percent` 升序排序，最严重 regression 在前。
- `Top Improvements`：阶段六已按 `normalized_change_percent` 降序排序，最大 improvement 在前。
- `Metric Comparisons`：报告层按 `abs(normalized_change_percent)` 降序排序，展示变化幅度最大的前 500 行。
- `Sample Statistics`：报告层按 `cv` 降序排序，展示最 noisy 的前 100 个 sample groups。
- `Analysis Record Preview`：保持 `analysis_records.csv` 原始顺序，展示前 200 行。

表格搜索和筛选由 `workflow/static/report.js` 实现：

- 搜索框匹配整行文本。
- 下拉筛选通过 `data-column` 指定表格列。
- 多个筛选条件同时生效。
- 不重新请求数据，只在浏览器端隐藏或显示已有行。

#### 使用方式

正常主线仍然是：

```bash
./run.sh
```

如果已经有可用的 `auto/analysis/` 数据，只想重新生成 HTML 报告，可以使用：

```bash
./run.sh report
```

报告输出路径：

```text
auto/reports/analysis_report.html
```

需要注意的是，一些 IDE preview 插件可能不会执行内嵌 JavaScript，因此可能看不到 Plotly chart。此时应使用真实浏览器打开，或通过简单 HTTP server 查看：

```bash
python3 -m http.server 8000
```

然后打开：

```text
http://localhost:8000/auto/reports/analysis_report.html
```

#### 当前限制与后续增强

- 当前图表可以发现变化数量和极端变化，但还没有专门展示某个 LLVM version pair 在某个 metric 上整体趋势的图。
- `compiler_pair_matrix` 展示的是变化行数量，不直接展示改善/回归方向和幅度分布。
- failed / missing results 目前仍主要通过 Snakemake 日志、metadata 和 inspect 工具分析，报告中尚未做专门展示。
- 当前 report 是静态 HTML，不提供服务端查询或动态加载大 CSV。
- 如果 HTML 表格数据继续变大，后续可以考虑分页、客户端排序或更轻量的数据加载策略。

#### 验证与结果

- 已执行 `py_compile` 检查 `workflow/lib/report/*.py` 和 `workflow/scripts/generate_report_cli.py`。
- 已执行 `bash -n run.sh` 检查快捷脚本语法。
- 已执行 `git diff --check` 检查格式。
- 已执行 `./run.sh report`，确认可以基于现有 `auto/analysis/` 生成 `auto/reports/analysis_report.html`。
- 已检查生成的 HTML 中包含 Plotly 图表容器和 `Plotly.newPlot` 调用。
- 已确认 report 代码从旧的大型 Python 字符串拼接结构，拆分为 report 包、Jinja2 模板和静态 CSS/JS。

#### Commit Message

Add global analysis HTML report.
Render the stage-six analysis dataset as a self-contained static HTML report, add report data/figure/table modules, move page structure into Jinja2 templates, and provide a lightweight report regeneration command.

#### Weekly Update

- This week I connected the analysis dataset to a global HTML report under `auto/reports/analysis_report.html`.
- I replaced the old single-experiment report path with a report that reads `auto/analysis` tables and summarizes all retained parsed results.
- I added overview cards, Plotly charts, suite summaries, top regression/improvement tables, comparison tables, sample statistics, and provenance previews.
- I refactored report generation into a clearer structure with `workflow/lib/report/`, Jinja2 templates, and static CSS/JS.
- I kept the report self-contained so it can be archived and opened offline.
- I added `./run.sh report` as a development shortcut for regenerating the report from existing analysis data without rerunning benchmarks.
- I documented current limitations, especially that the version-pair matrix shows change counts rather than full direction/magnitude trends.
