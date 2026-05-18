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

结合 `workflow/` 和 `auto/` 当前状态，可以把现有系统理解为一个“Snakemake 阶段二后基线版”，已经具备以下能力：

- 已从单体 Python orchestration 迁移为 Snakemake DAG。
- 已实现 LLVM、Official test-suite、RAJAPerf 的 checkout / build / run / parse / aggregate / report 全流程。
- 已引入参数化目录布局，支持按 `llvm_tag`、suite tag、`run_label` 复用源码/构建/结果，并按 `experiment_id` 隔离解析结果、报告、元数据和实验级日志。
- 已能生成统一表格数据：
  - `auto/parsed/<experiment_id>/benchmark_records.csv`
  - `auto/parsed/<experiment_id>/benchmark_records_aggregated.csv`
- 已能生成 Plotly HTML 报告：
  - `auto/reports/<experiment_id>/benchmark_report.html`
- 已支持 simple matrix mode 和 explicit experiment mode，可以从配置展开多实验矩阵和重复运行标签。
- 已为每个 experiment 生成 `auto/metadata/<experiment_id>/experiment.json`，并提供只读 inspect 命令辅助查看已有产物。
- 已通过 `run.sh` 固化常用入口：默认 `--keep-going`、`resume`、`strict`、`dry-run`、`inspect`。
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

1. 构建缓存策略仍偏保守。
   当前 `build_with_cmake()` 默认清空 build 目录，会削弱同版本重跑、补跑和多实验复用的价值。

2. 资源与磁盘可观测性不足。
   benchmark 已做独占调度，构建并行度也已有基础配置，但系统还缺少 build/install/results 的磁盘占用摘要，以及面向大规模采集的资源使用说明。

3. 数据解析层对格式变化的适应能力有限。
   当前 parser 基本依赖固定文件名、固定字段名，对不同 suite 版本、字段缺失、格式升级的兼容较弱。

4. 测试子集选择功能尚未实现。
   报告和 work plan 都明确提到要支持用户控制测试范围，以减少运行时间、输出体积和资源消耗。

5. 历史运行数据复用能力还不完整。
   当前可以通过 Snakemake target 从已有原始结果重建派生产物，也能通过 inspect 查看 metadata-backed experiment，但系统仍缺少：
   - 面向多个历史 experiment 的显式对比输入模型
   - 面向历史 experiment/run 的更友好筛选入口
   - 面向跨 run 复用和比较的数据选择模型

6. 可视化还处于演示版。
   当前图表固定、过滤能力弱，尚未支持 kernel 级交互、对比模式、差异高亮、失败结果展示等。

7. 自动性能变化检测尚未开始。
   目前只有聚合均值，没有“版本对版本”的差异分析引擎，也没有阈值过滤。

8. 重复实验和统计显著性尚未形成闭环。
   当前配置模型已支持 `repeat_count` 展开多个 run label，但系统还没有：
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
- 继续明确“仅重跑失败版本/失败 suite”的推荐 Snakemake target 用法。
- 增强从历史 experiment/run 重建派生产物的选择模型，例如按 metadata 条件选择 parsed/aggregated/report 输入。
- 增加数据清洗规则，自动识别异常值、空结果、编译失败和运行崩溃。
- 持续整理 `workflow/lib/` 的模块边界，避免 `common.py` 再次变成混合配置、路径、构建和 suite 细节的工具箱。

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
- 现在所处时间点（`2026-05-18`，阶段 2 已完成，准备进入阶段 3）

---

## 阶段 0：基线固化与现状清理

### 目标

在继续扩展功能前，把当前 Snakemake 版本固化为一个清晰、可测试、可回归的基线，避免后面一边改架构一边失去参考点。

### 当前状态

阶段 0 已基本完成。当前文档和配置已经能支持单版本/单实验的基本运行、dry-run 检查、目录布局理解和恢复入口说明。后续如果修改 README 或 docs，应以当前 simple/explicit 配置结构和 `experiment_id` 目录布局为准，不再回到阶段一早期的旧描述。

### 已完成的功能

- 补充当前架构说明文档。
- 固化一套最小演示配置和样例输出。
- 标记当前系统已知限制。
- 把“能成功跑通的配置”与“仅设想支持但未真正实现的能力”区分清楚。

### 已修改/新增的代码或文件

- `README.md`
  - 增补当前限制说明：暂无 test subset、暂无统计显著性分析、暂无自动监控。
- 新增 `docs/` 或扩展根目录文档
  - 增加运行样例、目录布局说明、日志定位说明。
- `config.yml`
  - 增加注释模板，说明哪些字段已支持、哪些字段是计划支持。

### 已完成的具体修改

- 把当前 `workflow` 的输入、输出、日志路径写成稳定文档。
- 记录 `auto/` 中已跑通样例的参数组合作为回归基线。
- 补一个 `--dry-run` 示例和一个“仅生成报告”的示例。

