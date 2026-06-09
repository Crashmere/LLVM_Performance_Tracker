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
- 已实现 LLVM、Official test-suite、RAJAPerf 的 checkout / build / run / parse / analyze / report 全流程。
- 已引入参数化目录布局，支持按 `llvm_tag`、suite tag、全局 `label` 复用源码/构建/结果，并按 `experiment_id` 隔离解析结果、报告、元数据和实验级日志。
- 已能生成统一表格数据：
  - `auto/parsed/<experiment_id>/benchmark_records.csv`
- 已能生成全量分析数据：
  - `auto/analysis/analysis_records.csv`
  - `auto/analysis/analysis_summary.json`
- 已能生成 Plotly HTML 报告：
  - `auto/reports/<experiment_id>/benchmark_report.html`
- 已支持 simple matrix mode 和 explicit experiment mode，可以从配置展开多实验矩阵；全局 `label` 统一标识本次运行，未配置时自动使用时间戳。
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

5. 全量历史结果分析能力已有基础闭环。
   当前主流水线已经可以扫描 `auto/` 中保留的可用 parsed 结果并构建统一 analysis dataset；后续重点应放在更好的可视化呈现和更细的对比视图上。

6. 可视化还处于演示版。
   当前图表固定、过滤能力弱，尚未支持 kernel 级交互、对比模式、差异高亮、失败结果展示等。

7. 自动性能变化检测已有轻量实现。
   当前系统已经能基于全量 analysis dataset 做阈值过滤、样本统计和候选 regression / improvement 分类；复杂显著性检验暂不作为主线需求，避免在报告系统成熟前引入过重的统计分支。

8. HPC 环境可移植性支持仍不完整。
   报告计划中包括 EIDF VM 与 ARCHER2 的可移植性验证，但当前工作流没有显式环境抽象、模块加载层或平台配置层。

9. 自动监控与持续执行尚未实现。
   尚无 CRON / GitLab CI 驱动的新版本检测与自动触发。

10. 工程性基础设施仍偏弱。
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
- 增强从历史 experiment 重建派生产物的说明，但分析主线默认基于 `auto/` 中保留的全部可用结果。
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
- 为每个组合生成独立目录和独立结果。

### 已修改/新增的代码或文件

- `workflow/Snakefile`
- `workflow/lib/common.py`
- 可能新增：
  - 当前实现暂未单独拆出 `experiment_matrix.py` / `config_schema.py`，实验归一化仍在 `common.py` 中。

### 已完成的具体修改

1. 扩展配置结构，当前支持两种模式：
   - 简单模式：
     - `llvm.tags`
     - `test_suite.official.tags`
     - `test_suite.raja.tags`
   - 显式实验矩阵模式：
     - `experiments:`
       - 每项明确定义 `llvm_tag`、`official_tag`、`raja_tag`、可选平台和参数覆盖。
   - 全局公共配置：
     - `label`
       - 统一标识本次运行；不配置时自动生成时间戳。

2. 在 `common.py` 中新增配置归一化逻辑：
   - 统一生成实验列表。
   - 校验 tag、label、组合重复项。
   - 给每个实验分配稳定 ID。

3. 在 `Snakefile` 中用 `expand()` 驱动最终目标：
   - 对每个实验组合生成结果和报告目标。
   - 让 checkout/build/run/parse/report 都基于 wildcard。

4. 明确 source/build/install 缓存策略：
   - LLVM install 可按 `llvm_tag` 复用。
   - Official/RAJA build 可按 `suite_tag + llvm_version` 复用。
   - 运行结果必须按全局 `label` 隔离。

### 已引入的配置字段

- `label`
- `project.default_platform`
- `experiments[]`

### 验收标准

- 同一命令可以一次性跑多个 LLVM 版本。
- 多个版本共享已有 source/build/install，不重复 checkout 和全量重编。
- 同一配置下未显式设置 `label` 时，会用时间戳生成新的结果目录，避免覆盖上一次运行。

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
  - 使用具体 target 只重建某个 experiment 的 parsed / report，或重建全局 analysis。
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
   - 内容包括：`experiment_id`、`llvm_tag`、`official_tag`、`raja_tag`、`label`、`platform`、关键输出路径、日志路径、配置快照、生成时间。
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
   - 输出每个 experiment 的产物存在性摘要，例如 raw results、parsed、report 是否存在。
   - 这个命令不生成调度计划、不写状态、不重跑任务，只帮助用户决定下一条 Snakemake 命令。

5. 明确恢复和补跑模式全部映射为 Snakemake 用法。
   - 中断后继续：`./run.sh resume`
   - 批量尽量继续：`./run.sh` 默认传递 `--keep-going`
   - 失败立即停止：`./run.sh strict`
   - 只重建某个报告：`./run.sh -- auto/reports/<experiment_id>/benchmark_report.html`
   - 只重跑某个规则：`./run.sh -- --forcerun run_raja auto/reports/<experiment_id>/benchmark_report.html`
   - 已有原始结果时重建派生产物：直接指定对应 parsed、report 或 analysis target。

6. 文档化“不要做”的边界。
   - 不做全局 mutable manifest 状态机。
   - 不做独立 retry 调度器。
   - 不在脚本里绕过 Snakemake 直接调用多个 workflow stage。
   - 不让 helper CLI 修改 Snakemake 输出或隐藏真实失败。

