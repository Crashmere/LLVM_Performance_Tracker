# Snakemake 迁移设计文档

## 1. 文档目的

本文档基于当前项目根目录下已有实现进行迁移设计，目标是将现有 LLVM benchmark pipeline 从手写 Python orchestration 迁移到 Snakemake 工作流，同时保留项目已有的数据处理与报告能力，并为后续多版本编译器对比、多次重复运行求平均值、自动化触发执行打下稳定基础。

本文档聚焦两件事：

1. 评估在当前代码基础上集成 Snakemake 的实际可操作性与推荐方案。
2. 给出一个循序渐进、可落地、可验证的迁移计划。

## 2. 当前项目现状

当前仓库主要由以下几个文件组成：

- `benchmark_pipeline.py`
- `parse_results.py`
- `generate_report.py`
- `config.yml`

其中：

- `benchmark_pipeline.py` 负责完整主流程：创建 Python 虚拟环境、读取配置、构建 LLVM、自定义构建 Official Test Suite、构建 RAJAPerf、运行 benchmark、输出日志。
- `parse_results.py` 负责遍历结果目录，将 Official suite 和 RAJA suite 的原始结果解析为统一的 `BenchmarkRecord` 数据结构。
- `generate_report.py` 负责读取解析结果、做聚合统计、生成 Plotly HTML 报告。
- `config.yml` 负责定义项目工作目录、LLVM 版本、测试套件版本及编译参数。

从代码结构上看，当前 pipeline 已经具备非常清晰的阶段划分和文件依赖关系，只是这些关系目前由 Python 主脚本手动维护，而不是由声明式工作流系统维护。

## 3. 迁移可行性评估

### 3.1 总体结论

将当前项目迁移到 Snakemake 的可行性很高，而且是适合完整迁移而非仅做表层包装的。

原因如下：

- 当前流程天然是一个 DAG。
- 各阶段之间存在明确的文件级依赖。
- 现有代码规模较小，重构成本可控。
- 已有功能边界较清晰，适合拆成独立规则。
- 后续确实存在多版本比较、重复运行、多次求平均值、自动化触发等工作流需求，Snakemake 能直接支持这些需求。

### 3.2 为什么适合 Snakemake

当前实际流程可抽象为：

1. 准备源码目录和结果目录
2. checkout / update LLVM 源码
3. 构建 LLVM 并安装
4. checkout / update Official Test Suite
5. 构建 Official Test Suite
6. checkout / update RAJAPerf
7. 构建 RAJAPerf
8. 运行 Official benchmark
9. 运行 RAJA benchmark
10. 解析结果
11. 聚合结果
12. 生成报告

这与 Snakemake 的 rule 模型完全一致。更重要的是，Snakemake 在这个项目中的收益不是“把命令换个写法”，而是：

- 用 `input` / `output` 正式表达依赖关系
- 自动判断哪些步骤需要跳过或重跑
- 允许 Official 与 RAJA 的 build 阶段并行
- 让多 LLVM 版本、多 suite tag、多 run label 的组合实验变得可管理
- 统一日志、错误传播和执行入口

### 3.3 为什么现在适合做一步较完整的迁移

当前仓库中的 orchestration 逻辑主要集中在 `benchmark_pipeline.py` 中，没有大规模分散在多个模块中。对这种结构来说，继续在原脚本上增量打补丁的收益会越来越低，而一次性把“工作流控制权”交给 Snakemake，长期维护成本更低。

不过，“适合完整迁移”不意味着“一次提交做完全部实现”是最佳方式。更合理的做法是：

- 设计上一步到位
- 实施上分阶段迁移

也就是说，先把最终目标架构一次性定清楚，再按阶段落地，确保每一步都可运行、可验证、可回退。

## 4. 对当前实现的关键观察

### 4.1 已经适合直接转为 rule 的部分

当前代码中以下阶段已经具有明显的规则边界：

- LLVM 构建：`build_llvm()`
- Official 构建：`build_official_suite()`
- RAJA 构建：`build_raja_suite()`
- Official 运行：`run_benchmarks()` 中的 Official 分支
- RAJA 运行：`run_benchmarks()` 中的 RAJA 分支
- 结果解析：`parse_results.py`
- 报告生成：`generate_report.py`

