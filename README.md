# Auto-computation-catalysis-research-Agent

自动计算催化研究 Agent。当前仓库保存“稳定可审计计算化学科研发文 Agent”的自有主线代码、设计文档和最小可运行验证流程。

## 当前工程主线

这个项目现在分成两层，后续开发要按这个边界走，避免重复造模块。

```text
创新点和问题提出Agent/
  前端 Agent：文献证据、共识/争议、问题卡片、初步排序。

research_agent/
  自建科学把关主线：schema、adapter、P0/P1/P2... gate、protocol、claim ledger 等。

docs/
  需求、架构、模块复用、重复比对和工程整合说明。

tests/
  顶层 research_agent 的 P0 科学把关测试。

合成氨综述/07_AI流水线/
  与综述写作项目衔接的可复用脚本。其他综述工作区默认不纳入 Git。
```

核心规则：

- 新增自建科学把关模块时，优先放到 `research_agent/`。
- `创新点和问题提出Agent/` 只继续承担前端文献/问题发现和兼容入口。
- 不再在 `catalysis_question_agent` 里新增独立的 P0/P1/P2 gate、protocol registry、claim ledger 主模块。
- 旧 dry-run 兼容代码可以保留，但必须调用 `research_agent` 的正式 schema/gate/protocol。

## 模块职责

### `创新点和问题提出Agent/`

已有前端 MVP，负责：

- 本地文献/资料读取。
- evidence table、method evidence、literature matrix。
- 共识、争议、open gap 提取。
- research question cards 生成。
- 前端 G1-G3 预审和 ranking。

它的标准下游输出包括：

```text
literature/evidence_table.csv
literature/method_evidence.csv
literature/literature_matrix.csv
question_cards/all_question_cards.json
review/ranking_table.csv
review/gate_audit_report.md
run_summary.json
```

### `research_agent/`

正式自建科学把关包，负责承接前端输出，并执行可审计 gate。

当前已实现 P0：

- `QuestionAgentAdapter`：导入前端 Agent 输出。
- `ComputationalFeasibilityGatekeeper`：复核 C0-C3 和 computation-only claim 边界。
- `ProtocolRegistry`：只允许 `executable_mvp` / `executable_reviewed` protocol 进入后续计算。
- `AuditGateOrchestrator`：执行 G1 文献证据、G2 计算可验证性、G3 protocol gate。

后续 P1/P2/P3 应继续在这里扩展：

```text
research_agent/
  structures/      # P1 Structure Model/Audit
  inputs/          # P1 Input Builder/Audit
  aiida_bridge/    # P1/P2 AiiDA provenance
  execution/       # P2 monitor / retry ledger
  results/         # P2 parser / result audit / reference-state audit
  figures/         # P3 figure/table artifact and G8
  claims/          # P3 claim ledger and G9
  manuscript/      # manuscript claim audit
  compliance/      # graduation/submission G10
```

## 当前流程

### 1. 运行前端问题发现 Agent

```powershell
cd "创新点和问题提出Agent"
python run_agent.py --input examples\toy_sources --output outputs\debug_protocol_gate
```

正式文献库运行请使用脱敏配置或本地 `.local.yaml`，不要把真实路径、API key 或封闭文献上传。

公开仓库中的 `06_config_real_ammonia_library.yaml` 是脱敏模板；真实本地文献路径请放到已忽略的 `06_config_real_ammonia_library.local.yaml`。

### 2. 执行 P0 科学把关

在仓库根目录运行：

```powershell
python -m research_agent.p0_audit `
  --question-agent-output "创新点和问题提出Agent\outputs\debug_protocol_gate" `
  --out "pipeline_outputs\p0_audit_debug_protocol_gate.json"
```

P0 会输出：

- 导入了多少问题、证据和 method evidence。
- 每个问题的 G1/G2/G3 状态。
- 哪些 protocol 是 `planning_stub`，因此不能继续生成结构或输入。

### 3. 运行兼容 dry-run 全链入口

```powershell
python "创新点和问题提出Agent\run_research_pipeline.py" `
  --question-output "创新点和问题提出Agent\outputs\debug_protocol_gate" `
  --output "pipeline_outputs\integrated_scaffold"
```

注意：这个入口只是兼容入口。它的 P0 导入、可计算性和 protocol gate 已经调用顶层 `research_agent`。

