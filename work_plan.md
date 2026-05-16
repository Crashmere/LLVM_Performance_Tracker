# LLVM Performance Tracking 项目开发规划

## 1. 文档目的

本文档基于以下三类背景信息制定：

- `pp_report.pdf` 中的 MVP、Work Plan、Future Work、Risk Analysis。
- `snakemake_design.md` 中的迁移设计目标。
- 当前 `workflow/` 目录中的实际实现，以及 `auto/` 目录中的试运行产物。

本文档的目标不是重复 proposal，而是把“报告中的规划”翻译成面向当前代码库的、可执行的开发路线。每个阶段都会明确：

- 要解决的差距是什么。
- 需要修改哪些文件或新增哪些模块。
- 具体功能要做到什么程度。
- 如何验证该阶段已完成。

后续开发建议以本文档为主线推进，并在每个阶段完成后同步更新状态、风险和实际偏差。

## 2. 当前系统基线

结合 `workflow/` 和 `auto/` 当前状态，可以把现有系统理解为一个“Snakemake 第一阶段迁移版”，已经具备以下能力：

- 已从单体 Python orchestration 迁移为 Snakemake DAG。
- 已实现 LLVM、Official test-suite、RAJAPerf 的 checkout / build / run / parse / aggregate / report 全流程。
- 已引入参数化目录布局，支持按 `llvm_tag`、suite tag、`run_label` 分离源码、构建、结果、报告和日志。
- 已能生成统一表格数据：
  - `auto/parsed/<run_label>/benchmark_records.csv`
  - `auto/parsed/<run_label>/benchmark_records_aggregated.csv`
- 已能生成 Plotly HTML 报告：
  - `auto/reports/<run_label>/benchmark_report.html`
- 已验证 RAJA OpenMP 链接链路，采用 `libomp.so` 自动发现 + RPATH 的方案。
- 已经保留了多次运行结果目录，这对后续重复实验和统计分析是正确方向。

从 `auto/` 的试运行结果可以确认，当前系统已经真实跑通过至少一次单版本实验，属于“能运行，但还没有进入研究级数据采集和分析状态”的阶段。

## 3. 与报告目标的差距总览

### 3.1 已经基本覆盖的内容

- MVP 中的“全流程自动化 pipeline”：已初步完成。
- MVP 中的“JSON/CSV 解析适配层”：已有初版，但仍较脆弱。
- MVP 中的“静态 HTML 报告生成”：已完成初版。
- PP 阶段后的核心工作“迁移到 Snakemake”：已完成第一阶段。

### 3.2 仍然存在的核心差距

1. 多版本实验能力尚未真正落地。
   当前配置允许 `tags` 为列表，但 `Snakefile` 实际只取每个列表的第一个元素，尚未展开为版本矩阵。

2. 容错与恢复能力不足。
   目前每个 rule 能写日志，但系统还没有：
   - 统一的 run manifest
   - 失败状态归档
   - 版本级 continue-on-error 策略
   - 中断后恢复到“待补跑项”而不是手工判断

3. 数据解析层对格式变化的适应能力有限。
   当前 parser 基本依赖固定文件名、固定字段名，对不同 suite 版本、字段缺失、格式升级的兼容较弱。

4. 测试子集选择功能尚未实现。
   报告和 work plan 都明确提到要支持用户控制测试范围，以减少运行时间、输出体积和资源消耗。

5. 历史运行数据复用能力还不完整。
   当前 `parse_results` 虽然可以扫描整个 `results/` 并按 `run_label` 过滤，但这项能力还没有被明确设计成一等功能。系统仍缺少：
   - 面向历史 run 的显式重解析/重聚合/重出报告入口
   - 历史 run 可发现性与清单展示
   - 对“已有原始结果但缺少 parsed/report 产物”场景的恢复支持
   - 面向跨 run 复用和比较的数据选择模型

6. 可视化还处于演示版。
   当前图表固定、过滤能力弱，尚未支持 kernel 级交互、对比模式、差异高亮、失败结果展示等。

7. 自动性能变化检测尚未开始。
   目前只有聚合均值，没有“版本对版本”的差异分析引擎，也没有阈值过滤。

8. 重复实验和统计显著性尚未形成闭环。
   当前数据模型已经保留了 `run_label`，但系统还没有：
   - 同一配置自动重复执行
   - 汇总均值/标准差/置信区间
   - t-test 或其他显著性分析

9. HPC 环境可移植性支持仍不完整。
   报告计划中包括 EIDF VM 与 ARCHER2 的可移植性验证，但当前工作流没有显式环境抽象、模块加载层或平台配置层。

