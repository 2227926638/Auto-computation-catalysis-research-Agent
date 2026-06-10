# 稳定可审计计算化学科研发文 Agent 需求文档

版本：v1.0
日期：2026-06-10
定位：以 AiiDA provenance 为主干，面向 AI4Catalysis / 计算催化方向，构建稳定、科学、可审计、可复现、可人工接管的自动化计算化学科研发文流程 Agent。

## 1. 文档目的

上一版《毕业导向 AI4Catalysis 自动科研 Agent 需求文档》以“最快满足博士毕业成果要求”为核心目标，设计了文献共识、问题发现、计算规划、图表和论文生成等多 Agent 模块。

经过进一步讨论，当前最核心的问题被重新定义为：

> 如何科学稳定地生成、执行、审核和追溯计算化学相关内容，并在此基础上形成可投稿、可答辩、可复核的论文材料。

因此，本版需求文档将系统底座从“轻量 Agent 编排 + 计算工具调用”调整为“以 AiiDA 为 provenance 主干的计算化学科研流水线”。LLM 不再被视为科学事实的最终裁判，而是作为规划、检索、解释、写作和审计辅助层；所有关键结论必须落到结构化证据、计算节点、原始输出和可复现脚本上。

## 2. 与旧版需求的关系

旧版文档仍然有重要价值，不应废弃。新版应继承其中的毕业约束、发文策略、问题卡片思想和论文产出目标，但系统架构和多 Agent 分工需要明显调整。

| 模块/思想 | 旧版状态 | 新版处理 |
| --- | --- | --- |
| 毕业成果 A/B/C 档规则 | 已整理得较完整 | 保留为 `Graduation Compliance RuleSet`，作为发文出口检查，不再作为底层架构中心 |
| 文献共识 Agent | 保留 | 升级为 `Literature Evidence Agent`，所有结论必须进入 evidence table |
| 问题发现 Agent | 保留 | 保留问题卡片，但增加 `Protocol Feasibility` 和 `AiiDA Executability` 字段 |
| 纯计算可验证性判别 | 保留 | 升级为硬性 Gate，未通过不得生成计算任务 |
| 计算规划 Agent | 保留但重构 | 从自由规划改为基于 `Protocol Registry` 的受控规划 |
| 结构与输入生成 Agent | 拆分 | 拆成 `Structure Model Agent`、`Protocol Registry Agent`、`Input Audit Agent` |
| 执行与失败修复 Agent | 重构 | 由 AiiDA daemon / WorkChain / CalcJob 承担执行主干，Agent 只做诊断和策略建议 |
| 数据分析与图表 Agent | 保留 | 绑定 AiiDA node UUID、原始数据、脚本 hash 和 claim ledger |
| 证据审计 Agent | 大幅强化 | 从后处理模块提升为贯穿全流程的 `Audit Gate System` |
| 论文/PPT/SI 生成 Agent | 保留但降权 | 只能基于已通过审计的 claim、figure、table 生成稿件 |
| atomate2/jobflow 作为底座 | 旧版建议之一 | 不作为主底座；作为协议参考、局部工具和可选 adapter |
| AiiDA | 旧版未作为核心 | 新版核心主干，负责 provenance、计算执行、节点追踪和可复现导出 |

## 3. 核心原则

### 3.1 Provenance First

每个计算结果必须可追溯：

`论文结论 -> 图表/表格 -> 分析脚本 -> 解析数据 -> AiiDA CalcJob/WorkChain node -> 输入结构/参数/代码/远程计算目录 -> 原始输出文件`

没有 provenance 链的结果不能进入主文关键结论。

### 3.2 Protocol First

Agent 不能自由发挥计算设置。所有计算必须基于明确的 `CalcProtocol`：

- 适用问题。
- 软件与版本。
- 结构模型要求。
- 输入参数默认值。
- 收敛标准。
- 参考态定义。
- 可接受误差。
- 必需对照组。
- 失败处理规则。
- 论文中允许如何表述。

### 3.3 LLM Is Not the Source of Scientific Truth

LLM 可以：

- 提出候选问题。
- 总结文献。
- 建议计算方案。
- 解释结果。
- 起草论文。
- 发现潜在漏洞。

LLM 不可以：

