# GitHub 脚手架可复用模块映射

日期：2026-06-11
对象：`docs/稳定可审计计算化学科研发文Agent需求文档.md`
目的：梳理新版需求文档中哪些模块应保留、重构或新建，以及哪些部分可以直接依赖现成 GitHub 项目做脚手架。

## 1. 总体结论

当前系统应采用“本地已有文献问题 Agent + AiiDA 计算 provenance 主干 + 自定义审计/claim ledger”的组合。

不建议寻找一个大而全的“自动科研 Agent”仓库直接 fork。原因是计算化学发文的核心风险不在于写作或多 Agent 对话，而在于：

- 结构模型是否合理；
- 输入参数是否符合 protocol；
- 计算是否真正收敛；
- 参考态是否一致；
- 图表数值是否来自可追溯计算；
- 论文 claim 是否被文献和计算证据支持。

这些环节没有一个单一 GitHub 项目可以完整替代，必须用成熟科学计算项目做底座，再用本项目自定义规则串起来。

推荐主干：

```text
已有“创新点和问题提出Agent”
  -> PaperQA2/本地文献证据增强
  -> 自定义 Protocol Registry + Audit Gates
  -> AiiDA Core + aiida-* 插件
  -> pymatgen/ASE/custodian/atomate2 工具层
  -> 自定义 Claim Ledger
  -> 论文/SI/PPT 生成
```

## 2. 模块级映射

