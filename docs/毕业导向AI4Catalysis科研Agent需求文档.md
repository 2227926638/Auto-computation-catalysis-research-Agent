# 毕业导向 AI4Catalysis 自动科研 Agent 需求文档

版本：v0.2
日期：2026-06-01
定位：以博士毕业成果达成为首要目标的、可审计、可复现、可人工接管的 AI4Catalysis 自动科研流水线。

## 1. 背景

用户希望构建一个面向催化领域，尤其是 AI4Catalysis / 计算催化方向的自动科研 Agent。该 Agent 需要自动检索催化领域已有共识和待解决问题，判断哪些问题可以完全由纯计算化学验证或更新认识，并进一步自动生成图表、PPT、论文草稿和可复现实验材料。

与通用“全自动科研 Agent”不同，本项目的近期核心目标不是无人监管地发表论文，而是快速、稳健地满足博士毕业成果要求。因此系统设计必须围绕“有效成果产出”倒推，包括目标期刊选择、A/B/C 档成果合规、作者与单位要求、数据和计算可复现、投稿材料准备、审稿回复辅助等。

## 2. 毕业成果约束

本节依据用户提供的《信息与智能学部研究生学位申请要求》人工摘录，作为 Agent 的毕业合规规则库初版。该文件自 2026 年 5 月 1 日起施行；实际申请学位前必须再次核验学部最新原文、当年负面期刊清单、中科院分区和期刊检索状态。

### 2.1 博士成果数量组合

博士研究生申请博士学位的成果质量与数量需满足以下任一组合：

1. A 档成果 1 个 + B 档成果 1 个。
2. B 档成果 3 个。
3. B 档成果 2 个 + C 档成果 2 个。
4. B 档成果 1 个 + C 档成果 3 个。

成果可以是论文、学科竞赛、专利、标准、科研获奖等。对本项目而言，主路径仍应优先使用论文成果，竞赛、标准、专利、获奖仅作为保险或补充。

### 2.2 A/B/C 档论文成果定义

| 档位 | 论文成果具体标准 |
| --- | --- |
| A 档 | SCI 一区和 SCI 二区收录的国际期刊，不包括 IEEE Access；IEEE Transactions 期刊；IEEE Journal 期刊；ACM Transactions 期刊；ACM Proceedings 期刊；中国计算机学会 CCF 推荐 A 类国际英文期刊/会议；信息与智能学部学位分委员会认定的 A 档期刊/会议。 |
| B 档 | SCI 收录的外文期刊；中国计算机学会 CCF 推荐 B 类国际英文期刊/会议；信息与智能学部学位分委员会认定的 B 档期刊/会议。 |
| C 档 | SCI 或 EI 收录的中文期刊/国际会议；EI 收录的外文期刊；中国计算机学会 CCF 推荐 C 类国际英文期刊/会议；中国计算机学会 CCF 推荐中文期刊；CSCD 收录期刊；已授权的国内外发明专利。 |

对 AI4Catalysis 发文的直接含义：

- 催化、计算化学、材料信息学方向的 SCI 外文期刊，若为中科院一区/二区，原则上可作为 A 档候选；若为 SCI 收录外文期刊但不是一区/二区，原则上可作为 B 档候选。
- `IEEE Access` 即使满足某些 SCI 或分区条件，也不得作为 A 档。
- CCF 和学部认定会议/期刊偏信息学科，对 AI4Catalysis 方法论文有参考价值，但对纯催化机制论文不是主路径。
- 期刊档位必须以论文发表或申请时的可证明分区、检索和学部认定规则为准。

### 2.3 署名、录用和内容要求

论文类成果必须满足：

- 学位申请人必须是第一作者，导师署名不计在内。
- 中国科学技术大学必须是第一署名单位。
- 论文内容必须与博士学位论文研究内容相关。
- SCI 分区使用中科院分区标准。
- A/B 档国际会议论文被录用即可用于申请学位。
- 博士研究生用于申请学位的 C 档国际会议必须已经被 EI 检索。
- 如果学术论文分档标准有修订，以在读学位期间所发表学术论文所属最高档为准，需附证明。
- 学术论文如获得最佳论文奖，该学术论文升一档次。
- 学术论文如属交叉学科，该学术论文以所有交叉学科中的最高档次标准作为标准，需附证明。

