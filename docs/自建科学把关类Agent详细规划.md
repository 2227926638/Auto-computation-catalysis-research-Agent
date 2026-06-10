# 自建科学把关类 Agent 详细规划

日期：2026-06-11
关联文档：

- `docs/毕业导向AI4Catalysis科研Agent需求文档.md`
- `docs/稳定可审计计算化学科研发文Agent需求文档.md`
- `docs/GitHub脚手架可复用模块映射.md`
- `创新点和问题提出Agent/11_基于新版稳定可审计需求的文献证据与问题发现Agent补充设计.md`

## 1. 文档目的

本项目已经初步完成“文献共识发现、文献中争议点发现、研究问题提出与 G1-G3 预审”的前端 Agent。下一步的核心不应继续扩大问题生成能力，而是补齐计算化学科研流程中必须自建的科学把关模块。

这些模块不能简单从 GitHub 脚手架复制，原因是它们承载的是本项目的科学可信度：

- 研究问题是否真的能由纯计算回答。
- 计算 protocol 是否受控。
- 结构模型是否合理。
- 输入参数是否符合 protocol。
- AiiDA provenance 是否完整。
- 结果是否收敛、自洽、可发表。
- 图表和论文 claim 是否被文献与计算证据支持。
- 毕业和投稿路径是否合规。

本文档给出需要自建的 Agent 划分、职责边界、输入输出、审计规则、依赖工具、数据模型和实现优先级。

## 2. 总体定位

当前系统应分成三类模块。

| 类别 | 代表模块 | 处理方式 | 原因 |
| --- | --- | --- | --- |
| 已有前端 Agent | 文献证据、共识、争议、问题卡片、G1-G3 预审 | 保留并做 adapter | 已经能输出 `evidence_table.csv`、`method_evidence.csv`、`all_question_cards.json`、`gate_audit_report.md` |
| 可复用工具底座 | AiiDA、pymatgen、ASE、custodian、PaperQA2、atomate2 参考 | 直接复用或局部参考 | 这些项目适合做 provenance、结构处理、错误规则和文献增强 |
| 必须自建模块 | Protocol Registry、结构/输入/结果审计、Claim Ledger、毕业合规、科学审核 Gates | 自建 | 这些是项目的科研判断规则和发文约束，不能外包给通用库或 LLM |

核心原则：

```text
已有文献问题 Agent 负责提出可计算问题；
自建科学把关类 Agent 负责判断、生成、执行、审计、追溯；
AiiDA 和工具库负责底层计算 provenance 与科学计算对象；
论文和 SI 只能从通过审计的 Claim Ledger 生成。
```

## 3. 与现有前端 Agent 的接口

现有 `创新点和问题提出Agent` 已经具备以下下游接口：

- `literature/evidence_table.csv`
- `literature/method_evidence.csv`
- `literature/literature_matrix.csv`
- `insight/consensus_list.md`
- `insight/controversy_list.md`
- `insight/open_gap_list.md`
- `question_cards/all_question_cards.json`
- `question_cards/high_priority_cards.md`
- `review/gate_audit_report.md`
- `review/ranking_table.csv`

下游自建模块第一步应实现 `QuestionAgentAdapter`，把这些输出转成统一项目账本对象：

- `LiteratureRecord`
- `EvidenceClaim`
- `MethodEvidence`
- `ResearchQuestionCardV2`
- `GateAuditRecord`

适配要求：

- 不修改前端 Agent 的原始输出。
- 保留原始文件路径、文件 hash、run_id。
- 对 DOI、页码、题名、期刊、年份等未核验信息标记 `unchecked`。
- 只允许 G1/G2/G3 均为 PASS 或 WARN 且可人工确认的问题进入后续规划池。
- C0/C1 问题不得进入计算主线，只能进入综述背景或未来工作。

## 4. 必须自建的 Agent 总览