### 验收标准

- 每个最终报告都能追溯到一份 experiment metadata。
- 运行失败时，用户能从 Snakemake 报错定位到对应日志，并在日志中看到清楚的失败命令和期望产物。
- `./run.sh` 默认 `--keep-going`、`./run.sh resume` 和 `./run.sh strict` 被文档化并验证可用。
- 用户可以通过指定 Snakemake target，只重建某个 experiment 的 parsed / report，或重建全局 analysis，而不重新 checkout/build/run。
- 汇总命令能列出各 experiment 的关键产物存在性，帮助判断缺的是 raw results、parsed 还是 report。
- 阶段 2 完成后，主入口仍然是 Snakemake / `run.sh`，没有引入新的主调度入口。

---

## 阶段 3：构建缓存与磁盘可观测性

### 目标

解决当前构建缓存复用不足、构建配置边界不清、磁盘占用不透明的问题，为后续大规模版本采集打基础。

本阶段继续坚持 Snakemake-first 原则：缓存复用通过现有 DAG 和配置字段实现；整体并发继续交给 Snakemake 原生 `-j` 选项控制；磁盘和产物检查可以通过只读 helper 命令辅助完成；清理操作必须显式、保守，不在 DAG 中自动删除关键产物。

### 当前状态

阶段 3 已完成。当前系统默认保留 build 目录，支持通过配置显式 clean build，构建参数已从 `common.py` 拆入 `build_configs.py`，并通过 `run.sh disk` 只读查看磁盘占用。构建并发不引入额外资源配置，继续由 Snakemake `-j` 统一控制。

### 已解决的差距

- `build_with_cmake()` 默认 `clear_first=True`，会削弱缓存价值。
- LLVM、Official、RAJA 的 CMake 参数生成函数仍在 `common.py` 中，`common.py` 又开始承担 suite-specific 构建细节。
- 目前通过 Snakemake `-j` 控制总体并发，benchmark run 已做独占线程处理；阶段 3 不再增加额外的构建并发配置。
- 没有 build/install/results/parsed/reports 的磁盘占用摘要。
- 清理策略尚未文档化；如果未来提供清理工具，需要避免误删结果或绕过 Snakemake 的输出状态。

### 已完成的功能

- 默认保留 build 缓存。
- 允许用户通过配置显式请求 clean build，而不是每次 build 自动清空目录。
- 将 suite-specific CMake 参数生成逻辑从 `common.py` 拆出。
- 保持并发模型简单：使用 Snakemake `-j` 控制整体并发，不新增构建专用资源配置。
- 提供只读磁盘占用报告，帮助用户判断是否需要人工清理。
- 文档化安全清理边界：默认不自动删除源码、install、原始结果或报告。

### 已修改/新增的代码或文件

- `workflow/lib/common.py`
- `workflow/lib/cmake_build.py`
- `workflow/Snakefile`
- `config.yml`
- `run.sh`
- 新增：
  - `workflow/lib/build_configs.py`
  - `tools/report_disk_usage.py`
  - 可选：`docs/storage.md` 或在现有恢复文档中增加磁盘与缓存说明

### 已完成的具体修改

1. 修改 `build_with_cmake()`：
   - 默认不清空构建目录。
   - 增加 `clean_first` / `clean_build` 参数，并只在配置显式开启时调用 `clear_directory()`。
   - 保持每次运行 CMake configure，因为重新 configure 不等于清空缓存；这样既能吸收 CMake 参数变化，又能保留 Ninja 增量构建能力。

2. 增加构建配置字段：
   - `build.clean_build`
   - `build.reconfigure`

3. 保持 Snakemake 原生并发控制：
   - 不新增构建专用资源字段。
   - 继续使用 `run.sh` 中的 `-j 2` 默认值控制全局 job 并发。
   - 如需调整并发，用户直接通过 Snakemake 参数或修改 `run.sh` 的 `DEFAULT_JOBS` 控制。

4. 拆分构建参数模块：
   - `workflow/lib/cmake_build.py` 保持只负责通用 CMake/Ninja 执行流程。
   - 将 LLVM、Official、RAJA 的 CMake 参数生成函数从 `common.py` 移入 `workflow/lib/build_configs.py`。
   - 将 RAJA OpenMP 探测逻辑与 RAJA CMake 参数放在同一模块中，避免 `common.py` 承担 suite 细节。

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
- Snakemake 并发控制保持简单，没有引入额外 build slot 配置。
- 系统能给出清晰的磁盘占用报告。
- 阶段 3 不引入自动删除关键产物的 DAG rule。

### 暂不纳入本阶段的内容

- 不做自动磁盘阈值阻断，例如 `disk_soft_limit_gb`。这类功能涉及检查时机、文件系统选择和并发写入后的空间变化，后续确有需求再加入 preflight。
- 不做“清理旧 install / 清理旧结果 / 清理旧日志”的自动策略。清理是破坏性操作，应等缓存布局和正式数据归档规则稳定后再设计。
- 不在 Snakemake 之外实现资源调度器，避免重复 Snakemake 已有能力。

---

## 阶段 4：数据解析层重构与多格式适配

### 目标

