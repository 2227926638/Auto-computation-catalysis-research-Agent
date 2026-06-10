# 基于新版稳定可审计需求的文献证据与问题发现 Agent 补充设计

本文档用于承接 `docs/稳定可审计计算化学科研发文Agent需求文档.md` 中对“文献共识和问题发现 Agent”的新增要求。

## 1. 定位调整

当前模块不再只定位为“创新点雷达”，而是升级为：

`Literature Evidence + Research Question Agent`

它的职责是把文献、会议/采访、产业成果和本地数据中的信息转化为：

1. 可审计的 literature evidence table。
2. 方法证据 `MethodEvidence`。
3. 可计算研究问题卡片。
4. G1/G2/G3 预审结果。
5. 下游 Protocol Registry / AiiDA 规划层可读取的接口字段。

本 Agent 仍然不负责实际 AiiDA 计算提交、结构生成、输入文件审计、结果分析和论文成文。这些属于新版总系统的下游模块。

## 2. 新版需求对本 Agent 的硬约束

### G1 Literature Evidence Gate

每个进入推荐池的问题卡必须至少有 2 条机器链接的文献/数据证据。

当前实现：

- `EvidenceItem` 已补充 `source_doi`、`source_title`、`source_journal_or_source`、`source_year`、`source_location`。
- 输出文件：`literature/evidence_table.csv`。
- 输出报告：`review/evidence_gap_report.md`。

注意：目前位置字段来自本地文本的段落/句子定位，例如 `paragraph 3, sentence 2`。PDF 页码级定位仍需后续 PDF parser 或上游文献转换器提供。

### MethodEvidence

新版需求要求抽取常用计算设置和方法证据。

当前实现：

- 新增 `MethodEvidence` 数据模型。
- 从包含 DFT、NEB、Bader、PDOS、microkinetic、oxygen vacancy、adsorption 等方法/计算语句中抽取：
  - `protocol_hints`
  - `software_hints`
  - `calculation_type`
  - `parameter_hints`
  - `reference_state_hints`
  - `source_location`
- 输出文件：`literature/method_evidence.csv`。

### G2 Computational Verifiability Gate

新版需求要求“纯计算可验证性”成为硬门槛。

当前实现：

- `computability_prefilter.acceptable_for_next_stage` 默认只允许 `C2` 和 `C3`。
- `QuestionReviewer` 中新增 `G2_computational_verifiability` 硬门槛。
- `C0/C1` 问题不会进入推荐池，可保留为背景或综述线索。

### G3 Protocol Gate

新版需求要求问题卡必须绑定受控 `CalcProtocol`，不能自由规划计算。

当前实现：

- 新增 `protocol_registry/protocols.yaml`。
- 每张 `ResearchQuestionCard` 新增：
  - `required_protocols`
  - `required_reference_states`
  - `protocol_feasibility`
  - `aiida_executability`
  - `expected_audit_risks`
- `QuestionReviewer` 中新增 `G3_protocol_registered` 硬门槛。
- 输出报告：`review/gate_audit_report.md`。

当前 protocol registry 只用于“预绑定/预筛”，不代表已经能直接生成 AiiDA WorkChain。

## 3. 已新增或修改的核心文件

- `src/catalysis_question_agent/models.py`
  - 新增 `MethodEvidence`。
  - 扩展 `EvidenceItem` 和 `ResearchQuestionCard`。
  - `AgentRunResult` 增加 `method_evidence_count`。

- `src/catalysis_question_agent/evidence_builder.py`
  - Evidence 增加来源元数据和段落/句子位置。
  - 新增 `extract_method_evidence()`。

- `src/catalysis_question_agent/question_generator.py`
  - 根据 topic/pattern 自动绑定第一批 protocol。
  - 自动生成参考态、AiiDA 可执行性、湿实验依赖和审计风险。

- `src/catalysis_question_agent/question_reviewer.py`
  - 将 G1/G2/G3 纳入硬门槛。

- `src/catalysis_question_agent/workflow.py`
  - 新增 `literature/method_evidence.csv`。
  - 新增 `review/gate_audit_report.md`。
  - 高优先级问题卡 Markdown 中显示 protocol/reference/audit 字段。

- `src/catalysis_question_agent/llm_tasks.py`
  - DeepSeek 生成问题卡 schema 增加 protocol、reference state、audit risk 和 AiiDA executability 字段。
  - LLM 缺字段时回退到规则生成器的字段，不静默放行。

- `protocol_registry/protocols.yaml`
  - 新增 MVP 第一批 protocol 草案。

- `05_config_catalysis_question_agent.yaml`
  - 新增 `protocol_registry` 配置。
  - 新增 `method_evidence` 输出文件声明。

- `06_config_real_ammonia_library.yaml`
  - 同步新增 `protocol_registry` 配置和 `method_evidence` 输出声明。
  - 未改动 API key 值。

## 4. 当前输出结构

一次运行后，重点查看：

- `literature/evidence_table.csv`
  - 文献证据表。
- `literature/method_evidence.csv`
  - 方法和计算设置证据。
- `insight/consensus_list.md`
  - 机器抽取的共识候选。
- `question_cards/high_priority_cards.md`
  - 推荐问题卡，含 protocol/reference/audit 字段。
- `question_cards/all_question_cards.json`
  - 完整结构化问题卡。
- `review/gate_audit_report.md`
  - G1/G2/G3 门槛结果。
- `review/meta_review.md`
  - 推荐问题总览。
- `llm/llm_call_log.json`
  - DeepSeek 调用记录。

## 5. 推荐调试方式

### 规则模式 smoke test

```powershell
cd D:\SaXin\Science\自动科研Agent\创新点和问题提出Agent
python run_agent.py --config 05_config_catalysis_question_agent.yaml --input examples\toy_sources --output outputs\debug_protocol_gate
```

### 真实合成氨文献库

```powershell
cd D:\SaXin\Science\自动科研Agent\创新点和问题提出Agent
python run_agent.py --config 06_config_real_ammonia_library.yaml --request "围绕 Ru-CeO2 合成氨，找出可以用纯计算验证的机制性创新问题，优先考虑氧空位、界面位点、N2 活化和 NHx 氢化。"
```

自然语言模式会把每次问询隔离到 `outputs/natural_requests/nl_时间戳_hash_slug/`。

## 6. 当前边界

已实现：

- 文献证据表。
- 方法证据表。
- C2/C3 计算可验证硬门槛。
- protocol 预绑定。
- G1/G2/G3 审计报告。
- DeepSeek 接口 schema 更新。

未实现：

- 真正的 DOI/题名/期刊/年份自动强校验。
- PDF 页码级定位。
- 完整 novelty search。
- Protocol Registry Agent 的参数级校验。
- AiiDA profile / Computer / Code / WorkChain 生成。
- AiiDA node UUID 级 provenance。
- 后续 G4-G10 审计门。

## 7. 给下一个对话窗口的结论

当前 Agent 已经从“创新点和问题提出 MVP”升级为“文献证据 + 方法证据 + 可计算问题卡 + G1/G2/G3 预审”的前端 Agent。

下一步不应继续扩展更多发散式问题生成，而应优先做三件事：

1. 用真实合成氨文献库跑一次新版输出，检查 `method_evidence.csv` 和 `gate_audit_report.md` 是否符合预期。
2. 建立真正的 Protocol Registry Agent，把 `protocol_registry/protocols.yaml` 从草案变成参数级规范。
3. 对接 AiiDA 最小闭环，只允许通过 G1/G2/G3 的 C2/C3 问题进入计算规划。