| Agent | 是否已有基础 | 自建优先级 | 外部工具角色 | 核心 Gate |
| --- | --- | --- | --- | --- |
| `QuestionAgentAdapter` | 无独立实现 | P0 | pandas/Pydantic | G1-G3 接入 |
| `Computational Feasibility Gatekeeper` | 前端已有预筛 | P0 | 规则库 + 文献证据 | G2 |
| `Protocol Registry Agent` | 只有 stub | P0 | atomate2/pymatgen/custodian 作参考 | G3 |
| `Audit Gate Orchestrator` | 无 | P0 | LangGraph 可选 | G0-G10 |
| `Structure Model Agent` | 无 | P1 | pymatgen/ASE | G4 |
| `Structure Audit Agent` | 无 | P1 | pymatgen/ASE | G4 |
| `Input Builder Agent` | 无 | P1 | AiiDA plugins/pymatgen | G5 |
| `Input Audit Agent` | 无 | P1 | custodian/atomate2 参考 | G5 |
| `AiiDA Provenance Agent` | 无 | P1 | AiiDA Core/aiida-* | G6 |
| `Execution Agent` | 无 | P2 | AiiDA daemon/scheduler | G6 |
| `Error Diagnosis Agent` | 无 | P2 | AiiDA exit status/custodian | G6 |
| `Result Parser Agent` | 无 | P2 | AiiDA parsers/pymatgen/cclib | G7 |
| `Result Audit Agent` | 无 | P2 | 规则库 + parser 输出 | G7 |
| `Reference State Audit Agent` | 无 | P2 | protocol registry | G7/G9 |
| `Figure and Table Agent` | 综述侧有规范 | P3 | pandas/matplotlib/plotly | G8 |
| `Claim Ledger Agent` | 综述侧有 claim 规则 | P3 | PaperQA2 可辅助 | G9 |
| `Manuscript Claim Audit Agent` | 无 | P3 | Markdown/LaTeX 工具 | G9 |
| `Graduation Compliance Agent` | 文档规则已有 | P3 | 规则库 | G10 |
| `Novelty and Journal Match Agent` | 前端有相似工作线索 | P4 | OpenAlex/Crossref/期刊表 | G1/G10 |

P0/P1 是进入真实计算前必须完成的模块。P2 是让计算结果可信的最低要求。P3 是让输出能进入论文草稿的最低要求。P4 可在第一篇示范论文推进时增强。

## 5. Agent 详细规划

### 5.1 QuestionAgentAdapter

定位：连接已完成的文献问题 Agent 与新版 AiiDA-native 科研流水线。

职责：

- 读取前端 Agent 输出目录。
- 统一 run manifest。
- 转换问题卡、文献证据、方法证据和 gate 报告。
- 写入项目账本。
- 标记所有需要人工核验的字段。

输入：

- `all_question_cards.json`
- `evidence_table.csv`
- `method_evidence.csv`
- `gate_audit_report.md`
- `ranking_table.csv`

输出：

- `ResearchQuestionCardV2`
- `EvidenceClaim`
- `MethodEvidence`
- `QuestionImportReport`

验收标准：

- 每个导入的问题卡都能追溯到原始前端 Agent run。
- 只有 C2/C3 且 G1/G2/G3 合格的问题进入 `candidate_for_protocol_planning`。
- 所有未核验 DOI/页码字段默认不被论文写作 Agent 当作已核验证据。

### 5.2 Computational Feasibility Gatekeeper

定位：从“初筛”升级为硬性科学 gate，判断问题是否能进入计算规划。

职责：

- 复核前端 Agent 给出的 C0-C3 评分。
- 判断该问题需要哪些计算证据才能回答。
- 明确 claim 边界，避免把机制解释写成实验性能证明。
- 识别必须湿实验验证的问题。

输入：

- `ResearchQuestionCardV2`
- `EvidenceClaim`
- `MethodEvidence`
- `ProjectScope`

输出：

- `ComputabilityAuditReport`
- `claim_boundary`
- `required_protocols`
- `unanswered_by_computation`

关键规则：

- 需要真实合成可行性、长期稳定性或工业条件活性证明的问题，不得判为 C3。
- 只要主 claim 需要湿实验直接证明，应降为 C0/C1。
- 吸附能、能垒、电子结构、微观动力学能回答机制性问题，但不能直接证明“实验最优催化剂”。
- C2/C3 必须有明确结构模型、参考态和最小计算集。

验收标准：

- 每个进入 protocol 的问题都有可计算 claim 边界。
- 每个 C2/C3 问题列出最小可发表结果集。
- 每个 C0/C1 问题有阻断理由和可替代表述。

### 5.3 Protocol Registry Agent

定位：项目的计算 protocol 中枢。它不是简单 YAML 列表，而是参数级、版本化、可审计的计算协议系统。

职责：

- 管理 `CalcProtocol` 版本。
- 将问题卡绑定到可执行 protocol。
- 定义结构要求、输入参数、参考态、收敛标准、失败处理、允许发表的表述。
- 阻止自由拼装输入文件。
- 给 Structure/Input/Result Audit 提供规则。