完成报告中 Task 1.4 的核心要求，让 parser 对 suite 版本变化、字段缺失、异常结果更稳健。

本阶段的直接触发案例是 RAJAPerf `v2025.03.0` 的真实失败运行：该版本正常执行并生成 `RAJAPerf-timing-Average.csv`、`RAJAPerf-speedup-Average.csv`、`RAJAPerf-fom.csv`、`RAJAPerf-kernels.csv`，但没有生成当前工作流硬编码期待的 `RAJAPerf-kernel-run-data.csv`，导致失败被归类为 `run_raja` 失败，而不是解析层发现了“不支持的 RAJA 输出 schema”。

因此阶段 4 的核心目标不是简单增加字段兼容，而是重新划清边界：

- `run_*` 阶段只负责确认 benchmark 程序运行完成，并记录原始输出目录中出现了哪些结果文件。
- `parse_results` 阶段负责发现、识别和解析具体结果格式。
- 版本/格式差异通过 parser adapter 处理，而不是继续写死在 `Snakefile` 或 run 脚本中。

### 当前差距

- `workflow/lib/parse_results.py` 仍以“固定文件名 + 固定字段名”为主。
- `workflow/Snakefile` 和 `workflow/scripts/run_raja.py` 都把 `RAJAPerf-kernel-run-data.csv` 当成 RAJA run 成功的唯一标志。
- RAJA 新格式 `RAJAPerf-kernel-run-data.csv` 是长表格式，当前 parser 能够隐式解析。
- RAJA 旧/不同格式 `RAJAPerf-timing-Average.csv` 是矩阵格式，当前 parser 不能解析。
- RAJA 不同格式可提供的指标不同：`kernel-run-data` 可提供 checksum、runtime、bandwidth、GFLOP/s；`timing-Average` 主要提供 runtime。
- 当前失败诊断落点不够准确：格式不支持时会表现为 run 阶段缺少输出文件，而不是 parse 阶段报告 unsupported schema。
- 解析逻辑把 suite 版本和目录命名耦合在一起，缺少基于文件内容的 schema 检测。
- 缺少 schema version、字段映射层和兼容测试。

### 需要完成的功能

- 建立 parser adapter 层。
- 支持 RAJA 至少两种已观察到的输出格式：
  - `RAJAPerf-kernel-run-data.csv`
  - `RAJAPerf-timing-Average.csv`
- 支持不同 suite 版本的字段兼容和格式识别。
- 支持部分缺失字段时降级解析而不是整体失败。
- 把“测试失败/崩溃/无结果”纳入统一记录模型。
- 提供清晰的 unsupported schema 错误信息，包括结果目录、已发现文件、期望格式和建议检查的日志。

### 需要修改/新增的代码或文件

- `workflow/Snakefile`
- `workflow/lib/parse_results.py`
- `workflow/scripts/run_raja.py`
- `workflow/scripts/write_experiment_metadata.py`
- 新增：
  - `workflow/lib/parsers/base.py`
  - `workflow/lib/parsers/official.py`
  - `workflow/lib/parsers/raja.py`
  - `workflow/lib/result_schema.py`
  - 可选：`workflow/lib/tables.py`

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

3. 调整 RAJA run 和 parse 的职责边界。
   - `run_raja` 不再要求固定产物必须是 `RAJAPerf-kernel-run-data.csv`。
   - `run_raja` 应在 RAJAPerf 程序返回成功后扫描结果目录，确认至少存在一个受支持或可诊断的 RAJA 输出文件。
   - `.run_complete` 中记录本次发现的 RAJAPerf 输出文件列表。
   - `Snakefile` 中 `run_raja` 的显式输出应避免绑定到某一个格式文件；可以改为结果目录 + `.run_complete`，或只把 `.run_complete` 作为下游依赖。
   - `parse_results` 从 RAJA result directory 中进行文件发现，而不是依赖单一 CSV 文件路径。

4. 对 RAJA 建立两个首批 adapter。
   - `KernelRunDataAdapter`
     - 识别 `RAJAPerf-kernel-run-data.csv`。
     - 解析长表字段：`Kernel`、`Variant`、`Tuning`、`Checksum`、`Mean time per rep (sec.)`、`Mean Bandwidth (GiB per sec.)`、`Mean flops (gigaFLOP per sec.)`。
     - 作为信息最完整的优先格式。
   - `TimingAverageAdapter`
     - 识别 `RAJAPerf-timing-Average.csv`。
     - 解析矩阵式 header：第一行 report title，第二行 variant，第三行 tuning，后续行为 kernel。
     - 将矩阵拉平成统一记录：`kernel`、`variant`、`tuning`、`exec_time`。
     - 对 `Not run`、空值、非数值单元格做跳过或记录为非成功状态。
     - `status` 暂设为 `UNKNOWN` 或 `COMPLETED`，后续可结合 `RAJAPerf-checksum.txt` 补充。
     - `bandwidth_gib` 和 `flops_gflops` 在该格式下允许为空。

5. 建立 RAJA adapter 选择规则。
   - 如果同时存在 `RAJAPerf-kernel-run-data.csv` 和 `RAJAPerf-timing-Average.csv`，优先使用 `kernel-run-data`，因为指标更完整。
   - 如果只存在 `timing-Average`，降级解析 runtime。
   - 如果没有受支持的 RAJA 文件，则 parse 阶段失败，并输出可读诊断。
   - adapter 不应依赖 tag 名称判断格式，优先通过文件存在性和 header 内容检测。