这些都可以直接转为 Snakemake rule，无需改变其功能目标，只需要改变调用方式与输入输出接口。

### 4.2 当前实现里不适合原样保留的部分

以下设计在 Snakemake 体系下不应原样保留：

#### 4.2.1 主脚本自建虚拟环境并重启自身

`benchmark_pipeline.py` 当前在启动时自动创建 `.venv`、安装依赖并 `execv` 重启。这种模式适用于“单一脚本即入口”的工具型脚本，但不适用于 Snakemake 工作流。

迁移后建议：

- 由 Snakemake 管理执行环境
- Python 脚本只承担业务逻辑，不再负责自举环境

#### 4.2.2 构建目录未参数化

当前 Official 和 RAJA 的 build 目录是固定路径：

- `official/build`
- `raja/build`

这会带来以下问题：

- 多 LLVM 版本共存困难
- 多 suite tag 共存困难
- 同时执行不同参数组合时会互相覆盖
- 无法有效保留跨版本构建缓存

迁移后应改为按参数组合组织目录。

#### 4.2.3 构建函数每次清空 build 目录

当前 `build_with_cmake()` 会先清空 build 目录。这在串行脚本中是简单直接的，但在 Snakemake 中会削弱缓存复用能力，也会使重复实验变得低效。

迁移后建议：

- build 目录按参数隔离
- 默认不主动清空已有目录
- 仅在显式需要重建时通过 Snakemake 参数或清理规则完成

#### 4.2.4 日志系统过于绑定单次运行上下文

当前日志路径绑定 `LLVM_VERSION` 和 `RUN_ID`，并由全局变量控制当前日志文件。Snakemake 已经具备每个 rule 独立 `log:` 的机制，因此无需继续使用这种集中式日志状态管理方式。

迁移后建议：

- 每个 rule 独立指定日志文件
- 如有需要，再额外生成一个 manifest 或 summary 文件，而不是维护全局日志状态

### 4.3 可以保留并复用的部分

以下逻辑不需要推翻，适合抽取后继续复用：

- 读取和校验 `config.yml`
- `git clone` / `git fetch` / `git checkout` 流程
- LLVM/Official/RAJA 的 CMake 参数拼装逻辑
- Clang 主版本号探测逻辑
- `libomp.so` 自动发现逻辑
- Official 原始 JSON 解析逻辑
- 报告绘图逻辑

它们应该从“主流程脚本的内联函数”变成“可被 rule 调用的辅助函数或独立脚本”。

## 5. 时间戳保留策略

### 5.1 保留时间戳结果是合理且必要的

本项目后续希望对同一参数组合做多次运行，再对结果求平均值。这意味着每次执行都保留独立结果目录是合理的，不应为了迎合传统“单目标构建”思路而取消时间戳。

因此，本设计不建议删除“每次运行保留独立结果”的能力。

### 5.2 需要调整的不是“保留时间戳”，而是“时间戳来源”

问题不在于结果目录含时间戳，而在于当前时间戳是脚本内部自动生成的隐式状态。对于 Snakemake，应该把它改成显式工作流参数，例如：

- `run_label=20260504_153000`
- `run_label=trial_01`
- `run_label=repeat_03`

也就是说：

- “每次运行保留独立结果”继续保留
- 但运行标识必须成为 rule 输出路径中的显式变量，而不是 Python 模块加载时偷偷生成的值

这样既能保留多次运行结果，也能让工作流可控、可追踪、可重复调用。

### 5.3 对后续平均值分析的影响

一旦 `run_label` 成为显式参数，后续聚合统计就可以按以下维度进行：

- `suite_name`
- `suite_version`
- `compiler_version`
- `run_label`
- `test_name`

然后在报告层决定：

- 显示每次原始运行结果
- 对多个 `run_label` 求平均值、标准差
- 比较不同 LLVM 版本之间的差异

这与 Snakemake 完全兼容。

## 6. 多版本缓存与目录设计

### 6.1 设计目标

目录结构需要同时满足以下要求：

- 支持多个 LLVM 版本共存
- 支持多个 Official tag / RAJA tag 共存
- 支持同一参数组合的多次重复运行
- 支持保留构建缓存
- 支持结果和构建目录一一对应，便于追踪

### 6.2 推荐目录结构

建议将 `base_dir` 下结构设计为：