10. 自动监控与持续执行尚未实现。
   尚无 CRON / GitLab CI 驱动的新版本检测与自动触发。

11. 工程性基础设施仍偏弱。
   包括：
   - 缺少自动化测试
   - 缺少 schema 校验
   - 缺少报告生成回归测试
   - 缺少更清晰的 CLI / 文档 / 示例配置

### 3.3 额外值得补充的改进点

这些点在 PP 文档中没有全部展开，但从当前代码实际情况看，建议纳入开发计划：

- 记录运行环境元数据：CPU、内核版本、内存、编译器 commit、suite commit、线程数、OpenMP 环境变量。
- 引入数据与配置的 provenance 追踪：确保一份报告能回溯到输入配置和源码版本。
- 将“原始结果解析”和“分析视图模型”分层，避免后续复杂分析都直接耦合在 CSV 上。
- 为 Snakemake 提供 profile、cluster/HPC 运行说明和资源声明。
- 增加“仅重跑失败版本/失败 suite”的目标规则。
- 增加“从历史 run 重建派生产物”的规则，例如只凭已有 `results/` 重新生成 parsed/aggregated/report。
- 增加数据清洗规则，自动识别异常值、空结果、编译失败和运行崩溃。

## 4. 总体开发原则

后续实现建议遵循以下原则：

1. 先补基础设施，再做大规模采集。
   当前最危险的情况不是“功能不够多”，而是“数据采集开始后发现格式、恢复、过滤、版本矩阵都不稳定”。

2. 所有新增功能都应尽量进入 Snakemake DAG，而不是回退到散落的手工脚本。

3. 优先保留原始数据和元数据，不要只保留最终聚合结果。

4. 所有“多版本、多轮次、多平台”的能力都应该通过配置驱动，而不是改代码常量。

5. 每个阶段都要有可验证的交付物，包括：
   - 新增配置字段
   - 新增或修改的 rule
   - 新增输出文件
   - 一个最小可复现的测试案例

## 5. 建议的开发阶段

下面的阶段顺序综合考虑了：

- `pp_report.pdf` 中的 work plan 顺序
- 当前代码差距
- 研究项目最怕返工的部分
- 现在所处时间点（`2026-05-11`，接近报告中的 Task 1.4）

---

## 阶段 0：基线固化与现状清理

### 目标

在继续扩展功能前，把当前 Snakemake 版本固化为一个清晰、可测试、可回归的基线，避免后面一边改架构一边失去参考点。

### 需要完成的功能

- 补充当前架构说明文档。
- 固化一套最小演示配置和样例输出。
- 标记当前系统已知限制。
- 把“能成功跑通的配置”与“仅设想支持但未真正实现的能力”区分清楚。

### 需要修改/新增的代码或文件

- `README.md`
  - 增补当前限制说明：只使用 `tags[0]`、暂无 test subset、暂无多轮统计、暂无自动监控。
- 新增 `docs/` 或扩展根目录文档
  - 增加运行样例、目录布局说明、日志定位说明。
- `config.yml`
  - 增加注释模板，说明哪些字段已支持、哪些字段是计划支持。

### 具体修改内容

- 把当前 `workflow` 的输入、输出、日志路径写成稳定文档。
- 记录 `auto/` 中已跑通样例的参数组合作为回归基线。
- 补一个 `--dry-run` 示例和一个“仅生成报告”的示例。

### 验收标准

- 新成员只看文档即可跑通一次单版本流程。
- 文档中不会误导读者以为“多 tag 列表已经真正支持矩阵运行”。

---

## 阶段 1：配置模型升级与多版本矩阵执行

### 目标

把“配置层支持多个版本”从名义支持变成真实支持，为后续大规模采集和跨版本比较打基础。

### 当前差距

- `workflow/Snakefile` 直接取：
  - `llvm.tags[0]`
  - `official.tags[0]`
  - `raja.tags[0]`
- 系统无法一次性声明多个 LLVM 版本并自动展开。
- 还不支持“一个 LLVM 版本对应多个 suite 版本”或“重复运行列表”。

### 需要完成的功能

- 真正支持多版本矩阵展开。
- 支持显式定义实验组合。
- 支持多次重复运行。
- 为每个组合生成独立目录和独立结果。

### 需要修改/新增的代码或文件

- `workflow/Snakefile`
- `workflow/lib/common.py`
- 可能新增：
  - `workflow/lib/experiment_matrix.py`
  - `workflow/lib/config_schema.py`

### 具体修改内容