6. 对 Official suite 重点处理：
   - JSON 中不同 test 类型字段差异
   - MicroBenchmarks 与普通 tests 的差异
   - 运行失败项、缺少 exec_time 项

7. 增加元数据列：
   - `suite_name`
   - `suite_version`
   - `compiler_tag`
   - `compiler_version`
   - `compiler_commit`
   - `label`
   - `platform`
   - `hostname`
   - `source_file`
   - `parser_adapter`
   - `status_detail`

8. 输出格式建议升级：
   - 继续保留 CSV，便于人工查看。
   - 暂不强制把 Parquet 变成默认输出；可以先保留可选支持，避免阶段 4 同时改变数据格式和解析架构。

9. 模块边界整理：
   - 将 `BenchmarkMetrics`、`BenchmarkRecord` 等数据模型移入 `result_schema.py`。
   - 将 Official 和 RAJA 的文件发现、schema 检测和字段映射从 `parse_results.py` 中拆出。
   - 视情况把 `read_table` / `write_table` 这类通用表格 IO 抽到 `tables.py`，供 parser、reporting 和后续分析模块共享。

### 验收标准

- 当前已观察到的 RAJA 新格式结果可以继续解析：
  - `RAJAPerf-kernel-run-data.csv`
- 当前已观察到的 RAJA `v2025.03.0` 旧/不同格式结果可以解析：
  - `RAJAPerf-timing-Average.csv`
- `v2025.03.0` 这类 RAJA 运行不应因为缺少 `RAJAPerf-kernel-run-data.csv` 在 `run_raja` 阶段失败；如果解析仍不支持某种格式，应在 `parse_results` 阶段给出清晰错误。
- `TimingAverageAdapter` 输出的 RAJA records 至少应包含 `suite_name`、`suite_version`、`compiler_version`、`label`、`test_name`、`exec_time`、`parser_adapter`、`source_file`。
- `KernelRunDataAdapter` 保留现有 runtime、bandwidth、GFLOP/s、checksum 信息。
- 对缺失字段会给 warning，不会整批解析失败。
- 使用已有真实输出验证关键路径：
  - 新格式 RAJA 长表解析。
  - 旧/不同格式 RAJA timing matrix 解析。
  - 新旧 RAJA 解析结果都能继续进入 aggregate/report。
  - 没有受支持 RAJA 文件时的错误信息清晰可读。

---

## 阶段 5：测试子集选择与运行参数控制

### 目标

落实报告中的 Task 1.5，使用户可以控制运行范围，降低资源消耗并提升实验可管理性。

阶段 5 建议拆成两层推进：

- 阶段 5A：先实现最小可用的运行参数透传和 selection provenance。
- 阶段 5B：在确认 Official lit 和 RAJAPerf 参数稳定后，再实现更高级的结构化 profile、kernel group 和过滤规则。

这样可以尽快得到“smoke run / 子集运行”的实际能力，同时避免过早设计一套复杂抽象，最后又被各 suite 的真实命令行参数细节推翻。

### 当前差距

- 当前 Official 和 RAJA 都是按默认方式整体构建、整体运行。
- `run_official.py` 中 lit 命令固定为 `lit -v -o <json> <build_dir>`，没有配置化附加参数。
- `run_raja.py` 中 RAJAPerf 命令固定为只执行 `raja-perf.exe`，没有配置化附加参数。
- 没有在 `.run_complete` 或 metadata 中记录本次运行是否使用了子集参数。
- 没有“快速 smoke run”模式。
- 当前阶段四已解决 RAJA 多输出格式解析，因此阶段五可以安全地让 run 阶段传递不同 RAJAPerf 参数，而不再依赖固定 raw CSV 文件名。

### 阶段 5A：最小可用运行参数透传

#### 目标

第一步只做两件事：

- 允许用户通过配置给 Official lit 和 RAJAPerf 追加原生命令行参数。
- 把这些参数写入 run stamp 和 experiment metadata，保证结果可以追溯。

这一版不尝试把所有 suite 参数抽象成统一语义。Official 先暴露 `lit_args`，RAJA 先暴露 `extra_args`，让用户可以直接使用上游工具已经支持的过滤方式。

#### 需要完成的功能

- 支持全局 test selection 配置。
- Official 支持透传 `lit_args`。
- RAJA 支持透传 `extra_args`。
- 运行 stamp 记录实际执行参数。
- experiment metadata 记录 selection 配置快照。
- 能通过配置写出一个较快的 smoke run。

#### 需要修改/新增的代码或文件

- `config.yml`
- `workflow/Snakefile`
- `workflow/scripts/run_official.py`
- `workflow/scripts/run_raja.py`
- `workflow/scripts/write_experiment_metadata.py`
- 可选新增：
  - `workflow/lib/test_selection.py`

#### 建议配置结构

建议先增加简单、直接、接近原生命令行的配置：

```yaml
test_selection:
  official:
    lit_args: []

  raja:
    extra_args: []
```

后续可以在注释中给出 smoke 示例，但第一版代码只需要读取 `lit_args` 和 `extra_args`。

