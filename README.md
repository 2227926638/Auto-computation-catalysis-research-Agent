# 自动科研 Agent

本仓库保存当前“稳定可审计计算化学科研发文 Agent / 自动化开源流程”的自有主线代码与设计文档。

## 主要内容

- `创新点和问题提出Agent/`：可运行的 Python MVP，包含文献证据抽取、问题卡片生成、审计 gate、protocol registry、AiiDA dry-run 研究流水线等模块。
- `docs/`：需求文档、Agent 框架集成说明、GitHub 脚手架复用映射。
- `合成氨综述/07_AI流水线/`：与综述写作项目衔接的 AI 流水线脚本和配置。

## 不纳入 Git 的内容

- `external/github_scaffolds/`：第三方开源项目克隆，仅作为本地参考；仓库内用文档和注册表记录来源。
- `pipeline_outputs/`、`**/outputs/`、`**/generated/`：运行产物和调试输出。
- `.env`、`*.local.*`、`secrets/`、私钥文件：本地密钥和凭据。
- 本地 PDF/Markdown 文献库和 Zotero 导出。

## 密钥使用

不要把真实 API key 写入可提交配置。推荐使用环境变量：

```powershell
$env:DEEPSEEK_API_KEY="<your local key>"
$env:UNPAYWALL_EMAIL="you@example.com"
```

如需保留本机调试配置，请使用 `*.local.yaml` 或 `.env`，这些文件已被 `.gitignore` 忽略。

## 快速验证

```powershell
cd "创新点和问题提出Agent"
python -m unittest discover -s tests
```
