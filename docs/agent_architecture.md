# Agent 架构设计

本文记录 DailyLearningAssistant 当前本地 Agent 架构。目标是让每日学习日报流水线可以在本机定时、可补跑、可检查、可发布。

## 总体结构

系统由一个 Orchestrator 和 5 个独立 Agent 组成。

Orchestrator 位于 `orchestrator/run_daily.py`，负责：

- 根据命令行参数选择要运行的步骤。
- 默认运行时根据当天状态执行 Agent 粒度断点续连。
- 为每个 Agent 构造稳定 CLI 命令。
- 控制输入根目录、输出根目录、日期、时区、LLM 重试参数。
- 在第 4 步成功后按需执行 Git 发布。
- 在状态文件中记录总调度结果。

Agent 位于 `agents/`，每个 Agent 都是可单独运行的脚本。Orchestrator 不直接调用 Agent 内部函数，只通过 CLI 调度，从而保持边界清晰。

## Agent 顺序

1. `daily_work_summary`
   - 扫描 `config.repositories` 中的本地仓库。
   - 扫描 `config.remote_repositories` 中的远端仓库变化线索。
   - 收集当日提交、未提交变更、本地分支、worktree 证据。
   - 对远端仓库配置的 URL 执行 `git ls-remote`，支持 SSH Git 和 HTTP(S) Git，任一 URL 成功即可确认 ref 当前 SHA。
   - 输出 `prework/YYYY-MM/YYYY-MM-DD/work_summary_[repo].md`。

2. `concept_relevance`
   - 读取当日所有 `work_summary_*.md`。
   - 提炼数学、物理、计算机、软件工程、大语言模型相关概念和关联。
   - 输出 `concept_relevance.md`。

3. `knowledge_explaination`
   - 调用 `scripts/generate_knowledge_explaination.py`。
   - 基于 `concept_relevance.md` 生成完整知识讲解。
   - 输出 `knowledge_explaination.md`，并维护 `knowledge_log/YYYY-MM-knowledge-log.md`。

4. `learning_report_publish`
   - 调用 `scripts/generate_learning_report.py`。
   - 生成 HTML 学习日报。
   - 更新 `daily_report/manifest.json` 和 `knowledge_log/manifest.json`。

5. `daily_email_send`
   - 读取日报 manifest 和 HTML 文件。
   - 生成 HTML/纯文本邮件预览。
   - 显式传入 `--send-email` 时通过 SMTP 发送。

远端仓库和本地仓库在内容输入上不区分：都生成 `work_summary_*.md`，都被第 2 步读取。区别只写入配置和 `run_status.json` 状态记录。远端仓库变化监控的完整设计见 `docs/remote_repository_monitoring.md`。

## 调度入口

本机定时任务拆成两个 launchd 任务：

- `com.daily-learning.agent-pipeline`
  - 运行 `scripts/run_daily_pipeline.sh`。
  - 执行 `orchestrator/run_daily.py --generation-only --publish`。
  - 负责第 1-4 步和 Git 发布。

- `com.daily-learning.agent-email`
  - 运行 `scripts/run_daily_email.sh`。
  - 执行 `orchestrator/run_daily.py --only-step 5 --send-email`。
  - 负责邮件发送。

调度时间来自 `config.json`：

- `schedule.html_run_time`
- `schedule.email_send_time`
- `schedule.daily_run_time` 作为兼容回退字段。

## CLI 契约

Orchestrator 通过 `orchestrator/lifecycle.py` 中的 `AgentSpec` 描述每个 Agent 能力：

- `requires_input_root`
- `supports_llm_retry`
- `supports_dry_run`
- `supports_no_llm`

所有 Agent 至少接收：

- `--date`
- `--config`
- `--output-root`
- `--timeout`

需要读取上游产物的 Agent 还接收：

- `--input-root`

支持 LLM 重试的 Agent 还接收：

- `--llm-retries`
- `--llm-retry-delay`

## 断点续连

默认运行时，Orchestrator 会读取当天 `run_status.json`，从选定范围内第一个未完成 Agent 开始执行。已经成功的前序 Agent 会记录到 `resume_skipped_steps` 并跳过。

如果显式传入 `--from-step`、`--to-step` 或 `--only-step`，则视为手动阶段覆盖，指定范围内的 Agent 全部重跑。

第 1 步 `daily_work_summary` 的完成条件更严格：LLM 失败后回退到 Git 证据总结时状态为 `partial_success`，断点续连会重跑第 1 步；只有有变更仓库完成 LLM 总结，或仓库无变更而跳过 LLM，才视为完成。

详细规则见 `design/breakpoint_resume.md`。

## 发布边界

Git 发布不属于单个 Agent，而是 Orchestrator 在第 4 步成功后执行的集成阶段。

发布逻辑位于 `orchestrator/run_daily.py`：

- 检查当前目录是否为 Git 工作区。
- 检查当前分支是否等于 `publish.branch`。
- 拉取远端状态。
- 本地落后远端时停止发布。
- 只暂存 `publish.paths` 中配置的生成文件。
- 有变更则提交，无变更则跳过提交。
- 本地领先远端时推送。

## 设计原则

- Agent 只负责自己的输入、输出和状态。
- Orchestrator 负责流程控制、发布、跨步骤回退。
- LLM 只参与文本生成，不负责文件是否存在、是否覆盖、是否发布等工程判断。
- 每一步都可单独补跑。
- 同一天重复运行应保持幂等。
