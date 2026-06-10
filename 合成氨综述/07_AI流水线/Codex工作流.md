# Codex 工作流

## 总原则

Codex 负责加速整理和写作，但不替代人工判断。所有输出必须能追溯到文献 DOI、原文片段和证据表。

## 推荐流水线

```text
1. 文献入库
   PDF/Markdown/Zotero CSV

2. 元数据整理
   DOI、标题、年份、期刊、标签、催化剂体系

3. 文献矩阵
   催化剂结构、反应条件、性能、表征、计算

4. 证据表
   evidence_text、claim、mechanistic target、confidence

5. claim/gap 合成
   共识、争议、开放问题

6. 图表规划
   机制图、性能表、证据热图

7. 大纲生成
   中心论点、章节逻辑、每节 evidence bundle

8. 分章节初稿
   每段绑定 evidence_id

9. 人工核验
   DOI、数据、引用、图表来源、逻辑风险

10. 投稿版本
   Word/LaTeX、cover letter、synopsis
```

## 可复用的现有项目

现有项目：

```text
D:\SaXin\Science\自动科研Agent\创新点和问题提出Agent
```

已有能力：

- 从本地合成氨文献库扫描 Markdown/txt/csv。
- 生成 `literature_matrix.csv`。
- 生成 `evidence_table.csv`。
- 抽取 consensus、controversy、open gap。
- 生成 high priority question cards。
- 可接 DeepSeek API。

建议新增能力：

- `review_builder.py`：从 evidence table 生成综述大纲和每节证据包。
- `metric_normalizer.py`：标准化合成氨性能指标。
- `figure_planner.py`：根据 claim/gap 生成图表清单。
- `citation_auditor.py`：检查每个 claim 是否有 DOI 和 evidence_id。

## 每次运行后的人工检查

- 抽取内容是否来自正文而不是参考文献。
- DOI 和题名是否匹配。
- claim 是否被证据支持。
- 是否混淆实验观察和机制推断。
- 是否存在近五年高度相似综述。
