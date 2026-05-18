# 2026-05-17 ResearchPaperBase_codex 工作总结

本总结基于 `ResearchPaperBase_codex` 仓库在 2026-05-16 的 Git 提交记录生成。统计窗口为 `2026-05-16 00:00:00 +0800` 至 `2026-05-17 00:00:00 +0800`。

## 提交概览

| 项目 | 内容 |
| --- | --- |
| 仓库 | `ResearchPaperBase_codex` |
| 日期 | 2026-05-17 |
| 统计窗口 | 2026-05-16 00:00 至 2026-05-16 23:59 |
| 提交数量 | 1 |
| 涉及范围 | 设计文档总览与分层架构说明 |
| 核心主题 | 将旧索引文档替换为当前分层设计总览 |

- `ded4568`（2026-05-16 23:00）：`docs: update layers design`，删除旧的 `docs/design/00_index.md`，新增 `docs/design/00_layers.md`，把文档入口从“旧设计文件索引与现状盘点”调整为“Research Paper Base 分层设计总览”。

## 关键文件变更

| 文件 | 变化 | 说明 |
| --- | --- | --- |
| `docs/design/00_index.md` | 删除 | 移除旧的索引式总览文档，不再在该文件中维护旧设计文件索引、权威性声明和实现状态流水账。 |
| `docs/design/00_layers.md` | 新增 | 新增 274 行分层设计总览，确立五个核心层和四个横切约束，并给出 FR 闭环、能力族落位和 MVP 实施顺序。 |

本次提交新增 274 行、删除 470 行。变化性质更接近设计总览重写，而不是局部补丁。

## 主要工作主题

### 从文档索引转向架构基线

旧 `00_index.md` 的重点是设计文件索引、权威性说明和现状盘点；新 `00_layers.md` 则明确当前阶段的最小必要架构。文档角色发生了变化：它不再只是“告诉读者有哪些文件”，而是“告诉实现者系统应该按什么层次组织”。

### 五层共层方案收敛

新文档采用轻量但边界明确的五层结构：

- `UI / Workspace`
- `Application Use Cases`
- `Domain Core`
- `Agent & Knowledge Services`
- `Infrastructure Adapters`

其中 Agent 与 Knowledge 采用共层方案：二者同属服务层，但内部保持依赖方向，Agent 可以使用 Knowledge，Knowledge 不应依赖具体 Construction、Research 或 Review 流程。这是在项目体量、抽象边界和未来可拆分性之间做的折中。

### 横切约束被提升为所有层都要遵守的治理规则

文档把 `AuthZ`、`State & Locks`、`Runtime Config Snapshot`、`Content & Version Protection` 作为横切约束，而不是额外页面备注。这意味着权限、状态锁、运行时配置快照、人工内容保护和知识版本绑定都需要进入用例、领域规则、存储状态、测试和 UI 禁用原因。

### P0/P1 能力必须形成可追踪闭环

新文档要求每个 P0/P1 功能至少能追踪到 UI 入口、Application Command / Query、Domain 或 Agent 规则、Knowledge / Data Persistence、Permission / State / Lock Check、Diagnostics / Audit Hook 和 QA Case。这个闭环把需求、架构、实现和测试接在一起，降低“文档讲得清楚但实现无入口”或“功能做了但不可验证”的风险。

### 后续设计重写顺序变得更明确

文档给出后续修订顺序：领域模型、状态流程、数据与知识资产、API 契约、UI / Workspace、权限安全质量可观测和运维设计。MVP 实施顺序也从身份配置、Project、Workspace Shell、Construction Run、Research Session、Review Run，逐步推进到自动调度、邮件推送、导出和审计增强。

## 可能涉及的知识点线索

- 分层架构设计：用五层结构划分 UI、应用编排、领域核心、智能服务和基础设施适配。
- 横切关注点：权限、状态锁、配置快照、内容保护不是单层职责，而是贯穿用例和测试的系统约束。
- 应用编排层：把用户意图转化为可校验、可审计、可恢复的业务操作。
- 领域模型边界：Project、Construction Workspace、Run / Session、Knowledge Version、Content Protection 等对象应独立于数据库和外部 SDK。
- Agent 与 Knowledge 共层：在当前体量下减少目录和接口开销，同时保留未来拆分路径。
- 可追踪需求闭环：从 FR 到 UI、用例、领域规则、数据持久化、权限状态检查、诊断审计和 QA Case 的链路。
- 架构文档演进：从索引型文档迁移到基线型文档，本质是把“文档清单”升级为“实现约束”。

## 对后续概念提炼任务有帮助的备注

- 这次提交最适合提炼的主题是“分层架构”和“横切约束”，其次是“应用编排层”“共层设计”和“可追踪设计闭环”。
- 可以与 `DailyLearningAssistant` 当日的发布闭环类比：一个系统要长期演进，需要稳定入口、明确层次和可追踪索引；在学习日报中是 manifest 与 prework，在 Research Paper Base 中是分层总览与 FR 闭环。
- 数据来源：提交 `ded45685d091e450535aa3003f9f2ca7c587b227` 的提交信息、文件统计，以及新增的 `docs/design/00_layers.md` 内容。
