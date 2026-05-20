# 2026-05-20 概念与关联提炼

## 输入文件

- `work_summary_AInote.md`
- `work_summary_DailyLearningAssistant.md`
- `work_summary_interview_prepare.md`
- `work_summary_ResearchPaperBase_cc.md`
- `work_summary_ResearchPaperBase_codex.md`

## 当日核心主题

今天的可确认技术主题主要来自 `DailyLearningAssistant`。当天工作围绕日常学习日报自动化链路展开：一方面发布 2026-05-19 学习日报并维护静态站点索引，另一方面把知识讲解、邮件推送和发布前同步进一步工程化，形成“配置驱动 LLM 生成、结构化输出校验、事实边界约束、缺失输入降级、定时 git push”的自动化运行体系。

`AInote`、`interview_prepare`、`ResearchPaperBase_cc` 和 `ResearchPaperBase_codex` 在统计窗口内没有提交记录，因此不从这些仓库提炼新增概念。

## 概念清单

### 数学

- 未发现明确线索。

### 物理

- 未发现明确线索。

### 计算机科学

- 结构化输出契约
  - 来源：`DailyLearningAssistant`
  - 说明：知识讲解脚本要求外部 LLM 返回固定 JSON schema，并校验字段、HTML 表格和 `rowspan="3"` 等格式约束。这体现了把非确定性的自然语言输出转化为可解析数据接口的思想。

- 数据血缘
  - 来源：`DailyLearningAssistant`
  - 说明：日报、概念提炼、知识讲解、月度教学记录和 `manifest.json` 之间形成上游输入到下游发布的证据链，便于追踪内容来自哪些中间产物。

- 状态校验
  - 来源：`DailyLearningAssistant`
  - 说明：自动 git push 脚本检查分支、DNS、SSH、远端可读性以及 ahead/behind 状态，再决定是否推送，属于对系统状态进行显式判定后再执行动作。

- 最新可用数据选择
  - 来源：`DailyLearningAssistant`
  - 说明：邮件推送在目标日期日报不存在时，选择不晚于发送日期的最新可用日报，同时区分发送日期和日报日期。

### 软件工程

- 配置驱动自动化
  - 来源：`DailyLearningAssistant`
  - 说明：知识讲解生成脚本从 `config.json` 读取 LLM endpoint、model、API key、timezone 等参数，使同一流程可通过配置切换运行环境和模型。

- 自动化流水线
  - 来源：`DailyLearningAssistant`
  - 说明：从仓库总结、概念提炼、知识讲解、日报 HTML、manifest 索引到邮件发送，形成连续的每日发布链路。

- 降级策略
  - 来源：`DailyLearningAssistant`
  - 说明：邮件任务在当天日报缺失时推荐最近可用日报；概念和知识生成任务也强调输入缺失时应显式失败或记录，而不是伪造正常结果。

- 发布前置同步
  - 来源：`DailyLearningAssistant`
  - 说明：新增定时 git push 辅助脚本，在邮件发送前把本地 `main` 分支同步到远端，减少本地已生成但 GitHub Pages 未发布的断链。

- 防护式自动化
  - 来源：`DailyLearningAssistant`
  - 说明：自动推送脚本不盲目执行，而是先验证网络、认证、远端状态和分支关系；本地落后远端时要求人工审查。

- 静态站点发布契约
  - 来源：`DailyLearningAssistant`
  - 说明：`manifest.json` 作为日报发现索引，和 HTML 日报、prework 材料、知识日志共同约定了静态站点可展示内容的入口。

### 大语言模型

- LLM 生成调度
  - 来源：`DailyLearningAssistant`
  - 说明：任务 3 的 prompt 从“直接撰写知识讲解”调整为“调度脚本调用配置的外部 LLM”，Codex 主要负责运行、检查和落盘。

- 防幻觉生成边界
  - 来源：`DailyLearningAssistant`
  - 说明：知识讲解任务不允许在 LLM 调用失败时由 Codex 补写正式内容；邮件 prompt 也要求不猜测收件人现实状态，不把摘要外的信息扩写成事实。

- Prompt 风格档案
  - 来源：`DailyLearningAssistant`
  - 说明：邮件文案 prompt 引入多个随机风格 profile，让每日邮件减少重复感，同时用写作边界控制亲切感不过度越界。

- LLM 输出校验
  - 来源：`DailyLearningAssistant`
  - 说明：脚本对模型响应进行 JSON 解析和字段校验，只有符合约定的内容才写入 `knowledge_explaination.md` 和月度知识日志。

## 概念关联

| 概念 A | 关系 | 概念 B | 说明 |
| --- | --- | --- | --- |
| 配置驱动自动化 | 支撑 | LLM 生成调度 | 外部 LLM 的 endpoint、model 和 key 来自配置文件，使调度脚本不绑定单一模型或环境。 |
| LLM 生成调度 | 依赖 | 结构化输出契约 | 调度脚本要把模型输出写入后续文件，必须要求模型返回可解析、可校验的 JSON 结构。 |
| 结构化输出契约 | 落实为 | LLM 输出校验 | schema 只是约定，脚本解析字段和格式才把约定变成工程上的准入条件。 |
| 防幻觉生成边界 | 约束 | LLM 生成调度 | 当 LLM 调用失败或输入不足时，流程不能让 Codex 代写正式内容，否则会破坏来源可追溯性。 |
| 防幻觉生成边界 | 约束 | Prompt 风格档案 | 邮件可以有随机风格，但不能猜测用户现实状态，也不能把摘要外信息写成事实。 |
| 数据血缘 | 支撑 | 防幻觉生成边界 | 明确内容来源后，系统才能判断哪些信息可用、哪些信息不能被扩写。 |
| 自动化流水线 | 组织 | 数据血缘 | 仓库总结、概念提炼、知识讲解、日报和 manifest 是流水线上的连续节点，数据血缘描述节点之间的来源关系。 |
| 降级策略 | 处理 | 最新可用数据选择 | 当当天日报缺失时，选择不晚于发送日期的最新日报，是邮件推送环节的具体降级方式。 |
| 最新可用数据选择 | 依赖 | 数据血缘 | 邮件主题必须区分发送日期和日报日期，避免把旧日报误标为当天内容。 |
| 发布前置同步 | 服务于 | 静态站点发布契约 | 本地生成日报和 manifest 后，需要推送到远端，GitHub Pages 才能按静态站点契约展示最新内容。 |
| 防护式自动化 | 约束 | 发布前置同步 | 自动 git push 只有在分支、网络、认证和 ahead/behind 状态安全时才执行，避免把同步动作变成风险源。 |
| 状态校验 | 支撑 | 防护式自动化 | 分支检查、远端可读性和 ahead/behind 比较为自动化决策提供明确状态依据。 |
| 静态站点发布契约 | 依赖 | `manifest.json` 索引 | 日报 HTML 只有进入 manifest，首页和归档才能稳定发现它。 |

## 后续知识讲解建议

建议后续知识讲解重点围绕“如何把 LLM 纳入可靠的软件流水线”展开，可依次讲解：

1. 为什么 LLM 生成任务需要配置驱动，而不是把模型参数写死在 prompt 或脚本里。
2. 为什么结构化输出契约和输出校验是 LLM 工程化的关键。
3. 为什么自动化系统要把输入缺失、旧数据降级和发布前同步视为正常状态，而不是异常边角料。
4. 为什么邮件文案的随机风格必须服从事实边界，不能为了亲切感牺牲可追溯性。
5. 为什么自动 git push 需要 ahead/behind、分支和远端状态校验，才能成为可靠的发布前置环节。