会议短文和非长文要求：

- 在 CCF-A 或 CCF-B 类推荐会议上以非长文形式发表的论文，如 Short paper 或 Findings，降一档次认定：原 CCF-A 视作 CCF-B，原 CCF-B 视作 CCF-C。
- 在 CCF-A 类推荐会议上以 Demo paper、Technical Brief、Summary 或伴随会议 Workshop 论文等非长文形式发表的论文，视作信息与智能学部 C 档成果，且必须已经被 EI 检索。
- 在非 CCF-A 或非 CCF-B 类推荐会议上以其他形式发表的论文，不能作为申请学位的有效成果。

### 2.4 专利、竞赛、标准和科研获奖折算

专利要求：

- 学位申请人必须为排序第一的发明人，导师不计在内。
- 中国科学技术大学必须为排序第一的专利权人。
- 专利内容必须与学位论文研究内容相关。
- 已授权的国内外发明专利可作为 C 档成果。

学科竞赛要求：

- 博士研究生作为第一完成人，参加信息与智能学部学位分委员会认定的学科竞赛，获得最高等级奖励，且与学位论文工作相关，可作为 B 档成果申请学位。
- 学科竞赛最多计算 1 个成果。

标准成果要求：

- 博士研究生参与国际标准或国家标准制定工作，取得符合要求的成果，可视同 1 个 B 档成果。
- 标准成果最多计算 1 个。
- 标准需为 IETF、ITU-T、ISO/IEC、IEEE、3GPP 或其他由学位分委员会认定的国际标准化组织制定的标准，或我国 GB 系列国家标准。
- 标准必须已经正式发布，参与撰写以署名为准。

科研获奖折算：

| 成果类型 | 排名要求 | 折算档位 |
| --- | --- | --- |
| 国家科学技术奖励二等奖或以上 | 排名前 6 | A 档成果 1 个 |
| 国家科学技术奖励二等奖或以上 | 其他排名 | B 档成果 1 个 |
| 省部级或有国家奖推荐资格的一级学会科学技术奖励一等奖或以上 | 排名前 3 | A 档成果 1 个 |
| 省部级或有国家奖推荐资格的一级学会科学技术奖励一等奖或以上 | 排名前 5 | B 档成果 1 个 |
| 省部级或有国家奖推荐资格的一级学会科学技术奖励一等奖或以上 | 其他排名 | C 档成果 1 个 |

### 2.5 成果补充规定

共同第一作者：

- 研究生以共同第一作者含排名第一发表的学术论文，用于申请学位时必须有导师与所有共同作者署名的同意使用和相关贡献量说明证明。
- 所有学生的贡献量总和不大于 1。
- 共同第一作者论文只能有一位学生作为学术成果用于申报学位，且必须中国科学技术大学第一。

按英文字母排序作者：

- 发表刊物原则上仅限 CCF 推荐计算机科学理论方向的国际会议/国际期刊。
- 需提前一次提交本学位分委员会并获认定，本次认定下次生效。
- 需有导师与所有作者署名的同意使用、相关贡献量说明和无第一作者证明。
- 同一成果只能一位学生作为学术成果用于申报学位，且作者本人第一完成单位必须是中国科学技术大学。

录用后署名稳定性：

- 研究生若以被录用的学术论文申请学位，该论文正式发表前不能对作者排名和单位署名做任何改动。
- 一旦发现违规，学校将严肃处理，直至撤销学位。

科教融合单位成果：

- 科教融合单位研究生用于申请学位的成果，研究生必须是第一作者，导师署名不计在内。
- 中国科学技术大学应为第一署名单位或第二署名单位。
- 其中科大署名为第一的成果至少要有 1 个。

负面期刊清单：

- 用于申请学位的成果必须与学位论文相关。
- 原则上不建议使用发表在中国科学技术大学《学术论文负面期刊清单》所列期刊上的成果申请学位。
- 学术论文被列入负面期刊清单的期刊或会议发表/录用，若投稿日期在我校当年度负面期刊清单公布之后，不得用于申请学位。
- 若投稿日期在我校当年度负面期刊清单公布之前，且未被列入上一年度负面期刊清单，由所在学位评定分委员会对该论文及其同行评议材料进行重点审核，通过后方可用于申请学位。
- 该条款自 2024 年 1 月 1 日起生效。