1. 扩展配置结构，建议支持两种模式：
   - 简单模式：
     - `llvm.tags`
     - `test_suite.official.tags`
     - `test_suite.raja.tags`
     - `runs.labels`
   - 显式实验矩阵模式：
     - `experiments:`
       - 每项明确定义 `llvm_tag`、`official_tag`、`raja_tag`、`run_label`、可选平台和参数覆盖。

2. 在 `common.py` 中新增配置归一化逻辑：
   - 统一生成实验列表。
   - 校验 tag、run_label、组合重复项。
   - 给每个实验分配稳定 ID。

3. 在 `Snakefile` 中用 `expand()` 驱动最终目标：
   - 对每个实验组合生成结果和报告目标。
   - 让 checkout/build/run/parse/report 都基于 wildcard。

4. 明确 source/build/install 缓存策略：
   - LLVM install 可按 `llvm_tag` 复用。
   - Official/RAJA build 可按 `suite_tag + llvm_version (+ optional build profile)` 复用。
   - 运行结果必须按 `run_label` 隔离。

5. 设计重复实验接口：
   - 允许同一实验自动生成 `repeat_01`、`repeat_02`、`repeat_03`。

### 建议新增配置字段

- `runs.labels`
- `runs.repeat_count`
- `project.default_platform`
- `experiments[]`
- `build_profiles[]`

### 验收标准

- 同一命令可以一次性跑多个 LLVM 版本。
- 多个版本共享已有 source/build/install，不重复 checkout 和全量重编。
- 同一实验可重复执行 N 次并形成多份结果目录。

---

## 阶段 2：Snakemake 内聚的可观测性、恢复与实验元数据

### 目标

落实 MVP 中“严格错误处理和恢复”的要求，但不在 Snakemake 之外再实现一套独立调度系统。

本阶段的核心目标是：增强现有 DAG 的可观测性、可诊断性和可恢复性，让用户仍然通过 Snakemake target、`--keep-going`、`--rerun-incomplete`、明确输出文件和少量轻量 helper 命令完成恢复，而不是引入复杂的 manifest 状态机或新的主入口。

换句话说，阶段 2 不应尝试替代 Snakemake 的 job 状态管理，而应把“实验配置、输出路径、日志位置、失败诊断和派生产物重建”整理成更清晰、更可复现的工作流产物。

### 当前差距

- 当前失败后主要依赖 Snakemake 默认报错和分散的 rule 日志。
- `parsed/`、`reports/` 已按 `experiment_id` 隔离，但每个实验缺少一份轻量的配置快照和 provenance 文件。
- 失败诊断仍然需要人工在多个日志目录之间跳转。
- “从已有原始结果重建 parsed / aggregated / report”在 DAG 层已经接近可行，但文档和目标入口还不够明确。
- 原阶段 2 设想的全局 manifest、每个 rule 主动更新状态、retry CLI 等功能容易和 Snakemake 自身的 DAG 与状态机制重复，增加维护成本和入口复杂度。

### 需要完成的功能

- 为每个 experiment 生成轻量元数据文件，记录配置、路径和环境摘要。
- 改善 rule 级日志和错误信息，使失败原因可以从对应日志中快速定位。
- 明确推荐的恢复方式：
  - 使用 Snakemake `--rerun-incomplete` 处理中断或半成品。
  - 使用 Snakemake `--keep-going` 让批量实验尽量跑完其它独立项。
  - 使用具体 target 只重建某个 experiment 的 parsed / aggregated / report。
  - 使用 `--forcerun` 或删除特定输出触发某个 rule 重跑。
- 增加轻量的状态/诊断辅助命令，只负责“读取现有文件并汇总”，不负责调度或修改状态。
- 把历史 run 恢复设计为普通 Snakemake target，而不是单独的恢复系统。

### 需要修改/新增的代码或文件

- `workflow/Snakefile`
- `workflow/lib/common.py`
- 新增：
  - `workflow/scripts/write_experiment_metadata.py`
  - `tools/inspect_workflow_outputs.py`
  - `docs/recovery.md` 或在 `README.md` 中新增恢复章节

### 具体修改内容

1. 新增 experiment metadata 产物。
   - 建议路径：`auto/metadata/<experiment_id>/experiment.json`
   - 内容包括：`experiment_id`、`llvm_tag`、`official_tag`、`raja_tag`、`run_label`、`platform`、关键输出路径、日志路径、配置快照、生成时间。
   - 可选加入轻量环境信息：hostname、CPU 型号、kernel、Python 版本、Snakemake 版本。

