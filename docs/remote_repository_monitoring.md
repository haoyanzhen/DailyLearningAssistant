# 远端仓库变化监控设计

本文记录远端仓库变化监控的设计方案。远端仓库与本地仓库在后续内容流程中不做区别：二者都生成 `work_summary_*.md`，都作为 `concept_relevance`、`knowledge_explaination` 和学习日报的输入。区别只保留在配置和状态记录中，用于诊断来源、访问路径和连接结果。

## 目标

- 支持监控本地不存在的远端仓库。
- 支持只有读取权限、没有写入权限的私人仓库。
- 支持无密钥访问的公开仓库。
- 每个远端仓库同时支持 SSH Git 和 HTTP(S) Git 两类访问路径，任一 URL 成功即可视为本次 ref 检查成功。
- 只读取远端 refs，不 clone、不 fetch、不下载 commit object、tree、blob 或工作区文件。
- 远端仓库和本地仓库统一进入后续知识点提取流程。
- 不新增独立远端总结文件，不新增独立远端基线文件。

## 非目标

- 不通过 GitHub API、GitLab API 或其他平台 API 获取提交详情。
- 不解析远端 commit message、作者、diff 或文件列表。
- 不自动拉取、合并、提交或推送任何被监控仓库。
- 不要求被监控仓库存在于本地。
- 不在后续内容处理阶段区分“本地输入”和“远端输入”。

## 总体方案

将远端仓库监控纳入第 1 步 Git 证据收集阶段。

- 扩展现有 `agents/daily_work_summary.py`，让它同时读取 `config.repositories` 和 `config.remote_repositories`。

第 1 步输出目录保持不变：

```text
prework/YYYY-MM/YYYY-MM-DD/
```

本地仓库和远端仓库都生成同一类输入文件：

```text
work_summary_[repo].md
```

例如：

```text
work_summary_DailyLearningAssistant.md
work_summary_private-notes.md
work_summary_public-library.md
```

第 2 步 `concept_relevance` 继续读取当日所有 `work_summary_*.md`，不需要知道文件来自本地仓库还是远端仓库。

远端仓库检查使用：

```bash
git ls-remote <url> <ref>
```

`git ls-remote` 只询问远端 ref 当前指向的 SHA，不会创建本地仓库，也不会下载 Git 对象。

## 配置设计

在 `config.json` 中新增可选字段：

```json
{
  "remote_repositories": [
    {
      "urls": [
        "git@github.com:your-name/private-notes.git",
        "https://github.com/your-name/private-notes.git"
      ]
    },
    {
      "urls": [
        "https://github.com/some-org/some-library.git"
      ],
      "refs": ["refs/heads/main", "refs/tags/v1.0.0"]
    }
  ]
}
```

字段说明：

- `urls`：必填。远端 Git URL 列表，可以包含 SSH URL 和 HTTP(S) URL。按配置顺序尝试，任一 URL 成功即可完成该 ref 的检查。
- `refs`：可选。要监控的 ref 列表，默认 `["refs/heads/main"]`。
- `name`：可选。仓库显示名，进入统一输出文件名 `work_summary_[name].md`。
- `enabled`：可选，默认 `true`。

`name` 默认从第一个 URL 和 ref 派生：

```text
{repo_name}:{ref_name}
```

例如：

- `git@github.com:your-name/private-notes.git` + `refs/heads/main` -> `private-notes:main`
- `https://github.com/some-org/public-library.git` + `refs/tags/v1.0.0` -> `public-library:v1.0.0`

如果一个远端配置包含多个 refs，且未显式设置 `name`，每个 ref 应生成独立输出名，避免多个 ref 写入同一个 `work_summary_*.md`。如果显式设置 `name`，多个 refs 可合并到同一个仓库总结中。

派生输出文件名时需要做文件名安全转换：去掉 URL 末尾 `.git`，将 ref 中的 `/` 转为 `-`，并把不适合文件名的字符替换为 `_`。状态里的 `name` 可以保留 `private-notes:main` 这种可读形式，实际文件可写为 `work_summary_private-notes_main.md`。

私人仓库通常通过 SSH URL 成功，依赖本机 SSH key 的读取权限。公开仓库通常通过 HTTP(S) URL 成功，不要求密钥。

配置约束：

- `urls` 不能为空。
- `refs` 为空或未配置时，按 `["refs/heads/main"]` 处理。
- 最终生成的远端输出名必须和 `repositories[].name` 及其他远端输出名全局唯一。
- 远端仓库配置只表达访问来源；后续内容流程不根据该来源分叉。

## 访问路径与判定

每个远端仓库的每个 ref 按 `urls` 顺序执行连接尝试。访问类型从 URL 自动识别：

1. `ssh_git`
   - URL 形态：`git@github.com:owner/repo.git` 或 `ssh://git@host/owner/repo.git`
   - 命令：`git ls-remote <ssh-url> refs/heads/main`
   - 适用：私人仓库、需要账号授权的仓库、已配置 SSH key 的机器。

