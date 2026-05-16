# 2026-05-16 概念与关联提炼

## 输入文件

- `work_summary_AInote.md`
- `work_summary_DailyLearningAssistant.md`
- `work_summary_interview_prepare.md`
- `work_summary_ResearchPaperBase_cc.md`
- `work_summary_ResearchPaperBase_codex.md`

## 当日核心主题总览

今天的新增材料主要来自两个仓库：

1. `DailyLearningAssistant` 完成 2026-05-15 学习日报发布，并新增邮件推送配置、SMTP 发送脚本和 macOS launchd 安装脚本，使学习日报从静态页面发布进一步走向定时主动触达。
2. `ResearchPaperBase_codex` 重整功能需求编号，把 `FR-WORKSPACE-*` 纳入统一 `FR-*` 序列，并新增旧新编号映射表、同步修正交叉引用，降低需求文档演进中的引用风险。

`AInote`、`interview_prepare` 和 `ResearchPaperBase_cc` 在统计窗口内无提交，因此不从这些仓库提炼新增概念。

## 概念清单

### 数学

- 未发现明确线索。

### 物理

- 未发现明确线索。

### 计算机科学

- 结构化索引
  - 来源：`DailyLearningAssistant`, `ResearchPaperBase_codex`
  - 说明：`daily_report/manifest.json` 用日期和路径索引学习日报，FR 编号体系用稳定编号索引功能需求；二者都把散落内容转成可查找、可引用的结构化入口。

- 双格式内容表示
  - 来源：`DailyLearningAssistant`
  - 说明：邮件脚本同时生成 HTML 与纯文本邮件，让同一份日报通知适配不同邮件客户端和降级显示场景。

- 定时任务调度
  - 来源：`DailyLearningAssistant`
  - 说明：launchd 通过 plist、`StartCalendarInterval`、工作目录和日志路径描述本地定时执行环境，使脚本可以在指定时间自动运行。

- 配置驱动程序行为
  - 来源：`DailyLearningAssistant`
  - 说明：SMTP、收件人、发送时间、LLM API 和站点 base URL 都由配置文件控制，使发送脚本和 launchd 安装脚本不需要把环境参数写死在代码中。

### 软件工程

- 自动化发布闭环
  - 来源：`DailyLearningAssistant`
  - 说明：日报 HTML、manifest、知识日志、邮件脚本和定时任务共同构成从内容生成、索引发布到主动通知的闭环。

- Manifest 发布契约
  - 来源：`DailyLearningAssistant`
  - 说明：新日报必须写入 `daily_report/manifest.json`，才能被主页、归档和邮件脚本稳定发现。

- 邮件自动化与 SMTP 推送
  - 来源：`DailyLearningAssistant`
  - 说明：发送脚本负责读取配置、定位目标日期报告、生成 HTML/Plain 双格式内容，并通过 SMTP 完成邮件投递。

- 本地运维脚本
  - 来源：`DailyLearningAssistant`
  - 说明：`setup_launchd.sh` 提供安装、卸载和状态查看能力，把一次性脚本执行包装成本机可维护的运行机制。

- 优雅降级
  - 来源：`DailyLearningAssistant`
  - 说明：LLM 个性化问候生成失败时回退固定文案，使非核心增强能力不会阻断日报发送主流程。

- 配置样例与密钥隔离
  - 来源：`DailyLearningAssistant`
  - 说明：`config.example.json` 公开配置结构，真实 `config.json` 保留在本地，降低 SMTP 密码、LLM API Key 等敏感信息泄露风险。

- 需求编号体系设计
  - 来源：`ResearchPaperBase_codex`
  - 说明：FR 编号不仅是文档标签，还承担引用、排期、审查、测试追踪和跨文档同步的索引职责。

- 迁移映射表
  - 来源：`ResearchPaperBase_codex`
  - 说明：重编号时保留旧编号到新编号的映射，便于后续修复架构、状态机、数据需求和 UI 文档中的引用。

- 交叉引用一致性
  - 来源：`ResearchPaperBase_codex`
  - 说明：需求之间的引用必须随编号变化同步更新，否则实现、审查和测试可能追踪到错误目标。

- 需求分层与统一索引
  - 来源：`ResearchPaperBase_codex`
  - 说明：Workspace 能力既是一个模块，又被纳入全局 FR 序列，便于和构建、深度研究、主题综述等流程共同排布。

- 审查驱动文档演进
  - 来源：`ResearchPaperBase_codex`
  - 说明：功能需求文档从补充功能点转向逐条审查，重点检查需求闭环、最小必要性、验收标准和测试覆盖。