2. 在 `Snakefile` 中把 metadata 纳入 DAG。
   - `rule all` 可继续以最终 report 为默认目标。
   - `generate_report` 可以依赖 experiment metadata，保证报告旁边总有可追溯配置。
   - 不要求每个 rule 写运行状态，避免并发写文件和状态不一致问题。

3. 改善关键脚本的失败输出。
   - checkout 失败
   - configure 失败
   - build 失败
   - result missing
   - parse 失败
   - 失败时仍由 Snakemake 判定 job failed，但脚本日志中应保留清晰的命令、cwd、返回码和期望输出路径。

4. 增加只读汇总命令。
   - `inspect_workflow_outputs.py` 扫描 `auto/metadata/`、`auto/results/`、`auto/parsed/`、`auto/reports/` 和 `auto/logs/`。
   - 输出每个 experiment 的产物存在性摘要，例如 raw results、parsed、aggregated、report 是否存在。
   - 这个命令不生成调度计划、不写状态、不重跑任务，只帮助用户决定下一条 Snakemake 命令。

5. 明确恢复和补跑模式全部映射为 Snakemake 用法。
   - 中断后继续：`./run.sh resume`
   - 批量尽量继续：`./run.sh` 默认传递 `--keep-going`
   - 失败立即停止：`./run.sh strict`
   - 只重建某个报告：`./run.sh -- auto/reports/<experiment_id>/benchmark_report.html`
   - 只重跑某个规则：`./run.sh -- --forcerun run_raja auto/reports/<experiment_id>/benchmark_report.html`
   - 已有原始结果时重建派生产物：直接指定对应 report 或 aggregated CSV target。

6. 文档化“不要做”的边界。
   - 不做全局 mutable manifest 状态机。
   - 不做独立 retry 调度器。
   - 不在脚本里绕过 Snakemake 直接调用多个 workflow stage。
   - 不让 helper CLI 修改 Snakemake 输出或隐藏真实失败。

### 验收标准

- 每个最终报告都能追溯到一份 experiment metadata。
- 运行失败时，用户能从 Snakemake 报错定位到对应日志，并在日志中看到清楚的失败命令和期望产物。
- `./run.sh` 默认 `--keep-going`、`./run.sh resume` 和 `./run.sh strict` 被文档化并验证可用。
- 用户可以通过指定 Snakemake target，只重建某个 experiment 的 parsed / aggregated / report，而不重新 checkout/build/run。
- 汇总命令能列出各 experiment 的关键产物存在性，帮助判断缺的是 raw results、parsed、aggregated 还是 report。
- 阶段 2 完成后，主入口仍然是 Snakemake / `run.sh`，没有引入新的主调度入口。

---

## 阶段 3：构建缓存、清理策略与资源管理

### 目标

解决当前构建复用和资源控制上的隐患，支撑后续大规模版本采集。

### 当前差距

- `build_with_cmake()` 默认 `clear_first=True`，会削弱缓存价值。
- 还缺少显式清理策略。
- 没有磁盘占用摘要。
- 没有对并发、内存、磁盘阈值的配置控制。

### 需要完成的功能

- 默认保留 build 缓存。
- 允许按规则执行清理，而不是每次 build 清空目录。
- 提供空间控制和资源保护。

### 需要修改/新增的代码或文件

- `workflow/lib/common.py`
- `workflow/Snakefile`
- 新增：
  - `workflow/scripts/cleanup_cli.py`
  - `workflow/scripts/disk_usage_report_cli.py`

### 具体修改内容

1. 修改 `build_with_cmake()`：
   - 默认不清空构建目录。
   - 仅在配置显式要求 `reconfigure: true` 或 `clean_build: true` 时清理。

2. 增加清理类 rule：
   - 清理临时 build
   - 清理旧 install
   - 清理指定 run_label 的结果和日志
   - 保留结果、删除中间产物

3. 增加资源配置：
   - `resources.max_parallel_builds`
   - `resources.disk_soft_limit_gb`
   - `resources.require_clean_before_build`

4. 输出资源摘要：
   - 单个 LLVM install 占用
   - 单个 build 占用
   - 当前 results/parsed/reports 占用

### 验收标准

- 二次运行相同版本时不会无意义全量重编。
- 清理行为是显式且可控的。
- 系统能给出清晰的磁盘占用报告。

---

## 阶段 4：数据解析层重构与多格式适配

### 目标

完成报告中 Task 1.4 的核心要求，让 parser 对 suite 版本变化、字段缺失、异常结果更稳健。

### 当前差距

- `workflow/lib/parse_results.py` 仍以“固定文件名 + 固定字段名”为主。
- 解析逻辑把 suite 版本识别直接绑定到目录命名。
- 缺少 schema version、字段映射层和兼容测试。