- 在无证据时生成定量结论。
- 覆盖计算失败事实。
- 修改原始结果。
- 绕过 protocol 和 audit gate。
- 将未审计结果写入正式稿。

### 3.4 Human-Interruptible

所有关键节点必须允许人工接管：

- 选题确认。
- 计算 protocol 确认。
- 结构模型确认。
- 失败任务是否重跑。
- 论文主结论确认。
- 投稿前合规确认。

### 3.5 Publishable Evidence, Not Just Automation

系统的输出不是“自动跑了很多任务”，而是可投稿论文需要的证据包：

- 文献证据。
- 结构模型。
- 计算输入。
- 原始输出。
- 数据表。
- 图表。
- 脚本。
- claim ledger。
- SI。
- manuscript draft。
- graduation compliance report。

## 4. 产品目标

### 4.1 近期目标

建立一个 AiiDA-native 的最小科研闭环，能够围绕一个计算催化问题完成：

1. 文献证据整理。
2. 研究问题卡片生成。
3. 计算可验证性判断。
4. protocol 选择。
5. 结构模型生成与审计。
6. AiiDA 计算提交与 provenance 记录。
7. 结果解析与质量审计。
8. 图表生成。
9. claim ledger 生成。
10. 论文骨架和 SI 骨架生成。

### 4.2 中期目标

支持一个完整 AI4Catalysis 论文项目：

- 1 个主反应体系。
- 1 个材料族。
- 3-5 个核心科学问题。
- 20-100 个可追溯计算任务。
- 1 套论文级主图和 SI 图。
- 1 份可投稿 manuscript draft。
- 1 份可复现数据包。

### 4.3 长期目标

形成可扩展的计算化学科研 Agent 平台：

- 支持 VASP、Quantum ESPRESSO、CP2K、ORCA 等多计算引擎。
- 支持 DFT、MLIP、NEB、Bader、DOS/PDOS、COHP、微观动力学等任务。
- 支持多反应、多材料族、多论文项目并行。
- 支持与毕业合规、投稿、审稿回复和答辩材料联动。

## 5. 非目标

第一阶段不追求：

- 完全无人监督投稿。
- 自动替代导师或作者做最终科学判断。
- 一开始覆盖所有计算软件。
- 一开始实现复杂 HPC 多集群管理。
- 一开始实现完整 AiiDA 插件开发。
- 自动证明需要湿实验才能验证的真实性能。
- 用 LLM 直接生成未被计算和文献支持的科学结论。

## 6. 总体架构

系统采用五层架构。

### 6.1 Knowledge Layer

负责文献、数据库、毕业规则和项目背景。

组件：

- 本地 PDF/Markdown 文献库。
- DOI/Crossref/OpenAlex/Semantic Scholar 元数据。
- PaperQA2 或等价科学 RAG。
- 反应知识库。
- 催化材料知识库。
- 毕业成果规则库。
- 目标期刊与负面期刊状态表。

### 6.2 Research Planning Layer

负责问题发现、可计算性判断和 protocol 选择。

组件：

- Research Question Card。
- Computational Verifiability Gate。
- Novelty Check。
- CalcProtocol Registry。
- Minimal Publishable Result Set Planner。

### 6.3 Computation Provenance Layer

系统核心层，以 AiiDA 为主干。

组件：

- AiiDA profile。
- AiiDA Computer。
- AiiDA Code。
- AiiDA Data nodes。
- AiiDA CalcJob。
- AiiDA WorkChain。
- AiiDA provenance graph。
- 原始输入/输出文件归档。
- AiiDA export/dump。

工具定位：

- `ASE`：结构对象、几何操作、初始构型生成。
- `pymatgen`：晶体、表面、缺陷、VASP/QE 输入辅助、结构分析。
- `custodian`：错误模式和修复策略参考，可被 WorkChain 调用或转写为 retry policy。
- `atomate2`：成熟 workflow 参考和局部可复用代码，不作为第一版 provenance 底座。
- `cclib/QCElemental/QCEngine`：分子量化输出解析和 schema，可作为后续扩展。

### 6.4 Audit Layer

负责计算化学内容审核。

组件：

- Structure Audit。
- Input Audit。
- Run Audit。
- Result Audit。
- Reference State Audit。
- Figure Audit。
- Claim Ledger。
- Manuscript Claim Audit。

### 6.5 Publication Layer

