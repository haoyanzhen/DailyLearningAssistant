# 本地 Agent 配置说明

本项目的本地流水线读取 `config.json`。可以从 `config.example.json` 复制一份后填写真实密钥：

```bash
cp config.example.json config.json
python3 -m pip install -r requirements.txt
python3 scripts/check_config.py --config config.json --strict
```

## schedule

- `html_run_time`：HTML 日报生成与发布任务时间，格式为 `HH:MM`。
- `email_send_time`：邮件发送任务时间，格式为 `HH:MM`。建议晚于 `html_run_time`，给生成、提交和 GitHub Pages 更新留出缓冲。
- `daily_run_time`：兼容旧配置的默认调度时间。如果未配置 `html_run_time` 或 `email_send_time`，安装脚本会回退使用它。
- `launchd` 会按 macOS 当前本地时区解释上述时间。
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

## publish

`publish` 是可选配置，用于完整流水线的发布阶段。正式本地调度会在第 4 步日报 HTML 和 manifest 生成成功后执行发布，再进入第 5 步邮件通知。

- `remote`：Git 远端名，默认 `origin`。
- `branch`：允许自动发布的分支，默认 `main`。如果当前分支不是该分支，流水线会停止发布。
- `commit_message`：提交信息模板，支持 `{date}` 和 `{year_month}`。
- `paths`：要纳入自动提交的生成文件路径模板。建议只包含当日 prework、日报 HTML、manifest、知识日志和 `index.html`，不要包含配置密钥或临时预览文件。

发布阶段会先检查本地分支是否落后远端；如果落后，会停止自动发布，避免覆盖远端进度。

## 本地调度脚本

本地调度会拆成两个 launchd 任务：

- `com.daily-learning.agent-pipeline`：运行 `scripts/run_daily_pipeline.sh`，执行第 1-4 步并发布 HTML。
- `com.daily-learning.agent-email`：运行 `scripts/run_daily_email.sh`，只执行第 5 步并发送邮件。

两个任务会写入同一个 `prework/YYYY-MM/YYYY-MM-DD/run_status.json`。状态文件中的 `orchestrator_runs.html_publish` 保存第 1-4 步生成发布结果，`orchestrator_runs.email_send` 保存第 5 步邮件结果；如果邮件任务发现当天 HTML 生成发布未成功，会自动发送失败提醒并回退附上上一份可用日报。

安装脚本不会在预览时修改当前每日任务。可先预览：

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