```text
<base_dir>/
  sources/
    llvm-project/
      <llvm_tag>/
    official/
      <official_tag>/
    raja/
      <raja_tag>/

  builds/
    llvm/
      <llvm_tag>/
    official/
      <official_tag>/
      llvm-<llvm_version>/
    raja/
      <raja_tag>/
      llvm-<llvm_version>/

  installs/
    llvm/
      <llvm_tag>/

  results/
    official-<official_tag>/
      <llvm_version>/
        <run_label>/
          baseline_results.json
    raja-<raja_tag>/
      <llvm_version>/
        <run_label>/
          RAJAPerf-*.csv

  parsed/
    <run_label>/
      benchmark_records.parquet
      benchmark_records.csv

  reports/
    <run_label>/
      benchmark_report.html

  logs/
    <run_label>/
      ...
```

### 6.3 设计 rationale

这样设计有以下好处：

- `sources`、`builds`、`installs`、`results` 职责清晰分离
- build 目录和 install 目录按版本参数隔离，不会互相覆盖
- 同一个 LLVM 版本的 install 可以被多个 suite build 复用
- 多次运行只会新增 `results/<run_label>/...`，不会破坏已有结果
- 日后做多版本矩阵实验时，路径结构不需要再次重构

## 7. Snakemake 目标架构

### 7.1 总体结构

推荐工作流目录结构如下：

```text
workflow/
  Snakefile
  rules/
    common.smk
    llvm.smk
    official.smk
    raja.smk
    report.smk
  scripts/
    common.py
    checkout_repo.py
    build_llvm.py
    build_official.py
    build_raja.py
    run_official.py
    run_raja.py
    parse_results_cli.py
    generate_report_cli.py

envs/
  python-tools.yml

config/
  workflow_config.yaml
```

这里的思想是：

- Snakemake 只负责依赖调度、目标管理、日志和参数传递
- 复杂业务逻辑放到 `workflow/scripts/` 中
- 共享 helper 放到 `common.py`
- 环境依赖显式写在 `envs/` 下

### 7.2 推荐 rule 划分

建议将规则拆分为以下层级。

#### 基础准备层

- `rule checkout_llvm`
- `rule checkout_official`
- `rule checkout_raja`

#### 构建层

- `rule build_llvm`
- `rule build_official`
- `rule build_raja`

#### 运行层

- `rule run_official`
- `rule run_raja`

#### 数据处理层

- `rule parse_results`
- `rule aggregate_results`

#### 输出层

- `rule generate_report`
- `rule all`

### 7.3 规则依赖关系

推荐依赖图如下：

1. `checkout_llvm` -> `build_llvm`
2. `checkout_official` + `build_llvm` -> `build_official`
3. `checkout_raja` + `build_llvm` -> `build_raja`
4. `build_official` -> `run_official`
5. `build_raja` -> `run_raja`
6. `run_official` + `run_raja` -> `parse_results`
7. `parse_results` -> `aggregate_results`
8. `aggregate_results` -> `generate_report`
9. `generate_report` -> `all`

其中 `build_official` 与 `build_raja` 可以天然并行，前提是 Snakemake 的 `-j` 大于 1。

## 8. 各模块迁移设计

### 8.1 `benchmark_pipeline.py`

迁移后不建议继续保留为工作流主入口。

推荐处理方式：

- 将其中的纯 helper 逻辑抽取到 `workflow/scripts/common.py`
- 将每个阶段拆成独立脚本
- 最终仅保留一个极薄的兼容包装层，或者直接退役

建议保留的 helper：

- 配置读取
- 仓库准备逻辑
- OpenMP 动态库发现逻辑
- Clang major version 探测
- 构建参数组装逻辑

建议移除的职责：

- venv 自举
- `main()` 中的顺序式 orchestration
- 全局日志状态管理
- 隐式时间戳生成

### 8.2 `parse_results.py`

迁移后建议将其重构为两个层次：

1. 保留库函数层
2. 增加明确的 CLI 层

推荐结果：

- `parse_results.py` 作为纯库模块，提供解析函数
- 新增 `parse_results_cli.py` 作为 Snakemake `script:` 或 `shell:` 的调用入口

需要补充的能力：

- 接收输入文件或输入目录参数，而不是固定读取 `config.yml`
- 接收输出文件路径参数
- 输出标准化表格文件，例如 CSV 或 Parquet
- 明确保留 `run_label`