#### 具体修改内容

1. 配置归一化。
   - 在 `common.py` 的配置归一化结果中加入 `test_selection`。
   - `official.lit_args` 默认为空列表。
   - `raja.extra_args` 默认为空列表。
   - 明确只接受 list，不做字符串拆分，避免 shell quoting 歧义。

2. Snakemake 参数传递。
   - `rule run_official` params 增加 `lit_args`。
   - `rule run_raja` params 增加 `extra_args`。
   - 保持 run rule 输出路径不随参数自动变化；是否复用 `label` 由用户负责。
   - 文档中提醒：同一个 `label` 下改变 selection 参数会覆盖或重用同一路径，因此正式实验应给不同 selection 使用不同 `label`。

3. Official run 脚本。
   - 当前命令：
     - `lit -v -o <result_path> <build_dir>`
   - 修改为：
     - `lit -v -o <result_path> <lit_args...> <build_dir>`
   - `.run_complete` 中记录 `lit_args`。

4. RAJA run 脚本。
   - 当前命令：
     - `raja-perf.exe`
   - 修改为：
     - `raja-perf.exe <extra_args...>`
   - `.run_complete` 中记录 `extra_args`。

5. Metadata。
   - `experiment.json` 中新增 `test_selection` 字段。
   - 记录 normalized selection，而不是只记录原始 config。
   - 后续报告可根据该字段显示本次使用的 Official/RAJA 参数。

6. smoke 配置示例。
   - 在 `config.yml` 注释中提供一个可切换的 smoke 示例。
   - 第一版可以只作为配置示例，不新增 Snakemake rule。

#### 阶段 5A 验收标准

- `./run.sh dry-run` 能看到 run rule 接收 selection 参数。
- Official 能通过 `lit_args` 改变 lit 命令。
- RAJA 能通过 `extra_args` 改变 `raja-perf.exe` 命令。
- `.run_complete` 中能看到本次使用的参数。
- `auto/metadata/<experiment_id>/experiment.json` 中能看到 normalized `test_selection`。
- 使用 smoke 配置时，运行时间或输出规模明显小于 full run。
- parsed / aggregate / report 仍能正常生成。

### 阶段 5B：结构化子集选择增强

#### 目标

在阶段 5A 的参数透传稳定后，再把常用选择方式封装成更友好的结构化配置，减少用户直接记忆 suite 命令行参数的负担。

#### 当前第一层实现方向

阶段 5B 第一层只做轻量结构化选择层，不引入完整 DSL。

当前设计是新增 `workflow/lib/test_selection.py`，由它负责把结构化字段和原始透传参数合并成最终命令行参数。`run_official.py` 和 `run_raja.py` 仍然只接收已经解析好的参数列表，不在 run 脚本里堆积 suite-specific 解释逻辑。

第一层支持：

```yaml
test_selection:
  official:
    filters:
      - "TSVC"
    excluded: []
    lit_args: []

  raja:
    kernels:
      - "Basic_DAXPY"
    excluded: []
    extra_args: []
```

归一化后会生成：

- `test_selection.official.resolved_lit_args`
  - 例如 `["--filter", "TSVC"]`
- `test_selection.raja.resolved_extra_args`
  - 例如 `["--kernels", "Basic_DAXPY"]`

原始 `lit_args` / `extra_args` 继续保留为 escape hatch，用于暂未结构化支持的上游参数。

Official 和 RAJA 都支持统一的 `excluded` 写法。Official 会转换为 lit 的 `--filter-out`，RAJA 会转换为 RAJAPerf 的 `--exclude-kernels`。

#### 后续可完善功能

- Official 结构化选择：
  - `test_paths`
  - 更友好的 benchmark group 模板
  - 常用 lit filter 的配置模板

- RAJA 结构化选择：
  - `kernel_groups`
  - `variants`
  - `problem_sizes`
  - 常用 RAJAPerf smoke 参数模板

- 新增 `workflow/lib/test_selection.py`。
  - 当 selection 逻辑不再只是简单列表透传时，将配置解释和命令参数生成移入该模块。
  - run 脚本只接收已经生成好的参数列表，避免脚本里堆积 suite-specific 规则。

- 报告展示增强。
  - 在 HTML report 中显示当前 Official/RAJA selection 参数。
  - 在 parsed / analysis 表格中增加 selection 相关字段，便于后续跨 run 对比时过滤 full/subset run。

#### 阶段 5B 验收标准

- 用户可以通过结构化配置只跑 TSVC 或只跑 RAJA 中的某类 kernels。
- 一组注释示例可以作为开发后的快速验证配置。
- 报告中能看到这次结果基于哪些参数子集生成。
- 不同 selection 的结果不会在 provenance 上混淆。

---

## 阶段 6：全量结果分析数据层

### 目标

落实报告中的 Task 3.1 和 Future Work 中的 repeated runs / significance testing，但不另起一套独立的文字报告系统。

阶段六的目标是为后续 HTML report 构建 report-ready analysis data layer：

- Snakemake 主流水线完成 benchmark、parse、analyze 数据生成。
- 系统默认扫描并分析当前 `auto/` 中保留下来的全部可用结果。
- 用户如果不希望某些结果进入分析，应删除对应产物，而不是通过复杂命令手工筛选。
- analysis layer 只产出结构化 CSV/JSON；HTML 读取和展示放到阶段七。