如果 P0/G3 为 `BLOCK`，后续 dry-run 不会继续生成结构、输入或模拟 AiiDA task。这是正确行为，不是失败。

## Protocol 状态规则

Protocol registry 主线在：

```text
research_agent/protocols/core_protocols.yaml
```

状态含义：

- `planning_stub`：只允许问题预绑定，不能生成输入或 AiiDA task。
- `executable_mvp`：允许进入 MVP 输入/结构/计算 dry-run，但仍需要人工复核。
- `executable_reviewed`：后续用于更严格的真实计算任务。
- `deprecated`：不能用于新任务。

当前只有少数 protocol 是 `executable_mvp`。如果问题同时要求 `planning_stub` protocol，P0/G3 会阻断整条计算主线。

## 避免重复开发

下表是当前权威模块归属：

| 功能 | 权威位置 | 不再新增到 |
| --- | --- | --- |
| 前端文献/问题生成 | `创新点和问题提出Agent/src/catalysis_question_agent/` | `research_agent/` |
| 前端输出导入 | `research_agent/adapters/question_agent_adapter.py` | `catalysis_question_agent/question_agent_adapter.py` |
| P0 schema | `research_agent/schemas/core.py` | `catalysis_question_agent/research_pipeline_models.py` |
| 计算可验证性 G2 | `research_agent/gates/feasibility.py` | `catalysis_question_agent/audit_gates.py` |
| G1-G3 orchestration | `research_agent/gates/orchestrator.py` | `catalysis_question_agent/audit_gates.py` |
| Protocol Registry | `research_agent/protocols/registry.py` | `catalysis_question_agent/protocol_registry.py` |
| 后续 P1/P2/P3 自建模块 | `research_agent/` 新子包 | 前端 Agent 包 |

详细比对见：

```text
docs/模块重复比对与工程整合.md
```

## 快速验证

根目录 P0 测试：

```powershell
python -m unittest discover -s tests
```

前端 Agent 兼容测试：

```powershell
cd "创新点和问题提出Agent"
python -m unittest discover -s tests
```

建议上传 GitHub 前两套都跑一遍。

## GitHub 上传前检查

不要上传：

- 真实 API key、`.env`、`*.local.yaml`、`*.secret`。
- 本地 PDF、Zotero 导出、封闭出版社全文、未获授权文献。
- `external/github_scaffolds/` 第三方项目克隆。
- `pipeline_outputs/`、`**/outputs/`、`**/generated/` 运行产物。
- AiiDA 数据库、SQLite 账本、原始计算输出、压缩归档。
- 含个人路径、导师/组内信息、未公开投稿计划的文档。

上传前建议运行：

```powershell
git status --short --ignored
```

确认 `!!` 忽略项里包含：

```text
external/
pipeline_outputs/
**/outputs/
__pycache__/
*.local.yaml
```

再做一次敏感词粗查：

```powershell
Select-String -Path README.md,docs\*.md,**\*.py,**\*.yaml `
  -Pattern "api_key|secret|token|password|sk-|DEEPSEEK_API_KEY|UNPAYWALL_EMAIL" `
  -CaseSensitive:$false
```

如果命中的是 `.env.example` 或说明性占位符可以保留；如果是真实 key、邮箱、路径或账号，先脱敏。

## 密钥使用

不要把真实 API key 写入可提交配置。推荐用环境变量：

```powershell
$env:DEEPSEEK_API_KEY="<your local key>"
$env:UNPAYWALL_EMAIL="you@example.com"
```

本机调试配置请使用：

```text
*.local.yaml
.env
```

这些文件已被 `.gitignore` 忽略。

## 当前 Git 策略

建议纳入 Git：

- `README.md`
- `.gitignore`
- `.gitattributes`
- `.env.example`
- `docs/*.md`
- `research_agent/**/*.py`
- `research_agent/protocols/core_protocols.yaml`
- `tests/*.py`
- `创新点和问题提出Agent/` 中的源代码、测试、示例配置和 toy sources
- `创新点和问题提出Agent/06_config_real_ammonia_library.yaml` 可作为脱敏模板提交

建议不要纳入 Git：

- `external/github_scaffolds/`
- `pipeline_outputs/`
- `创新点和问题提出Agent/outputs/`
- `合成氨综述/` 除 `07_AI流水线/` 外的工作区内容
- 本地文献库、PDF、计算输出和私有数据
