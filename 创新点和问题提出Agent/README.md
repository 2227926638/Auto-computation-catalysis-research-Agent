# 创新点和问题提出 Agent

本文件夹用于沉淀“文献共识与问题发现 Agent”的前端设计。目标是借鉴 Google/DeepMind Co-Scientist 的假设生成思想，但服务于本项目更窄的任务：

> 从催化文献、会议/访谈、专利与产学研信号中发现创新点，并生成可被后续“纯计算可验证性判别 Agent”和“计算规划 Agent”接管的问题卡片。

## 设计结论

当前不建议照搬完整 Co-Scientist，也不建议一开始拆成很多独立 Agent。

推荐第一版采用：

```text
单个复合 Agent + 三阶段可审计工作流
```

三阶段为：

1. `EvidenceBuilder`：资料采集、文献矩阵、共识/争议/空白抽取。
2. `QuestionGenerator`：生成候选创新点和研究问题卡片。
3. `QuestionReviewer`：批判、去重、纯计算潜力预筛、排序、演化。

内部借鉴 Co-Scientist 的 `Generate -> Critique/Reflect -> Rank -> Evolve -> Meta-review` 思想，但不在 MVP 中实现大规模 tournament、Elo 排名或异步多 Agent 竞赛。

## 文件说明

| 文件 | 用途 |
| --- | --- |
| `01_CoScientist源码与架构调研.md` | 记录官方资料和开源复现代码中可借鉴的架构元素。 |
| `02_创新点和问题提出Agent设计.md` | 当前 Agent 的总体设计、流程、内部角色和取舍。 |
| `03_数据模型与上下游接口.md` | 输入、输出、核心数据结构、项目账本接口。 |
| `04_MVP实施路线.md` | 第一版实现路线、验收标准、后续增强项。 |
| `05_config_catalysis_question_agent.yaml` | 面向 Ru-CeO2/N2 活化示范方向的配置草案。 |
| `06_config_real_ammonia_library.yaml` | 接入真实合成氨文献库的调试配置。 |
| `10_自动化升级方案与认知整合层.md` | 后续自动化路线，以及 InsightLedger 长期认识账本设计。 |

## 当前实现骨架

已加入一个可运行的离线 MVP Python 骨架：

```text
src/catalysis_question_agent/
  models.py              # Pydantic 数据模型
  config.py              # YAML 配置读取
  evidence_builder.py    # 本地 md/txt/csv 证据抽取
  question_generator.py  # 问题卡片生成
  question_reviewer.py   # 批判、去重、评分、排序
  insight_ledger.py      # 长期认识账本和每次运行的 delta report
  source_registry.py     # 优秀信源注册表
  source_harvester.py    # 开放 API / 元数据增量搜集
  signal_ranker.py       # 信源质量和相关性初筛
  workflow.py            # 三阶段顺序工作流
  cli.py                 # 命令行入口
```

运行测试：

```powershell
python -m unittest discover -s tests
```

运行 toy 示例：

```powershell
python run_agent.py --input examples\toy_sources --output outputs\smoke_test
```

注意：`examples/toy_sources` 仅用于验证流程，不是可引用文献证据。正式运行时应输入真实文献导出的 `.csv`、本地 `.md` 或 `.txt` 资料。

运行真实合成氨文献库调试：

```powershell
python run_agent.py --config 06_config_real_ammonia_library.yaml --output outputs\real_ammonia_debug
```

该配置默认读取：

```text
D:\SaXin\Science\合成氨催化剂入库文献
```

并用 `source_filters` 优先筛选 Ru/CeO2、ceria-supported Ru、oxygen vacancy、Ce3+ 和 hydrogen poisoning 相关材料。

如果 `metadata_enrichment.enabled` 或 `similar_work_search.enabled` 为 true，运行时还会调用 Crossref/OpenAlex 获取：

- `metadata/enriched_metadata.csv`
- `metadata/similar_works.csv`
- `metadata/metadata_enrichment_report.md`

## 认知收集层 / Source Harvest

现在增加了独立的信源发现与初筛入口。它只做元数据和开放全文线索发现，不模拟浏览器下载封闭出版社全文：

```powershell
python run_agent.py --config 06_config_real_ammonia_library.yaml --harvest --limit 20
```

如果要把信源发现结果直接接入现有问题发现 workflow：

```powershell
python run_agent.py --config 06_config_real_ammonia_library.yaml --harvest-workflow --limit 20
```

默认输出：