负责论文、SI、图表、PPT 和毕业材料。

组件：

- Figure/Table Generator。
- Manuscript Generator。
- SI Generator。
- PPT Generator。
- Cover Letter Generator。
- Reviewer Response Assistant。
- Graduation Compliance Agent。

## 7. 多 Agent 分工

### 7.1 PI Orchestrator Agent

职责：

- 维护项目目标和当前阶段。
- 调度各子 Agent。
- 确保所有关键动作经过 audit gate。
- 管理人工确认点。

不能做：

- 跳过 protocol。
- 跳过计算审计。
- 直接给出未经证据支持的最终结论。

### 7.2 Literature Evidence Agent

职责：

- 检索和整理文献。
- 抽取共识、争议、开放问题和常用计算设置。
- 将文献 claim 写入 evidence table。
- 标记证据强度和来源。

输出：

- `LiteratureRecord`。
- `ConsensusClaim`。
- `ControversyClaim`。
- `MethodEvidence`。

验收：

- 每个关键背景 claim 至少有 2 条文献证据。
- 每条文献证据必须有 DOI、题名、期刊、年份、页码或段落位置。

### 7.3 Research Question Agent

职责：

- 从文献证据中生成问题卡片。
- 把泛泛问题改写为可计算问题。
- 生成最小可发表结果集。

新增字段：

- `required_protocols`。
- `required_reference_states`。
- `aiida_executability`。
- `expected_audit_risks`。
- `wet_experiment_dependency`。

### 7.4 Computational Feasibility Gatekeeper

职责：

- 判断问题能否由纯计算回答。
- 判断是否适合第一版系统执行。
- 输出 C0-C3 评分。

评分：

- C0：必须湿实验，不能作为纯计算主线。
- C1：计算只能提供辅助讨论。
- C2：计算可回答机制性问题。
- C3：计算可形成独立论文核心。

进入计算执行的最低要求：C2。

### 7.5 Protocol Registry Agent

职责：

- 管理可用计算 protocol。
- 根据问题选择 protocol。
- 禁止不受控的自由输入。
- 为每个 protocol 维护适用范围和审计规则。

第一批 protocol：

- `slab_model_construction_protocol`。
- `oxygen_vacancy_formation_protocol`。
- `adsorption_energy_protocol`。
- `adsorbate_configuration_screening_protocol`。
- `reaction_energy_path_protocol`。
- `neb_barrier_protocol`。
- `bader_charge_protocol`。
- `pdos_analysis_protocol`。
- `cohp_analysis_protocol`。
- `microkinetic_model_protocol`。
- `mlip_prescreening_protocol`。

### 7.6 Structure Model Agent

职责：

- 基于 ASE/pymatgen 生成结构模型。
- 生成 slab、缺陷、掺杂、吸附构型。
- 记录结构来源。
- 提交结构审计。

必须记录：

- bulk 来源。
- 晶面。
- slab 层数。
- 真空层。
- 固定原子。
- 覆盖度。
- 吸附位点。
- 缺陷位置。
- 电荷/自旋假设。

### 7.7 Structure Audit Agent

职责：

- 检查几何合理性。
- 检查原子重叠。
- 检查真空层。
- 检查 slab 厚度。
- 检查吸附物是否过近/过远。
- 检查周期性镜像相互作用风险。
- 检查固定层设置。

输出：

- PASS。
- WARN。
- BLOCK。

BLOCK 结构不得进入计算。

### 7.8 Input Audit Agent

职责：

- 检查输入参数是否符合 protocol。
- 检查 functional、U 值、赝势、ENCUT、k-points、smearing、spin、dipole correction、收敛阈值。
- 检查参考态定义。
- 检查与文献和项目 protocol 的一致性。

输出：

- `InputAuditReport`。

### 7.9 AiiDA Provenance Agent

职责：

- 创建和维护 AiiDA project/profile 映射。
- 将结构、参数、代码、计算任务写入 AiiDA。
- 记录 AiiDA node UUID。
- 导出 provenance 子图。
- 提供结果追溯接口。

该 Agent 是系统的证据中枢，不由 LLM 随意修改。

### 7.10 Execution Agent

职责：

- 提交 AiiDA CalcJob/WorkChain。
- 监控任务状态。
- 读取 exit status。
- 报告失败原因。