第一批必须落地的 protocol：

- `slab_model_construction_protocol`
- `adsorption_energy_protocol`
- `oxygen_vacancy_formation_protocol`
- `adsorbate_configuration_screening_protocol`
- `reaction_energy_path_protocol`
- `neb_barrier_protocol`
- `bader_charge_protocol`
- `pdos_analysis_protocol`
- `microkinetic_model_protocol`
- `mlip_prescreening_protocol`

输入：

- `ResearchQuestionCardV2.required_protocols`
- `MethodEvidence`
- 项目默认计算设置
- 人工确认的计算资源和软件

输出：

- `CalcProtocol`
- `ProtocolBinding`
- `ProtocolAuditReport`

关键规则：

- 每个 protocol 必须有 `version`、`applicable_systems`、`forbidden_uses`。
- 每个 protocol 必须有参考态定义。
- 每个 protocol 必须有 publication boundary，即结果在论文中最多能如何表述。
- protocol 变更不得覆盖历史计算；必须产生新版本。
- `planning_stub` 状态的 protocol 只能用于问题预绑定，不能生成 AiiDA 任务。

验收标准：

- 至少 2 个 protocol 达到 `executable_mvp`：slab model 和 adsorption energy。
- 每个进入 AiiDA 的任务都能反查 protocol version。
- 任意缺少参考态或收敛标准的 protocol 不允许通过 G3。

### 5.4 Audit Gate Orchestrator

定位：贯穿 G0-G10 的状态机和审计记录器。

职责：

- 管理每个对象所处 gate。
- 调用对应审计 Agent。
- 记录 PASS/WARN/BLOCK。
- 管理人工确认点。
- 禁止下游模块读取未过 gate 的对象。

建议第一版先用顺序 CLI 工作流实现，后续再引入 LangGraph。

Gate 定义：

| Gate | 名称 | 自建模块 |
| --- | --- | --- |
| G0 | Project Scope Gate | Orchestrator + Graduation Compliance |
| G1 | Literature Evidence Gate | QuestionAgentAdapter + Evidence Audit |
| G2 | Computational Verifiability Gate | Feasibility Gatekeeper |
| G3 | Protocol Gate | Protocol Registry |
| G4 | Structure Gate | Structure Model/Audit |
| G5 | Input Gate | Input Builder/Audit |
| G6 | Run Gate | AiiDA Provenance/Execution/Error Diagnosis |
| G7 | Result Gate | Result Parser/Audit/Reference State Audit |
| G8 | Figure Gate | Figure and Table Agent |
| G9 | Claim Gate | Claim Ledger + Manuscript Claim Audit |
| G10 | Graduation/Submission Gate | Graduation Compliance |

验收标准：

- 任一对象被 BLOCK 后，下游默认不可见。
- WARN 对象必须有 `human_review_required`。
- 所有 gate 报告必须写入项目账本，且保留输入对象 hash。

### 5.5 Structure Model Agent

定位：把研究问题和 protocol 转换成可计算结构模型。

职责：

- 从数据库、文献、CIF、POSCAR 或人工输入生成结构。
- 构建 bulk、slab、缺陷、掺杂、界面、吸附构型。
- 记录结构来源和每一步转换。
- 生成结构候选集，不负责最终放行。

依赖工具：

- pymatgen：晶体、slab、缺陷、I/O、结构分析。
- ASE：原子对象、构型操作、calculator 生态。
- Materials Project/OPTIMADE：后续结构来源。
- MLIP 工具：只做预筛选，不作为最终论文定量依据。

输入：

- `CalcProtocol`
- `ResearchQuestionCardV2`
- `StructureSource`
- `AdsorbateSpec`

输出：

- `StructureModel`
- `StructureTransformLog`
- `CandidateStructureSet`

必须记录：

- bulk 来源。
- 晶面和终止。
- slab 层数、真空层、固定原子。
- 缺陷类型和位置。
- 掺杂位置。
- 吸附物、覆盖度、位点、初始构型。
- 电荷、自旋和磁矩假设。
- 文件 hash 和后续 AiiDA node UUID。

验收标准：

- 生成结构必须可重复生成。
- 结构文件、参数、转换步骤均有 hash。
- 所有结构必须进入 Structure Audit，不得直接进入输入生成。

### 5.6 Structure Audit Agent

定位：计算前的结构几何和化学合理性把关。

职责：

