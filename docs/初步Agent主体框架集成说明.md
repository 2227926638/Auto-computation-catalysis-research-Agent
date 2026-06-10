# 初步 Agent 主体框架集成说明

日期：2026-06-11

## 已完成

已按 `docs/GitHub脚手架可复用模块映射.md` 的主线，把外部成熟项目作为参考脚手架浅克隆到：

```text
external/github_scaffolds/
```

当前已获取：

- `aiida-core`
- `aiida-quantumespresso`
- `aiida-vasp`
- `aiida-cp2k`
- `pymatgen`
- `custodian`
- `atomate2`
- `jobflow`
- `paper-qa`
- `langgraph`
- `cclib`
- `QCEngine`
- `optimade-python-tools`
- `MatGL`
- `CHGNet`
- `FAIR-Chem`

说明：ASE 上游主仓库在 GitLab，不在 GitHub，本轮未克隆，但已在代码 manifest 中标记为后续依赖项。

## 新增主体框架

新增入口：

```text
创新点和问题提出Agent/run_research_pipeline.py
```

新增核心模块：

```text
src/catalysis_question_agent/
  question_agent_adapter.py     # 前端文献问题 Agent 输出 -> 自建账本对象
  research_pipeline.py          # 从已有问题卡片接入完整科研流水线骨架
  research_pipeline_cli.py      # CLI
  research_pipeline_models.py   # Project/Protocol/Structure/Task/Result/Gate/Claim schema
  protocol_registry.py          # protocol registry loader
  audit_gates.py                # G0-G7/G9 初版 gate
  aiida_adapter.py              # AiiDA 边界；当前支持 dry-run
  scaffold_registry.py          # 外部 GitHub 脚手架 manifest
```

`pyproject.toml` 增加了可选依赖组：

- `provenance`
- `materials`
- `literature`
- `orchestration`
- `parsers`
- `mlip`

## 当前可运行命令

使用已有 `outputs/debug_protocol_gate` 跑主体框架 dry-run：

```powershell
python "创新点和问题提出Agent\run_research_pipeline.py" `
  --question-output "创新点和问题提出Agent\outputs\debug_protocol_gate" `
  --output "pipeline_outputs\debug_scaffold" `
  --max-questions 3 `
  --max-protocols-per-question 3
```

当前示范输出：

```text
pipeline_outputs/debug_scaffold_connected/
  project.json
  question_agent_import_manifest.json
  question_import_report.json
  imported_question_records.json
  imported_literature_records.json
  imported_evidence_items.json
  imported_method_evidence.json
  selected_question_cards.json
  protocol_bindings.json
  protocol_binding_table.csv
  structure_models.json
  calculation_tasks.json
  calc_results.json
  audit_gates.json
  audit_gate_report.md
  claim_ledger.json
  claim_ledger_report.md
  manuscript_skeleton.md
  scaffold_manifest.json
  self_built_agent_connection_manifest.json
  self_built_agent_connection_report.md
  pipeline_manifest.md
  pipeline_run_summary.json
```

## 当前 dry-run 语义

这版已经能把“文献问题 Agent 输出”连到“计算科研主体框架”：

```text
QuestionAgentAdapter
  -> imported question/evidence/method/literature records
  -> candidate_for_protocol_planning filter
  -> Protocol Registry
  -> G0-G3 preplanning gates
  -> StructureModel placeholder
  -> G4-G5 audit placeholder
  -> dry-run AiiDA CalculationTask / CalcResult
  -> G6-G7 run/result gates
  -> Claim Ledger
  -> Manuscript skeleton
```

重要边界：

- dry-run 任务会生成模拟 UUID，但不会冒充真实 AiiDA 计算。
- 前端 Agent 原始输出不会被修改；adapter 记录输入文件路径和 SHA256。
- 只有 C2/C3 且前端 G1/G2/G3 合格的问题会进入 protocol planning。
- `planning_stub` protocol 只能预绑定，不能生成输入或 AiiDA dry-run task。
- 当前只有 `slab_model_construction_protocol` 和 `adsorption_energy_protocol` 标记为 `executable_mvp`。
- G7 会阻断 dry-run result 进入定量 claim。
- `manuscript_skeleton.md` 只允许 L1 文献背景 claim 进入背景部分。
- 所有 planned calculation claim 都是 L0，必须等真实 AiiDA 结果和审计通过后才能升级。

## 下一步

1. 配置真实 AiiDA profile / local computer / code。
2. 将 `AiiDAAdapter.submit()` 从 dry-run 替换为最小 AiiDA CalcJob/WorkChain 提交。
3. 用 pymatgen/ASE 生成真实 `StructureModel`，替代 placeholder。
4. 把 G4/G5 从 WARN 升级为真实结构和输入参数检查。
5. 实现 result parser，把真实 AiiDA node 输出转为 `CalcResult`。
6. 只有通过 G6/G7 的结果才能把 claim 从 L0 升级到 L2+。
