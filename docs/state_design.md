# 状态设计

本文记录 DailyLearningAssistant 当前状态文件设计。状态目标是支持拆分调度、单步补跑、失败定位和回退邮件判断。

## 状态文件位置

每个目标日期共用一个状态文件：

```text
prework/YYYY-MM/YYYY-MM-DD/run_status.json
```

同目录下的 LLM 调用追踪文件为：

```text
prework/YYYY-MM/YYYY-MM-DD/llm_trace.jsonl
```

## 顶层结构

`run_status.json` 的核心字段：

- `date`：目标日期。
- `updated_at`：最后更新时间。
- `agents`：各单步 Agent 的状态。
- `orchestrator`：最近一次 Orchestrator 运行状态。
- `orchestrator_runs`：按运行阶段保留的 Orchestrator 状态。

`orchestrator` 是兼容字段，始终指向最近一次运行。拆分调度后，不应只依赖它判断完整流水线状态。

## agents

每个 Agent 运行完成后写入：

```text
agents.<agent_name>
```

常见字段：

- `status`：`success`、`failed`、`partial_success` 等。
- `started_at` / `finished_at`。
- `input_*`：输入文件、输入目录、manifest 路径等。
- `output_*`：输出文件、报告路径、预览路径等。
- `llm.status`：LLM 调用状态。
- `problems`：可读诊断列表。

各 Agent 只更新自己的 `agents.<agent_name>`，不会覆盖其他 Agent 的状态。

待实现的远端仓库变化监控作为第 1 步输入扩展，仍写入：

```text
agents.daily_work_summary.repositories[]
```

本地仓库和远端仓库在后续内容输入上都生成 `work_summary_*.md`；只在状态中通过 `source` 区分来源，并记录 SSH Git / HTTP(S) Git 连接尝试：

```json
{
  "status": "success",
  "repositories": [
    {
      "name": "private-notes",
      "source": "remote",
      "status": "success",
      "evidence_type": "remote_ref_change",
      "output_path": "prework/2026-05/2026-05-26/work_summary_private-notes.md",
      "remote": {
        "urls": [
          "git@github.com:your-name/private-notes.git",
          "https://github.com/your-name/private-notes.git"
        ],
        "refs": [
          {
            "ref": "refs/heads/main",
            "status": "changed",
            "previous_sha": "aaa111",
            "current_sha": "bbb222",
            "changed": true,
            "selected_access": "ssh_git",
            "attempts": [
              {
                "access": "ssh_git",
                "status": "success",
                "url": "git@github.com:your-name/private-notes.git"
              },
              {
                "access": "http_git",
                "status": "skipped_after_success",
                "url": "https://github.com/your-name/private-notes.git"
              }
            ]
          }
        ]
      }
    }
  ],
  "repository_summary": {
    "remote_repositories": 1,
    "local_repositories": 0,
    "ssh_git_success": 1,
    "http_git_success": 0,
    "failed_refs": 0,
    "changed_refs": 1
  }
}
```

不新增 `agents.remote_repository_watch`，不新增 `remote_repository_summary.md`，不新增 `prework/remote_repository_state.json`。远端 ref 的上次 SHA 从历史日期的 `run_status.json` 中查找最近一次成功记录。完整设计见 `docs/remote_repository_monitoring.md`。

## orchestrator

`orchestrator` 记录最近一次 Orchestrator 运行，字段包括：

- `status`
- `requested_steps`
- `selected_steps`
- `manual_stage_override`
- `resume_skipped_steps`
- `dry_run`
- `publish`
- `send_email`
- `continue_on_failure`
- `commands`
- `failures`
- `fallback_events`
- `publish_events`
- `skipped_steps`
- `agent_summary`
- `llm_trace_path`

因为 HTML 生成发布和邮件发送现在是两个定时任务，后运行的邮件任务会让 `orchestrator.selected_steps` 变成 `[5]`。因此完整状态判断应看 `orchestrator_runs`。

## orchestrator_runs

`orchestrator_runs` 用来避免拆分调度互相覆盖状态。

当前约定：

- `orchestrator_runs.html_publish`
  - 第 1-4 步 HTML 生成与发布。
  - 对应 `run_daily.py --generation-only --publish`。

- `orchestrator_runs.email_send`
  - 第 5 步邮件发送。
  - 对应 `run_daily.py --only-step 5 --send-email`。

- `orchestrator_runs.full`
  - 兼容一次性执行第 1-5 步的旧模式。

- `orchestrator_runs.custom_*`
  - 其他手动补跑范围。

`orchestrator/state.py` 中的 `update_orchestrator(..., run_key=...)` 同时更新 `orchestrator` 和 `orchestrator_runs[run_key]`。

## 断点续连状态

断点续连会在 Orchestrator 状态中记录请求范围、实际执行范围和跳过原因。

- `requested_steps`：本次请求覆盖的步骤范围。例如 `--generation-only` 为 `[1, 2, 3, 4]`。
- `selected_steps`：断点续连后实际执行的步骤范围。如果第 1 步已完成、第 2 步失败，则为 `[2, 3, 4]`。
- `manual_stage_override`：是否显式传入 `--from-step`、`--to-step` 或 `--only-step`。
- `resume_skipped_steps`：因历史成功而跳过的 Agent 列表。

手动阶段覆盖时，`manual_stage_override = true`，Orchestrator 不会根据历史状态跳过 Agent。

第 1 步 `daily_work_summary` 的 `partial_success` 不作为断点续连完成态。若 LLM 失败后回退写入 Git 证据总结，下一次默认运行仍会从第 1 步重跑。

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

## 完整成功判断

`orchestrator/check_status.py` 读取状态文件并调用 `orchestrator.state.is_success`。

判断逻辑：

- 每个必要 Agent 必须成功。
- `daily_work_summary` 接受 `success` 或 `partial_success`。
- 如果第 1 步确认所有仓库无变化，状态会记录 `day_context.no_change_day = true`，但第 2/3 步仍必须成功；第 2 步负责生成复习型 `concept_relevance.md`。
- 拆分调度时，优先使用 `orchestrator_runs.html_publish` 判断生成阶段状态。

## LLM trace

`orchestrator/lifecycle.py` 会为 Agent 子进程注入 `DLA_LLM_TRACE_PATH`。

`orchestrator/llm.py` 将每次 LLM 尝试写入 `llm_trace.jsonl`，包括：

- 时间戳。
- Agent 名称。
- 尝试次数。
- 模型和接口。
- 是否信任环境代理。
- 调用耗时。
- 成功或失败状态。
- 错误类型。

`orchestrator/check_status.py` 会按 Agent、状态、错误类型和 `trust_env_proxy` 汇总 trace，便于判断失败是否与环境代理有关。

## 状态设计注意事项

- 状态文件是工程事实记录，不作为最终发布内容。
- 状态写入使用临时文件替换，避免半写入文件。
- 单步补跑会更新对应 Agent 状态和对应 Orchestrator run key。
- 拆分调度后，邮件任务应读取 `html_publish`，不要只看最近一次 `orchestrator`。