### 8.3 `generate_report.py`

迁移后建议同样拆成：

1. 数据处理与绘图函数
2. 命令行入口

建议修改点：

- 不再自行推导结果目录
- 直接接收聚合结果文件路径
- 直接接收输出 HTML 路径
- 报表逻辑只关注“画什么”，不关注“从哪里找输入”

### 8.4 配置文件

当前 `config.yml` 仍是单版本思维。迁移后建议扩展为支持列表和运行标签。

推荐结构如下：

```yaml
project:
  base_dir: "~/msc/auto"

runs:
  run_label: "20260504_153000"

llvm:
  repo_url: "https://github.com/llvm/llvm-project.git"
  tags:
    - "llvmorg-21.1.0"
  build:
    c_compiler: "gcc"
    cxx_compiler: "g++"
    ninja_jobs: 8

test_suite:
  official:
    repo_url: "https://github.com/llvm/llvm-test-suite.git"
    tags:
      - "llvmorg-21.1.0"
    cxx_standard: 17
  raja:
    repo_url: "https://github.com/LLNL/RAJAPerf.git"
    tags:
      - "v2025.03.0"
    cxx_standard: 17

report:
  output_format: "html"
```

对于只跑单个版本的情况，也仍然建议用列表形式，因为这能让后续扩展到多版本时不再改 schema。

## 9. 推荐的 Snakemake 实现细节

### 9.1 构建规则的完成标记

对于 LLVM、Official、RAJA 构建规则，建议不要只依赖目录存在来判断任务完成，而是使用：

- 关键产物文件
- 或额外的 stamp 文件

例如：

- LLVM：`installs/llvm/<llvm_tag>/bin/clang++`
- Official：`builds/official/.../.build_complete`
- RAJA：`builds/raja/.../.build_complete`

这样可以减少“目录存在但构建未完整成功”的误判。

### 9.2 对目录输出使用 `directory()`

Snakemake 支持 `directory()` 输出。对于 build 目录和 clone 目录，这非常适合：

- `directory("sources/llvm-project/{llvm_tag}")`
- `directory("builds/official/{official_tag}/llvm-{llvm_version}")`

但对于真正决定任务完成性的关键信号，仍建议辅以 stamp 文件。

### 9.3 日志管理

每个 rule 都应声明独立 `log:` 文件，例如：

- `logs/{run_label}/build_llvm.log`
- `logs/{run_label}/build_official.log`
- `logs/{run_label}/run_raja.log`

这样用户定位错误时会比当前全局日志状态更直接。

### 9.4 环境管理

建议统一使用 Snakemake 环境文件，至少把以下 Python 依赖纳入：

- `pyyaml`
- `lit`
- `pandas`
- `plotly`

后续如果需要，还可补充：

- `pyarrow`
- `tabulate`

如果项目运行环境长期固定，也可先使用统一环境，再视需要拆成多个 rule 环境。

### 9.5 参数化方式

建议工作流至少对以下维度参数化：

- `llvm_tag`
- `official_tag`
- `raja_tag`
- `run_label`

必要时还可继续扩展：

- `ninja_jobs`
- `official_cxx_standard`
- `raja_cxx_standard`

### 9.6 多次重复运行策略

Snakemake 不需要自己“生成多个 run_label”，而是可以：

- 每次手工指定一个新的 `run_label`
- 或由外部脚本负责生成 `run_label`
- 或未来再增加一个专门的“实验批量驱动器”

这与“保留所有结果目录”的需求并不冲突。

## 10. 分阶段迁移计划

本节给出推荐的完整迁移计划。整体原则是：

- 每一阶段都应有明确的产出物
- 每一阶段都应能独立验证
- 在新工作流稳定前，不立刻删除旧脚本

### 阶段 0：冻结当前行为并建立基线

目标：

- 明确当前项目的行为基线
- 在迁移过程中有可对照对象

具体操作：

1. 记录当前 `config.yml` 的有效配置。
2. 保存一份当前成功运行产生的结果目录样本。
3. 保存一份当前 Official 和 RAJA 原始结果文件样本。
4. 记录当前输出目录结构。
5. 记录当前 `parse_results.py` 和 `generate_report.py` 的使用方式。

