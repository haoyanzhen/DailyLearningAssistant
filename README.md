# DailyLearningAssistant

DailyLearningAssistant 是一个本地运行的日常学习日报助手。它会读取本机多个 Git 仓库的每日变化，自动生成工作总结、概念关联、知识讲解、HTML 学习日报，并通过 GitHub Pages 发布和邮件推送。

## 功能概览

- **每日 Git 变更总结**：扫描配置中的本地仓库，生成每个仓库的当日总结。
- **概念提炼**：从每日变更中提炼数学、物理、计算机、软件工程和大语言模型相关知识点。
- **知识讲解**：把概念整理成适合阅读和复习的详细讲解。
- **HTML 日报**：生成可在 GitHub Pages 上访问的学习日报页面。
- **知识日志**：维护按月份归档的知识讲解记录。
- **发布与邮件**：成功生成后自动提交、推送到 GitHub，并在指定时间发送日报邮件。
- **状态追踪与回退**：每次运行都会写入状态文件；生成失败时可发送维护者提醒，并回退链接上一份有效日报。

## 运行环境

- macOS 或类 Unix 环境。
- Python 3.10+。
- Git 和可推送到 GitHub 的凭据。
- 一个 OpenAI Chat Completions 兼容的 LLM API。
- 可用的 SMTP 邮箱账号；如需发送后验收，可配置 IMAP。

安装 Python 依赖：

```bash
python3 -m pip install -r requirements.txt
```

依赖项：

- `httpx`：调用 LLM API。

## 快速部署

1. 克隆仓库并进入目录：

```bash
git clone git@github.com:<your-name>/DailyLearningAssistant.git
cd DailyLearningAssistant
```

2. 准备配置文件：

```bash
cp config.example.json config.json
```

3. 编辑 `config.json`：

- `repositories`：要扫描的本地 Git 仓库列表。
- `llm`：LLM API 地址、API key 和模型名。
- `llm.trust_env_proxy`：是否让 LLM 请求读取终端环境代理，默认建议关闭。
- `email`：发件邮箱、收件人、SMTP/IMAP 配置。
- `site.base_url`：GitHub Pages 站点根地址。
- `schedule.html_run_time`：日报生成和发布任务时间。
- `schedule.email_send_time`：邮件发送任务时间。
- `publish`：自动提交和推送的远端、分支、提交信息和文件范围。

> 注：`email.recipients` 包含所有收件人的信息，每一个 recipient 的名字可以自取，其内容包含邮箱和昵称，昵称将决定发送邮件到对应邮箱时的称呼。在下面的 `target_recipient_ids` 中可以配置普通的发送对象邮箱，内容为 recipient 中的名字。`failure_recipient_id` 则为服务端邮箱信息，若自动运行产生错误将会向该邮箱发送，默认为 `server`。

1. 检查配置：

```bash
python3 scripts/check_config.py --config config.json --strict
```

## 手动运行

只预览命令，不实际生成：

```bash
python3 orchestrator/run_daily.py --today --dry-run
```

生成并发布 HTML 日报，不发送邮件：

```bash
python3 orchestrator/run_daily.py --today --generation-only --publish
```

只生成邮件预览，不发送：

```bash
python3 orchestrator/run_daily.py --today --only-step 5
```

发送邮件：

```bash
python3 orchestrator/run_daily.py --today --only-step 5 --send-email
```

补跑指定步骤：

```bash
python3 orchestrator/run_daily.py --date 2026-05-23 --only-step 4
python3 orchestrator/run_daily.py --date 2026-05-23 --from-step 2 --to-step 4
```

## 定时任务

项目提供 macOS `launchd` 安装脚本，会创建两个任务：

- `com.daily-learning.agent-pipeline`：运行第 1-4 步，生成并发布 HTML。
- `com.daily-learning.agent-email`：运行第 5 步，发送日报邮件。

先预览将写入的 plist：

```bash
bash scripts/setup_daily_agent_launchd.sh --print
```

写入 plist 但不加载：

```bash
bash scripts/setup_daily_agent_launchd.sh --write
```

安装并加载任务：

```bash
bash scripts/setup_daily_agent_launchd.sh --install
```

查看状态：

```bash
bash scripts/setup_daily_agent_launchd.sh --status
```

卸载任务：

```bash
bash scripts/setup_daily_agent_launchd.sh --uninstall
```

## 输出文件

每日运行会生成以下内容：

```text
prework/YYYY-MM/YYYY-MM-DD/work_summary_[repo].md
prework/YYYY-MM/YYYY-MM-DD/concept_relevance.md
prework/YYYY-MM/YYYY-MM-DD/knowledge_explaination.md
daily_report/YYYY-MM/YYYY-MM-DD-learning-report.html
knowledge_log/YYYY-MM-knowledge-log.md
```

状态和排障文件：

```text
prework/YYYY-MM/YYYY-MM-DD/run_status.json
prework/YYYY-MM/YYYY-MM-DD/llm_trace.jsonl
prework/YYYY-MM/YYYY-MM-DD/email_preview.html
prework/YYYY-MM/YYYY-MM-DD/email_preview.txt
```

## 查看运行状态

```bash
python3 orchestrator/check_status.py
python3 orchestrator/check_status.py --date 2026-05-23
```

状态文件会记录每个 Agent 的输入、输出、运行结果、错误信息和 LLM 调用摘要。拆分调度时，同一天的 `run_status.json` 会同时保存 HTML 生成发布和邮件发送两段运行记录。

## 发布到 GitHub Pages

`--publish` 会在第 4 步成功后执行自动发布：

1. 检查当前目录是否为 Git 工作区。
2. 检查当前分支是否等于 `publish.branch`。
3. 拉取远端状态。
4. 如果本地落后远端，则停止发布。
5. 只暂存 `publish.paths` 中声明的生成文件。
6. 有变更时提交，无变更时跳过提交。
7. 本地领先远端时推送到 `publish.remote`。

建议在 GitHub 仓库设置中启用 GitHub Pages，并将发布源指向当前分支。

## 安全建议

- `config.json` 已加入 `.gitignore`，不要提交真实 API key、SMTP 授权码或邮箱密码。
- `publish.paths` 建议只包含 `daily_report`、`knowledge_log`、manifest 和 `index.html`，不要发布 `prework`、邮件预览或临时状态文件。
- 正式邮件只会在传入 `--send-email` 时发送。
- 建议将 `email_send_time` 设置得晚于 `html_run_time`，给生成、推送和 GitHub Pages 更新留出缓冲。

## 目录说明

```text
agents/          五个独立 Agent 入口
orchestrator/    流程编排、状态管理、发布和回退逻辑
scripts/         生成、邮件、配置检查和 launchd 脚本
prompt/          每个阶段使用的提示词
daily_report/    HTML 学习日报和日报 manifest
knowledge_log/   月度知识日志和 manifest
prework/         每日中间产物和运行状态
style/           GitHub Pages 前端样式与交互脚本
docs/            详细配置说明
```

更多配置细节见 [docs/configuration.md](docs/configuration.md)。