支撑材料：

- 申请学位论文材料时，需提交全部支撑材料复印件。
- 包括但不限于发表论文首页、录用待发表论文的录用通知及文章首页、授权专利证书、获奖证书、参与标准等署名页。

### 2.6 学部认定可视同 B 档成果的学科竞赛

| 竞赛名称 | 主办单位 | 要求 |
| --- | --- | --- |
| “挑战杯”全国大学生系列科技学术竞赛 | 共青团中央、中国科协、教育部、全国学联 | 获自然科学或科技发明制作类特等奖 |
| CHiME, Computational Hearing in Multisource Environments | 法国计算机科学与自动化研究所、英国谢菲尔德大学、美国三菱电子研究实验室等知名研究机构联合举办 | 获第一名 |
| 中国高校计算机大赛, China Collegiate Computing Contest, C4 | 教育部 | 获一等奖 |

### 2.7 学部认定 A/B 档会议，仅限长文

| 序号 | 档次 | 会议简称 | 会议全名 |
| --- | --- | --- | --- |
| 1 | A | ISSCC | IEEE International Solid-State Circuits Conferences |
| 2 | A | CCC | IEEE Conference on Computational Complexity |
| 3 | A | NDSS | ISOC Network and Distributed System and Security Symposium |
| 4 | A | CHES | International Conference on Cryptographic Hardware and Embedded Systems |
| 5 | A | ASIACRYPT | International Conference on the Theory and Application of Cryptography and Information Security |
| 6 | A | ICRA | IEEE International Conference on Robotics and Automation |
| 7 | A | ECCV | European Conference on Computer Vision |
| 8 | A | ICLR | International Conference on Learning Representations |
| 9 | A | MICCAI | International Conference on Medical Image Computing and Computer Assisted Intervention，仅限 ORAL |
| 10 | A | EMNLP | Conference on Empirical Methods in Natural Language Processing |
| 11 | A | SIGMETRICS | ACM SIGMETRICS International Conference on Measurement and Modeling of Computer Systems |
| 12 | A | Mobisys | International Conference on Mobile Systems, Applications, and Services |
| 13 | A | Sensys | ACM Conference on Embedded Networked Sensor Systems |
| 14 | A | IEDM | IEEE International Electron Devices Meeting |
| 15 | A | ISPSD | IEEE International Symposium on Power Semiconductor Devices and ICs |
| 16 | A | VLSI | Symposium on VLSI Technology and Circuits |
| 17 | B | EMBC | International Conference of the IEEE Engineering in Medicine and Biology Society |
| 18 | B | STACS | Symposium on Theoretical Aspects of Computer Science |
| 19 | B | CSL | Computer Science Logic |
| 20 | B | FMCAD | Formal Methods in Computer-Aided Design |
| 21 | B | ITCS/ICS | Innovations in Theoretical Computer Science |
| 22 | B | RANDOM/APPROX | International Conference on Randomization and Computation / International Conference on Approximation Algorithms for Combinatorial Optimization Problems |
| 23 | B | ISIT | IEEE International Symposium on Information Theory |
| 24 | B | IROS | IEEE/RSJ International Conference on Intelligent Robots and Systems |
| 25 | B | CDC | IEEE Conference on Decision and Control |
| 26 | B | IFAC | World Congress of the International Federation of Automatic Control |
| 27 | B | ACC | American Control Conference |
| 28 | B | NAACL-HLT | Annual Conference of the North American Chapter of the Association for Computational Linguistics: Human Language Technologies |
| 29 | B | RadarConf | IEEE Radar Conference |

### 2.8 学部认定 A/B 档期刊