边界：

- 不直接改写科学结论。
- 不覆盖原始输入。
- 不静默重跑。

### 7.11 Error Diagnosis Agent

职责：

- 基于 AiiDA exit status、scheduler 输出、计算输出和 custodian 规则诊断失败。
- 给出重试建议。
- 将每次重试写入 retry ledger。

失败类型：

- 电子步不收敛。
- 离子步发散。
- 磁矩异常。
- 吸附物脱附。
- 吸附物解离。
- 真空层不足。
- NEB 图像异常。
- 过渡态虚频不合理。

### 7.12 Result Parser Agent

职责：

- 从 AiiDA node 和原始输出中提取结构化结果。
- 生成 `CalcResult`。
- 记录单位、参考态、校正项和解析脚本版本。

输出：

- 能量。
- 力。
- 优化后结构。
- 磁矩。
- 电荷。
- DOS/PDOS。
- Bader。
- COHP。
- 频率。
- 反应能。
- 能垒。

### 7.13 Result Audit Agent

职责：

- 检查计算是否收敛。
- 检查结构是否发生不合理变化。
- 检查参考态是否一致。
- 检查重复计算是否一致。
- 检查数值是否落在合理范围。
- 检查是否满足论文 claim 的证据强度。

常见审核规则：

- 未收敛任务不得用于定量结论。
- 吸附能必须明确气相参考态。
- 不同 coverage 的吸附能不得直接混用。
- 含氧空位体系必须明确 vacancy formation energy 参考。
- NEB 能垒必须检查端点和图像连续性。
- 微观动力学必须明确温度、压力、覆盖度假设。

### 7.14 Figure and Table Agent

职责：

- 从审计通过的数据生成图表。
- 每张图绑定数据源、脚本、AiiDA node UUID 和 claim。
- 生成主文图和 SI 图。

禁止：

- 使用手工复制的无 provenance 数值。
- 图表数值与 source table 不一致。
- 图注中写入未审计 claim。

### 7.15 Claim Ledger Agent

职责：

- 管理论文所有关键 claim。
- 绑定文献、计算、图表和风险等级。
- 标记是否可进入摘要、结果、讨论或结论。

claim 等级：

- L0：未经证据支持，不得使用。
- L1：文献支持，可用于背景。
- L2：单一计算支持，只能谨慎表述。
- L3：多计算/对照支持，可作为结果。
- L4：多证据链支持，可作为主结论。

### 7.16 Manuscript Agent

职责：

- 基于通过审计的 claim 生成论文草稿。
- 生成摘要、引言、方法、结果、讨论、结论。
- 生成 SI 草稿。
- 保证引用和图表编号一致。

限制：

- 不能新增 claim。
- 不能虚构文献。
- 不能夸大计算结论。

### 7.17 Graduation Compliance Agent

职责：

- 继承旧版文档中的毕业规则。
- 检查 A/B/C 档路径。
- 检查作者顺序。
- 检查中国科大第一单位。
- 检查期刊分区和负面期刊状态。
- 生成毕业申请材料清单。

## 8. 审计 Gate 设计

所有项目必须经过以下 Gate。

| Gate | 名称 | 目标 | 未通过后果 |
| --- | --- | --- | --- |
| G0 | Project Scope Gate | 反应、材料、毕业目标、计算资源明确 | 不生成问题卡片 |
| G1 | Literature Evidence Gate | 背景和问题有文献证据 | 不进入选题池 |
| G2 | Computational Verifiability Gate | 问题可纯计算回答 | 不进入计算规划 |
| G3 | Protocol Gate | 有已注册 protocol 支持 | 不生成输入 |
| G4 | Structure Gate | 模型几何合理 | 不提交计算 |
| G5 | Input Gate | 参数符合 protocol | 不提交计算 |
| G6 | Run Gate | 任务正常完成且收敛 | 不进入定量分析 |
| G7 | Result Gate | 结果自洽且参考态正确 | 不进入图表 |
| G8 | Figure Gate | 图表与数据一致 | 不进入论文 |
| G9 | Claim Gate | 论文 claim 有证据链 | 不进入正式稿 |
| G10 | Graduation/Submission Gate | 满足毕业和投稿合规 | 不进入投稿包 |

每个 Gate 输出：

