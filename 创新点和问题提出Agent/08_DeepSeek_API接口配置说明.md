# DeepSeek API 接口配置说明

本项目已为“创新点和问题提出 Agent”预留 DeepSeek API 接口。API key 默认留空，不写入 Python 代码。

## 1. 填写位置

真实合成氨文献库调试使用：

```text
06_config_real_ammonia_library.yaml
```

找到以下配置块：

```yaml
llm:
  enabled: false
  provider: "deepseek"
  api_key: ""
  api_key_env: "DEEPSEEK_API_KEY"
  base_url: "https://api.deepseek.com"
  model: "deepseek-v4-pro"
```

将其改为：

```yaml
llm:
  enabled: true
  provider: "deepseek"
  api_key: "你的 DeepSeek API key"
  api_key_env: "DEEPSEEK_API_KEY"
  base_url: "https://api.deepseek.com"
  model: "deepseek-v4-pro"
```

也可以不把 key 写入文件，而是设置环境变量：

```powershell
$env:DEEPSEEK_API_KEY="你的 DeepSeek API key"
```

然后只把 YAML 中的：

```yaml
llm:
  enabled: true
  api_key: ""
```

## 2. 当前 LLM 参与的模块

### 2.1 generate_question_cards

配置：

```yaml
llm:
  tasks:
    generate_question_cards:
      enabled: true
      target_count: 24
      max_tokens: 5000
```

作用：

- 读取 EvidenceBuilder 得到的共识、争议和规则种子卡片。
- 让 DeepSeek 生成更自然、更具体、更偏计算催化的问题卡片。
- 输出会与规则卡片合并。

合并方式：

```yaml
llm:
  merge_mode: "prepend"  # prepend | append | replace
```

含义：

- `prepend`：LLM 卡片排在规则卡片前面。
- `append`：规则卡片排在 LLM 卡片前面。
- `replace`：只使用 LLM 卡片。

### 2.2 critique_cards

配置：

```yaml
llm:
  tasks:
    critique_cards:
      enabled: true
      top_n: 8
      max_tokens: 3500
```

作用：

- 对高分问题卡片做批判。
- 改写模板化标题。
- 增加下游“纯计算可验证性判别 Agent”需要检查的内容。

## 3. 调试命令

进入 Agent 目录：

```powershell
cd "D:\SaXin\Science\自动科研Agent\创新点和问题提出Agent"
```

先跑测试：

```powershell
python -m unittest discover -s tests
```

跑真实文献库 + DeepSeek：

```powershell
python run_agent.py --config 06_config_real_ammonia_library.yaml --output outputs\real_ammonia_deepseek_debug
```

重点看：

```text
outputs\real_ammonia_deepseek_debug\question_cards\high_priority_cards.md
outputs\real_ammonia_deepseek_debug\review\meta_review.md
outputs\real_ammonia_deepseek_debug\llm\llm_call_log.json
```

## 4. 目前使用的 DeepSeek API 形式

代码文件：

```text
src/catalysis_question_agent/llm_client.py
```

当前使用 OpenAI-compatible chat completions：

```text
POST https://api.deepseek.com/chat/completions
```

默认模型：

```text
deepseek-v4-pro
```

如果后续希望低成本快速调试，可把模型改成：

```yaml
model: "deepseek-v4-flash"
```

## 5. 安全说明

- 不要把 API key 提交到公开仓库。
- 如果只在本机调试，推荐用环境变量 `DEEPSEEK_API_KEY`。
- LLM 调用日志不会记录 API key。
- LLM 输出仍需人工核验，不能直接作为论文结论。