| 序号 | 档次 | 期刊名 | 期刊号 | 主办单位 |
| --- | --- | --- | --- | --- |
| 1 | A | 国家科学评论（英文）, National Science Review | 2095-5138 | 中国科技出版传媒股份有限公司 |
| 2 | A | 科学通报（英文）, Science Bulletin | 2095-9273 | 中国科学院 |
| 3 | A | 中国科学：信息科学（英文）, SCIENCE CHINA Information Sciences | 1674-733X | 中国科学院 |
| 4 | B | 中国生物医学工程学报 | 0258-8021 | 中国生物医学工程学会 |
| 5 | B | 密码学报 | 2095-7025 | 中国密码学会、北京信息科学技术研究院、中国科学技术出版社 |
| 6 | B | 软件学报 | 1000-9825 | 中国科学院软件研究所和中国计算机学会联合主办 |
| 7 | B | 雷达学报 | 2095-283X | 中国科学院电子学研究所、中国雷达行业协会 |
| 8 | B | 通信学报 | 1000-436X | 中国通信学会 |
| 9 | B | 计算机学报 | 0254-4164 | 中国科学院计算技术研究所；中国计算机学会 |
| 10 | B | 计算机研究与发展 | 1000-1239 | 中国科学院计算技术研究所、中国计算机学会 |
| 11 | B | 电子学报 | 0372-2112 | 中国电子学会 |
| 12 | B | 自动化学报 | 0254-4156 | 中国自动化学会、中国科学院自动化研究所 |

### 2.9 学部补充硕士发表期刊，仅限硕士申请学位有效

该清单仅限硕士申请学位有效，不作为博士毕业主路径，但 Agent 应在合规检查中标记“硕士专用，不建议博士使用”。

| 序号 | 档次 | 期刊名 | 期刊号 | 主办单位 |
| --- | --- | --- | --- | --- |
| 1 | 硕士 | 网络空间安全科学学报 | 2097-3136 | 中国航天系统科学与工程研究院 |
| 2 | 硕士 | 信息对抗技术 | 2097-163X | 国防科技大学电子对抗学院 |

## 3. 产品目标

### 3.1 近期目标

构建一个毕业导向的 AI4Catalysis 研究流水线，优先支持从具体催化反应出发，自动形成可发表的纯计算研究项目。

近期成功标准：

- 能自动生成不少于 20 个候选研究问题卡片。
- 能筛选出不少于 3 个“纯计算可验证、论文潜力明确、毕业成果档位清晰”的研究题目。
- 每个入选题目均有文献证据、计算方案、目标期刊、风险评估和最小可发表结果集。
- 至少跑通 1 个完整示范案例：文献检索、问题识别、计算任务设计、数据分析、图表生成、论文骨架生成。
- 输出材料可以被用户或导师审阅、修改和接管。

### 3.2 中期目标

形成 1 篇 A 档候选论文和 1-2 篇 B 档候选论文的完整素材包。

中期成功标准：

- A 档候选：AI4Catalysis Agent 方法论文，展示系统架构、可审计科研流程和多个催化案例。
- B 档候选：具体催化体系的机制/筛选/描述符论文。
- 所有数据、图表、脚本、输入文件、计算日志均可追溯。
- 能自动生成 manuscript draft、SI draft、PPT draft、cover letter draft 和 reviewer response draft。

### 3.3 长期目标

将毕业导向系统扩展为通用 AI4Catalysis 自动科研平台，支持多反应、多材料体系、多计算引擎和多轮人机协同研究。

## 4. 非目标

第一阶段不追求：

- 完全无人监管投稿。
- 自动得出需要湿实验才能证明的最终性能结论。
- 覆盖所有催化反应和所有计算软件。
- 替代导师和作者对科学结论、署名、投稿伦理的最终判断。
- 只生成漂亮论文草稿但缺乏可复现计算证据。

## 5. 推荐发文策略

### 5.1 主路径

优先走 A + B 路线。

A 档候选论文：

- 主题：毕业导向、文献驱动、可审计的 AI4Catalysis 自动科研 Agent。
- 贡献：提出系统架构、可计算性判别框架、催化问题卡片、自动工作流、可复现证据链。
- 目标类型：AI for Science、计算材料、计算化学、数据驱动化学相关 SCI Q1/Q2 期刊。

B 档候选论文：

- 主题：围绕具体反应和具体材料体系的计算催化研究。
- 贡献：更新某个反应机制认识，提出可验证候选，或给出描述符/微观动力学解释。
- 目标类型：SCI 收录催化、物理化学、计算材料、材料信息学期刊。

