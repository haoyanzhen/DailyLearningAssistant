# 日常学习推送助手 MVP

Author: haoyanzhen
Date:   2026-05-24

## 目标

在本机定时运行一个独立 Agent 流水线，读取 `~/projects` 下配置的本地 Git 仓库每日变化，生成学习日报 HTML，发布到 GitHub Pages，并在发布后发送邮件通知。

MVP 只关注可运行、可补跑、可诊断的最小闭环，不包含复杂前端改版、跨日期智能规划或额外内容运营功能。

## MVP 范围

系统由一个 Orchestrator 和 5 个独立 Agent 组成：

1. `daily_work_summary`
   - 扫描 `config.repositories` 中的本地仓库。
   - 收集当日提交、未提交变更、本地分支和 worktree 证据。
   - 输出 `prework/YYYY-MM/YYYY-MM-DD/work_summary_[repo].md`。

2. `concept_relevance`
   - 读取当日所有 `work_summary_*.md`。
   - 提炼数学、物理、计算机、软件工程和大语言模型相关概念及关联。
   - 输出 `prework/YYYY-MM/YYYY-MM-DD/concept_relevance.md`。

3. `knowledge_explaination`
   - 基于 `concept_relevance.md` 生成完整知识讲解。
   - 输出 `prework/YYYY-MM/YYYY-MM-DD/knowledge_explaination.md`。
   - 维护 `knowledge_log/YYYY-MM-knowledge-log.md`。

4. `learning_report_publish`
   - 基于知识讲解生成 HTML 学习日报。
   - 输出 `daily_report/YYYY-MM/YYYY-MM-DD-learning-report.html`。
   - 更新 `daily_report/manifest.json` 和 `knowledge_log/manifest.json`。

5. `daily_email_send`
   - 读取日报 manifest 和 HTML 文件。
   - 生成邮件预览。
   - 显式传入发送参数时通过 SMTP 发送邮件。

## 运行入口

本地总入口：

```bash
python3 orchestrator/run_daily.py
```

常用模式：

```bash
python3 orchestrator/run_daily.py --generation-only --publish
python3 orchestrator/run_daily.py --only-step 5 --send-email
python3 orchestrator/run_daily.py --date YYYY-MM-DD --from-step N --to-step N
python3 orchestrator/run_daily.py --only-step N
python3 orchestrator/run_daily.py --dry-run
```

本机定时任务 MVP 拆成两个阶段：

- HTML 生成与发布：运行第 1-4 步，并在成功后提交和推送生成文件。
- 邮件发送：单独运行第 5 步；如果生成发布失败，则发送失败提醒并链接上一份可用日报。

## 状态与断点续连

每个日期使用一个状态文件：

```text
prework/YYYY-MM/YYYY-MM-DD/run_status.json
```

状态文件记录：

- 每个 Agent 的输入、输出、状态和问题诊断。
- Orchestrator 本次运行范围、实际执行步骤、跳过步骤和失败原因。
- 拆分调度下的 `html_publish`、`email_send` 等运行阶段状态。

默认运行会从当天第一个未完成 Agent 自动继续。显式传入 `--from-step`、`--to-step` 或 `--only-step` 时，按手动指定范围重跑，不做自动跳过。

## 回退规则

- 上游输入缺失时，下游停止并记录原因，不生成伪内容。
- 第 1 步确认全部仓库无变更时，跳过第 2/3 步，复用上一份有效知识讲解继续生成当日复习型日报。
- 第 1-4 步失败时，停止生成发布流程。
- 发布失败时记录诊断，不发送“成功日报”。
- 邮件阶段发现当天生成发布失败时，发送失败提醒并链接上一份可用日报。
- LLM 只负责文本生成，不负责判断文件是否存在、是否覆盖或是否发布。

## MVP 设计约束

- 每个 Agent 必须可单独运行和补跑。
- Orchestrator 只通过 CLI 调度 Agent，不直接调用 Agent 内部函数。
- 程序负责流程控制、文件校验、Git 证据收集、状态落盘和发布。
- 同一天重复运行必须幂等，不重复追加 manifest 或知识日志记录。
- 必要输出缺失、空文件、manifest 指向无效文件时必须失败并记录诊断。

## 文件地图

- `agents/`：5 个独立 Agent 脚本。
- `orchestrator/`：流水线调度、生命周期、状态、LLM 重试和发布逻辑。
- `prework/`：每日中间产物和运行状态。
- `daily_report/`：HTML 学习日报与日报 manifest。
- `knowledge_log/`：月度知识日志与 manifest。
- `scripts/`：生成、发送、调度和检查脚本。
- `docs/`：架构、状态、断点续连和回退机制设计文档。
- `config.example.json`：本地仓库、调度、LLM、邮件和发布配置示例。
- `index.html`：GitHub Pages 首页。