| 新版模块 | 本地已有基础 | 处理方式 | 可用 GitHub 脚手架 | 复用等级 | 说明 |
| --- | --- | --- | --- | --- | --- |
| `PI Orchestrator Agent` | `创新点和问题提出Agent/src/.../workflow.py` 已有顺序 workflow | 重构 | LangGraph、Agent Laboratory | 部分复用 | 本地 workflow 已能跑文献到问题卡片。若要显式状态机、人工中断、Gate 流转，可引入 LangGraph；Agent Laboratory 可借鉴研究流程，但不适合作为计算化学底座。 |
| `Literature Evidence Agent` | 已有 `EvidenceBuilder`、`source_harvester`、`metadata_enricher`、输出 `evidence_table.csv` | 保留并增强 | PaperQA2 | 直接复用/增强 | 本地模块不应重写。PaperQA2 适合增强 PDF/RAG、带页码引用、矛盾检测和证据检索。 |
| `Research Question Agent` | 已有 `QuestionGenerator`、`QuestionReviewer`、`ResearchQuestionCard` | 保留并适配 | 本地项目为主；Agent Laboratory 只作参考 | 本地复用 | 已经有 C0-C3、protocol hints、aiida_executability 等字段雏形。下一步是适配新版 schema。 |
| `Computational Feasibility Gatekeeper` | 已有 preliminary computability 和 reviewer | 重构 | 无成熟 turnkey；可参考 atomate2/pymatgen protocol 和本地规则 | 自定义 | 这是项目核心判断逻辑，不能直接依赖 LLM 或外部项目。应做规则库 + 人工确认。 |
| `Protocol Registry Agent` | 旧版仅有 protocol hints | 新建 | atomate2、pymatgen、custodian | 参考/部分复用 | 需要自定义 registry。atomate2 可作为标准 workflow 参考；pymatgen/custodian 提供输入、错误和解析经验。 |
| `Structure Model Agent` | 基本无 | 新建 | pymatgen、ASE、catkit/相关吸附位点工具 | 直接复用工具层 | pymatgen 负责结构、slab、缺陷、I/O；ASE 负责原子对象和 calculator 生态。吸附位点可先用 pymatgen `AdsorbateSiteFinder` 或后续接入专门工具。 |
| `Structure Audit Agent` | 基本无 | 新建 | pymatgen、ASE | 部分复用 | 几何检查、距离、PBC、真空层、slab 层数等可用 pymatgen/ASE 实现，但 audit 规则需要自定义。 |
| `Input Audit Agent` | 基本无 | 新建 | pymatgen、custodian、atomate2 | 部分复用 | VASP/QE/CP2K 输入解析可借助现有库；是否符合论文 protocol 需要自定义规则。 |
| `AiiDA Provenance Agent` | 无 | 完全重构/新建 | AiiDA Core、aiida-vasp、aiida-quantumespresso、aiida-cp2k | 直接复用 | 这是新版主干。应直接围绕 AiiDA node UUID、CalcJob/WorkChain、Computer/Code、export/dump 设计，不应先走 atomate2 再迁移。 |
| `Execution Agent` | 无 | 完全重构/新建 | AiiDA Core + aiida-* 插件 | 直接复用 | 执行、队列、远程机器、状态跟踪应交给 AiiDA。Agent 只做任务创建、监控和摘要。 |
| `Error Diagnosis Agent` | 无 | 新建 | custodian、AiiDA exit status、atomate2 错误处理经验 | 部分复用 | custodian 是最直接的错误处理规则来源；但在 AiiDA 架构下应把每次 retry 写成可追踪 process 或 retry ledger。 |
| `Result Parser Agent` | 无 | 新建 | AiiDA parsers、pymatgen、cclib、QCEngine/QCElemental | 直接/部分复用 | 周期材料优先用 AiiDA 插件 parser + pymatgen；分子/簇量化可用 cclib 或 QCEngine schema。 |
| `Result Audit Agent` | 无 | 新建 | pymatgen、custodian、atomate2 参考 | 自定义为主 | 结果是否能支撑 claim 是本项目核心。库只能给数值和状态，科学判断规则必须自定义。 |
| `Figure and Table Agent` | 综述目录有图表规范；计算图表无 | 新建 | pandas、matplotlib、plotly；atomate2 输出结构可参考 | 工具直接复用，逻辑自定义 | 图表生成工具成熟，但必须加 source table、script hash、AiiDA UUID 绑定。 |
| `Claim Ledger Agent` | `合成氨综述/03_证据矩阵` 和本地 `InsightLedger` 有基础 | 重构并扩展 | 无成熟 turnkey；PaperQA2 可辅助引用证据 | 自定义 | 可复用本地 claim 等级和 evidence table 思路，但计算 claim 必须绑定 AiiDA UUID。 |
| `Manuscript Agent` | 综述项目已有写作模板；计算论文模板无 | 新建/部分保留 | Agent Laboratory、AI-Scientist、PaperQA2 | 参考/部分复用 | 可以借鉴 Agent Laboratory/AI-Scientist 的论文生成流程，但不能让它们直接写科学结论。稿件只能从 claim ledger 生成。 |
| `Graduation Compliance Agent` | 旧版需求文档第 2 章已整理 | 保留并实现规则化 | 无直接合适项目 | 自定义 | A/B/C 档、署名、单位、负面期刊、中科院分区是本项目规则库，需自建。 |
| `Audit Gate System G0-G10` | 无完整实现 | 新建 | LangGraph 可承载状态机 | 自定义为主 | Gate 规则必须项目内定义；LangGraph 只解决流程状态，不解决科学判断。 |
| `MLIP Prescreening Protocol` | 之前环境中已有 MatGL/CHGNet 相关探索 | 新建 | FAIR-Chem、MatGL、CHGNet | 直接复用但需审计 | 可作为低成本预筛选，不应直接作为最终论文定量结论，除非有 DFT 复核或 benchmark。 |
| `Database/Structure Discovery` | 文献 Agent 有 OpenAlex/Crossref；结构数据库无 | 新建 | OPTIMADE Python tools、Materials Project API/pymatgen.ext | 直接复用 | 用于材料结构和数据库查询；进入计算前必须转成 StructureModel 并审计。 |

## 3. 可以直接用 GitHub 项目做脚手架的部分

### 3.1 计算 provenance 与执行主干

首选：