### 5.2 兜底路径

若 A 档论文进度不可控，则转为 B + B + B。

三个 B 档方向建议：

1. 具体催化机制论文。
2. LLM/Agent 辅助吸附构型或计算工作流 benchmark 论文。
3. 催化数据集、描述符筛选或机器学习势辅助高通量筛选论文。

## 6. 目标用户与使用场景

主要用户：

- 博士生本人：规划选题、生成计算任务、汇总图表、写论文和答辩材料。
- 导师/课题组：审阅选题价值、计算可信度和论文故事线。
- 后续合作者：复现实验、扩展体系、接手计算任务。

典型场景：

1. 用户输入“聚焦 Ru-CeO2 上 N2 活化和 NHx 氢化”。
2. Agent 自动检索综述和关键论文，抽取已有共识与争议。
3. Agent 生成候选问题，例如“氧空位是否改变 N2 解离与 NHx 氢化的速控步”。
4. Agent 判断该问题是否可由纯计算回答。
5. Agent 给出 DFT/MLIP/NEB/微观动力学组合方案。
6. Agent 生成结构、输入文件、任务清单和数据表模板。
7. 计算完成后，Agent 生成图表、结论边界、论文骨架和 PPT。

## 7. 系统总体架构

系统采用多 Agent + 工作流编排架构。

核心子系统：

1. 毕业合规 Agent。
2. 文献共识 Agent。
3. 问题发现 Agent。
4. 纯计算可验证性判别 Agent。
5. 新颖性与期刊匹配 Agent。
6. 计算规划 Agent。
7. 结构与输入生成 Agent。
8. 执行与失败修复 Agent。
9. 数据分析与图表 Agent。
10. 证据审计 Agent。
11. 论文/PPT/SI 生成 Agent。

所有 Agent 必须写入统一的项目账本，包括输入、输出、引用、计算文件、日志、决策理由和人工修改记录。

## 8. 模块需求

### 8.1 毕业合规 Agent

功能：

- 管理 A/B/C 档成果要求。
- 记录每个候选论文的目标成果档位。
- 检查第一作者、第一单位、论文相关性、分区、负面期刊风险。
- 维护目标期刊和投稿状态台账。

输入：

- 毕业要求文本。
- 目标期刊列表。
- 论文草稿元数据。
- 作者和单位信息。

输出：

- 成果合规评分。
- 毕业路径建议。
- 投稿风险提示。
- 支撑材料清单。

验收标准：

- 每篇候选论文均能生成 A/B/C 档判断。
- 对不满足毕业要求的成果必须给出明确原因。
- 所有期刊分区和负面清单状态必须标记“待人工核验”或“已核验”。

### 8.2 文献共识 Agent

功能：

- 自动检索综述、代表性论文、最新论文和数据库条目。
- 抽取研究背景、已有共识、争议点、待解决问题、常用方法和关键数据。
- 建立文献证据表。

输入：

- 反应名称。
- 催化体系。
- 时间范围。
- 数据源配置。

输出：

- 文献矩阵。
- 共识清单。
- 争议清单。
- 开放问题清单。
- 引用证据表。

验收标准：

- 每个共识和争议至少绑定 2 条文献证据。
- 引用必须包含 DOI、标题、期刊、年份、核心结论。
- 不允许无来源结论进入后续论文草稿。

### 8.3 问题发现 Agent

功能：

- 从文献共识和争议中生成具体研究问题。
- 避免泛泛问题，要求问题可验证、可计算、可写成论文故事线。
- 将问题结构化为“问题卡片”。

问题卡片字段：

- 问题标题。
- 所属反应。
- 所属催化材料。
- 背景共识。
- 未解决点。
- 可计算验证路径。
- 预期结果类型。
- 潜在贡献。
- 最小可发表结果集。
- 目标期刊类型。
- 毕业成果档位预估。
- 风险等级。

验收标准：

- 初版每个方向生成不少于 20 个问题卡片。
- 至少 3 个问题卡片达到“可立即进入计算规划”标准。

### 8.4 纯计算可验证性判别 Agent

功能：

- 判断研究问题能否完全由纯计算化学验证。
- 区分“可计算回答”“可计算部分支持”“必须湿实验验证”。
- 给出结论边界，避免过度宣称。

