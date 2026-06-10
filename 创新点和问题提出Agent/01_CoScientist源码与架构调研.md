# Co-Scientist 源码与架构调研

调研日期：2026-06-01

## 1. 可用来源

### 1.1 官方资料

Google Research/DeepMind 公开了 AI Co-Scientist 的论文和介绍，但未看到可直接使用的官方完整代码仓库。

可参考资料：

- Google Research blog: <https://research.google/blog/accelerating-scientific-breakthroughs-with-an-ai-co-scientist/>
- Google DeepMind blog: <https://deepmind.google/discover/blog/ai-co-scientist-a-multi-agent-ai-partner-to-accelerate-scientific-discovery/>
- arXiv paper: <https://arxiv.org/abs/2502.18864>

官方系统的核心思想：

- 以科学目标为输入，生成候选假设。
- 多 Agent 协同完成生成、反思、排序、演化和元评审。
- 使用文献和外部工具增强假设质量。
- 通过多轮迭代让假设从粗糙想法演化为更具体、可测试的研究计划。

### 1.2 开源复现 1：jataware/open-coscientist

仓库：<https://github.com/jataware/open-coscientist>

该仓库是 source-available 的 Co-Scientist 风格复现，值得借鉴的不是具体科学领域内容，而是工程组织方式。

可借鉴点：

- 使用工作流图组织系统，而不是一次性长 prompt。
- 将研究目标、假设、反思、排名、进化结果放进共享状态。
- 支持不同生成模式，例如 literature-grounded、assumptions-first、simulation-grounded。
- 将领域适配作为配置问题，而不是把某一领域写死在核心逻辑中。
- 强调可观察的中间产物，便于调试和审计。

不建议直接照搬的点：

- 它的目标是通用开放式 hypothesis generation，而本项目目标是催化领域的毕业导向问题卡片。
- 它偏向完整 co-scientist 原型，MVP 直接照搬会增加实现复杂度。
- 它的领域配置不能替代催化专用的 DFT/NEB/微观动力学约束。

### 1.3 开源复现 2：LLNL/open-ai-co-scientist

仓库：<https://github.com/LLNL/open-ai-co-scientist>

该仓库更像一个开放式科学假设生成应用原型。它可作为“交互式 hypothesis generation UI/应用形态”的参考，但不适合作为本项目的核心架构蓝本。

可借鉴点：

- 将用户科学目标转化为结构化研究问题。
- 将多个 agent 的产出汇总成可读报告。
- 可用于理解开放式假设生成系统的用户交互形态。

不建议直接照搬的点：

- 与催化计算工作流衔接较弱。
- 不包含本项目需要的毕业合规、纯计算可验证性、计算成本估计、证据账本等强约束。

## 2. Co-Scientist 架构中可借鉴的机制

| Co-Scientist 机制 | 本项目借鉴方式 | MVP 是否实现 |
| --- | --- | --- |
| Generation | 生成候选创新点和问题卡片 | 是 |
| Reflection/Critique | 检查逻辑、文献支撑、过度宣称、催化合理性 | 是 |
| Ranking | 按新颖性、可计算性、毕业价值、成本排序 | 是 |
| Evolution | 把泛泛问题改写为更具体、更可计算的问题 | 是 |
| Proximity/Diversity | 对问题去重，避免 20 张卡片只是同一问题改写 | 是，先用聚类/规则 |
| Meta-review | 输出推荐题目和淘汰理由 | 是 |
| Tournament/Elo | 大规模假设锦标赛排序 | 暂缓 |
| Asynchronous multi-agent loop | 多 Agent 长循环异步探索 | 暂缓 |
| External tool use | 联网检索、数据库查询、文献解析 | 分阶段接入 |

## 3. 对本项目的关键改造

原版 Co-Scientist 的核心问题是“提出科学假设”。本项目的核心问题更具体：

> 提出催化领域中有文献证据、有新颖性、有论文故事线，并可能由纯计算实验解决的研究问题。

因此必须新增以下约束层：

1. 催化领域本体
   - 反应、催化剂、活性位点、吸附物、中间体、缺陷、界面、反应路径。

2. 纯计算可验证性预筛
   - 区分 C0/C1/C2/C3，避免把必须湿实验验证的问题送入毕业主线。

3. 计算成本估计
   - slab 数、缺陷/掺杂数、吸附物数量、NEB 数量、电子结构分析、微观动力学复杂度。

4. 证据账本
   - 每个共识、争议、问题卡片必须绑定文献或数据源。

5. 毕业导向评分
   - 选题不只追求有趣，还要考虑发表可能性、目标成果档位、时间成本和与学位论文主线相关性。

## 4. 架构取舍结论

建议采用：

```text
Co-Scientist-inspired workflow
+ Catalysis-specific evidence constraints
+ Computability pre-filter
+ Graduation-oriented scoring
```

不建议采用：

```text
完整 Co-Scientist 异步多 Agent tournament 架构
```

理由：

- 当前模块只是整个自动科研系统的前端，不应该吞掉太多复杂度。
- MVP 的核心风险不是假设数量不够，而是假设无证据、不可计算、不可发表。
- 三阶段工作流已经足够复现 Co-Scientist 中最有价值的生成、批判、演化逻辑。