### 验收标准

- 新成员只看文档即可跑通一次单版本流程。
- 文档中不会继续使用阶段一早期的旧路径或旧配置写法误导读者。

---

## 阶段 1：配置模型升级与多版本矩阵执行

### 目标

把“配置层支持多个版本”从名义支持变成真实支持，为后续大规模采集和跨版本比较打基础。

### 当前状态

阶段 1 已完成。当前系统已经支持 simple matrix mode 和 explicit experiment mode，不再只取 `tags[0]`。`Snakefile` 会基于归一化后的 `experiments` 列表生成最终报告目标，并使用 `experiment_id` 管理每个实验的 parsed/report/metadata 输出。

### 已完成的功能

- 真正支持多版本矩阵展开。
- 支持显式定义实验组合。
- 支持多次重复运行。
- 为每个组合生成独立目录和独立结果。

### 已修改/新增的代码或文件

- `workflow/Snakefile`
- `workflow/lib/common.py`
- 可能新增：
  - 当前实现暂未单独拆出 `experiment_matrix.py` / `config_schema.py`，实验归一化仍在 `common.py` 中。

### 已完成的具体修改

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

### 已引入的配置字段

- `runs.labels`
- `runs.repeat_count`
- `project.default_platform`
- `experiments[]`
- `build_profile` 字段已预留在 experiment 元数据中，但尚未形成实际构建参数模型。

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

### 当前状态

阶段 2 已完成。当前系统已经生成 experiment metadata，`generate_report` 依赖 metadata，`run.sh` 提供 `resume`、`strict`、`inspect` 等轻量入口，恢复方式保持 Snakemake-first，没有引入新的调度器或全局 mutable manifest。

### 已完成的功能

- 为每个 experiment 生成轻量元数据文件，记录配置、路径和环境摘要。
- 改善 rule 级日志和错误信息，使失败原因可以从对应日志中快速定位。
- 明确推荐的恢复方式：
  - 使用 Snakemake `--rerun-incomplete` 处理中断或半成品。
  - 使用 Snakemake `--keep-going` 让批量实验尽量跑完其它独立项。
  - 使用具体 target 只重建某个 experiment 的 parsed / aggregated / report。
  - 使用 `--forcerun` 或删除特定输出触发某个 rule 重跑。
- 增加轻量的状态/诊断辅助命令，只负责“读取现有文件并汇总”，不负责调度或修改状态。
- 把历史 experiment/run 恢复设计为普通 Snakemake target，而不是单独的恢复系统。

### 已修改/新增的代码或文件

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

## 阶段 3：构建缓存与资源可观测性

### 目标

解决当前构建缓存复用不足、构建配置边界不清、磁盘占用不透明的问题，为后续大规模版本采集打基础。

本阶段继续坚持 Snakemake-first 原则：缓存复用和资源控制应尽量通过现有 DAG、配置字段和 Snakemake resources 实现；磁盘和产物检查可以通过只读 helper 命令辅助完成；清理操作必须显式、保守，不在 DAG 中自动删除关键产物。

### 当前差距

- `build_with_cmake()` 默认 `clear_first=True`，会削弱缓存价值。
- LLVM、Official、RAJA 的 CMake 参数生成函数仍在 `common.py` 中，`common.py` 又开始承担 suite-specific 构建细节。
- 目前能通过 Snakemake `-j` 控制总体并发，也已经让 benchmark run 独占线程，但还没有单独控制“同时最多几个构建任务”的资源模型。
- 没有 build/install/results/parsed/reports 的磁盘占用摘要。
- 清理策略尚未文档化；如果未来提供清理工具，需要避免误删结果或绕过 Snakemake 的输出状态。

### 需要完成的功能

- 默认保留 build 缓存。
- 允许用户通过配置显式请求 clean build，而不是每次 build 自动清空目录。
- 将 suite-specific CMake 参数生成逻辑从 `common.py` 拆出。
- 使用 Snakemake resources 控制构建任务并发。
- 提供只读磁盘占用报告，帮助用户判断是否需要人工清理。
- 文档化安全清理边界：默认不自动删除源码、install、原始结果或报告。

### 需要修改/新增的代码或文件

- `workflow/lib/common.py`
- `workflow/lib/cmake_build.py`
- `workflow/Snakefile`
- `config.yml`
- `run.sh`
- 新增：
  - `workflow/lib/build_configs.py`
  - `tools/report_disk_usage.py`
  - 可选：`docs/storage.md` 或在现有恢复文档中增加磁盘与缓存说明

### 具体修改内容