### 需要完成的功能

- 建立 parser adapter 层。
- 支持不同 suite 版本的字段兼容。
- 支持部分缺失字段时降级解析而不是整体失败。
- 把“测试失败/崩溃/无结果”纳入统一记录模型。

### 需要修改/新增的代码或文件

- `workflow/lib/parse_results.py`
- 新增：
  - `workflow/lib/parsers/base.py`
  - `workflow/lib/parsers/official.py`
  - `workflow/lib/parsers/raja.py`
  - `workflow/lib/result_schema.py`
  - `tests/data/` 样例数据
  - `tests/test_parse_results.py`

### 具体修改内容

1. 重构数据模型，建议把记录分三层：
   - 实验元数据
   - 测试条目状态
   - 指标数据

2. 为 Official 和 RAJA 建立独立 parser adapter：
   - 文件发现
   - schema 检测
   - 字段映射
   - 容错清洗

3. 对 Official suite 重点处理：
   - JSON 中不同 test 类型字段差异
   - MicroBenchmarks 与普通 tests 的差异
   - 运行失败项、缺少 exec_time 项

4. 对 RAJA 重点处理：
   - CSV 标题变化
   - `Kernel / Variant / Tuning` 拼接规则
   - PASSED 之外的状态
   - FOM、带宽、GFLOP/s 额外字段兼容

5. 增加元数据列：
   - `suite_name`
   - `suite_version`
   - `compiler_tag`
   - `compiler_version`
   - `compiler_commit`
   - `run_label`
   - `platform`
   - `hostname`
   - `status_detail`

6. 输出格式建议升级：
   - 继续保留 CSV，便于人工查看。
   - 把 Parquet 变成默认分析格式，提升后续多版本分析效率。

### 验收标准

- 至少能兼容当前 `auto/` 结果和一份字段略有变化的模拟结果。
- 对缺失字段会给 warning，不会整批解析失败。
- parser 单元测试覆盖关键分支。

---

## 阶段 5：测试子集选择与运行参数控制

### 目标

落实报告中的 Task 1.5，使用户可以控制运行范围，降低资源消耗并提升实验可管理性。

### 当前差距

- 当前 Official 和 RAJA 都是按默认方式整体构建、整体运行。
- 没有选择 kernel / benchmark 子集的接口。
- 没有“快速 smoke run”模式。

### 需要完成的功能

- 支持按 suite 定义测试子集。
- 支持不同粒度的过滤：
  - Official：目录、文件、正则、lit filter
  - RAJA：kernel list、variant list、运行模式
- 支持预定义 profile：
  - smoke
  - vectorization
  - microbenchmarks
  - full

### 需要修改/新增的代码或文件

- `config.yml`
- `workflow/Snakefile`
- `workflow/scripts/run_official.py`
- `workflow/scripts/run_raja.py`
- 新增：
  - `workflow/lib/test_selection.py`

### 具体修改内容

1. 为 Official 增加配置字段：
   - `benchmark_filter`
   - `lit_args`
   - `test_paths`
   - `exclude_patterns`

2. 为 RAJA 增加配置字段：
   - `kernel_groups`
   - `variants`
   - `extra_args`
   - `problem_sizes`

3. 修改 run 脚本，使其将配置转换成真实命令参数。

4. 在结果目录或 manifest 中记录本次选择了哪些子集，避免报告失去上下文。

5. 增加“快速验证目标”：
   - 少量 Official 测试
   - 少量 RAJA kernels
   - 用于改代码后的快速回归

### 验收标准

- 用户能通过配置只跑 TSVC 或只跑 RAJA 中的某类 kernels。
- smoke profile 能在明显更短时间内完成一次完整流程。
- 报告中能看到这次结果是基于哪个子集生成的。

---

## 阶段 6：结果聚合、差异分析与自动回归检测

### 目标

落实报告中的 Task 3.1，把系统从“收集结果”升级为“自动发现变化”的分析工具。

### 当前差距

- `workflow/lib/reporting.py` 只有均值/标准差聚合。
- 没有版本间差异计算。
- 没有基准版本概念。
- 没有阈值过滤和回归榜单。
- 历史 run 还不能方便地作为对比输入集合被显式选择和复用。

### 需要完成的功能

- 提供版本对比分析。
- 自动检测改善和回归。
- 支持用户设定显著变化阈值。
- 生成可直接写入论文分析部分的数据表。
- 支持从多个历史 run 选择输入数据，而不是只依赖当前一次执行的输出。

### 需要修改/新增的代码或文件