判别维度：

- 是否需要真实合成可行性证明。
- 是否需要实验活性/选择性/稳定性数据。
- 是否能用吸附能、反应能垒、表面能、电子结构、微观动力学等回答。
- 是否有可获得结构模型。
- 是否可通过已有数据库或可负担计算完成。

输出标签：

- C0：不可纯计算回答。
- C1：可由计算提供支持，但不能独立构成主要结论。
- C2：可由计算回答机制性问题。
- C3：可由计算形成独立论文核心。

验收标准：

- 进入计算执行阶段的问题必须达到 C2 或 C3。
- C1 问题只能作为辅助讨论或未来实验建议。
- C0 问题不得进入毕业主线。

### 8.5 新颖性与期刊匹配 Agent

功能：

- 检查候选问题是否已经被充分发表。
- 匹配目标期刊、成果档位、审稿周期和风险。
- 生成投稿优先级。

输出：

- 新颖性评分。
- 竞争论文列表。
- 目标期刊候选。
- A/B/C 档预估。
- 投稿风险说明。

验收标准：

- 每个候选题目至少检查近 5 年相关论文。
- 若存在高度相似论文，必须提示改题、换角度或放弃。

### 8.6 计算规划 Agent

功能：

- 将问题卡片转化为计算任务树。
- 根据任务选择 DFT、MLIP、GNN surrogate、NEB、微观动力学、电子结构分析等工具。
- 输出最小可发表计算集和增强计算集。

计算类型：

- 表面模型构建。
- 缺陷和掺杂模型。
- 吸附构型搜索。
- 吸附能和反应能计算。
- 过渡态和 NEB。
- Bader 电荷、PDOS、COHP、差分电荷密度。
- 微观动力学和速控步分析。
- 机器学习辅助筛选。

验收标准：

- 每个计算任务必须有目的、输入、输出、成功判据和失败处理策略。
- 高成本任务必须先有低成本预筛选。

### 8.7 结构与输入生成 Agent

功能：

- 生成 slab、缺陷、掺杂、吸附构型。
- 自动生成 VASP/QE/CP2K 等输入文件。
- 标记结构来源和修改历史。

推荐工具：

- ASE。
- pymatgen。
- catkit。
- pymatgen-analysis-defects。
- atomate2 / custodian。

验收标准：

- 所有结构必须保存 POSCAR/CIF/JSON。
- 所有模型必须记录晶面、层数、真空层、固定原子、覆盖度、吸附位点。
- 生成结构需通过基本几何合理性检查。

### 8.8 执行与失败修复 Agent

功能：

- 提交计算任务。
- 监控运行状态。
- 识别常见失败并自动修复。
- 汇总计算日志和失败原因。

失败类型：

- 电子步不收敛。
- 离子步发散。
- 磁矩设置不合理。
- 真空层或晶胞设置错误。
- 吸附物解离或漂移。
- 过渡态路径不合理。

验收标准：

- 失败任务必须有可读的失败报告。
- 自动修复不得覆盖原始输入。
- 每次重跑必须记录差异。

### 8.9 数据分析与图表 Agent

功能：

- 提取能量、结构参数、电子结构数据。
- 自动生成论文级图表。
- 生成表格和补充信息数据。

图表类型：

- 文献共识图。
- 研究问题漏斗图。
- 反应路径能量图。
- 吸附能热图。
- 火山图。
- 描述符相关性图。
- PDOS/COHP/Bader 图。
- 微观动力学速率图。
- 计算工作流图。

验收标准：

- 每张图必须绑定原始数据和绘图脚本。
- 图中所有数值必须可追溯到计算输出或文献来源。
- 论文主图和 SI 图分开管理。

### 8.10 证据审计 Agent

功能：

- 检查文献引用是否支持对应论断。
- 检查计算数据是否自洽。
- 检查论文结论是否超出计算可支持范围。
- 生成 claim ledger。

claim ledger 字段：

- 论文论断。
- 证据类型。
- 证据来源。
- 支持强度。
- 风险说明。
- 是否需要人工确认。

验收标准：

- 论文摘要、结论、图注中的每个关键 claim 必须进入 claim ledger。
- 无证据 claim 不得进入正式稿。