- `status`: PASS / WARN / BLOCK。
- `reason`。
- `evidence_links`。
- `human_review_required`。
- `next_action`。

## 9. 数据模型

### 9.1 Project

- `project_id`。
- `title`。
- `reaction`。
- `catalyst_family`。
- `graduation_target`。
- `aiida_profile`。
- `status`。
- `created_at`。
- `updated_at`。

### 9.2 ResearchQuestionCard

- `question_id`。
- `title`。
- `background_consensus`。
- `open_problem`。
- `computational_verifiability_score`。
- `required_protocols`。
- `required_structures`。
- `minimal_publishable_result_set`。
- `expected_claims`。
- `risks`。
- `human_decision`。

### 9.3 CalcProtocol

- `protocol_id`。
- `name`。
- `purpose`。
- `applicable_systems`。
- `forbidden_uses`。
- `software`。
- `default_parameters`。
- `convergence_criteria`。
- `reference_state_definition`。
- `required_controls`。
- `audit_rules`。
- `publication_text_template`。
- `version`。

### 9.4 StructureModel

- `structure_id`。
- `source`。
- `format`。
- `ase_hash`。
- `pymatgen_hash`。
- `aiida_node_uuid`。
- `model_type`。
- `surface_miller_index`。
- `slab_layers`。
- `vacuum_angstrom`。
- `fixed_atoms`。
- `adsorbates`。
- `coverage`。
- `defects`。
- `audit_status`。

### 9.5 CalculationTask

- `task_id`。
- `question_id`。
- `protocol_id`。
- `structure_id`。
- `aiida_process_uuid`。
- `software`。
- `code_uuid`。
- `computer_label`。
- `status`。
- `exit_status`。
- `retry_count`。
- `created_at`。
- `completed_at`。

### 9.6 CalcResult

- `result_id`。
- `task_id`。
- `aiida_node_uuid`。
- `parser_version`。
- `energy`。
- `forces`。
- `magnetization`。
- `charge`。
- `optimized_structure_uuid`。
- `derived_quantities`。
- `units`。
- `reference_state`。
- `audit_status`。

### 9.7 AuditReport

- `audit_id`。
- `target_type`。
- `target_id`。
- `gate`。
- `status`。
- `findings`。
- `risk_level`。
- `required_actions`。
- `reviewer`。
- `reviewed_at`。

### 9.8 EvidenceClaim

- `claim_id`。
- `claim_text`。
- `claim_level`。
- `literature_evidence`。
- `calculation_evidence`。
- `figure_evidence`。
- `aiida_node_uuids`。
- `risk_notes`。
- `allowed_sections`。
- `human_approval_status`。

### 9.9 FigureArtifact

- `figure_id`。
- `title`。
- `source_table`。
- `source_aiida_nodes`。
- `plot_script`。
- `script_hash`。
- `output_path`。
- `caption_claims`。
- `audit_status`。

### 9.10 ManuscriptArtifact

- `manuscript_id`。
- `target_journal`。
- `graduation_tier_estimate`。
- `sections`。
- `claim_ids`。
- `figure_ids`。
- `bibtex_path`。
- `compliance_report_id`。
- `status`。

## 10. 计算化学 Protocol 初版

### 10.1 Slab Model Protocol

目标：

- 构建可用于表面催化计算的 slab 模型。

必须定义：

- bulk 来源。
- 晶面。
- slab 层数。
- 真空层厚度。
- 表面终止。
- 固定原子策略。
- 对称/非对称 slab。
- 是否使用 dipole correction。

审核重点：

- 真空层不足 BLOCK。
- slab 太薄 WARN 或 BLOCK。
- 固定层不合理 WARN。
- 表面化学计量不明 BLOCK。

### 10.2 Adsorption Energy Protocol

目标：

- 计算吸附物在表面的吸附能。

必须定义：

- 吸附能公式。
- 气相参考态。
- slab 参考态。
- coverage。
- 自旋态。
- 结构优化标准。

审核重点：

- 气相参考态缺失 BLOCK。
- slab 和 adsorbate-slab 参数不一致 BLOCK。
- 吸附物优化后脱附或解离需单独标记。

### 10.3 Vacancy Formation Protocol

目标：

- 计算氧空位或其他缺陷形成能。

必须定义：

- 缺陷位置。
- 氧化学势参考。
- 环境条件。
- 电荷态假设。