- `workflow/lib/reporting.py`
- 新增：
  - `workflow/lib/regression_analysis.py`
  - `workflow/scripts/compare_versions_cli.py`

### 具体修改内容

1. 定义比较模型：
   - baseline 版本
   - candidate 版本
   - suite
   - test_name
   - metric
   - absolute delta
   - relative delta
   - direction

2. 支持多指标比较：
   - `exec_time`
   - `compile_time`
   - `binary_size`
   - `bandwidth_gib`
   - `flops_gflops`

3. 增加阈值过滤：
   - 例如执行时间变化超过 5%
   - GFLOP/s 下降超过 3%

4. 生成分析输出：
   - `regressions.csv`
   - `improvements.csv`
   - `comparison_summary.json`

5. 增加“最值得关注的 kernels”榜单：
   - Top regressions
   - Top improvements
   - 波动最大测试

6. 扩展输入模型：
   - 支持按 `run_label` 列表读取多个历史 parsed 文件
   - 或从 `results/` 中按条件重建比较输入
   - 明确区分“单次实验报告输入”和“跨 run 比较输入”

### 验收标准

- 用户能指定基准 LLVM 版本并自动生成回归列表。
- 用户能从已有历史 run 中选择比较对象，而不需要重新执行 benchmark。
- 结果表可以直接支撑论文中“性能变化分析”章节。

---

## 阶段 7：报告系统升级与交互式可视化

### 目标

落实报告中的 Task 1.6 和 Future Work 中的高级展示能力，让报告从演示图升级为分析界面。

### 当前差距

- 目前图表固定，只有两个子图。
- 缺少筛选、搜索、对比和失败项展示。
- 尚未突出多版本、多轮次、变化阈值分析的价值。
- 报告入口仍主要围绕当前 run 输出，缺少“对历史 run 重新出报告”的显式工作流。

### 需要完成的功能

- 改进静态 HTML 报告。
- 增加交互过滤和多视图展示。
- 如果时间允许，再追加轻量 Web App。
- 支持历史 run 的报告重生成与历史 run 对比报告。

### 需要修改/新增的代码或文件

- `workflow/lib/reporting.py`
- `workflow/scripts/generate_report_cli.py`
- 可能新增：
  - `workflow/lib/report_views.py`
  - `app/streamlit_app.py` 或 `app/dash_app.py`

### 具体修改内容

1. 静态报告至少增加以下视图：
   - 版本总览页
   - Official suite 视图
   - RAJA 视图
   - 回归/改善排行榜
   - 失败与缺失结果视图

2. 图表建议：
   - 多版本柱状图替代部分折线图
   - 盒图/小提琴图展示重复运行分布
   - 热力图展示版本-测试矩阵
   - 散点图展示性能与编译时间/二进制大小的关系

3. 交互能力：
   - 按 suite 过滤
   - 按 kernel/test_name 搜索
   - 按 metric 切换
   - 按版本选择 baseline/candidate
   - 仅显示显著变化项

4. 视觉与可读性增强：
   - 明确标注 lower-is-better / higher-is-better
   - 用颜色高亮 regression / improvement
   - 增加数据表导出按钮

5. 如果进入 Web App 阶段：
   - 首选 Streamlit，降低维护成本。
   - 页面聚焦结果筛选与对比，不做复杂后端。

6. 增加历史报告工作流：
   - 允许用户指定一个已有 `run_label` 直接重建 HTML 报告
   - 允许用户选择多个历史 run 生成对比报告
   - 在报告首页展示数据来源 run、生成时间和输入文件摘要

### 验收标准

- 静态报告不再局限于两个固定图。
- 用户能在报告中快速定位某个 kernel 或某类 benchmark。
- 回归和改善项在界面上可直接识别。
- 历史 run 的报告可以在不重跑 benchmark 的前提下重新生成。

---

## 阶段 8：重复实验、统计显著性与噪声控制

### 目标

把 `run_label` 从“保留多次结果”推进到“支持统计结论”，覆盖 Future Work 中的 repeated runs 和 significance testing。

### 当前差距

- 已保留 run_label，但没有自动重复执行 orchestration。
- 聚合只有 `mean/std/count`，且没有显著性判断。
- 缺少环境稳定性记录，不利于解释噪声。

### 需要完成的功能

- 自动重复运行指定实验若干次。
- 聚合时加入统计检验。
- 为论文分析输出更稳健的结论。

### 需要修改/新增的代码或文件

- `workflow/Snakefile`
- `workflow/lib/reporting.py`
- 新增：
  - `workflow/lib/statistics.py`
  - `workflow/scripts/run_batch_cli.py`

### 具体修改内容