### 8.11 论文/PPT/SI 生成 Agent

功能：

- 生成论文大纲。
- 生成 manuscript draft。
- 生成 supporting information。
- 生成答辩/组会 PPT。
- 生成投稿信和审稿回复草稿。

输出：

- Markdown/LaTeX 论文草稿。
- Word 或 LaTeX SI 草稿。
- PPTX 汇报材料。
- 图表目录。
- 投稿材料清单。

验收标准：

- 所有结论均需引用 claim ledger。
- 论文不得引用不存在的文献。
- 图表编号、正文引用和 SI 引用必须一致。

## 9. 数据模型

### 9.1 Project

- project_id。
- reaction。
- catalyst_family。
- graduation_target。
- target_outputs。
- status。
- owner。
- created_at。
- updated_at。

### 9.2 LiteratureRecord

- doi。
- title。
- authors。
- journal。
- year。
- source_url。
- evidence_tags。
- key_findings。
- limitations。
- relevance_score。

### 9.3 ResearchQuestionCard

- question_id。
- title。
- reaction。
- catalyst。
- consensus。
- controversy。
- computational_verifiability。
- novelty_score。
- graduation_value。
- target_journals。
- minimal_publishable_results。
- risks。
- status。

### 9.4 CalculationTask

- task_id。
- question_id。
- structure_id。
- method。
- software。
- input_files。
- expected_outputs。
- success_criteria。
- status。
- retry_history。

### 9.5 EvidenceClaim

- claim_id。
- manuscript_section。
- claim_text。
- evidence_type。
- evidence_links。
- support_level。
- risk_level。
- human_review_status。

### 9.6 OutputArtifact

- artifact_id。
- artifact_type。
- source_data。
- generation_script。
- file_path。
- review_status。

## 10. 推荐技术栈

### 10.1 Agent 与编排

- Python。
- LangGraph 或等价工作流状态机。
- Pydantic 数据模型。
- SQLite/PostgreSQL 作为项目账本。
- 文件系统保存结构、计算输入、图表和论文草稿。

### 10.2 文献与知识库

- Crossref。
- Semantic Scholar。
- OpenAlex。
- PubMed/Europe PMC。
- arXiv。
- 本地 PDF/Markdown 文献库。
- 向量库：FAISS、LanceDB 或 Chroma。

### 10.3 计算化学与材料

- ASE。
- pymatgen。
- catkit。
- custodian。
- atomate2。
- VASP/QE/CP2K 接口。
- FAIRchem/OC20/OC22/AdsorbML。
- CHGNet/M3GNet/MatGL。

### 10.4 数据分析与写作

- pandas。
- numpy。
- scipy。
- matplotlib。
- seaborn。
- plotly。
- python-pptx。
- LaTeX 或 Quarto。
- Zotero/BibTeX。

## 11. MVP 范围

第一阶段只做“可跑通、可审计、可接管”的最小系统。

MVP 输入：

- 一个具体反应。
- 一个催化材料族。
- 一组本地或在线文献。

MVP 输出：

- 文献共识报告。
- 不少于 20 个问题卡片。
- 不少于 3 个高优先级问题。
- 每个高优先级问题的计算方案。
- 1 个示范问题的结构生成、数据表、图表和论文骨架。
- 毕业成果档位评估。

MVP 不包含：

- 自动提交正式投稿。
- 大规模 HPC 队列管理。
- 完整审稿回复闭环。
- 全自动多期刊格式适配。

## 12. 第一批推荐示范方向

优先方向：Ru-CeO2 / 氧空位 / N2 活化与 NHx 氢化。

理由：

- 与 AI4Catalysis 和计算催化方向高度一致。
- 可用 DFT、吸附能、NEB、电子结构和微观动力学形成纯计算证据链。
- 可围绕“文献共识与争议”构造机制问题。
- 适合作为 Agent 方法论文的展示案例。

备选方向：

1. CO2RR 中 C1 中间体吸附与选择性描述符。
2. ORR/OER 中吸附能标度关系异常点挖掘。
3. HER 作为低成本 benchmark，不建议作为主论文核心。

## 13. 论文产出规划

### 13.1 A 档候选

暂定题目：