- 检查原子重叠、异常键长、异常真空层。
- 检查 slab 厚度、固定层、表面终止。
- 检查吸附物位置、覆盖度、镜像相互作用风险。
- 检查缺陷位置和化学计量。
- 标记模型与真实催化剂之间的差距。

输入：

- `StructureModel`
- `CalcProtocol.audit_rules`

输出：

- `StructureAuditReport`

关键规则：

- 原子严重重叠必须 BLOCK。
- 真空层低于 protocol 阈值必须 BLOCK 或 WARN。
- slab 层数不足但可做预筛选时 WARN，不能进入最终定量 claim。
- 吸附物初始构型不明确时 BLOCK。
- 缺陷/掺杂位置未标明时 BLOCK。

验收标准：

- 每个结构至少给出几何、PBC、protocol 一致性三类检查。
- G4 BLOCK 的结构不能生成计算输入。
- WARN 结构必须在 claim ledger 中保留模型风险。

### 5.7 Input Builder Agent

定位：基于 protocol 生成计算输入，不允许自由发挥参数。

职责：

- 根据 `CalcProtocol` 和 `StructureModel` 生成 VASP/QE/CP2K 等输入对象。
- 为 AiiDA CalcJob/WorkChain 准备 builder。
- 写入参数来源和默认值来源。

输入：

- `CalcProtocol`
- `StructureModel`
- `SoftwareProfile`
- `ProjectComputeConfig`

输出：

- `CalculationTaskDraft`
- `InputFileSet`
- `AiiDABuilderSpec`

验收标准：

- 所有参数能追溯到 protocol 或人工 override。
- override 必须有理由和审核记录。
- 未通过 Structure Gate 的结构不可生成输入。

### 5.8 Input Audit Agent

定位：检查输入文件和 AiiDA builder 是否符合 protocol。

职责：

- 检查泛函、U 值、赝势、ENCUT/cutoff、k-points、smearing、spin、dipole correction。
- 检查优化阈值和电子收敛阈值。
- 检查 slab 与 adsorbate-slab 参数一致性。
- 检查气相参考态计算设置。
- 检查 NEB 图像、端点和路径设置。

输入：

- `CalculationTaskDraft`
- `InputFileSet`
- `CalcProtocol`

输出：

- `InputAuditReport`

关键规则：

- protocol 必需参数缺失时 BLOCK。
- 参考态参数不一致时 BLOCK。
- 与 protocol 默认值不同但无 override 记录时 BLOCK。
- 低精度参数可作为预筛选 WARN，但不得进入最终论文主结论。

验收标准：

- G5 PASS 后才能提交 AiiDA。
- 每个输入文件都有 hash 和 protocol version。
- 每个 BLOCK 都有可执行修复建议。

### 5.9 AiiDA Provenance Agent

定位：计算证据链中枢。AiiDA 是计算 provenance 的事实来源。

职责：

- 管理 AiiDA profile、Computer、Code、Group。
- 将结构、参数、输入文件、计算任务写入 AiiDA。
- 提交 CalcJob/WorkChain。
- 保存 AiiDA process UUID、node UUID、exit status。
- 导出 provenance 子图摘要。
- 给 Result Parser、Figure Agent、Claim Ledger 提供追溯接口。

输入：

- `CalculationTaskDraft`
- `AiiDABuilderSpec`
- `InputAuditReport`

输出：

- `CalculationTask`
- `AiiDAProvenanceRecord`

关键规则：

- 项目账本只保存 AiiDA UUID 和摘要，不复制一套伪 provenance。
- 原始输出文件必须能从 AiiDA repository 或归档路径找到。
- 任何手动导入的历史计算必须标记为 `ExternalCalcRecord`，不能伪装成 AiiDA-native。

验收标准：

- 至少能完成一个本地 dummy 或低成本计算的 AiiDA 记录闭环。
- 每个计算任务能反查结构、输入、参数、code、computer、输出。
- 每个主文计算数值最终能追溯到 AiiDA node UUID。

### 5.10 Execution Agent

定位：计算任务提交和状态监控层。

职责：

- 调用 AiiDA 提交任务。
- 监控 queued/running/finished/failed。
- 汇总 scheduler 输出和 AiiDA exit status。
- 控制 retry，不做静默重跑。

输入：

- `CalculationTask`

输出：

- `ExecutionStatusReport`
- `RunAuditRecord`

关键规则：

- 失败任务不得被覆盖。
- retry 必须生成新记录或明确 retry ledger。
- 用户可在长任务前人工确认资源、队列、预计耗时。

验收标准：