验收标准：

- 能说清当前 pipeline 在一次成功运行后，最终有哪些关键产物。

### 阶段 1：抽取公共逻辑，降低 `benchmark_pipeline.py` 耦合

目标：

- 把可复用逻辑从主脚本中抽出来，为 rule 化做准备

具体操作：

1. 新建 `workflow/scripts/common.py`。
2. 将以下逻辑从 `benchmark_pipeline.py` 抽出：
   - 配置读取
   - git repo 准备
   - CMake/Ninja 调用封装
   - `libomp.so` 查找
   - Clang major version 探测
3. 将构建参数拼装整理成可重用函数。
4. 保持旧 `benchmark_pipeline.py` 仍可运行，但内部改为调用抽出的 helper。

验收标准：

- 旧 pipeline 仍可运行
- helper 已可被其他脚本单独 import

### 阶段 2：重构结果处理脚本为“库 + CLI”

目标：

- 让结果解析和报告生成可以被 Snakemake 独立调用

具体操作：

1. 将 `parse_results.py` 改造成纯库模块。
2. 新增 `workflow/scripts/parse_results_cli.py`。
3. 支持以下 CLI 参数：
   - 输入结果目录
   - 输出 CSV/Parquet 文件
   - 可选过滤条件
4. 将 `generate_report.py` 的核心绘图逻辑保留为库函数。
5. 新增 `workflow/scripts/generate_report_cli.py`。
6. 支持以下 CLI 参数：
   - 输入聚合数据文件
   - 输出 HTML 文件

验收标准：

- 不依赖 `config.yml` 也能手动调用解析和报告生成
- 给定输入文件后可稳定产出标准化结果文件和 HTML 报告

### 阶段 3：重构目录布局与配置模型

目标：

- 为多版本缓存和重复运行提供稳定路径结构

具体操作：

1. 在 `config.yml` 中引入 `run_label`。
2. 将 `llvm.tag` 改为 `llvm.tags`。
3. 将 `test_suite` 扩展成 `official` / `raja` 子结构。
4. 引入新的 `sources/`、`builds/`、`installs/` 目录约定。
5. 保留旧结果目录读取兼容逻辑，至少在过渡期内不打断已有数据使用。

验收标准：

- 新配置模型可以表达单版本和多版本两种场景
- 新目录结构可落地到真实路径

### 阶段 4：搭建最小可运行 Snakemake 工作流

目标：

- 建立最小但真实可运行的 `Snakefile`

具体操作：

1. 创建 `workflow/Snakefile`。
2. 先写最基本的 `rule all`。
3. 增加：
   - `rule checkout_llvm`
   - `rule build_llvm`
4. 为 `build_llvm` 设计明确的完成验证信号：
   - 保留关键产物检查，如 `bin/clang++`
   - 同时写出 `.build_complete` 之类的 stamp 文件
5. 用单一 `llvm_tag` 跑通 LLVM checkout + build。
6. 为每个 rule 配置独立日志文件。

验收标准：

- 可以通过 Snakemake 单独完成 LLVM 构建
- 重复执行时不会无意义重建
- 构建完成必须同时满足关键产物存在和 stamp 文件存在，避免半成品目录被误判为成功

### 阶段 5：接入 Official 和 RAJA 构建规则

目标：

- 将两个 benchmark suite 的 build 流程纳入 DAG

具体操作：

1. 增加 `rule checkout_official` 和 `rule build_official`。
2. 增加 `rule checkout_raja` 和 `rule build_raja`。
3. Official / RAJA 的 build 目录采用新参数化路径。
4. 为 `build_official` 和 `build_raja` 均增加 stamp 完成标记，例如 `.build_complete`。
5. LLVM install 路径通过 rule input 显式传递，而不是通过全局变量隐式读取。
6. 验证 `build_official` 与 `build_raja` 可并行执行。

验收标准：

- `snakemake -j 2` 时，两个 suite build 能正确并行
- 多次执行不会覆盖不同版本的构建缓存
- Official 和 RAJA 构建规则都具备稳定的完成判定，不依赖“目录存在”这种弱信号

### 阶段 6：接入 benchmark 运行规则

目标：

- 让 Snakemake 负责 benchmark 执行与结果产出

具体操作：