### 当前差距

- 尚无统一的全量 analysis dataset。
- 尚无版本间差异计算、阈值过滤、回归/改善榜单。
- 当前系统只保留一个全局 `label`，还需要独立的 sample 维度支撑重复实验。
- 缺少样本统计、置信区间和显著性证据，不利于区分真实性能变化与噪声。

### 需要完成的功能

- 增加独立的重复实验 sample 模型。
- 将相同配置的多次运行组织成可分析的统计样本组。
- 自动扫描 `auto/parsed/*/benchmark_records.csv` 中全部可用结果。
- 生成统一的 analysis dataset，作为阶段七 HTML report 的数据输入。
- 自动计算改善和回归，并区分候选变化与统计上可信的变化。
- 支持用户设定显著变化阈值。
- 生成可供 HTML report 可视化消费的结构化分析表。

### 需要修改/新增的代码或文件

- 新增：
  - `workflow/lib/analysis.py`
  - `workflow/scripts/analyze.py`
- 修改：
  - `workflow/Snakefile`

### 具体修改内容

1. 增加重复实验 sample 维度。
   - 设计应避免重新引入多个标签概念。
   - 使用独立的 `sample` 字段标识同一实验组中的不同观测，不复用 `label`。
   - 通过清晰的 sample 数量配置自动展开多次运行。

2. 新增 Snakemake `analyze` rule。
   - 输入为当前 workflow 生成的 parsed CSV，以及 `auto/parsed/` 中已存在且可用的历史 parsed CSV。
   - 默认纳入所有可用结果。
   - 不要求用户手写复杂历史 experiment 列表。
   - 不满意或不想纳入的结果由用户从 `auto/` 中删除。

3. 删除冗余 aggregated 中间层。
   - `benchmark_records.csv` 是 parsed 阶段唯一事实表。
   - 不再生成或依赖 `benchmark_records_aggregated.csv`。
   - 如果 report 暂时需要聚合数据，只在内存中从 parsed 表临时生成。

4. 生成 report-ready analysis tables。
   - `auto/analysis/analysis_records.csv`
   - `auto/analysis/sample_statistics.csv`
   - `auto/analysis/metric_comparisons.csv`
   - `auto/analysis/top_regressions.csv`
   - `auto/analysis/top_improvements.csv`
   - `auto/analysis/analysis_summary.json`

5. analysis records 至少保留：
   - `experiment_id`
   - `source_file`
   - `compiler_version`
   - `suite_name`
   - `suite_version`
   - `test_name`
   - `metric`
   - `label`
   - `sample`
   - `value`
   - `source_observations`

6. 基于全量 analysis dataset 生成轻量统计结果。
   - 均值
   - 标准差
   - 变异系数
   - 置信区间
   - regression / improvement 分类
   - stable / candidate / reliable 状态

7. 记录噪声控制元数据。
   - CPU 型号
   - 核数
   - 负载快照
   - 内存大小
   - 线程数
   - OpenMP 环境变量

8. 保持阶段边界清晰。
   - 所有分析结果都写成结构化 CSV/JSON，而不是另起命令生成独立文字报告。
   - 差异计算、样本聚合和轻量统计判断放在 `analysis.py` 中。
   - HTML 读取、展示和交互过滤放到阶段七。

### 验收标准

- 用户只需运行主 Snakemake 流水线即可得到 benchmark、analysis 数据和现有 HTML report。
- 系统默认分析当前 `auto/` 中保留下来的全部可用 parsed 结果。
- 用户可以通过配置展开同一实验组的多个 sample。
- 同一版本的多轮结果可被自动识别为同一个统计样本组。
- 阶段六产出的分析表可以直接支撑阶段七的可视化报告。
- 第六阶段不实现 HTML 展示，不让 `generate_report_cli.py` 读取 analysis 数据。

---

## 阶段 7：报告系统升级与交互式可视化

### 目标

落实报告中的 Task 1.6 和 Future Work 中的高级展示能力，让报告从单个 experiment 的演示图升级为面向全量 analysis dataset 的静态 HTML 分析报告。

阶段七的核心目标不是再增加一套运行入口，而是让主 Snakemake 流水线最终生成一个可归档、可离线打开、能解释阶段六分析结果的 HTML report。

### 当前差距

- 目前图表固定，只有两个子图。
- 缺少筛选、搜索、对比和失败项展示。
- 尚未突出多版本、多轮次、变化阈值分析的价值。
- 报告入口仍主要围绕单个 experiment 输出，尚未消费阶段六生成的全量 analysis tables。
- 旧报告逻辑同时包含 table 读取、临时聚合和 Plotly 布局，后续继续堆功能会变得难维护。
- `generate_report_cli.py` 目前只接受单个 benchmark table，不能表达全局 analysis report 的输入。

### 需要完成的功能

- 新增或改造为一个全局静态 HTML analysis report。
- 将阶段六的 `auto/analysis/` 产物接入 report。
- 报告默认反映 `auto/` 中保留下来的全部可用结果。
- 提供结果总览、回归/改善榜单、suite 视图和指标分布视图。
- 提供轻量交互能力：搜索、Plotly hover/zoom、表格筛选和 CSV 链接。
- 保持单一 Snakemake 主流水线；不要引入额外 `run.sh report` 或复杂手工选择入口作为主线。
- 暂不开发 Streamlit/Dash Web App；如果静态报告已经不足，再作为后续阶段单独规划。