- 所有任务都有状态转移记录。
- 所有失败都有失败类型和原始输出链接。
- G6 未通过的任务不可进入 Result Parser。

### 5.11 Error Diagnosis Agent

定位：失败计算的原因诊断和修复建议，不是自动掩盖失败。

职责：

- 基于 exit status、scheduler stderr/stdout、计算输出和 custodian 规则诊断失败。
- 给出 retry 策略和风险等级。
- 记录每次修复参数差异。

失败类型：

- 电子步不收敛。
- 离子步发散。
- 磁矩异常。
- 吸附物脱附/解离。
- NEB 图像异常。
- 真空层或 PBC 设置错误。
- 资源超时或内存不足。
- parser 失败。

输出：

- `ErrorDiagnosisReport`
- `RetryPlan`

验收标准：

- 每个 retry plan 都说明科学影响。
- 影响科学可比性的修复必须回到 Input Audit。
- 自动修复不能覆盖原始输入和原始输出。

### 5.12 Result Parser Agent

定位：把 AiiDA 节点和原始输出转成结构化结果。

职责：

- 提取能量、力、优化后结构、磁矩、电荷、DOS/PDOS、Bader、COHP、NEB 能垒。
- 生成统一 `CalcResult`。
- 记录单位、参考态、parser 版本和脚本 hash。

依赖工具：

- AiiDA plugin parser。
- pymatgen。
- cclib/QCElemental：用于后续分子/簇计算。
- pandas/numpy：结构化表。

输出：

- `CalcResult`
- `ParsedResultTable`

验收标准：

- parser 输出必须包含单位。
- derived quantity 必须记录公式和输入 result_id。
- parser 失败不能手工补数后继续流入图表。

### 5.13 Result Audit Agent

定位：判断计算结果是否能进入图表和 claim ledger。

职责：

- 检查收敛状态。
- 检查优化后结构是否合理。
- 检查参考态一致性。
- 检查重复计算一致性。
- 检查数值范围是否异常。
- 判断结果证据等级。

输入：

- `CalcResult`
- `CalcProtocol`
- `StructureAuditReport`
- `InputAuditReport`

输出：

- `ResultAuditReport`

关键规则：

- 未收敛任务不得进入定量结论。
- 吸附能必须明确气相参考态和符号约定。
- 不同 coverage、不同 slab、不同 functional 的结果不得直接混用。
- 氧空位形成能必须明确氧化学势参考。
- NEB 必须检查端点、路径连续性和最高点合理性。
- 电子结构结果只能作为机制解释，不能单独证明活性。

验收标准：

- G7 PASS 才能进入图表和 claim ledger。
- G7 WARN 可以进入 SI 或探索性讨论，但必须带风险标记。
- G7 BLOCK 不得进入论文图表。

### 5.14 Reference State Audit Agent

定位：专门审核计算化学中最容易出错的参考态和能量归一问题。

职责：

- 检查吸附能、反应能、空位形成能、能垒、微观动力学的参考态。
- 检查气相分子、自旋态、零点能和热力学校正。
- 检查每张能量图中的状态是否同一 convention。

输入：

- `CalcProtocol.reference_state_definition`
- `CalcResult`
- `DerivedQuantity`

输出：

- `ReferenceStateAuditReport`

验收标准：

- 每个 derived energy 都能显示公式。
- 缺失参考态时 BLOCK。
- 参考态不一致时 BLOCK。

### 5.15 Figure and Table Agent

定位：只从通过审计的数据生成图表和表格。

职责：

- 生成主文图、SI 图、source table。
- 每张图绑定 AiiDA node UUID、result_id、claim_id、脚本 hash。
- 检查图中数值与 source table 一致。

输入：

- `ResultAuditReport`
- `CalcResult`
- `EvidenceClaim`
- `FigurePlan`

输出：

- `FigureArtifact`
- `TableArtifact`
- `FigureAuditReport`

关键规则：

- 不允许手工复制无 provenance 数值。
- 图注不能引入 claim ledger 中不存在的结论。
- 每个主文图必须有 source table 和脚本。

验收标准：

- G8 PASS 后图表才能进入 manuscript。
- 图表数值能反查 AiiDA UUID 或文献 evidence_id。
- 修改脚本后必须更新 script hash。

### 5.16 Claim Ledger Agent

定位：论文所有科学论断的统一账本。它是文献、计算、图表和写作之间的硬边界。

职责：

