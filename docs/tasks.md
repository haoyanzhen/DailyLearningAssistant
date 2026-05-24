# 本地独立 Agent 改造任务

本分支目标：将当前依赖 Codex 自动化任务启动的日报流水线，迁移为可在本机通过 `launchd` / cron 调度的独立 Agent 应用。调度环境以本机为准，需要能够读取 `~/projects` 下的本地 Git 仓库。

## 当前缺失步骤

- [x] 第 1 步 Agent：读取每日 Git change，生成 `prework/YYYY-MM/YYYY-MM-DD/work_summary_[reponame].md`。
  - 覆盖存在目标日期提交的情况。
  - 覆盖无提交但工作区存在未提交变更的情况。
  - 覆盖主路径无变化，但其他本地 branch 或 worktree 存在提交/变更的情况。
- [x] 第 2 步 Agent：读取 6 个 `work_summary_*.md`，生成 `concept_relevance.md`。
- [x] 第 3 步集成：把现有 `scripts/generate_knowledge_explaination.py` 接入统一 runner。
- [x] 第 4 步 Agent：读取 `knowledge_explaination.md`，生成 HTML 日报并更新两个 manifest。
- [x] 第 5 步 Agent：基于 `scripts/send_daily_email.py` 生成 HTML/纯文本邮件内容，并通过 SMTP 发送日报通知。
- [x] Orchestrator 管理层：新增 `orchestrator/`，集中管理 Agent 调度、状态检查、生命周期、LLM 重连和结果校验。
- [x] Orchestrator 回退策略：前四步失败时停止后续生成并记录诊断；第 1 步无变更时跳过第 2/3 步并复用上一份第三步结果；前四步失败时第 5 步生成失败提醒并链接上一份有效日报。
- [x] 本地总入口：新增 `orchestrator/run_daily.py`，支持 `--today`、`--date YYYY-MM-DD`、`--from-step N`、`--to-step N`、`--only-step N`、`--dry-run`。
- [x] 本地运行状态：生成 `prework/YYYY-MM/YYYY-MM-DD/run_status.json`，记录每一步输入、输出、状态和错误，并补充顶层 `orchestrator` 汇总状态。
- [x] 本地调度：新增完整流水线的 launchd 准备脚本，调度 `run_daily.py`，而不是只调度邮件或 git push；当前只新增脚本，不修改或加载现有每日自动运行项。
- [x] 发布集成：在完整流水线成功后执行 git commit / push，并在成功发布后调用第 5 步邮件 Agent。
- [x] 配置整理：补充 `config.example.json` 中的本地仓库路径、调度时间、时区、LLM、邮件和站点配置说明，并新增配置检查脚本与文档。
- [ ] 远端私人仓库变化监控：新增基于 SSH key 的 `git ls-remote` 方案，在不 clone/fetch、不下载仓库内容的前提下记录远端分支/tag SHA 变化，用于跟踪本地不存在的远端仓库更新。

## 设计约束

- 程序负责流程控制、文件校验、Git 证据收集和落盘。
- LLM 只负责总结、提炼、讲解和改写，不负责判断文件是否存在或是否覆盖。
- 每一步必须可单独补跑。
- 上游缺失时，下游必须停止并明确记录原因。
- 同一天重复运行必须幂等，不重复追加 manifest 或教学记录。
