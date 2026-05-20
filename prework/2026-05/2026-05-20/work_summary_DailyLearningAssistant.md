# 2026-05-20 DailyLearningAssistant 工作总结

本总结基于 `DailyLearningAssistant` 仓库在 2026-05-19 00:00:00 +0800 至 2026-05-20 00:00:00 +0800 之间的 Git 提交记录生成。前一天的核心推进有两条线：一是完成 2026-05-19 学习日报发布，把“输入缺失时仍需可追溯记录”的主题沉淀为正式日报；二是继续把日常自动化从“手工运行脚本”推进到“配置驱动、LLM 生成、定时推送、自动同步”的运行体系。

## 提交概览

| 项目 | 内容 |
| --- | --- |
| 仓库 | `DailyLearningAssistant` |
| 日期 | 2026-05-20 |
| 统计窗口 | 2026-05-19 00:00:00 +0800 至 2026-05-20 00:00:00 +0800 |
| 提交数量 | 4 |
| 涉及范围 | 15 个文件，约 1736 行新增、33 行删除 |
| 核心主题 | 学习日报发布、邮件文案风格约束、配置化 LLM 知识讲解、定时 git push 辅助 |

- `fc03c71`（2026-05-19 08:06:08 +0800）：`Publish 2026-05-19 learning report`。发布 2026-05-19 学习日报，新增当日概念提炼、知识讲解、5 个工作总结，并更新 `manifest.json` 与月度教学记录。
- `8f5d7fb`（2026-05-19 11:02:45 +0800）：`Refine daily email prompt style`。调整每日邮件 LLM prompt，引入随机风格档案，降低过度亲密或无依据扩写的风险。
- `256a7dd`（2026-05-19 11:19:05 +0800）：`Use configured LLM for knowledge explanations`。把知识讲解任务改为通过 `config.json` 中的 LLM 配置调用外部模型生成，新增独立生成脚本，并让邮件推送可以选择不晚于发送日期的最新日报。
- `fc9bbe2`（2026-05-19 22:10:12 +0800）：`Add scheduled git push helper`。新增自动 git push 脚本与 macOS launchd 安装脚本，在邮件发送前自动把本地 `main` 分支同步到远端。

## 关键文件变更

| 文件 | 变化 | 说明 |
| --- | --- | --- |
| `daily_report/2026-05/2026-05-19-learning-report.html` | 新增 | 发布 2026-05-19 学习日报，主题聚焦数据血缘、防幻觉生成约束与失败状态产品化。 |
| `daily_report/manifest.json` | 修改 | 新增 2026-05-19 日报索引，使首页和归档可以发现最新日报。 |
| `knowledge_log/2026-05-knowledge-log.md` | 修改 | 新增 2026-05-19 的三条教学记录：数据血缘、防幻觉生成约束、失败状态产品化。 |
| `prework/2026-05/2026-05-19/*.md` | 新增 | 补齐当日概念提炼、知识讲解和 5 个仓库工作总结，形成日报发布的上游证据链。 |
| `scripts/send_daily_email.py` | 修改 | 邮件文案 prompt 引入随机风格 profile、写作边界和更稳妥的回退文案；后续又改为推荐不晚于发送日期的最新可用日报。 |
| `prompt/03_knowledge_explaination.md` | 修改 | 将任务 3 的角色从 Codex 直接写正文改为“知识讲解生成调度员”，要求优先执行脚本调用配置的 LLM。 |
| `scripts/generate_knowledge_explaination.py` | 新增 | 新增无第三方依赖的知识讲解生成脚本，负责读取概念文件和教学记录、调用 Chat Completions 兼容接口、校验 JSON 输出并落盘。 |
| `scripts/auto_git_push.sh` | 新增 | 自动检查分支、DNS、SSH、远端可读性和 ahead/behind 状态，仅在本地 `main` 领先且未落后时推送。 |
| `scripts/setup_git_push_launchd.sh` | 新增 | 根据 `config.json` 的 `schedule.daily_run_time` 推导提前 30 分钟的 git push 时间，并安装/卸载/查看 launchd 任务。 |

## 主要工作主题

### 1. 学习日报发布链路继续保持可追溯

`fc03c71` 把 2026-05-19 的日报、概念提炼、知识讲解和月度教学记录一起发布。日报主题围绕“数据血缘、防幻觉生成约束、失败状态产品化”，与前一天的状态页工作直接相关：当自动化任务缺少上游输入时，系统不能假装生成正常内容，而应把缺失原因、影响链路和恢复路径写清楚。

这次提交也延续了 `manifest.json` 作为静态站点发布索引的契约：只要日报产物进入 manifest，首页和归档就能稳定发现它。

### 2. 邮件推送从固定口吻转向可控的动态文案