- 管理所有 manuscript claim。
- 绑定文献证据、计算证据、图表证据。
- 给 claim 分级。
- 判断 claim 允许进入哪个章节。
- 输出论文写作 Agent 可读取的 claim bundle。

建议采用双层 claim 等级。

综述/文献来源 claim：

- `Observation`
- `Author inference`
- `Cross-paper synthesis`
- `Hypothesis`
- `Design principle`

计算论文 claim：

- `L0`：无证据，不得使用。
- `L1`：文献支持，可用于背景。
- `L2`：单一通过审计的计算支持，只能谨慎表述。
- `L3`：多计算/对照支持，可作为结果。
- `L4`：文献、计算、图表、多对照支持，可作为主结论。

输入：

- `EvidenceClaim`
- `ResultAuditReport`
- `FigureArtifact`
- `ReferenceStateAuditReport`

输出：

- `ClaimLedger`
- `ClaimBundle`
- `ClaimAuditReport`

关键规则：

- 摘要和结论只能使用 L3/L4，或明确标记为假设。
- L2 不得写成普适结论。
- 任何 claim 修改都必须保留版本和来源。
- claim 的 evidence 不足时必须降级或 BLOCK。

验收标准：

- manuscript 中每个关键句都有 claim_id。
- claim_id 能反查 evidence_id、result_id、figure_id、AiiDA UUID。
- 无 claim_id 的科学结论不得进入正式稿。

### 5.17 Manuscript Claim Audit Agent

定位：审核论文草稿是否越过 Claim Ledger 的边界。

职责：

- 扫描摘要、结果、讨论、结论、图注。
- 检查每个关键 claim 是否存在于 claim ledger。
- 检查语气是否符合 claim level。
- 检查引用、图表编号和 SI 编号一致。

输入：

- `ManuscriptArtifact`
- `ClaimLedger`
- `FigureArtifact`

输出：

- `ManuscriptClaimAuditReport`

关键规则：

- 未进入 claim ledger 的新结论必须 BLOCK。
- L2 claim 不允许出现在摘要主结论中。
- 图注不得加入未审计机制解释。
- 讨论部分可以提出假设，但必须标为 hypothesis。

验收标准：

- G9 PASS 后才能生成投稿前稿件包。
- 所有 BLOCK 都给出具体段落和修改建议。

### 5.18 Graduation Compliance Agent

定位：把毕业要求文档中的 A/B/C 档、署名、单位、负面期刊和支撑材料要求规则化。

职责：

- 管理成果档位规则。
- 检查第一作者和第一单位。
- 检查目标期刊 SCI/分区/负面清单状态。
- 生成毕业路径建议。
- 生成支撑材料清单。

输入：

- `ManuscriptArtifact`
- `TargetJournalProfile`
- `AuthorContributionRecord`
- `GraduationRuleSet`

输出：

- `GraduationComplianceReport`

关键规则：

- 期刊分区、检索状态、负面清单必须标记核验日期和来源。
- 未核验的期刊信息不得作为最终毕业判断。
- 共同一作、科教融合单位、会议短文等特殊情形必须单独提示。

验收标准：

- 每篇候选论文都能得到 A/B/C 档预估和风险说明。
- G10 PASS 前必须列出仍需人工核验的事项。

### 5.19 Novelty and Journal Match Agent

定位：选题和投稿风险辅助，不替代科学审稿。

职责：

- 检查近 5 年相似论文。
- 匹配目标期刊范围、档位、审稿风险。
- 提示高度重复、边际创新不足和期刊不匹配。

输入：

- `ResearchQuestionCardV2`
- `LiteratureRecord`
- `TargetJournalProfile`

输出：

- `NoveltyAuditReport`
- `JournalMatchReport`

验收标准：

- 每个 B/A 档候选题目至少有相似工作列表。
- 高度相似题目必须给出改题、换角度或放弃建议。

## 6. 统一数据模型规划

第一版建议使用 Pydantic schema + SQLite 账本 + 文件系统 artifact。核心对象如下：

```text
Project
RunManifest
LiteratureRecord
EvidenceClaim
MethodEvidence
ResearchQuestionCardV2
CalcProtocol
ProtocolBinding
StructureModel
StructureAuditReport
CalculationTaskDraft
InputAuditReport
CalculationTask
AiiDAProvenanceRecord
ExecutionStatusReport
ErrorDiagnosisReport
CalcResult
DerivedQuantity
ResultAuditReport
ReferenceStateAuditReport
FigureArtifact
TableArtifact
ClaimLedger
ManuscriptArtifact
GraduationComplianceReport
GateAuditRecord
```