### 需要修改/新增的代码或文件

- 修改：
  - `workflow/Snakefile`
  - `workflow/scripts/generate_report_cli.py`
- 建议新增：
  - `workflow/lib/report_data.py`
  - `workflow/lib/report_views.py`

### 输入与输出设计

1. 报告输入来自阶段六 analysis 产物：
   - `auto/analysis/analysis_records.csv`
   - `auto/analysis/sample_statistics.csv`
   - `auto/analysis/metric_comparisons.csv`
   - `auto/analysis/top_regressions.csv`
   - `auto/analysis/top_improvements.csv`
   - `auto/analysis/analysis_summary.json`

2. 默认输出建议改为一个全局报告：
   - `auto/reports/analysis_report.html`

3. Snakemake 关系：
   - `analyze` 生成 `auto/analysis/*`。
   - `generate_report` 读取 `auto/analysis/*`。
   - `rule all` 以全局 HTML report 作为最终主产物。
   - 单 experiment report 可以暂时保留为旧调试能力，但不再作为阶段七主线。

4. CLI 边界：
   - `generate_report_cli.py` 不再只接收 `--input-file`。
   - 改为接收 `--analysis-dir` 或显式 analysis 文件路径。
   - 不提供复杂 baseline/candidate 命令行选择；报告内从已生成表格中展示和过滤。

### 具体修改内容

1. 拆分 report 代码职责。
   - `report_data.py` 负责读取 analysis CSV/JSON。
   - `report_data.py` 负责做轻量展示前整理，例如列选择、数量统计、表格截断。
   - `report_views.py` 负责生成 Plotly figure、HTML section 和完整 HTML 字符串。
   - `generate_report_cli.py` 负责解析参数、加载数据并写出 HTML 文件。

2. 报告首页 / 总览视图。
   - 数据来源：`analysis_summary.json`。
   - 展示纳入分析的 parsed 文件数量。
   - 展示 analysis records、sample groups、metric comparisons 数量。
   - 展示覆盖的 suite、compiler version、label、sample。
   - 展示 `classification_counts`。
   - 展示 analysis 设置，例如变化阈值和 `min_samples`。
   - 目的：让用户一眼判断报告覆盖范围是否符合预期。

3. 回归与改善排行榜。
   - 数据来源：`top_regressions.csv`、`top_improvements.csv`。
   - 展示 top N regression / improvement 表格。
   - 用颜色区分 regression、improvement、stable。
   - 明确展示 `normalized_change_percent`，并说明正数为变差、负数为变好。
   - 展示 `classification` 和 `evidence`，避免把 candidate 误读为强统计结论。
   - 目的：作为报告最重要的入口，帮助用户快速定位值得关注的变化。

4. Metric comparison 视图。
   - 数据来源：`metric_comparisons.csv`。
   - 增加按 suite、metric、classification 的过滤。
   - 增加 test/kernel 名搜索。
   - 增加按变化幅度排序的表格。
   - 可视化建议：
     - regression/improvement 条形图。
     - classification counts 堆叠条形图。
     - suite x metric 的变化数量热力图。
   - 目的：让用户从 top 列表下钻到完整 comparison 数据。

5. Sample statistics 视图。
   - 数据来源：`sample_statistics.csv`。
   - 展示每个 test/metric 的 `observations`、`mean`、`std`、`cv`、`ci95_low/high`。
   - 可视化建议：
     - CV 排行榜，用于发现噪声较大的测试。
     - observations 分布，用于确认哪些测试样本不足。
     - 置信区间图，用于解释 reliable/candidate 分类。
   - 目的：说明变化判断背后的样本稳定性，帮助区分真实变化和噪声。

6. Suite 视图。
   - Official 视图聚焦 execution time、compile time、binary size。
   - RAJA 视图聚焦 execution time、GFLOP/s、bandwidth。
   - 每个 suite 视图至少包含：
     - 指标摘要。
     - top regression/improvement。
     - 高噪声测试列表。
     - 可搜索明细表。
   - 目的：避免 Official 和 RAJA 数据混在一起难以解释。

7. 明细数据视图。
   - 数据来源：`analysis_records.csv`。
   - 默认不完整渲染全部行，避免 HTML 过大。
   - 只展示采样或前 N 行，并提供数据文件路径说明。
   - 展示字段含义链接或简短说明。
   - 目的：提供 provenance 和 debug 入口，而不是替代 CSV 分析。

8. 失败与缺失结果视图。
   - 第一版可先不做复杂失败分析。
   - 如果需要，优先利用 metadata / inspect 结果展示缺失 raw、parsed 或 report 的 experiment。
   - 不在 report 阶段重新扫描或推断 Snakemake 状态。
   - 目的：避免 report 模块变成第二套 inspect 工具。

9. 静态交互实现策略。
   - Plotly 图表使用内嵌 JS，保持离线可打开。
   - HTML 表格使用轻量原生 JavaScript 实现搜索和分类筛选。
   - 不引入大型前端框架。
   - 不依赖外部 CDN。
   - 表格导出第一版可通过直接链接到 CSV 文件实现，不必在浏览器端重新生成 CSV。