`8f5d7fb` 对 `scripts/send_daily_email.py` 的 LLM prompt 做了一次风格治理。脚本新增多个 `style_profiles`，每次从“清晨便签”“知识小导游”“安静陪跑”等风格中随机选择一个，以减少每日邮件的重复感。

更重要的是 prompt 加入了明确的写作边界：不要猜测收件人的现实状态，不要把摘要里没有的信息扩写成事实，信息不足时应更轻、更概括。这让邮件文案的亲切感与事实边界同时存在。

### 3. 知识讲解生成被改造成配置驱动的 LLM 调度任务

`256a7dd` 是当天最关键的自动化架构调整。`prompt/03_knowledge_explaination.md` 明确要求 Codex 不再默认直接撰写正式知识讲解，而是作为调度员运行 `scripts/generate_knowledge_explaination.py`，由 `config.json` 中配置的外部 LLM 生成正文和月度教学记录。

新脚本完成了几类职责：读取 `concept_relevance.md` 和已有 `knowledge_log`，构造严格 JSON 输出要求，调用 OpenAI Chat Completions 兼容接口，解析并校验返回内容，最后写入 `knowledge_explaination.md` 与月度日志。它还会在 `config.json` 缺失、LLM 配置不完整、API key 仍为占位符或响应格式不符合约定时直接失败，避免静默回退为不可追踪的 Codex 手写内容。

### 4. 邮件任务支持“最新可用日报”降级

同一提交还把 `send_daily_email.py` 从只查找“目标日期当天日报”改为查找“不晚于发送日期的最新可用日报”。这解决了一个真实自动化问题：如果今天日报尚未生成，邮件推送可以推荐最近一份已发布日报，而不是直接无内容。

脚本同时区分了“发送日期”和“日报日期”，邮件主题也使用实际推荐日报的日期，避免用户误以为旧日报是当天新内容。这是一个小改动，但对自动化系统的诚实降级很重要。

### 5. 定时 git push 补上静态站点发布前的同步环节

`fc9bbe2` 新增 `auto_git_push.sh` 和 `setup_git_push_launchd.sh`，目标是在每日邮件发送前把本地提交推到远端，减少“本地已有日报但 GitHub Pages 尚未发布”的断链。

推送脚本没有盲目执行 `git push`，而是先检查当前分支必须是 `main`、GitHub DNS 可解析、SSH 认证成功、远端可读，然后 fetch `origin/main` 并比较 ahead/behind。只有本地领先且没有落后时才推送；如果本地落后，则要求人工审查。这体现了自动化发布中的防护式设计。

## 可能涉及的知识点线索

- **配置驱动自动化**：知识讲解脚本从 `config.json` 读取 LLM endpoint、model、API key、timezone 等运行参数，使同一流程可以换模型或换环境。
- **LLM 输出契约**：要求外部模型返回固定 JSON schema，并对字段、HTML 表格和 `rowspan="3"` 做校验，是把自然语言输出纳入工程流程的关键。
- **防幻觉生成边界**：任务 3 不允许在 LLM 调用失败时由 Codex 补写正式讲解；邮件 prompt 也不允许无依据扩写现实事实。
- **降级策略与最新可用数据**：邮件推送在当天日报缺失时选择最近可用日报，同时保留发送日期与日报日期的区别。
- **定时任务与发布前置同步**：launchd 定时任务把本地提交同步纳入每日自动化链路，并把执行时间与邮件时间相对绑定。
- **Git 远端状态校验**：通过 ahead/behind 检查避免在本地落后远端时自动推送，降低覆盖或冲突风险。
- **静态站点发布契约**：`manifest.json`、日报 HTML、知识日志和 prework 材料之间形成可追溯发布链路。

## 对后续概念提炼任务有帮助的备注

2026-05-19 的新增内容非常适合提炼“自动化系统可靠性”主题。最值得关注的不是单个脚本，而是几条贯穿链路的工程原则：LLM 生成必须有输入证据和输出契约；每日发布必须处理缺失、延迟和降级；自动推送必须先验证远端状态；邮件文案也需要事实边界。后续概念提炼可以围绕“配置驱动 LLM 工作流”“结构化输出校验”“降级发布策略”“定时任务编排”“Git 发布前置校验”展开。

数据来源：`git log --since="2026-05-19 00:00:00 +0800" --until="2026-05-20 00:00:00 +0800"`，以及提交 `fc03c71`、`8f5d7fb`、`256a7dd`、`fc9bbe2` 对 `daily_report/manifest.json`、`knowledge_log/2026-05-knowledge-log.md`、`prompt/03_knowledge_explaination.md`、`scripts/send_daily_email.py`、`scripts/generate_knowledge_explaination.py`、`scripts/auto_git_push.sh` 和 `scripts/setup_git_push_launchd.sh` 的修改内容。
