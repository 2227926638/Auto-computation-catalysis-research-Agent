# Scripts

这些脚本用于综述项目的轻量自动化，不下载文献、不联网、不修改原始 PDF。

## validate_review_csv.py

校验 CSV 表头是否包含关键字段。

示例：

```powershell
python .\07_AI流水线\scripts\validate_review_csv.py --kind literature --path .\03_证据矩阵\literature_matrix_template.csv
python .\07_AI流水线\scripts\validate_review_csv.py --kind evidence --path .\03_证据矩阵\evidence_table_template.csv
python .\07_AI流水线\scripts\validate_review_csv.py --kind claims --path .\03_证据矩阵\claims_and_gaps_template.csv
```

## make_section_bundles.py

根据 evidence table 生成：

- `section_evidence_bundles.md`
- `claim_audit.csv`

示例：

```powershell
python .\07_AI流水线\scripts\make_section_bundles.py --evidence .\03_证据矩阵\evidence_table_filled.csv --out-dir .\07_AI流水线\generated
```

如果 `used_in_section` 为空，脚本会根据关键词粗略分配章节。正式写作前仍需人工核验。

## import_existing_agent_outputs.py

把已有 `创新点和问题提出Agent` 的输出转换成综述项目可用的启动证据表，并复制关键参考文件。

示例：

```powershell
python .\07_AI流水线\scripts\import_existing_agent_outputs.py `
  --agent-output "..\创新点和问题提出Agent\outputs\real_ammonia_with_metadata_final" `
  --out-dir ".\07_AI流水线\generated\from_existing_agent"
```

输出：

- `converted_evidence_table.csv`
- `reference_files/`

转换结果只作为启动参考，所有条目默认需要人工核验。