1. 增加 `rule run_official`。
2. 增加 `rule run_raja`。
3. 输出路径中显式包含：
   - suite tag
   - llvm version
   - run_label
4. 运行规则的输入必须依赖上游 build rule 的关键产物或 stamp 文件，而不是仅依赖 build 目录路径。
5. `run_label` 从配置或命令行传入，不再在脚本内部生成。
6. 验证多次使用不同 `run_label` 时结果目录可共存。

验收标准：

- 同一版本参数下，多次运行可保留多份结果
- 不同 `run_label` 不互相覆盖
- benchmark 运行不会在上游构建不完整时误触发

### 阶段 7：接入结果解析和报告生成

目标：

- 将数据处理纳入完整工作流闭环

具体操作：

1. 增加 `rule parse_results`。
2. 将原始结果转换为标准化记录文件。
3. 增加 `rule aggregate_results`。
4. 增加 `rule generate_report`。
5. 让 `rule all` 默认指向最终报告文件，或者报告文件与标准化数据文件集合。

验收标准：

- 从源码 checkout 到最终 HTML 报告可以一条命令跑通
- 解析与报告阶段不再依赖人工中间操作

### 阶段 8：完成旧入口退役与文档更新

目标：

- 完成工作流切换，降低双维护成本

具体操作：

1. 更新 `README.md`，以 Snakemake 为默认使用方式。
2. 将 `benchmark_pipeline.py` 标记为 legacy wrapper，或移除其主入口职责。
3. 增加典型运行示例：
   - 单版本单次运行
   - 单版本多次重复运行
   - 多 LLVM 版本比较
4. 补充常见故障排查说明。

验收标准：

- 新用户仅凭 README 就能使用 Snakemake 工作流
- 旧脚本不再是主入口

## 11. 推荐的实施顺序与优先级

如果按性价比排序，我建议优先级如下：

1. 抽取 helper
2. 重构结果处理脚本接口
3. 设计并落地新目录结构
4. 写最小 Snakemake 工作流
5. 接入 Official/RAJA build
6. 接入 run rules
7. 接入 parse/report
8. 更新文档并退役旧入口

这样做的好处是：

- 前几步几乎不依赖大规模环境验证
- 能尽早把最脆弱的 orchestration 耦合拆掉
- 真正开始写 Snakemake 时，输入输出契约已经更清楚

## 12. 风险与注意事项

### 12.1 规则完成信号必须设计清楚

如果只把“目录存在”当作构建完成标准，可能出现半成品目录导致 Snakemake 误判的问题。因此推荐使用关键产物或 stamp 文件。

### 12.2 构建缓存与结果保留是两类不同问题

需要明确区分：

- build/install 目录：应该尽量复用缓存
- results 目录：应该按 `run_label` 保留多次运行结果

这两者不能混在同一层级上处理。

### 12.3 配置 schema 迁移要考虑兼容期

从旧 `config.yml` 迁移到新 schema 时，建议保留一个短暂兼容期，避免迁移过程中每个脚本同时大改导致调试困难。

### 12.4 不建议一开始就过度复杂化

虽然最终目标支持多版本矩阵，但第一版 Snakemake 实现建议先用单个 `llvm_tag` 跑通全流程，再扩展到版本列表。

设计上要支持矩阵，实施上先跑通最小用例。

## 13. 最终建议

综合当前代码结构、未来实验需求和维护成本，建议采用以下策略：

1. 以 Snakemake 作为最终唯一主入口。
2. 保留“每次运行保留独立结果目录”的策略，但把时间戳改为显式 `run_label`。
3. 将 build/install/source 目录参数化，以支持多个 LLVM 版本和 suite 版本共存。
4. 将 `benchmark_pipeline.py` 从主 orchestrator 重构为可复用 helper 来源，最终退役主入口角色。
5. 将结果解析与报告生成改造成可被 rule 独立调用的 CLI。
6. 按阶段迁移，而不是在单次改动中同时推翻全部逻辑。

如果严格按本文档实施，迁移后的工作流将具备以下能力：

- 更稳定的依赖管理
- 更清晰的错误定位
- 更高的构建缓存复用率
- 更自然的多版本对比能力
- 更规范的重复实验管理能力
- 更低的后续维护成本

这会比继续扩展现有顺序式 Python 主脚本更适合作为项目后续的长期基础设施。
