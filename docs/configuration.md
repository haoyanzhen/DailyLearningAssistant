# 本地 Agent 配置说明

本项目的本地流水线读取 `config.json`。可以从 `config.example.json` 复制一份后填写真实密钥：

```bash
cp config.example.json config.json
python3 -m pip install -r requirements.txt
python3 scripts/check_config.py --config config.json --strict
```

## schedule

- `daily_run_time`：本机调度时间，格式为 `HH:MM`。`launchd` 会按 macOS 当前本地时区解释这个时间。
- `timezone`：Agent 内部解析“今天”的时区，建议保持 `Asia/Shanghai`。

## repositories

`repositories` 是第 1 步 Git 变更监测范围。当前应包含 6 个本地仓库：

- `~/projects/AInote`
- `~/projects/DailyLearningAssistant`
- `~/projects/interview_prepare`
- `~/projects/mcp`
- `~/projects/ResearchPaperBase_cc`
- `~/projects/ResearchPaperBase_codex`

每个条目必须包含 `name` 和 `path`。`name` 会进入输出文件名 `work_summary_[name].md`。

## llm

- `api_url`：OpenAI Chat Completions 兼容接口地址。
- `api_key`：真实 API key，不能保留 `YOUR_...` 占位符。
- `model`：使用的模型名。

当前建议模型为 `deepseek-v4-pro`。LLM 网络调用使用 `httpx`，因此本地调度环境需要安装 `requirements.txt` 中的依赖。

## email

- `smtp_server` / `smtp_port`：SMTP 服务器与端口。
- `sender_email` / `sender_password`：发件邮箱与授权码。
- `sender_name`：邮件展示名称。
- `target_emails`：正式收件人列表。
- `imap_server` / `imap_port` / `imap_user` / `imap_password`：可选，但如果要做发送给自己的邮件验收，应完整填写。

测试邮件约定：发送测试时标题会以 `test: ` 开头；如果收件人只有发件邮箱本身，也会自动进入测试标题模式。

## site

- `base_url`：GitHub Pages 站点根地址，用于邮件中的日报链接。

## 本地调度脚本

新增的完整流水线调度脚本不会自动修改当前每日任务。可先预览：

```bash
bash scripts/setup_daily_agent_launchd.sh --print
```

只写入 plist 但不加载：

```bash
bash scripts/setup_daily_agent_launchd.sh --write
```

确认后才手动安装：

```bash
bash scripts/setup_daily_agent_launchd.sh --install
```