2. `http_git`
   - URL 形态：`https://host/owner/repo.git` 或 `http://host/owner/repo.git`
   - 命令：`git ls-remote <http-url> refs/heads/main`
   - 适用：公开仓库、无需密钥的只读访问。

成功判定：

- 任一访问路径返回 0，并且 stdout 中包含目标 ref，则该 ref 检查成功。
- 两条路径都失败，则该 ref 检查失败。
- 命令返回 0 但没有目标 ref，视为 `ref_missing`。

建议默认行为：

- 按 `urls` 顺序尝试。
- 第一条 URL 成功后，可以跳过剩余 URL，并在状态中记录 `skipped_after_success`。
- 如果传入诊断参数，例如 `--probe-all-access`，则即使第一条路径成功，也继续尝试其他路径并记录真实连接结果。

失败分类建议：

- `auth_failed`：SSH 权限不足、私有仓库 HTTPS 未认证等。
- `network_failed`：DNS、连接超时、TLS 或 SSH 连接失败。
- `repo_missing`：仓库不存在或当前身份不可见。
- `ref_missing`：仓库可访问但目标 ref 不存在。
- `command_failed`：其他 Git 命令错误。

MVP 不需要精准解析所有平台错误，但状态中必须保留 stderr 摘要，便于人工诊断。

## 变化判断

不新增远端基线文件。远端 ref 的上次 SHA 从历史每日状态中读取：

```text
prework/YYYY-MM/*/run_status.json
```

查找规则：

1. 从目标日期之前的日期倒序查找。
2. 找到最近一次 `agents.daily_work_summary.repositories[]` 中同名远端仓库、同一 ref、且状态为成功的记录。
3. 使用该记录的 `current_sha` 作为 `previous_sha`。
4. 如果找不到历史记录，则本次状态为 `first_seen`，不判断为“新增提交”。

变化状态：

- `first_seen`：首次成功看到该 ref。
- `unchanged`：当前 SHA 等于历史 SHA。
- `changed`：当前 SHA 不同于历史 SHA。
- `ref_missing`：本次仓库可访问但 ref 不存在。
- `failed`：所有访问路径均失败。

因为不下载 commit object，`changed` 只能证明 ref 指针变化，不能证明新增提交数量、提交信息或文件变化。它可能代表新增提交、回滚、强推或分支重写。内容总结中应如实表达为“ref 指针变化”或“远端版本变化线索”，不要编造提交详情。

## 状态设计

远端仓库状态写入现有第 1 步状态：

```text
run_status.json
agents.daily_work_summary.repositories[]
```

本地仓库和远端仓库共用 `repositories` 列表，通过 `source` 字段区分来源：

```json
{
  "agents": {
    "daily_work_summary": {
      "status": "success",
      "repositories": [
        {
          "name": "DailyLearningAssistant",
          "source": "local",
          "path": "/Users/qingyue/projects/DailyLearningAssistant",
          "status": "success",
          "evidence_type": "confirmed_change",
          "output_path": "prework/2026-05/2026-05-26/work_summary_DailyLearningAssistant.md"
        },
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
                    "url": "git@github.com:your-name/private-notes.git",
                    "status": "success",
                    "returncode": 0,
                    "remote_ref": "refs/heads/main",
                    "sha": "bbb222",
                    "stderr_excerpt": ""
                  },
                  {
                    "access": "http_git",
                    "url": "https://github.com/your-name/private-notes.git",
                    "status": "skipped_after_success"
                  }
                ]
              }
            ]
          },
          "signals": {
            "has_confirmed_commits": false,
            "has_primary_uncommitted_changes": false,
            "has_branch_tip_changes": false,
            "has_worktree_candidate_changes": false,
            "has_remote_ref_changes": true
          }
        }
      ],
      "repository_summary": {
        "local_repositories": 1,
        "remote_repositories": 1,
        "ssh_git_success": 1,
        "http_git_success": 0,
        "remote_failed_refs": 0,
        "remote_changed_refs": 1
      }
    }
  }
}
```

状态记录约束：

- 只有状态记录区分 `source = "local"` 和 `source = "remote"`。
- SSH Git / HTTP(S) Git 连接记录只存在于 `remote.refs[].attempts`。
- 不写 `state_path`，不维护 `prework/remote_repository_state.json`。
- 不写单独的 `agents.remote_repository_watch`；MVP 设计中远端监控属于第 1 步输入扩展。
- HTTP(S) URL 如果包含用户名、token 或密码，写入状态前必须脱敏。

## 安全边界

- 不在配置中保存 SSH 私钥。
- 私人仓库通过本机 SSH agent、`~/.ssh/config` 或系统 credential 完成认证。
- 状态文件可记录 URL 和 SHA，但不要记录 token、密码或完整认证 URL。
- `git ls-remote` 命令必须使用参数数组调用，避免 shell 拼接带来的注入风险。