- 重构风险控制
  - 来源：`ResearchPaperBase_codex`
  - 说明：编号重整属于文档结构重构，映射表和引用同步是降低迁移风险的核心措施。

### 大语言模型

- LLM 增强通知文案
  - 来源：`DailyLearningAssistant`
  - 说明：邮件脚本可调用 LLM API 生成每日问候和点评，让自动通知具有个性化表达。

- AI 增强但不阻塞主流程
  - 来源：`DailyLearningAssistant`
  - 说明：LLM 只负责可替换的通知文案增强，失败时不影响日报链接定位、邮件构造和 SMTP 发送。

- 未发现新的模型架构线索
  - 来源：`AInote`, `interview_prepare`, `ResearchPaperBase_cc`, `ResearchPaperBase_codex`
  - 说明：当日材料没有新增 Transformer、Attention、Embedding 或训练推理机制方面的提交。

## 概念关联

| 概念 A | 关系 | 概念 B | 说明 |
| --- | --- | --- | --- |
| 自动化发布闭环 | 依赖 | Manifest 发布契约 | 日报只有进入 manifest，后续主页发现、归档展示和邮件链接定位才有稳定入口。 |
| Manifest 发布契约 | 属于 | 结构化索引 | manifest 用结构化记录管理日报入口，是面向静态站点发布的索引机制。 |
| 需求编号体系设计 | 属于 | 结构化索引 | FR 编号把需求组织成可引用、可追踪的索引系统，作用类似日报 manifest 对页面的组织。 |
| 需求编号体系设计 | 支撑 | 交叉引用一致性 | 只有编号稳定且统一，需求之间的依赖和引用才能被可靠追踪。 |
| 迁移映射表 | 降低风险 | 重构风险控制 | 重编号会破坏旧引用，映射表为后续迁移和审查提供可查依据。 |
| 迁移映射表 | 服务于 | 交叉引用一致性 | 旧新编号关系清晰后，其他文档才能逐项修正到新的 FR 编号。 |
| 需求分层与统一索引 | 延伸 | 需求编号体系设计 | Workspace 需求从独立前缀并入统一序列，体现模块分层和全局排期索引之间的协调。 |
| 审查驱动文档演进 | 强化 | 交叉引用一致性 | 逐条审查能发现编号、引用、验收标准和测试覆盖之间的不一致。 |
| 邮件自动化与 SMTP 推送 | 实现 | 自动化发布闭环 | SMTP 发送把日报从“被动访问的页面”推进为“主动触达的学习提醒”。 |
| 定时任务调度 | 触发 | 邮件自动化与 SMTP 推送 | launchd 在指定时间启动发送脚本，使邮件推送无需人工手动执行。 |
| 本地运维脚本 | 管理 | 定时任务调度 | 安装、卸载和状态查看脚本把 launchd 配置变成可维护的本地运维流程。 |
| 配置驱动程序行为 | 支撑 | 本地运维脚本 | 定时任务安装脚本从配置读取发送时间，避免脚本逻辑和本机运行参数耦合。 |
| 配置样例与密钥隔离 | 约束 | 配置驱动程序行为 | 配置驱动需要清晰模板，同时真实密钥必须留在本地而不是进入仓库。 |
| 双格式内容表示 | 提升兼容性 | 邮件自动化与 SMTP 推送 | HTML 和纯文本两种表示让邮件在不同客户端中都能被阅读。 |
| LLM 增强通知文案 | 增强 | 邮件自动化与 SMTP 推送 | LLM 生成问候和点评可以改善通知体验，但不改变邮件发送的核心路径。 |
| 优雅降级 | 保障 | AI 增强但不阻塞主流程 | 当 LLM 调用失败时，固定文案回退保证主流程继续完成。 |
| 自动化发布闭环 | 类比 | 需求编号体系设计 | 前者管理学习报告如何被发现和触达，后者管理需求如何被引用和追踪，本质上都在为复杂系统建立稳定入口。 |

## 后续知识讲解建议

1. 重点讲解“结构化索引为什么是自动化系统的骨架”，对比日报 manifest 与 FR 编号体系。
2. 讲解“从静态页面到主动推送的自动化闭环”，串联 HTML 报告、manifest、配置、SMTP 和 launchd。
3. 讲解“配置驱动与密钥隔离”，说明为什么可复用脚本需要配置样例，而真实密钥不应提交。
4. 讲解“优雅降级”，用 LLM 文案失败回退固定文案作为例子，解释增强能力与主流程可靠性的关系。
5. 讲解“需求重编号的风险控制”，围绕迁移映射表、交叉引用一致性和审查驱动文档演进展开。