1. 修改 `build_with_cmake()`：
   - 默认不清空构建目录。
   - 增加 `clean_first` / `clean_build` 参数，并只在配置显式开启时调用 `clear_directory()`。
   - 保持每次运行 CMake configure，因为重新 configure 不等于清空缓存；这样既能吸收 CMake 参数变化，又能保留 Ninja 增量构建能力。

2. 增加构建配置字段：
   - `build.clean_build`
   - `build.reconfigure`
   - `resources.build_slots`
   - `resources.benchmark_slots` 可选；如果继续使用 `threads` 独占 benchmark，可先不引入。

3. 在 `Snakefile` 中接入 Snakemake resources：
   - build 相关 rule 设置 `resources: build_slots=1`。
   - `run.sh` 可以传递默认 `--resources build_slots=1`，避免多个大型 build 同时竞争 CPU、内存和磁盘 IO。
   - 仍保留 `-j` 控制全局 job 并发，不另写调度逻辑。

4. 拆分构建参数模块：
   - `workflow/lib/cmake_build.py` 保持只负责通用 CMake/Ninja 执行流程。
   - 将 LLVM、Official、RAJA 的 CMake 参数生成函数从 `common.py` 移入 `workflow/lib/build_configs.py`。
   - 将 RAJA OpenMP 探测逻辑与 RAJA CMake 参数放在同一模块中，避免 `common.py` 承担 suite 细节。
   - 如果 build profile 后续进入配置模型，配置归一化层只保留 profile 名称和参数覆盖；具体 CMake 参数仍由构建配置模块解释。

5. 增加只读磁盘占用报告：
   - 提供 `tools/report_disk_usage.py` 或类似命令。
   - 通过 `./run.sh disk` 调用。
   - 输出以下目录占用：
     - `sources/`
     - `builds/`
     - `installs/`
     - `results/`
     - `parsed/`
     - `reports/`
     - `metadata/`
     - `logs/`
   - 报告单个 LLVM install、单个 suite build、单个 experiment 结果的占用，方便判断主要空间消耗来自哪里。

6. 暂缓自动清理工具：
   - 阶段 3 不新增会主动删除产物的 Snakemake rule。
   - 如确实需要清理脚本，应放在 `tools/`，默认 `--dry-run`，必须显式传入 `--execute` 才删除。
   - 清理脚本不作为默认入口，不隐藏 Snakemake incomplete/metadata 状态。

### 验收标准

- 二次运行相同版本时不会因为 build 目录被自动清空而无意义全量重编。
- 用户可以通过配置显式选择 clean build。
- 构建相关 CMake 参数不再放在 `common.py` 中。
- Snakemake 可以限制同时运行的 build job 数量。
- 系统能给出清晰的磁盘占用报告。
- 阶段 3 不引入自动删除关键产物的 DAG rule。

### 暂不纳入本阶段的内容

- 不做自动磁盘阈值阻断，例如 `disk_soft_limit_gb`。这类功能涉及检查时机、文件系统选择和并发写入后的空间变化，后续确有需求再加入 preflight。
- 不做“清理旧 install / 清理旧结果 / 清理旧日志”的自动策略。清理是破坏性操作，应等缓存布局、build profile 和正式数据归档规则稳定后再设计。
- 不在 Snakemake 之外实现资源调度器，避免重复 Snakemake 已有能力。

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
  - 可选：`workflow/lib/tables.py`
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

7. 模块边界整理：
   - 将 `BenchmarkMetrics`、`BenchmarkRecord` 等数据模型移入 `result_schema.py`。
   - 将 Official 和 RAJA 的文件发现、schema 检测和字段映射从 `parse_results.py` 中拆出。
   - 视情况把 `read_table` / `write_table` 这类通用表格 IO 抽到 `tables.py`，供 parser、reporting 和后续分析模块共享。

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
- 历史 experiment/run 还不能方便地作为对比输入集合被显式选择和复用。

### 需要完成的功能

- 提供版本对比分析。
- 自动检测改善和回归。
- 支持用户设定显著变化阈值。
- 生成可直接写入论文分析部分的数据表。
- 支持从多个历史 experiment/run 选择输入数据，而不是只依赖当前一次执行的输出。

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
   - 支持按 `experiment_id`、`run_label` 或 metadata 条件读取多个历史 parsed 文件
   - 或从 `results/` 中按条件重建比较输入
   - 明确区分“单次实验报告输入”和“跨 run 比较输入”

### 验收标准

- 用户能指定基准 LLVM 版本并自动生成回归列表。
- 用户能从已有历史 experiment/run 中选择比较对象，而不需要重新执行 benchmark。
- 结果表可以直接支撑论文中“性能变化分析”章节。

---

## 阶段 7：报告系统升级与交互式可视化

### 目标

落实报告中的 Task 1.6 和 Future Work 中的高级展示能力，让报告从演示图升级为分析界面。

### 当前差距

