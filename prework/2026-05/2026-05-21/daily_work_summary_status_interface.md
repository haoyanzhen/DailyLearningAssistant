# 第 1 步 Agent 状态接口：daily_work_summary

本文档定义本地独立 Agent `agents/daily_work_summary.py` 的运行状态记录格式。状态文件用于让后续 runner、补跑逻辑和人工排查理解第 1 步是否完成、是否调用 LLM、是否发生降级，以及每个仓库的输出文件位置。

## 状态文件位置

```text
prework/YYYY-MM/YYYY-MM-DD/run_status.json
```

第 1 步 Agent 只更新其中的 `agents.daily_work_summary` 字段，不应覆盖其他 Agent 的状态字段。

## 顶层结构

```json
{
  "date": "YYYY-MM-DD",
  "updated_at": "ISO-8601 timestamp",
  "agents": {
    "daily_work_summary": {
      "status": "success | partial_success | failed",
      "started_at": "ISO-8601 timestamp",
      "finished_at": "ISO-8601 timestamp",
      "timezone": "Asia/Shanghai",
      "window": {
        "start": "ISO-8601 timestamp",
        "end": "ISO-8601 timestamp"
      },
      "output_dir": "prework/YYYY-MM/YYYY-MM-DD",
      "llm": {
        "enabled": true,
        "configured": true,
        "model": "model-name",
        "retries": 3,
        "retry_delay_seconds": 3.0
      },
      "repositories": []
    }
  }
}
```

## 仓库状态结构

每个仓库在 `repositories` 中写入一条记录：

```json
{
  "name": "DailyLearningAssistant",
  "path": "/Users/qingyue/projects/DailyLearningAssistant",
  "status": "success | degraded | failed",
  "evidence_type": "no_change | confirmed_change | candidate_change | unavailable",
  "output_path": "prework/YYYY-MM/YYYY-MM-DD/work_summary_DailyLearningAssistant.md",
  "llm": {
    "status": "success | failed | skipped_no_change | skipped_disabled | skipped_unconfigured",
    "error": null
  },
  "signals": {
    "has_confirmed_commits": true,
    "has_primary_uncommitted_changes": false,
    "has_branch_tip_changes": false,
    "has_worktree_candidate_changes": true
  }
}
```

## 状态语义

- `success`：该仓库已生成输出文件。若需要 LLM，LLM 已成功；若无变化或 LLM 被禁用/未配置，则按规则生成确定性总结。
- `degraded`：该仓库有变化证据，尝试调用 LLM 但失败，已降级写入 Git 证据总结。
- `failed`：该仓库未能生成输出文件。正常情况下第 1 步 Agent 应尽量避免该状态，而是生成问题说明文件。
- `no_change`：无窗口内提交、无主工作区变更、无分支或 worktree 待确认线索。
- `confirmed_change`：存在目标窗口内已确认 commit。
- `candidate_change`：不存在已确认 commit，但存在主工作区、分支 tip 或 worktree 待确认变化线索。
- `unavailable`：仓库缺失、不是 Git 仓库或 Git 读取失败。

## 使用约束

- `work_summary_[reponame].md` 是第 1 步给下游的唯一正式内容文件。
- `run_status.json` 只记录运行状态和证据信号，不承载长篇 Git diff 或 LLM prompt。
- 后续 Agent 判断第 1 步是否完成时，应优先检查 5 个 `work_summary_*.md` 是否存在且非空，再参考 `run_status.json` 的状态解释。