所有对象必须包含：

- `id`
- `project_id`
- `created_at`
- `source_files`
- `source_hashes`
- `status`
- `audit_status`
- `human_review_required`

计算相关对象必须额外包含：

- `protocol_id`
- `protocol_version`
- `aiida_node_uuids`
- `software`
- `software_version`
- `parser_version`
- `units`
- `reference_state`

## 7. 推荐目录结构

```text
src/
  research_agent/
    schemas/
      project.py
      evidence.py
      question.py
      protocol.py
      structure.py
      calculation.py
      result.py
      claim.py
      artifact.py
      compliance.py
    adapters/
      question_agent_adapter.py
    protocols/
      registry.py
      validators/
    gates/
      orchestrator.py
      reports.py
    structures/
      model_builder.py
      audit.py
    inputs/
      builder.py
      audit.py
    aiida_bridge/
      profile.py
      submit.py
      provenance.py
    execution/
      monitor.py
      error_diagnosis.py
      retry_policy.py
    results/
      parser.py
      audit.py
      reference_state.py
    figures/
      builder.py
      audit.py
    claims/
      ledger.py
      audit.py
    manuscript/
      claim_audit.py
    compliance/
      graduation.py

projects/
  ru_ceo2_n2_001/
    project.yaml
    ledger.sqlite
    imported_question_agent_runs/
    protocols/
    structures/
    calculations/
    parsed_results/
    figures/
    claims/
    manuscripts/
    compliance/
```

## 8. MVP 实现顺序

### M0：Schema 和前端输出适配

目标：

- 建立 `research_agent` 基础包。
- 定义核心 schema。
- 实现 `QuestionAgentAdapter`。
- 能读取现有 `创新点和问题提出Agent` 输出并写入项目账本。

验收：

- 成功导入一个真实合成氨输出目录。
- 生成 `QuestionImportReport`。
- 只保留 G1/G2/G3 合格的 C2/C3 问题进入候选池。

### M1：Protocol Registry 和 Gate Orchestrator

目标：

- 将现有 `protocol_registry/protocols.yaml` 升级为版本化 protocol。
- 至少实现 slab 和 adsorption energy 两个 executable MVP protocol。
- 实现 G0-G3 的统一 gate 记录。

验收：

- 每个候选问题能绑定 protocol version。
- 缺少参考态、适用范围或审计规则的 protocol 被 BLOCK。

### M2：结构生成和结构审计

目标：

- 用 pymatgen/ASE 生成一个 Ru/CeO2 或简化 slab 结构。
- 实现基础结构审计。
- 输出 `StructureModel` 和 `StructureAuditReport`。

验收：

- G4 PASS 的结构可进入输入生成。
- G4 BLOCK 的结构不能继续。
- 结构来源、转换步骤和文件 hash 完整记录。

### M3：输入生成、输入审计和 AiiDA 最小闭环

目标：

- 生成一个低成本计算任务的输入。
- 通过 Input Audit。
- 接入 AiiDA profile，提交 dummy/local/低成本任务。
- 记录 AiiDA UUID。

验收：

- G5 PASS 才能提交。
- G6 记录 process UUID、node UUID、exit status。
- 可以导出 provenance 摘要。

### M4：结果解析、结果审计和参考态审计

目标：

- 解析一个计算结果。
- 生成 `CalcResult`。
- 计算一个 derived quantity，例如吸附能。
- 完成 G7 审计。

验收：

- 吸附能公式、单位、参考态完整。
- 未收敛结果被 BLOCK。
- G7 PASS 结果可进入图表。

### M5：图表、Claim Ledger 和论文骨架

目标：

- 生成一张可追溯图表。
- 建立计算 claim ledger。
- 生成 claim-ledger-only 的 manuscript skeleton。

验收：

- 图表绑定 source table、plot script hash、AiiDA UUID。
- 摘要/结论不允许出现 L0-L2 越界主结论。
- Manuscript Claim Audit 能定位未入账 claim。

### M6：毕业合规和投稿前检查

目标：

- 把已有毕业规则转成 `GraduationRuleSet`。
- 对 manuscript artifact 生成合规报告。

验收：

- 输出 A/B/C 档预估。
- 输出作者、单位、分区、负面期刊、支撑材料核验清单。

## 9. 第一版建议的最小闭环

第一版不要试图一次完成完整 Ru-CeO2/NH3 合成论文。应先证明以下闭环成立：