- 目前图表固定，只有两个子图。
- 缺少筛选、搜索、对比和失败项展示。
- 尚未突出多版本、多轮次、变化阈值分析的价值。
- 报告入口仍主要围绕单个 experiment 输出，缺少“对多个历史 experiment 生成组合报告”的显式工作流。

### 需要完成的功能

- 改进静态 HTML 报告。
- 增加交互过滤和多视图展示。
- 如果时间允许，再追加轻量 Web App。
- 支持历史 experiment 的报告重生成与历史 experiment 对比报告。

### 需要修改/新增的代码或文件

- `workflow/lib/reporting.py`
- `workflow/scripts/generate_report_cli.py`
- 可能新增：
  - `workflow/lib/analysis.py`
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
   - 允许用户指定一个已有 `experiment_id` 直接重建 HTML 报告
   - 将聚合分析逻辑与 Plotly 视图生成解耦，避免 `reporting.py` 同时承担 table IO、统计聚合和可视化布局。
   - 当差异分析和统计显著性加入后，优先把分析函数放入 `analysis.py`，报告模块只负责把分析结果渲染出来。
   - 允许用户选择多个历史 experiment/run 生成对比报告
   - 在报告首页展示数据来源 experiment/run、生成时间和输入文件摘要

### 验收标准

- 静态报告不再局限于两个固定图。
- 用户能在报告中快速定位某个 kernel 或某类 benchmark。
- 回归和改善项在界面上可直接识别。
- 历史 experiment 的报告可以在不重跑 benchmark 的前提下重新生成。

---

## 阶段 8：重复实验、统计显著性与噪声控制

### 目标

把当前的 `repeat_count` / `run_label` 机制从“能生成多次运行”推进到“能支持统计结论”，覆盖 Future Work 中的 repeated runs 和 significance testing。

### 当前差距

- 已支持通过 `repeat_count` 展开多个 run label，但聚合和报告还没有把这些重复运行组织成统计分析单元。
- 聚合只有 `mean/std/count`，且没有显著性判断。
- 缺少环境稳定性记录，不利于解释噪声。

### 需要完成的功能

- 将重复运行结果组织成可分析的统计样本。
- 聚合时加入统计检验。
- 为论文分析输出更稳健的结论。

### 需要修改/新增的代码或文件

- `workflow/lib/reporting.py`
- 新增：
  - `workflow/lib/statistics.py`
  - `workflow/scripts/compare_repeats_cli.py`

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

- 同一版本的多轮结果可被自动识别为同一个统计样本组。
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

4. 工程模块边界收尾：
   - 如果 `common.py` 仍包含大量配置归一化逻辑，将其拆到 `workflow/lib/experiments.py` 或 `workflow/lib/config_model.py`。
   - 保留 `common.py` 只放少量真正跨模块通用、且没有更明确归属的帮助函数；能归入 layout、cmake_build、build_configs、parser、analysis 的逻辑不再回流到 common。

5. 结果归档建议：
   - 保存最终配置
   - 保存关键对比表
   - 保存关键图表截图或导出文件

### 验收标准

- 仓库可以被作为一个完整毕业项目交付，而不是只有“作者自己能跑”的代码。

## 6. 推荐的近期优先级

按当前代码和时间节点，阶段 0、阶段 1、阶段 2 已作为基线完成。后续建议优先顺序如下：

1. 阶段 3：构建缓存与资源可观测性
2. 阶段 4：数据解析层重构与多格式适配
3. 阶段 5：测试子集选择与运行参数控制
4. 历史运行数据重解析 / 重聚合 / 重出报告能力
5. 阶段 6：差异分析与自动回归检测
6. 阶段 7：报告系统升级
7. 阶段 8：重复实验与统计显著性
8. 阶段 9：平台抽象与 HPC 支持
9. 阶段 10：自动版本监控
10. 阶段 11：自定义 suite 扩展
11. 阶段 12：工程质量与最终交付

这样排序的原因是：

- 阶段 3 先解决构建缓存和磁盘可见性，可以减少后续解析、测试子集和多版本采集时的无谓重编成本。
- 如果不能稳定复用历史 experiment/run，后续调报告、补 parser、做比较分析时会被迫重复运行 benchmark，成本过高。
- 报告增强和统计分析要建立在稳定的数据层之上。
- 自动监控和新 suite 扩展对毕业项目是加分项，但不是当前最急的堵点。

## 7. 建议的里程碑交付物

建议把后续开发拆成以下里程碑：

### 里程碑 A：基础设施可用于批量实验

- 已支持多 LLVM 版本矩阵运行
- 已支持清晰失败诊断、产物摘要与 Snakemake target 级补跑
- 已支持 test subset
- 已支持从历史 experiment/run 重建 parsed / aggregated / report
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
- 已能复用历史 experiment/run 生成比较输入与对比报告
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
