# 与现有 Agent 衔接方案

## 现有可用输出

当前已有合成氨相关输出目录示例：

```text
D:\SaXin\Science\自动科研Agent\创新点和问题提出Agent\outputs\real_ammonia_with_metadata_final
```

关键文件：

```text
literature\literature_matrix.csv
literature\evidence_table.csv
insight\consensus_list.md
insight\controversy_list.md
insight\open_gap_list.md
question_cards\high_priority_cards.md
review\meta_review.md
metadata\similar_works.csv
```

## 推荐迁移方式

后续确定题目后，将相关输出复制或转换到本项目：

```text
合成氨综述\03_证据矩阵\literature_matrix_filled.csv
合成氨综述\03_证据矩阵\evidence_table_filled.csv
合成氨综述\03_证据矩阵\claims_and_gaps_filled.csv
```

## 需要增强的地方

现有 Agent 更偏“发现创新问题”，综述项目还需要新增：

1. 综述选题评分。
2. 目标期刊匹配。
3. 章节 evidence bundle。
4. 图表自动规划。
5. 引用核验。
6. 性能数据标准化。
7. 分章节写作和审稿人式批判。

## Review Builder 设计草案

输入：

- literature_matrix.csv
- evidence_table.csv
- consensus_list.md
- controversy_list.md
- open_gap_list.md
- target_journal_profile.yaml

输出：

- review_outline.md
- section_evidence_bundles.json
- figure_plan.md
- table_plan.md
- claim_audit.csv
- draft_sections/

## Claim Audit 规则

每个正文 claim 必须满足：

- 有 `source_id`。
- 有 DOI 或明确本地文献路径。
- 有 evidence_text。
- 标注 evidence_type。
- 标注 claim_level：observation / inference / hypothesis / design principle。
- 标注是否人工核验。