- [aiida-core](https://github.com/aiidateam/aiida-core)
- [aiida-vasp](https://github.com/aiida-vasp/aiida-vasp)
- [aiida-quantumespresso](https://github.com/aiidateam/aiida-quantumespresso)
- [aiida-cp2k](https://github.com/aiidateam/aiida-cp2k)

对应模块：

- `AiiDA Provenance Agent`
- `Execution Agent`
- `CalculationTask`
- `CalcResult`
- `G6 Run Gate`
- 部分 `Result Parser Agent`

采用方式：

- 第一版就 AiiDA-native。
- 不先用 atomate2/jobflow 做主执行，再迁移 AiiDA。
- Agent 层只保存 AiiDA node UUID，不复制一套伪 provenance。

### 3.2 结构、输入、材料分析

首选：

- [pymatgen](https://github.com/materialsproject/pymatgen)
- ASE：注意 ASE 主仓库在 GitLab，不是 GitHub，但仍是事实标准工具。

对应模块：

- `Structure Model Agent`
- `Structure Audit Agent`
- `Input Audit Agent`
- `Result Parser Agent`
- `Slab Model Protocol`
- `Adsorption Energy Protocol`
- `Vacancy Formation Protocol`

采用方式：

- 结构对象和 I/O 尽量使用 pymatgen/ASE。
- 审计规则自己写，不依赖 LLM 判断。
- 所有结构 hash、来源、转换过程写入项目账本和 AiiDA。

### 3.3 错误诊断和自动修复规则

首选：

- [custodian](https://github.com/materialsproject/custodian)

可参考：

- [atomate2](https://github.com/materialsproject/atomate2)

对应模块：

- `Error Diagnosis Agent`
- `Input Audit Agent`
- `Run Gate`
- retry ledger

采用方式：

- custodian 可作为错误类型和修复策略来源。
- 在 AiiDA 中不要静默修复；每次修复都要形成新 process 或明确 retry record。

### 3.4 文献 RAG 和证据检索

首选：

- [PaperQA2](https://github.com/Future-House/paper-qa)

已有本地基础：

- `创新点和问题提出Agent`
- `合成氨综述/03_证据矩阵`

对应模块：

- `Literature Evidence Agent`
- `Research Question Agent`
- `Claim Ledger Agent` 的文献证据部分

采用方式：

- 不替换本地已有文献 Agent。
- PaperQA2 用于 PDF 全文证据定位、引用页码、矛盾检测、RAG 回答。
- 本地 Agent 保持“问题卡片生成、排序、证据矩阵输出”的主流程。

### 3.5 Agent 状态机与人工中断

可选：

- [LangGraph](https://github.com/langchain-ai/langgraph)

对应模块：

- `PI Orchestrator Agent`
- `Audit Gate System`
- 人工确认点

采用方式：

- 如果后续要做长期运行、断点续跑、人工确认、分支重试，用 LangGraph。
- 如果第一版只做 CLI 顺序流程，可以继续用本地 `workflow.py`，暂不引入。

### 3.6 材料 workflow 参考库

参考：

- [atomate2](https://github.com/materialsproject/atomate2)
- [jobflow](https://github.com/materialsproject/jobflow)

对应模块：

- `Protocol Registry Agent`
- `Input Audit Agent`
- `Error Diagnosis Agent`
- `Result Parser Agent`

采用方式：

- 不作为主执行底座。
- 用它的 standard workflows、输入集合、TaskDocument 思路、错误处理经验来设计我们的 protocol。
- 若短期要快速复现 Materials Project 风格流程，可局部调用，但最终 provenance 仍应进入 AiiDA。

### 3.7 分子/簇量化计算解析

可选：

- [cclib](https://github.com/cclib/cclib)
- [QCEngine](https://github.com/MolSSI/QCEngine)
- QCElemental/QCFractal 生态

对应模块：

- `Result Parser Agent`
- `Electronic Structure Protocol`
- 分子或团簇模型扩展

采用方式：

- 如果做 ORCA/Gaussian/Q-Chem/Psi4 等分子或团簇计算，引入。
- 如果第一版只做 VASP/QE 表面催化，可暂缓。

### 3.8 MLIP 预筛选

可选：

- [FAIR-Chem](https://github.com/facebookresearch/fairchem)
- [MatGL](https://github.com/materialyzeai/matgl)
- [CHGNet](https://github.com/CederGroupHub/chgnet)

对应模块：

- `MLIP Prescreening Protocol`
- `adsorbate_configuration_screening_protocol`
- 低成本结构预筛选

采用方式：

- 只作为预筛选和候选生成。
- 论文定量主结论应优先 DFT 复核。
- 所有 MLIP 结果必须标记模型版本、训练域、适用性风险。

### 3.9 数据库查询和结构发现

可选：

- [optimade-python-tools](https://github.com/Materials-Consortia/optimade-python-tools)
- pymatgen Materials Project 接口

对应模块：

- `Database/Structure Discovery`
- `StructureModel.source`
- 候选材料收集

采用方式：

- 用于结构来源发现和元数据统一。
- 进入计算前必须通过 Structure Audit。

## 4. 不建议直接作为主脚手架的项目

| 项目 | 为什么不作为主底座 | 可借鉴点 |
| --- | --- | --- |
| AI-Scientist | 偏 ML 实验自动化，不解决计算化学结构、收敛、参考态、provenance 审计问题 | idea -> experiment -> paper 流程、自动论文结构 |
| Agent Laboratory | 有研究 workflow 和报告生成，但不是计算化学 provenance 系统 | 文献综述、实验、报告三阶段组织方式 |
| ChemCrow | 化学工具 Agent，但不是计算催化 DFT/AiiDA 审计底座 | 工具封装、化学任务 routing |
| atomate2/jobflow | 材料 workflow 很强，但与 AiiDA 是不同执行/provenance 范式 | protocol、standard workflows、错误处理、TaskDocument |
| 通用 LangChain/LlamaIndex RAG | 不能保证科学证据质量 | 只可作为检索/问答组件，优先 PaperQA2 |

## 5. 保留、重构、新建优先级

### 5.1 直接保留

1. `创新点和问题提出Agent` 的文献、共识、争议、open gap、question cards、ranking 输出。
2. `合成氨综述/03_证据矩阵` 中 claim 等级和证据强度规则。
3. 旧版需求文档第 2 章毕业要求规则。

### 5.2 需要重构

1. `ResearchQuestionCard` schema：补齐 AiiDA、protocol、audit 风险字段。
2. 文献 Agent 输出：增加到新版 `EvidenceClaim` 和 `LiteratureRecord` 的适配器。
3. `QuestionReviewer`：从“创新潜力评分”升级为“进入计算 protocol 的 gatekeeper”。
4. `InsightLedger`：扩展为文献 claim + 计算 claim 双账本。

### 5.3 需要新建

1. `Protocol Registry`。
2. `Audit Gate System G0-G10`。
3. `AiiDA Adapter / Provenance Agent`。
4. `Structure Model Agent`。
5. `Structure/Input/Result Audit Agent`。
6. `Result Parser Agent`。
7. `Claim Ledger Agent` 的计算部分。
8. `Figure/Table Agent` 的 provenance 绑定。
9. `Manuscript Agent` 的 claim-ledger-only 写作约束。
10. `Graduation Compliance Agent` 的规则执行器。

## 6. 建议的第一阶段集成顺序

### 第 1 步：保留现有文献问题 Agent

目标：

- 不动已有核心逻辑。
- 写一个 adapter，把已有输出转换成新版 schema。

输入：

- `outputs/.../literature/evidence_table.csv`
- `outputs/.../insight/consensus_list.md`
- `outputs/.../insight/controversy_list.md`
- `outputs/.../question_cards/all_question_cards.json`
- `outputs/.../review/ranking_table.csv`

输出：

- `LiteratureRecord`
- `EvidenceClaim`
- `ResearchQuestionCardV2`

### 第 2 步：建 Protocol Registry

目标：

- 先不跑真实 DFT。
- 先把 adsorption energy、slab model、vacancy formation 三个 protocol 写成机器可读规则。

可参考：

- atomate2 workflows。
- pymatgen VASP input sets。
- custodian error handlers。

### 第 3 步：建 AiiDA 最小 adapter

目标：

- 初始化 profile。
- 注册 local computer/code。
- 跑一个 dummy 或低成本任务。
- 返回 AiiDA node UUID。

产出：

- `CalculationTask.aiida_process_uuid`
- `CalcResult.aiida_node_uuid`

### 第 4 步：建审计 gates

优先顺序：

1. `G3 Protocol Gate`
2. `G4 Structure Gate`
3. `G5 Input Gate`
4. `G6 Run Gate`
5. `G7 Result Gate`
6. `G9 Claim Gate`

### 第 5 步：生成 claim-ledger-only manuscript skeleton

目标：

- Manuscript Agent 不允许自由生成科学结论。
- 只能引用 claim ledger 中 `L2+` 的 claim。

## 7. 关键判断

如果目标是“快点有一个演示”，可以只用本地 Agent + pymatgen + matplotlib。

如果目标是“稳定科学可审计、能支撑博士发文”，必须尽快引入：

- AiiDA Core。
- 至少一个 AiiDA 计算插件。
- Protocol Registry。
- Audit Gate。
- Claim Ledger。

这些不是过度工程，而是计算化学内容可信度的最低工程化条件。
