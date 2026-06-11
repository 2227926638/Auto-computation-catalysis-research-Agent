# Auto-computation-catalysis-research-Agent

以 **AiiDA provenance** 为主干的全自动催化科研流水线（多 Agent 架构）。

## 目标

围绕催化领域（可聚焦到具体反应体系），自动完成：
1. 检索已有共识与争议问题；
2. 识别待解决科学问题；
3. 通过“纯计算化学可行性”闸门筛选无需湿实验即可验证/更新认知的问题；
4. 基于 AiiDA 可追溯执行计算任务并沉淀证据；
5. 自动输出图表、PPT 与科研文章草稿。

## 多 Agent 架构（必须组件）

- **PI Orchestrator Agent**：任务编排、里程碑控制、跨 Agent 调度。
- **Literature Evidence Agent**：文献检索、证据提取、共识/分歧总结。
- **Research Question Agent**：从证据中形成可计算验证的研究问题与假设。
- **Computational Feasibility Gatekeeper**：判定问题是否可由纯计算化学完成验证。
- **Protocol Registry Agent**：维护计算协议模板与方法学版本。
- **Structure Model Agent**：生成催化剂/中间体/过渡态结构模型与输入。
- **Structure/Input/Result Audit Agent**：对结构、输入与结果进行一致性审计。
- **AiiDA Provenance Agent**：将流程节点、参数、数据与依赖挂接到 AiiDA provenance。
- **Execution Agent**：提交、监控与回收计算任务（DFT/NEB/频率等）。
- **Error Diagnosis Agent**：对失败任务进行根因分析与自动修复重试。
- **Figure and Table Agent**：自动生成科研图表与汇总表。
- **Claim Ledger Agent**：将“结论-证据-可追溯节点”进行账本化管理。
- **Manuscript Agent**：生成论文初稿（摘要、方法、结果、讨论、补充信息）。
- **Graduation Compliance Agent**：按学位要求/格式规范生成答辩材料（含 PPT）。

## 端到端工作流

1. **选题输入**：指定反应（如 CO2RR、HER、NRR）与约束（算力、方法）。
2. **证据构建**：检索文献并形成“共识/空白/争议”知识图。
3. **问题生成**：提出可检验问题，附带计算可行性评估。
4. **协议与模型准备**：注册协议，构建结构并完成输入审计。
5. **AiiDA 驱动执行**：执行计算并自动记录 provenance。
6. **失败诊断闭环**：失败自动分类、修复、重提交流程。
7. **证据到账本**：把关键 claim 与 provenance 节点绑定。
8. **成果自动产出**：生成图表、PPT、论文草稿。

## 最小可交付规范（MVP）

- 任一研究结论都必须可追溯到 AiiDA 节点（可复现）。
- 仅当 `Computational Feasibility Gatekeeper` 判定通过时才允许进入执行。
- 输出至少包括：
  - 结论-证据对照表（Claim Ledger）
  - 关键能垒/吸附能图表
  - 汇报 PPT 草稿
  - 论文草稿（含方法与可复现实验信息）

## 建议目录（后续实现）

```text
agents/
  pi_orchestrator/
  literature_evidence/
  research_question/
  computational_feasibility_gatekeeper/
  protocol_registry/
  structure_model/
  structure_input_result_audit/
  aiida_provenance/
  execution/
  error_diagnosis/
  figure_table/
  claim_ledger/
  manuscript/
  graduation_compliance/
```

当前仓库先提供架构基线，后续可按以上目录落地具体代码实现。