Graduation-aware autonomous AI4Catalysis agent for literature-grounded computational catalysis discovery

核心图：

1. 系统总架构图。
2. 文献共识到问题卡片的自动抽取流程。
3. 纯计算可验证性评分框架。
4. 催化案例闭环结果。
5. Agent 与人工/基线方法对比。

最低结果集：

- 至少 2-3 个催化案例。
- 至少 1 个案例有完整计算闭环。
- 与人工构建流程或普通 RAG baseline 对比。
- 可复现代码和数据。

### 13.2 B 档候选 1

暂定题目：

Computational reassessment of N2 activation and NHx hydrogenation on defect-engineered Ru-CeO2 catalysts

核心图：

1. Ru-CeO2 模型与氧空位结构。
2. N2/NHx 吸附构型和吸附能。
3. 关键反应路径能量图。
4. 电子结构分析。
5. 微观动力学或速控步分析。

### 13.3 B 档候选 2

暂定题目：

LLM-guided adsorbate configuration search and MLIP-assisted screening for heterogeneous catalysis

核心图：

1. 自动吸附构型搜索流程。
2. LLM/规则/随机搜索对比。
3. MLIP 预筛选与 DFT 复算一致性。
4. 多吸附物、多表面 benchmark。
5. 失败案例分析。

## 14. 风险与缓解

风险 1：Agent 生成的问题不新颖。
缓解：强制新颖性检索、近 5 年相似论文检查、人工确认关口。

风险 2：计算量过大，影响毕业进度。
缓解：先 MLIP/GNN 预筛选，再小规模 DFT 精算；每篇论文定义最小可发表结果集。

风险 3：纯计算结论被认为缺少实验支撑。
缓解：选机制性问题，不宣称最终实验性能；用“解释、预测、更新认识”而非“证明最优催化剂”。

风险 4：论文不满足毕业档位。
缓解：毕业合规 Agent 在选题和投稿前强制检查分区、负面清单、作者、单位和相关性。

风险 5：LLM 幻觉文献或数据。
缓解：所有引用和数值必须进入证据账本；无 DOI/无原始数据的结论不得进入正式稿。

风险 6：自动计算结果不可复现。
缓解：保存输入、输出、版本、环境、随机种子、日志和绘图脚本。

## 15. 验收标准

阶段 1 验收：

- 形成可运行的文献共识与问题卡片生成流程。
- 对一个指定反应输出不少于 20 个问题卡片。
- 每个问题卡片有纯计算可验证性评分。
- 选出不少于 3 个毕业导向高优先级问题。

阶段 2 验收：

- 完成 1 个问题的计算规划和部分自动输入生成。
- 输出结构文件、任务表、图表模板和论文骨架。
- 建立项目账本和 claim ledger。

阶段 3 验收：

- 完成 1 个可投稿论文素材包。
- 包括 manuscript draft、SI draft、figures、data tables、scripts、PPT draft 和 graduation compliance report。

## 16. 开发里程碑

### M0：需求和数据结构

- 完成本文档。
- 建立项目目录结构。
- 定义核心 Pydantic schema。
- 整理毕业成果规则。

### M1：文献共识与问题卡片

- 实现文献导入。
- 实现文献证据抽取。
- 实现问题卡片生成。
- 实现纯计算可验证性评分。

### M2：计算规划

- 实现任务树生成。
- 支持 ASE/pymatgen 结构生成。
- 支持计算任务表导出。

### M3：示范案例

- 选择 Ru-CeO2/N2 活化案例。
- 跑通小规模计算或接入已有计算结果。
- 生成图表和论文骨架。

### M4：论文工厂

- 实现 manuscript/SI/PPT 生成。
- 实现 claim ledger 审计。
- 实现投稿材料清单。

## 17. 下一步行动

建议立即执行：

1. 固定第一示范反应和材料体系：优先 Ru-CeO2 / N2 活化 / NHx 氢化。
2. 建立项目目录结构和 schema。
3. 将本地已有文献、计算结果和数据表接入。
4. 先实现“文献共识 Agent + 问题卡片 Agent + 可计算性评分 Agent”。
5. 以 3 个候选问题为目标，选择最可能形成 B 档论文的一个进入计算规划。
