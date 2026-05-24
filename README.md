# DailyLearningAssistant

DailyLearningAssistant 是一个本地运行、GitHub Pages 展示的日常学习推送助手。它会读取 `~/projects` 下多个本地 Git 仓库的每日变化，生成项目日报、概念关联、知识讲解和 HTML 学习日报，并可在发布成功后发送邮件通知。

项目目标不是简单记录提交列表，而是把每天的工程与学习痕迹整理成可复习、可沉淀、可公开浏览的知识页面。

## 核心流程

完整流水线由 5 个独立 Agent 和一个 Orchestrator 组成：

1. `daily_work_summary`：扫描配置中的本地仓库，收集当日提交、未提交变更、其他分支和 worktree 证据，生成 `prework/YYYY-MM/YYYY-MM-DD/work_summary_[repo].md`。
2. `concept_relevance`：读取当日所有仓库总结，提炼数学、物理、计算机、软件工程和大语言模型相关概念，生成 `concept_relevance.md`。
3. `knowledge_explaination`：基于概念关联生成完整知识讲解，生成 `knowledge_explaination.md` 并维护知识日志。
4. `learning_report_publish`：把知识讲解转成 HTML 学习日报，写入 `daily_report/YYYY-MM/YYYY-MM-DD-learning-report.html`，并更新日报与知识日志 manifest。
5. `daily_email_send`：生成 HTML 和纯文本邮件内容。默认只生成预览；只有显式传入 `--send-email` 才会通过 SMTP 发送。

正式自动运行时，Orchestrator 会在第 4 步成功后执行发布阶段：提交并推送生成文件；发布成功后才进入第 5 步邮件 Agent。

## 目录说明

- `agents/`：5 个独立 Agent 入口。
- `orchestrator/`：本地流程管理、状态记录、回退策略、LLM 重试和命令调度。
- `scripts/`：生成日报、发送邮件、配置检查、launchd 安装和 Git 发布辅助脚本。
- `prompt/`：各步骤使用的提示词。
- `prework/`：每日中间产物，包括仓库总结、概念关联、知识讲解和运行状态。
- `daily_report/`：最终 HTML 学习日报和日报 manifest。
- `knowledge_log/`：知识讲解历史记录和 manifest。
- `style/`：GitHub Pages 前端样式与交互脚本。
- `docs/`：配置文档。
- `index.html`：GitHub Pages 首页。

## 配置

复制示例配置后填写本地信息：

```bash
cp config.example.json config.json
python3 -m pip install -r requirements.txt
python3 scripts/check_config.py --config config.json --strict
```

`config.json` 包含这些主要区域：

- `repositories`：第 1 步扫描的本地仓库路径。
- `llm`：OpenAI Chat Completions 兼容接口、API key 和模型名。
- `email`：SMTP/IMAP 和收件人配置。
- `email.recipients`：收件人 ID 到邮箱和昵称的映射，用于给不同收件人生成对应开头称呼。
- `site`：GitHub Pages 根地址。
- `schedule`：本地调度时间与时区。
- `publish`：自动提交和推送的远端、分支、提交信息和生成文件路径。

更详细的配置说明见 `docs/configuration.md`。

## 本地运行

完整检测链路，但不推送、不发送邮件：

```bash
python3 orchestrator/run_daily.py --date 2026-05-23 --no-llm
```

运行指定步骤：

```bash
python3 orchestrator/run_daily.py --date 2026-05-23 --only-step 4
python3 orchestrator/run_daily.py --date 2026-05-23 --from-step 2 --to-step 4
```

仅预览将执行的命令：

```bash
python3 orchestrator/run_daily.py --today --dry-run
```

正式生成发布与发送邮件可以拆开执行：

```bash
python3 orchestrator/run_daily.py --today --generation-only --publish
python3 orchestrator/run_daily.py --today --only-step 5 --send-email
```

注意：没有 `--send-email` 时，第 5 步会生成 `email_preview.html` 和 `email_preview.txt`，但不会发送邮件。没有 `--publish` 时，不会执行 Git commit 或 push。正式定时任务会将 HTML 生成发布和邮件发送拆成两个时间点。

## 状态与回退

每次运行都会写入：

```text
prework/YYYY-MM/YYYY-MM-DD/run_status.json
prework/YYYY-MM/YYYY-MM-DD/llm_trace.jsonl
```

状态检查：

```bash
python3 orchestrator/check_status.py --date 2026-05-23
```

拆分调度后，同一个状态文件会保留 `orchestrator_runs.html_publish` 和 `orchestrator_runs.email_send` 两块，分别记录第 1-4 步生成发布和第 5 步邮件发送。邮件任务会读取生成发布状态；如果当天 HTML 生成或发布失败，会向发件邮箱发送故障提醒，并回退附上上一份可用日报。

回退规则：

- 默认运行会读取当天已有 `run_status.json` 并按 Agent 粒度断点续跑；显式传入 `--from-step`、`--to-step` 或 `--only-step` 时，以手动阶段为准并重跑指定范围。
- 第 1 步如果因为 LLM 失败回退为 Git 证据总结，会被视为部分完成，下一次自动断点续跑仍会重跑第 1 步；只有 LLM 正式总结成功，或仓库无变更而跳过 LLM，才视为已完成。
- 前四步任一步失败时，后续生成默认停止并写入诊断。
- 第 1 步确认所有仓库无变化时，会跳过第 2/3 步，复用上一份有效知识讲解进入第 4 步。
- 前四步失败且运行范围包含第 5 步时，会生成失败提醒邮件内容；拆分调度时，第 5 步也会读取早先的生成发布状态并向发件邮箱发送失败提醒，目标邮箱保持静默。未传 `--send-email` 时仍只生成预览。
- 同一天重复运行保持幂等，manifest 和知识日志不会重复追加相同日期条目。

## 发布策略

发布阶段由 `orchestrator/run_daily.py --publish` 触发。它会：

1. 确认当前目录是 Git 工作区。
2. 确认当前分支与 `publish.branch` 一致。
3. 拉取远端分支状态。
4. 如果本地落后远端，停止发布。
5. 只暂存 `publish.paths` 中的生成文件。
6. 有变更时提交，无变更时跳过提交。
7. 本地领先远端时推送到 `publish.remote`。

默认发布路径覆盖日报 HTML、manifest、知识日志和 `index.html`，不会提交 `prework` 中间数据、`config.json`、邮件预览或其他临时文件。

## 本地调度

调度脚本不会自动安装任务，需要显式执行：

```bash
bash scripts/setup_daily_agent_launchd.sh --print
bash scripts/setup_daily_agent_launchd.sh --write
bash scripts/setup_daily_agent_launchd.sh --install
```

安装后的每日任务会运行 `scripts/run_daily_pipeline.sh`。该脚本会先严格检查配置，再执行完整流水线、发布和邮件发送。

## GitHub Pages 展示

`index.html` 读取 `daily_report/manifest.json` 和 `knowledge_log/manifest.json`，展示最新日报、历史归档和知识日志入口。`daily_report/YYYY-MM/*.html` 是可独立访问的日报页面，样式由 `style/main.css` 和 `style/app.js` 维护。

## 安全说明

- `config.json` 已加入 `.gitignore`，不要提交真实 API key、SMTP 授权码或邮箱密码。
- 发布阶段只提交配置指定的生成文件路径。
- 如果远端有新提交，本地自动发布会停止，避免在无人值守场景中覆盖远端状态。
- 邮件发送必须显式启用 `--send-email`，便于平时做端到端检测。