1. 提供重复实验配置：
   - `repeat_count`
   - `repeat_labels`
   - `warmup_runs`

2. 记录噪声控制元数据：
   - CPU 型号
   - 核数
   - 负载快照
   - 内存大小
   - 线程数
   - OpenMP 环境变量

3. 统计分析输出：
   - 均值
   - 标准差
   - 变异系数
   - 置信区间
   - t-test / Mann-Whitney 等简单检验

4. 对比时区分：
   - 单次观测变化
   - 统计上显著的变化

### 验收标准

- 同一版本可自动跑多轮，不需要手动改 `run_label`。
- 报告和分析结果能区分“真实变化”和“噪声波动”。

---

## 阶段 9：平台抽象与 HPC 可移植性支持

### 目标

为 EIDF VM 与 ARCHER2 验证做准备，避免平台差异硬编码在脚本里。

### 当前差距

- 当前工作流默认面向单机 Linux 环境。
- 没有平台 profile、module load 层、调度系统适配说明。
- 对不同平台的编译器、Python、Snakemake profile 缺少抽象。

### 需要完成的功能

- 引入平台配置层。
- 区分本地/EIDF/ARCHER2 的路径、编译器和运行方式。
- 为 HPC 环境增加 profile 和文档。

### 需要修改/新增的代码或文件

- `config.yml`
- `workflow/lib/common.py`
- 新增：
  - `profiles/eidf/`
  - `profiles/archer2/`
  - `env/` 或 `scripts/platform/`
  - `docs/platforms.md`

### 具体修改内容

1. 增加平台配置字段：
   - `platform.name`
   - `platform.module_commands`
   - `platform.env`
   - `platform.snakemake_profile`

2. 对运行命令增加环境注入能力。

3. 针对 ARCHER2 准备：
   - 作业脚本模板
   - profile 示例
   - 并行度与资源请求说明

4. 在结果元数据中写入平台信息，防止不同机器结果混淆。

### 验收标准

- 本地/EIDF/ARCHER2 至少有清晰的配置模板。
- 平台切换主要通过配置完成，而不是修改 Python 代码。

---

## 阶段 10：自动版本监控与持续执行

### 目标

覆盖报告中的可选任务 2.2，为长期趋势跟踪提供自动入口。

### 当前差距

- 尚无自动检测 LLVM 新版本的机制。
- 尚无定时触发工作流的入口。
- 尚无自动摘要通知。

### 需要完成的功能

- 周期性检测 LLVM 新 tag 或 commit。
- 检测到新版本后自动生成实验任务。
- 自动产出摘要。

### 需要修改/新增的代码或文件

- 新增：
  - `workflow/scripts/check_new_llvm_versions.py`
  - `.gitlab-ci.yml` 或 `ci/` 目录
  - `cron/` 示例脚本

### 具体修改内容

1. 版本检测脚本：
   - 查询远程 tags
   - 与本地已跑版本比对
   - 输出待跑列表

2. 自动生成实验配置：
   - 可生成新 `run_label`
   - 指定 baseline 比较版本

3. CI/CRON 任务：
   - 定时检测
   - 触发 Snakemake
   - 保存 logs 与 reports

4. 自动摘要输出：
   - 新版本是否成功构建
   - 有无显著 regression

### 验收标准

- 在不手工编辑配置的前提下，系统可以发现并触发新版本实验。

---

## 阶段 11：用户扩展能力与新测试套件接入

### 目标

覆盖 Future Work 中的“用户自定义测试集”和“新增 HPC benchmark suites”。

### 当前差距

- 当前 suite 类型在代码中是写死的：`official` 和 `raja`。
- 没有 suite plugin 或 adapter 注册机制。
- 没有用户提供自定义测试集的入口。

### 需要完成的功能

- 建立 suite adapter 注册模型。
- 支持新增 benchmark suite 而不大改核心 DAG。
- 支持用户指定自定义代码集或外部测试目录。

### 需要修改/新增的代码或文件

- `workflow/Snakefile`
- `workflow/lib/parse_results.py`
- 新增：
  - `workflow/lib/suites/`
  - `workflow/lib/suite_registry.py`
  - `workflow/lib/custom_suite.py`

### 具体修改内容

1. 抽象 suite 接口：
   - checkout strategy
   - build strategy
   - run strategy
   - parse strategy

2. 为未来扩展预留 suite 类型：
   - OpenMP micro-benchmarks
   - SOLLVE OMPVV
   - 用户自定义 lit tests

3. 允许用户通过配置声明：
   - 本地源码目录
   - 构建命令模板
   - 结果文件模式

