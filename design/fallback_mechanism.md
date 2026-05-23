# 回退机制设计

本文记录 DailyLearningAssistant 当前回退机制。回退目标是避免上游缺失时继续编造内容，同时在自动调度场景中给用户明确通知。

## 回退原则

- 上游输入缺失时，下游停止，不生成伪内容。
- 能复用已有有效知识时，明确记录复用来源。
- 失败时保留诊断，便于补跑。
- 邮件通知优先保证“告知状态”，而不是强行发送错误日报。

## 上游输入校验

每个 Agent 在正式处理前检查必要输入：

- 第 2 步需要当日 `work_summary_*.md`。
- 第 3 步需要非空 `concept_relevance.md`。
- 第 4 步需要非空 `knowledge_explaination.md` 和当月知识日志。
- 第 5 步需要日报 manifest 和可读取的日报 HTML。

输入不满足时，Agent 写入 `agents.<agent_name>.status = failed` 或跳过状态，并在 `problems` 中记录原因。

## 无变更日回退

如果第 1 步确认所有仓库均无新增变更，Orchestrator 会：

1. 跳过第 2 步 `concept_relevance`。
2. 跳过第 3 步 `knowledge_explaination`。
3. 查找上一份有效 `knowledge_explaination.md` 和知识日志。
4. 将上一份知识讲解复制到当日目录，并在文件开头写入“无新增变更复用说明”。
5. 继续运行第 4 步生成复习、深化或延展型日报。

该事件记录在：

```text
orchestrator_runs.html_publish.fallback_events
orchestrator_runs.html_publish.skipped_steps = [2, 3]
```

完整成功判断会接受这种跳过。

## 生成阶段失败

第 1-4 步任一步失败时，默认行为是：

- 停止后续生成步骤。
- 写入 `orchestrator_runs.html_publish.status = failed`。
- 在 `failures` 中记录失败步骤、Agent 名称、退出码和诊断。
- 不继续生成可能基于空输入的 HTML 日报。

如果显式传入 `--continue-on-failure`，Orchestrator 可以继续尝试后续步骤，但状态仍会保留失败信息。

## 发布失败

发布阶段位于第 4 步之后。以下情况会停止发布：

- 当前目录不是 Git 工作区。
- 当前分支不是 `publish.branch`。
- 本地分支落后远端。
- `git add`、`git commit` 或 `git push` 失败。

发布失败记录在：

```text
orchestrator_runs.html_publish.publish_events
orchestrator_runs.html_publish.failures
```

发布失败会让生成发布任务整体视为失败，因为邮件中的链接可能尚未更新到 GitHub Pages。

## 邮件失败提醒回退

当前调度拆成两个时间点：

- HTML 生成发布任务。
- 邮件发送任务。

邮件任务启动时会读取当天 `run_status.json`：

- 如果 `orchestrator_runs.html_publish.status == success`，正常发送当天日报。
- 如果 `html_publish` 失败，邮件任务自动追加：
  - `--failure-notice`
  - `--allow-latest-fallback`
  - `--failure-reason <失败原因>`
- 如果当天没有生成状态，且 manifest 中也找不到当天日报，则同样发送失败提醒。

失败提醒邮件会：

- 告知当天日报未成功生成或发布。
- 写明失败原因。
- 查找上一份不晚于前一天的可用日报。
- 附上上一份可用日报链接。

## 邮件内容回退

第 5 步邮件 Agent 有两层回退：

- LLM 邮件文案生成失败时，使用静态文案。
- 发送失败时，将错误写入 `agents.daily_email_send.problems`，并使第 5 步状态为 `failed`。

如果未传 `--send-email`，第 5 步只生成：

```text
email_preview.html
email_preview.txt
```

这用于本地验证和失败诊断。

## manifest 幂等回退

日报 manifest 和知识日志 manifest 更新时按日期或月份 upsert：

- 同一天重复生成不会追加重复日报条目。
- 同一月份重复生成不会追加重复知识日志条目。
- manifest 会保持合法 JSON 和倒序排序。

## 回退边界

系统不会在以下情况下自动“猜测生成”：

- 缺少必要上游文件。
- LLM 返回结构不合法。
- HTML 校验失败。
- manifest 指向的文件不存在。

这些情况应失败并记录诊断，而不是生成看似完整但不可追溯的日报。