审核重点：

- 缺陷结构未优化 BLOCK。
- 未说明参考化学势 BLOCK。
- 不同 vacancy 位置混用 WARN。

### 10.4 NEB Barrier Protocol

目标：

- 计算关键基元步骤能垒。

必须定义：

- 初态和终态。
- 图像数。
- 弹簧常数。
- climbing image 设置。
- 收敛标准。

审核重点：

- 初态/终态不收敛 BLOCK。
- 路径不连续 BLOCK。
- 最高点不合理 WARN。
- 需要频率或过渡态确认时必须标记。

### 10.5 Electronic Structure Protocol

目标：

- 用 PDOS、Bader、COHP、差分电荷密度解释机制。

必须定义：

- 使用软件。
- 计算参数。
- 投影轨道。
- 能量零点。
- 可视化脚本。

审核重点：

- 电子结构结果只能解释机制，不能单独证明活性最优。
- 图中峰位、积分、电荷转移必须可追溯。

### 10.6 Microkinetic Protocol

目标：

- 连接 DFT 能量与反应速率/速控步分析。

必须定义：

- 反应网络。
- 温度。
- 压力。
- 覆盖度假设。
- 速率常数公式。
- 热力学校正。

审核重点：

- 缺少反应网络 BLOCK。
- 参数来源不明 BLOCK。
- 过度解释实验活性 BLOCK。

## 11. 技术栈

### 11.1 主干

- Python。
- AiiDA Core。
- AiiDA daemon。
- AiiDA profile/database/repository。
- AiiDA plugins：优先评估 `aiida-vasp`、`aiida-quantumespresso`、`aiida-cp2k`。

### 11.2 结构与计算辅助

- ASE。
- pymatgen。
- custodian。
- atomate2 作为参考。
- catkit 或等价吸附位点生成工具。
- MatGL/CHGNet/M3GNet/FAIRchem 作为 MLIP 预筛选候选。

### 11.3 文献与知识库

- PaperQA2 或等价科学 RAG。
- Crossref。
- OpenAlex。
- Semantic Scholar。
- 本地 PDF/Markdown 文献库。
- Zotero/BibTeX。

### 11.4 数据分析与写作

- pandas。
- numpy。
- scipy。
- matplotlib。
- seaborn。
- plotly。
- LaTeX。
- Quarto。
- python-pptx。

### 11.5 项目账本

AiiDA 负责计算 provenance，但仍需独立项目账本管理非计算对象：

- research question。
- literature claim。
- protocol。
- audit report。
- manuscript claim。
- graduation compliance。

推荐：

- SQLite/PostgreSQL。
- Pydantic schema。
- 文件系统保存 manuscript、figures、SI、PPT。

## 12. MVP 范围

### 12.1 MVP 输入

- 一个具体反应。
- 一个材料体系。
- 一组本地文献。
- 一个可执行或可模拟的计算后端。
- 一个 AiiDA profile。

建议首个示范：

- 反应：N2 活化 / NHx 氢化。
- 材料：Ru-CeO2 或简化的氧化物模型。
- 任务：吸附能 + 结构审计 + 结果 claim ledger。

### 12.2 MVP 输出

- 10-20 条文献证据。
- 5-10 个研究问题卡片。
- 1-3 个通过 C2/C3 的问题。
- 1 套 CalcProtocol。
- 1 个结构模型。
- 1 个通过 AiiDA 记录的计算任务。
- 1 个 ResultAuditReport。
- 1 张可追溯图表。
- 1 份 claim ledger。
- 1 份论文骨架。

### 12.3 MVP 不做

- 大规模高通量。
- 多软件全覆盖。
- 复杂 NEB 全自动。
- 自动投稿。
- 全自动审稿回复。

## 13. 论文产出策略

新版系统更适合形成两类论文。

### 13.1 方法论文

暂定题目：

An auditable AiiDA-native AI agent workflow for computational catalysis research and manuscript generation

核心贡献：

- AiiDA provenance 与 LLM Agent 的分层架构。
- protocol-first 计算规划。
- claim ledger 驱动论文生成。
- 计算催化案例验证。

核心图：

1. AiiDA-native Agent 总架构。
2. 文献 claim 到计算 claim 的证据链。
3. audit gate 流程。
4. Ru-CeO2/N2 案例。
5. 自动稿件中 claim 可追溯示例。