```text
已有问题卡
  -> adapter 导入
  -> C2/C3 复核
  -> adsorption/slab protocol 绑定
  -> 生成一个结构模型
  -> G4/G5 审计
  -> AiiDA 记录一个计算
  -> parser 提取结果
  -> G7 审计
  -> 生成一张图
  -> 写入 claim ledger
  -> 生成只引用 claim_id 的论文骨架
```

只要这个闭环跑通，后续扩展 NEB、Bader、PDOS、微观动力学和多材料筛选就是横向增加 protocol，而不是重建架构。

## 10. 科学把关规则优先级

最优先规则：

1. 未通过 protocol gate，不得生成输入。
2. 未通过 structure gate，不得提交计算。
3. 未通过 input gate，不得进入 AiiDA。
4. 未收敛或 provenance 缺失，不得进入图表。
5. 参考态不一致，不得计算 derived quantity。
6. 未进入 claim ledger，不得进入摘要、结论或图注。
7. L2 claim 不得写成主结论。
8. 任何自动修复必须保留原始失败记录。
9. 任何期刊/毕业档位判断必须标记核验状态。

## 11. 与 GitHub 脚手架的关系

可直接复用：

- AiiDA Core 和 aiida-* 插件：计算 provenance 与执行。
- pymatgen/ASE：结构对象和几何操作。
- custodian：错误类型和修复策略参考。
- PaperQA2：文献证据定位增强。
- pandas/matplotlib/plotly：数据表和图表。

只作参考：

- atomate2/jobflow：成熟 workflow、输入集合、TaskDocument 思路。
- Agent Laboratory/AI-Scientist：研究流程和报告结构。
- LangGraph：后续状态机和人工中断。

必须自建：

- protocol 参数级规范。
- G0-G10 Gate 规则。
- 结构、输入、结果和参考态审计。
- claim ledger。
- manuscript claim audit。
- graduation compliance。
- 前端问题 Agent 到 AiiDA 计算层的 adapter。

## 12. 风险与缓解

| 风险 | 后果 | 缓解 |
| --- | --- | --- |
| protocol 过早写得太泛 | 输入生成仍然自由发挥 | 先只做 2 个 executable protocol，字段不全即 BLOCK |
| AiiDA 接入耗时 | 计算闭环延迟 | 先跑 dummy/local 任务，证明 provenance 链，再接真实 DFT |
| 结构生成自动化过度 | 生成化学上不合理模型 | 结构 Agent 只生成候选，Structure Audit 和人工确认负责放行 |
| 自动修复掩盖失败 | 结果不可复现 | retry ledger 强制记录原始失败、参数差异和科学影响 |
| 图表先于 claim ledger | 论文容易过度解释 | G8 图表只绑定数据，G9 才允许绑定 claim |
| LLM 生成新结论 | 幻觉或过度宣称 | Manuscript Agent 只能读取 claim bundle |
| 期刊档位信息过期 | 毕业判断错误 | 所有期刊分区和负面清单状态必须人工核验并记录日期 |

## 13. 近期开发建议

建议立即启动的三个实现任务：

1. 建立 `QuestionAgentAdapter + schema + ledger.sqlite`，把现有前端 Agent 产物接入统一账本。
2. 将 `protocol_registry/protocols.yaml` 升级为真正的 `CalcProtocol`，先完成 slab 和 adsorption energy 两个 protocol。
3. 实现 G3-G5 的最小审计链：Protocol Gate、Structure Gate、Input Gate。

在这三项完成前，不建议投入大量时间写 Manuscript Agent 或复杂论文生成，因为没有通过 G4-G7 的计算证据链，后续写作只能产生不可审计文本。

## 14. 阶段性完成定义

当以下条件满足时，可以认为“自建科学把关类 Agent MVP”完成：

- 已有文献问题 Agent 的输出能被稳定导入。
- 每个候选问题都有 C2/C3 复核和 protocol 绑定。
- 至少一个结构模型通过 G4。
- 至少一个输入任务通过 G5 并进入 AiiDA。
- 至少一个计算结果通过 G7。
- 至少一张图通过 G8。
- 至少一个 L2/L3 计算 claim 写入 claim ledger。
- manuscript skeleton 中的关键句全部引用 claim_id。
- 毕业合规报告能给出 A/B/C 档预估和人工核验清单。

该 MVP 的价值不是“自动写出一篇论文”，而是证明：任何进入论文草稿的计算化学结论，都能被追溯、被审计、被人工接管。
