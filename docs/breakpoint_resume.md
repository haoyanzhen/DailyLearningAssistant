# 断点续连设计

本文记录 DailyLearningAssistant 的 Agent 粒度断点续连设计。目标是在某日流水线失败后，下一次默认运行可以从第一个未完成 Agent 自动继续，同时保留手动补跑时的明确控制权。

## 设计目标

- 默认运行时自动读取当天 `run_status.json`。
- 按 Agent 顺序跳过已经完成的前序 Agent。
- 从第一个未完成 Agent 开始继续执行。
- 手动指定运行阶段时，完全以手动指定为准。
- 第 1 步 LLM 失败后回退到 Git 证据总结时，不视为真正完成。

## 适用范围

断点续连由 `orchestrator/run_daily.py` 执行，只作用于 Orchestrator 选择的 Agent 范围。

默认范围：

- 普通运行：第 1-5 步。
- `--generation-only`：第 1-4 步，用于 HTML 生成发布任务。

手动范围：

- `--from-step`
- `--to-step`
- `--only-step`

只要显式传入以上任一手动阶段参数，就关闭自动跳过，指定范围内 Agent 全部重跑。

## 完成状态判定

### 通用 Agent

第 2-5 步的完成条件是：

```text
agents.<agent_name>.status == "success"
```

这些 Agent 的失败、输入缺失、输出校验失败或 LLM 失败都不视为完成。

### 第 1 步 daily_work_summary

第 1 步有特殊判定，因为它允许 LLM 失败后回退到 Git 证据总结。

视为完成的条件：

- `agents.daily_work_summary.status == "success"`。
- 每个仓库的 `repositories[].status == "success"`。
- 对于有变更的仓库，`repositories[].llm.status == "success"`。
- 对于无变更仓库，允许 `repositories[].llm.status == "skipped_no_change"`。

不视为完成的情况：

- 总状态为 `partial_success`。
- 任一仓库状态为 `degraded`。
- 有变更仓库的 LLM 状态为 `failed`、`skipped_unconfigured` 或 `skipped_disabled`。

这保证了“回退到 Git 变更记录”只作为临时可诊断产物，而不是阻止后续自动重试 LLM 总结的完成态。

## 执行流程

默认运行流程：

1. 根据命令行参数得到请求运行范围 `requested_steps`。
2. 读取当天 `prework/YYYY-MM/YYYY-MM-DD/run_status.json`。
3. 从 `requested_steps` 的开头开始检查 Agent 是否已完成。
4. 连续跳过已经完成的前序 Agent。
5. 将跳过记录写入 `resume_skipped_steps`。
6. 从第一个未完成 Agent 开始执行。
7. 如果请求范围内 Agent 全部完成，则不重跑 Agent。

手动运行流程：

1. 只要传入 `--from-step`、`--to-step` 或 `--only-step`，设置 `manual_stage_override = true`。
2. 不读取完成状态来跳过 Agent。
3. 指定范围内 Agent 全部执行。

## 状态记录

Orchestrator 运行状态会记录：

- `requested_steps`：用户或默认策略请求的完整步骤范围。
- `selected_steps`：断点续连后实际要执行的步骤。
- `manual_stage_override`：是否由手动阶段参数关闭自动续跑。
- `resume_skipped_steps`：因上次成功而跳过的 Agent 列表。

示例：

```json
{
  "requested_steps": [1, 2, 3, 4],
  "selected_steps": [2, 3, 4],
  "manual_stage_override": false,
  "resume_skipped_steps": [
    {
      "step": 1,
      "agent": "daily_work_summary",
      "reason": "previous_success"
    }
  ]
}
```

## 发布阶段续连

Git 发布不是单独 Agent，而是第 4 步成功后的 Orchestrator 集成阶段。

因此存在一个边界：如果第 4 步已经成功并被断点续连跳过，但此前发布失败或没有成功发布记录，Orchestrator 仍应继续执行发布阶段。

发布处理规则：

- 第 4 步本次执行成功，且传入 `--publish`：立即发布。
- 第 4 步因断点续连跳过，且历史没有成功发布记录：继续发布。
- 第 4 步因断点续连跳过，且历史已有成功发布记录：记录 `skipped_previous_success`。

## 与无变更日回退的关系

无变更日回退仍属于 Orchestrator 的跨步骤回退机制：

- 第 1 步确认所有仓库无变更。
- 第 2/3 步可跳过。
- 复用上一份有效知识讲解进入第 4 步。

断点续连只负责决定“哪些前序 Agent 已完成，可以跳过”。无变更日是否跳过第 2/3 步，仍由运行中的 Orchestrator 根据第 1 步状态动态判断。

## 命令约定

定时 HTML 生成发布任务应使用：

```bash
python3 orchestrator/run_daily.py --generation-only --publish
```

`--generation-only` 选择第 1-4 步，但不算手动阶段覆盖，因此会启用断点续连。

手动补跑示例：

```bash
python3 orchestrator/run_daily.py --date 2026-05-24 --from-step 2 --to-step 4 --publish
```

该命令会强制重跑第 2-4 步，即使其中某些 Agent 在状态文件里已经成功。

## 设计边界

- 不做跨日期续连，每个日期只读取自己的状态文件。
- 不尝试判断输出文件内容是否语义过期，只根据 Agent 状态和第 1 步 LLM 完成规则判断。
- 不自动重跑已经成功的后序 Agent；一旦中间 Agent 未完成，会从该 Agent 开始顺序执行后续 Agent。
- 手动阶段参数优先级最高，用于用户明确想覆盖历史状态的场景。