### 13.2 计算催化论文

暂定题目：

Auditable computational reassessment of N2 activation and NHx hydrogenation on defect-engineered Ru-CeO2 catalysts

核心贡献：

- 具体催化机制。
- 可复现计算证据链。
- 氧空位/界面/吸附构型对反应路径的影响。

核心图：

1. 结构模型。
2. 吸附构型和吸附能。
3. 反应路径能量图。
4. 电子结构解释。
5. claim ledger / provenance 摘要图。

## 14. 风险与缓解

风险 1：AiiDA 学习成本较高。
缓解：第一版只实现最小 CalcJob/WorkChain，不一开始做复杂插件；先用已有插件和简单任务跑通。

风险 2：计算软件许可证或 HPC 接入不稳定。
缓解：MVP 支持 mock/local/低成本计算后端；真实论文任务再接 VASP/QE/CP2K。

风险 3：AiiDA 插件覆盖不完整。
缓解：优先选择成熟插件；必要时使用 AiiDA 记录外部执行 wrapper，但所有输入输出必须归档。

风险 4：LLM 生成不可靠结论。
缓解：所有 manuscript claim 必须从 claim ledger 读取，不允许自由新增。

风险 5：历史计算结果无法完整迁入 AiiDA。
缓解：历史结果作为 `ExternalCalcRecord` 进入项目账本，标记 provenance 等级；新计算必须 AiiDA-native。

风险 6：自动修复导致不可追踪。
缓解：每次重试创建新任务或新 process，保留差异和原因。

## 15. 验收标准

### 15.1 科学稳定性验收

- 未通过 protocol gate 的任务不能提交。
- 未收敛计算不能进入图表。
- 未通过 result audit 的数据不能进入 claim ledger。
- 未进入 claim ledger 的结论不能进入论文摘要和结论。

### 15.2 可追溯性验收

- 每个主文数字必须能追溯到 AiiDA node UUID 或明确标记的外部文献来源。
- 每张图必须有 source table 和 plotting script。
- 每个计算任务必须有输入、输出、软件、参数、结构和状态。

### 15.3 发文验收

- manuscript draft 中所有关键 claim 有 claim_id。
- SI 中包含计算细节和 provenance 摘要。
- 毕业合规报告能判断目标期刊档位、作者单位、负面期刊风险。

## 16. 开发里程碑

### M0：新版架构与 schema

- 完成本需求文档。
- 定义核心 Pydantic schema。
- 建立 protocol registry 草案。
- 建立 audit gate 状态机。

### M1：AiiDA 最小闭环

- 初始化 AiiDA profile。
- 注册本地或测试 computer/code。
- 提交 1 个简单计算任务。
- 保存 node UUID。
- 导出 provenance 摘要。

### M2：结构与输入审计

- 接入 ASE/pymatgen。
- 生成 1 个 slab 或简化结构。
- 实现 structure audit。
- 实现 input audit。

### M3：结果解析与 claim ledger

- 解析计算结果。
- 生成 ResultAuditReport。
- 生成 1 张图。
- 建立 claim ledger。

### M4：文献与问题卡片

- 接入本地文献。
- 生成文献 evidence table。
- 生成研究问题卡片。
- 将问题绑定 protocol。

### M5：论文材料生成

- 生成 manuscript skeleton。
- 生成 SI skeleton。
- 生成 figure/table package。
- 生成 graduation compliance report。

## 17. 第一批实现建议

优先实现顺序：

1. `schema`：Project、CalcProtocol、StructureModel、CalculationTask、CalcResult、AuditReport、EvidenceClaim。
2. `protocol registry`：先写 adsorption energy 和 slab model 两个 protocol。
3. `audit gates`：先实现 G3-G7，因为这些决定计算是否可信。
4. `AiiDA adapter`：先提交和读取一个最小任务。
5. `claim ledger`：让论文生成只能读取 ledger。
6. `literature/question`：接入旧版文献共识和问题卡片模块。
7. `graduation compliance`：复用旧版第 2 章规则库。

第一版可以不追求自动跑完复杂催化论文，但必须证明：

> 任何进入论文草稿的计算化学结论，都能被自动追溯、自动审计，并被人类研究者快速接管复核。