### 验收标准

- 新增第三类 suite 时，不需要复制整套 Official/RAJA 逻辑再大改主流程。

---

## 阶段 12：工程质量、测试与最终交付准备

### 目标

为论文提交和项目收尾做准备，确保代码、文档、结果和操作手册完整。

### 当前差距

- 缺少自动化测试。
- 缺少配置校验测试。
- 缺少报告回归测试。
- 缺少结果复现指南和故障排查清单。

### 需要完成的功能

- 建立基本测试体系。
- 收敛 CLI 接口。
- 完善 README 和运行手册。
- 为最终论文写作提供稳定材料。

### 需要修改/新增的代码或文件

- 新增：
  - `tests/`
  - `pytest.ini`
  - `requirements-dev.txt` 或等价开发依赖文档
  - `docs/troubleshooting.md`
  - `docs/reproducibility.md`

### 具体修改内容

1. 测试覆盖至少包括：
   - 配置归一化
   - 路径布局
   - parser 对样例数据的解析
   - 聚合逻辑
   - 差异分析逻辑

2. 对报告生成增加最小回归测试：
   - 给定样例表格能生成 HTML
   - 关键列缺失时给出明确错误

3. 整理最终文档：
   - 快速开始
   - 平台差异
   - 常见失败
   - 如何只重跑失败项
   - 如何添加新版本
   - 如何导出论文用图表

4. 结果归档建议：
   - 保存最终配置
   - 保存关键对比表
   - 保存关键图表截图或导出文件

### 验收标准

- 仓库可以被作为一个完整毕业项目交付，而不是只有“作者自己能跑”的代码。

## 6. 推荐的近期优先级

按当前代码和时间节点，建议优先顺序如下：

1. 阶段 1：配置模型升级与多版本矩阵执行
2. 阶段 2：Snakemake 内聚的可观测性、恢复与实验元数据
3. 阶段 4：数据解析层重构与多格式适配
4. 阶段 5：测试子集选择与运行参数控制
5. 阶段 3：构建缓存、清理策略与资源管理
6. 历史运行数据重解析 / 重聚合 / 重出报告能力
7. 阶段 6：差异分析与自动回归检测
8. 阶段 7：报告系统升级
9. 阶段 8：重复实验与统计显著性
10. 阶段 9：平台抽象与 HPC 支持
11. 阶段 10：自动版本监控
12. 阶段 11：自定义 suite 扩展
13. 阶段 12：工程质量与最终交付

这样排序的原因是：

- 如果不先解决矩阵执行、Snakemake 内聚的恢复体验、解析兼容和测试子集，后面的大规模数据采集会很痛苦。
- 如果不能稳定复用历史 run，后续调报告、补 parser、做比较分析时会被迫重复运行 benchmark，成本过高。
- 报告增强和统计分析要建立在稳定的数据层之上。
- 自动监控和新 suite 扩展对毕业项目是加分项，但不是当前最急的堵点。

## 7. 建议的里程碑交付物

建议把后续开发拆成以下里程碑：

### 里程碑 A：基础设施可用于批量实验

- 已支持多 LLVM 版本矩阵运行
- 已支持清晰失败诊断、产物摘要与 Snakemake target 级补跑
- 已支持 test subset
- 已支持从历史 run 重建 parsed / aggregated / report
- parser 对当前目标版本稳定

### 里程碑 B：可用于正式数据采集

- 已具备构建缓存与磁盘管理
- 已具备平台配置抽象
- 已具备重复实验入口
- 已能稳定导出标准化表格

### 里程碑 C：可用于论文分析

- 已具备版本比较与回归检测
- 已具备改进后的交互式报告
- 已具备显著性分析
- 已能复用历史 run 生成比较输入与对比报告
- 已能产出关键图表和结论表

### 里程碑 D：可作为完整项目交付

- 已具备文档、测试、平台说明
- 已具备自动监控或至少其原型
- 已具备扩展新 suite 的基础架构

## 8. 结论

当前项目已经完成了最关键的一步：从“单个 Python 脚本驱动的流水线”转向“具有清晰 DAG 的 Snakemake 工作流”。这说明项目已经不再停留在概念验证，而是进入了工程化收敛阶段。

接下来的关键，不是再去零散地补几个功能点，而是围绕以下主线持续推进：

- 让实验配置真正可扩展
- 让批量运行真正可恢复
- 让结果解析真正可兼容
- 让报告真正服务于性能变化分析

只要优先把这四条主线打稳，`pp_report.pdf` 中提到的 MVP、work plan 和绝大多数 future work 都可以在同一套架构上自然落地。