10. 视觉与解释性要求。
   - 明确标注 lower-is-better / higher-is-better。
   - 所有百分比变化都说明 raw 与 normalized 的区别。
   - candidate / reliable 必须视觉区分，避免过度声称统计显著性。
   - 报告首页说明：分析默认包含 `auto/` 中保留的全部 parsed 结果。
   - 提醒用户如需排除结果，应删除不想纳入的历史产物后重跑。

### 建议实施顺序

1. 第一轮：接入 analysis 数据。
   - 新增 `report_data.py`。
   - 修改 `generate_report_cli.py` 读取 `--analysis-dir`。
   - 修改 `Snakefile`，让 report 依赖 `ANALYSIS_OUTPUTS`。
   - 生成最小 HTML：summary cards + top regression/improvement tables。

2. 第二轮：重构 HTML 组装。
   - 新增 `report_views.py`。
   - 将 Plotly figure 构造和 HTML section 组装集中到 `report_views.py`。
   - 建立统一 HTML layout、CSS 和 section 结构。

3. 第三轮：增加核心图表。
   - classification counts。
   - top normalized change bar charts。
   - sample CV / observations 图表。
   - suite-level summary。

4. 第四轮：增加静态交互。
   - 表格搜索。
   - suite / metric / classification 过滤。
   - CSV 文件路径链接。

5. 第五轮：清理旧单 experiment report 路径。
   - 移除旧 `generate_pure_plotly_report()` 单实验报告实现，避免报告系统出现两条主线。
   - 将默认 report 目标切换为全局 `analysis_report.html`。
   - 更新 metadata 中 report 路径说明。

### 暂不进入本阶段的内容

- 不做 Streamlit / Dash 应用。
- 不新增 `./run.sh report`。
- 不提供复杂命令行筛选历史结果。
- 不在 report 阶段重新计算 statistics。
- 不在 report 阶段修改 analysis 数据。
- 不把整份 `analysis_records.csv` 全量渲染进 HTML。

### 验收标准

- 主 Snakemake 流水线能生成全局 HTML analysis report。
- HTML report 使用阶段六的 `auto/analysis/` 产物作为主要输入。
- 报告首页能说明本次分析覆盖范围、输入数量、样本数量和变化分类数量。
- 用户能在报告中快速定位 top regression 和 top improvement。
- 用户能按 suite、metric、classification 或 test/kernel 名查看 comparison 结果。
- 报告能展示样本数量、波动和 CI 信息，帮助解释 candidate / reliable 分类。
- 报告离线可打开，不依赖外部 CDN。
- 第七阶段完成后，默认 HTML report 反映当前 `auto/` 中保留下来的全部可用 parsed 结果。

---

## 阶段 8：平台抽象与 HPC 可移植性支持

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

## 阶段 9：自动版本监控与持续执行

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
   - 可生成新的全局 `label`
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

## 阶段 10：用户扩展能力与新测试套件接入

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

## 阶段 11：工程质量、测试与最终交付准备

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

按当前代码和时间节点，阶段 0、阶段 1、阶段 2、阶段 3 已作为基线完成。后续建议优先顺序如下：

1. 阶段 4：数据解析层重构与多格式适配
2. 阶段 5：测试子集选择与运行参数控制
3. 历史运行数据重解析 / 重聚合 / 重出报告能力
4. 阶段 6：重复实验、差异分析与可靠回归检测
5. 阶段 7：报告系统升级
6. 阶段 8：平台抽象与 HPC 支持
7. 阶段 9：自动版本监控
8. 阶段 10：自定义 suite 扩展
9. 阶段 11：工程质量与最终交付

这样排序的原因是：

- 阶段 3 已解决构建缓存和磁盘可见性，可以减少后续解析、测试子集和多版本采集时的无谓重编成本。
- 如果不能稳定复用 `auto/` 中保留下来的历史结果，后续调报告、补 parser、做分析时会被迫重复运行 benchmark，成本过高。
- 可靠回归检测需要把全量 analysis dataset、重复样本模型和统计显著性作为同一条分析链路逐层实现。
- 报告增强要建立在稳定的数据层和分析层之上。
- 自动监控和新 suite 扩展对毕业项目是加分项，但不是当前最急的堵点。

## 7. 建议的里程碑交付物

建议把后续开发拆成以下里程碑：

### 里程碑 A：基础设施可用于批量实验

- 已支持多 LLVM 版本矩阵运行
- 已支持清晰失败诊断、产物摘要与 Snakemake target 级补跑
- 已支持 test subset
- 已支持从历史 experiment/run 重建 parsed / analysis / report
- parser 对当前目标版本稳定

### 里程碑 B：可用于正式数据采集

- 已具备构建缓存与磁盘管理
- 已具备平台配置抽象
- 已具备重复实验入口
- 已能将同一实验组的多个 sample 聚合为统计样本
- 已能稳定导出标准化表格

### 里程碑 C：可用于论文分析

- 已具备版本比较与回归检测
- 已具备改进后的交互式报告
- 已具备显著性分析
- 已能基于 `auto/` 中保留的全部可用结果生成 analysis dataset 和 HTML 分析报告
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