```text
outputs/intelligence/YYYY-MM-DD/
  new_sources.csv
  new_sources.jsonl
  source_triage.md
  source_harvest_summary.json
  intake/
    metadata_evidence_stubs/
    selected_metadata_sources.csv
    fulltext_acquisition_queue.csv
    oa_fulltext_queue.csv
    intake_manifest.json
  workflow/
    literature/
    insight/
    question_cards/
    review/
```

默认信源注册表：

```text
source_registry.yaml
```

第一版已覆盖：

- OpenAlex：AI、AI4S、催化正式论文发现。
- Crossref：DOI 元数据和 TDM/full-text link 线索。
- arXiv：AI4S 开放预印本。
- ChemRxiv：通过 Crossref DOI prefix `10.26434` 做预印本元数据发现。
- Unpaywall：如果设置了 `UNPAYWALL_EMAIL` 或 `api.mailto`，自动补充开放全文路径。
- `local_pdf_inbox`：用于后续接收通过学校权限或人工合法获取的高价值封闭论文。

关键原则：

- `new_sources.csv` 是候选信源队列，不直接等同于论文证据。
- `source_triage.md` 会把候选分成 `oa_fulltext_ready`、`fulltext_queue`、`metadata_watch` 和 `archive_low_signal`。
- 封闭全文不做网页模拟下载；只进入 `local_pdf_inbox` 或已确认许可的 TDM/API 路线。

## DeepSeek LLM 接口

当前代码已预留 DeepSeek API 接口，默认关闭：

```yaml
llm:
  enabled: false
  provider: "deepseek"
  api_key: ""
  api_key_env: "DEEPSEEK_API_KEY"
  base_url: "https://api.deepseek.com"
  model: "deepseek-v4-pro"
```

填写位置：

- toy/MVP 配置：`05_config_catalysis_question_agent.yaml`
- 真实文献库配置：`06_config_real_ammonia_library.yaml`

启用方式二选一：

1. 直接在 YAML 中填写 `llm.api_key`，并将 `llm.enabled` 改成 `true`。
2. 保持 `llm.api_key: ""`，在环境变量中设置 `DEEPSEEK_API_KEY`，并将 `llm.enabled` 改成 `true`。

DeepSeek 启用后会参与：

- `generate_question_cards`：根据证据、共识和规则种子卡片生成更自然的问题卡片。
- `critique_cards`：批判高分卡片、改写模板化标题、补充下游检查项。

LLM 调用日志会写入：

```text
llm/llm_call_log.json
```

## 自然语言问询模式

现在支持直接用自然语言启动一次隔离问询：

```powershell
python run_agent.py --config 06_config_real_ammonia_library.yaml --request "我想围绕 Ru-CeO2 中氧空位、Ru cluster active site 和 hydrogen poisoning 对 N2 活化与 NHx 氢化机制的影响，找 5 个适合纯计算推进的创新问题"
```

也可以把请求写成一个 `.md` 文件：

```powershell
python run_agent.py --config 06_config_real_ammonia_library.yaml --request-file requests\ru_ceo2_oxygen_vacancy.md
```

自然语言模式会自动创建隔离目录：

```text
outputs\natural_requests\nl_时间戳_hash_slug\
```

每次问询会单独保存：

```text
request\user_request.md          # 原始自然语言请求
request\config_patch.json        # DeepSeek 生成的配置补丁
request\generated_config.yaml    # 本次运行配置，api_key 已脱敏
insight\consensus_list.md
question_cards\high_priority_cards.md
question_cards\all_question_cards.json
review\meta_review.md
llm\llm_call_log.json
insight\insight_ledger_snapshot.json
insight\insight_delta.json
insight\insight_delta_report.md
```

这样每次问询得到的共识、问题卡片、元数据和日志互不混杂。

## 认知整合层

现在 workflow 会在每次运行后更新 `InsightLedger`。它把本轮 `consensus`、`controversy` 和 `question_cards` 转成长期认识条目，并生成本次变化报告：

- `new_claim`：首次进入账本的共识/争议。
- `strengthened`：新增稳定支持证据。
- `challenged`：新增反向或争议证据。
- `new_question`：首次进入账本的问题卡。
- `unchanged`：重复观察到，但没有新的稳定证据键。

真实库配置的持久化账本默认写到：

```text
outputs/insight_ledger/real_ammonia_ru_ceo2_debug_ledger.json
```

## 和总系统的关系

本 Agent 是整个自动科研系统的前端模块，不负责完整计算规划、结构生成、计算执行、图表生成或论文写作。

它的直接下游是：

- `纯计算可验证性判别 Agent`
- `新颖性与期刊匹配 Agent`
- `计算规划 Agent`

它的核心交付物是：

- 文献矩阵
- 共识清单
- 争议清单
- 开放问题清单
- 研究问题卡片
- 高优先级候选问题推荐报告
