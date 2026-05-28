# 本地 Agent Orchestrator 设计

`orchestrator/` 负责把 5 个本地 Agent 从“可单独运行的脚本”组织成“可调度、可检查、可恢复”的本地流水线。

## 目录职责

- `run_daily.py`：总入口，按步骤运行 Agent，支持默认断点续跑、`--date`、`--from-step`、`--to-step`、`--only-step`、`--dry-run`。
- `check_status.py`：读取当天 `run_status.json`，检查各 Agent 状态和失败原因。
- `lifecycle.py`：定义 Agent 生命周期和命令构造，不直接耦合 Agent 内部实现。
- `state.py`：统一读写 `prework/YYYY-MM/YYYY-MM-DD/run_status.json`。
- `manifest.py`：统一读写、更新和强校验 `daily_report/manifest.json` 与 `knowledge_log/manifest.json`。
- `llm.py`：OpenAI Chat Completions 兼容调用、失败重试、指数退避，以及 SMTP/IMAP 断联重试原语。
- `validators.py`：通用文件、LLM 标签/JSON 输出、HTML 日报结构校验，并兼容调用 manifest 校验。
- `config.py`：配置读取、日期和时区解析、路径工具。

## 当前 Agent 顺序

1. `daily_work_summary`
2. `concept_relevance`
3. `knowledge_explaination`
4. `learning_report_publish`
5. `daily_email_send`

Orchestrator 只通过每个 Agent 的命令行参数调度，不直接调用 Agent 内部函数。这样每个 Agent 可以独立演进，总调度只依赖稳定 CLI 契约。

## 运行示例

```bash
python3 orchestrator/run_daily.py --date 2026-05-21 --dry-run
python3 orchestrator/run_daily.py --date 2026-05-21 --from-step 2 --to-step 4
python3 orchestrator/run_daily.py --date 2026-05-21 --output-root /tmp/pipeline-test
python3 orchestrator/run_daily.py --date 2026-05-21 --generation-only --publish
python3 orchestrator/check_status.py --date 2026-05-21
```

如果没有显式传入 `--input-root`，`run_daily.py` 会让下游步骤读取 `--output-root`。这样在临时目录补跑完整流水线时，步骤 2 会读取步骤 1 刚写入的临时产物；如果只想用正式仓库作为输入、把某一步输出写到临时目录，则显式传入 `--input-root .`。

第 5 步邮件 Agent 在总调度中默认以 `--dry-run` 方式生成预览，不会真实发送邮件。只有显式传入 `--send-email` 时，orchestrator 才允许第 5 步通过 SMTP 发送。测试邮件会使用 `test: ` 作为标题前缀；当前测试邮箱设置为发送邮箱本身时，也会自动进入测试标题模式。

## 状态管理

所有状态统一写入：

```text
prework/YYYY-MM/YYYY-MM-DD/run_status.json
```

单步 Agent 写入 `agents.<agent_name>`；总调度写入顶层 `orchestrator`，记录最近一次运行的步骤、命令、失败步骤和汇总状态。

拆分调度时，状态文件还会保留 `orchestrator_runs`：

- `orchestrator_runs.html_publish`：第 1-4 步 HTML 生成与发布状态。
- `orchestrator_runs.email_send`：第 5 步邮件发送状态。

第 5 步单独运行时会读取 `html_publish` 的状态；如果生成发布未成功，会自动转为失败提醒邮件，并回退附上上一份可用日报。

默认运行时，orchestrator 会读取当天已有状态并按 Agent 粒度断点续跑：从选定范围内第一个未完成 Agent 开始执行，之前已经成功的 Agent 会跳过。第 1 步较特殊：如果 LLM 总结失败后回退为 Git 证据总结，状态会是 `partial_success`，断点续跑时会视为未完成并重跑；只有实际变更仓库均完成 LLM 总结，或仓库无变更而跳过 LLM，才视为已完成。

如果显式传入 `--from-step`、`--to-step` 或 `--only-step`，则以手动指定阶段为准，指定范围内的 Agent 会全部重跑，不做断点跳过。`--generation-only` 用于定时生成发布任务选择第 1-4 步，但不视为手动阶段覆盖，因此仍会启用断点续跑。

## LLM 重连与结果校验

`llm.py` 使用 `httpx` 提供统一的 Chat Completions 调用和重试能力。各 Agent 只保留业务调用和失败解释，不再自行实现循环等待、指数退避或断联重连。现阶段 orchestrator 会把 `--llm-retries` 和 `--llm-retry-delay` 继续下发给支持的 Agent，具体重试执行由 `llm.py` 完成。总调度运行时会把每次 LLM 尝试写入当天的 `llm_trace.jsonl`，记录 Agent、尝试次数、耗时、模型、接口、是否信任环境代理和错误类型。LLM 请求默认不读取 `http_proxy`、`https_proxy` 等环境代理；如需代理访问，可在 `llm.trust_env_proxy` 中显式开启。

`manifest.py` 负责站点索引的统一管理，会强校验日期格式、路径格式、重复项、倒序和必要字段；在生成日报或发送邮件时，还会检查 manifest 指向的本地文件是否存在且非空。

`validators.py` 提供跨步骤结果校验能力，尤其用于长 HTML 和标签协议输出。当前第 4 步已采用标签协议避免长 HTML JSON 转义失败，后续可继续把第 2、3、5 步的更多输出校验迁移到这里。
