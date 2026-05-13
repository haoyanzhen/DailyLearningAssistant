# 2026-05-13 概念与关联提炼

## 输入文件

- `work_summary_AInote.md`
- `work_summary_DailyLearningAssistant.md`
- `work_summary_ResearchPaperBase_cc.md`
- `work_summary_ResearchPaperBase_codex.md`
- `work_summary_interview_prepare.md`

## 当日核心主题总览

今天的有效变更主要围绕三条主线展开：

1. **AI 辅助开发从提示式生成转向契约式协作。** `AInote` 强调 Product Brief、Architecture Note、Data Model、API Contract、Vertical Slice 与人工审核边界，目标是让 AI 生成代码受清晰系统契约约束。
2. **学习日报系统从单页发布扩展为可追踪学习资产流水线。** `DailyLearningAssistant` 将日报、prework 中间产物、教学记录、manifest 导航、公共样式和简读/精读模式纳入同一套静态站点发布链路。
3. **复杂 AI 论文管理系统的需求边界、安全验收和运行态约束被进一步压实。** `ResearchPaperBase_codex` 通过 FR 审计、P0/P1/P2 分层、并发锁、安全回退、PDF 元数据流程和容量估算，让 MVP 范围与工程风险更可控。

`ResearchPaperBase_cc` 与 `interview_prepare` 在统计窗口内没有新增提交，因此只作为无新增变更的输入证据，不从中提炼新增概念。

## 概念清单

### 数学

- 容量估算
  - 来源：`ResearchPaperBase_codex`
  - 说明：以用户数、Project 数、论文数和 PDF 平均大小估算存储与资源需求，是把运维部署从模糊描述转化为数量级约束的方法。

- 优先级分层
  - 来源：`ResearchPaperBase_codex`、`AInote`
  - 说明：P0/P1/P2、风险分级和 7 天最小开发节奏都体现了对任务集合按价值、风险和时间成本排序的思想。

### 物理

- 未发现明确线索。

### 计算机科学

- API 契约
  - 来源：`AInote`
  - 说明：API 不只是接口地址列表，而是前后端协作、数据形状、权限边界和业务逻辑保护的系统边界。

- 数据模型与 Schema 分层
  - 来源：`AInote`
  - 说明：ViewModel、JSON schema、数据库 schema 分别服务于展示、接口交换和持久化，不能混入同一层需求描述。

- 状态机
  - 来源：`AInote`、`ResearchPaperBase_codex`
  - 说明：AI Agent 状态机、Run 状态、取消、暂停、恢复、重试和只读状态都需要显式状态与迁移规则，避免运行态行为含混。

- 并发锁
  - 来源：`ResearchPaperBase_codex`
  - 说明：自动构建调度需要 Project 级锁或等效机制，避免同一 Project 被重复创建 active Run。

- 鉴权与签名 URL
  - 来源：`ResearchPaperBase_codex`
  - 说明：远程 PDF 访问必须通过鉴权或签名 URL 控制访问范围，防止静态或远程文件暴露。

- 元数据抽取与补全
  - 来源：`ResearchPaperBase_codex`
  - 说明：PDF-only 上传通过本地 PDF 解析、外部数据源补全、LLM 草稿抽取和人工确认构成逐层增强的数据获取流程。

- Manifest 驱动导航
  - 来源：`DailyLearningAssistant`
  - 说明：静态站点通过 `manifest.json` 管理日报、教学记录和默认展示顺序，将导航状态外置为可维护数据。

### 软件工程

- 契约式开发
  - 来源：`AInote`、`DailyLearningAssistant`
  - 说明：通过产品说明、架构说明、API 契约、中间产物路径和 prompt 输入输出约束协作过程，减少实现随意性。

- 垂直切片开发
  - 来源：`AInote`
  - 说明：围绕一条完整功能链推进，从 UI、API、数据到测试形成可运行、可审核的小闭环。

- 功能需求边界
  - 来源：`AInote`、`ResearchPaperBase_codex`
  - 说明：FR 应描述用户可见能力、业务规则、权限边界、失败路径和不可做事项，不应提前绑定字段名、表结构或 ViewModel。

- MVP 范围控制
  - 来源：`ResearchPaperBase_codex`
  - 说明：将上下文恢复、工作台复制、重跑、归档、删除、版本历史等能力拆分为 P0 基础能力与 P1/P2 增强，降低首版复杂度。

- 验收标准设计
  - 来源：`ResearchPaperBase_codex`
  - 说明：禁用账号会话失效、管理员并发保护、密钥脱敏、失效配置不得静默回落等规则被写入验收条件，使需求可以被测试。

- 内容修改保护
  - 来源：`ResearchPaperBase_codex`
  - 说明：跨 Agent 的内容修改保护用于防止系统或 Agent 静默覆盖人工内容，是人机协作系统的重要安全基座。

- 多阶段自动化流水线
  - 来源：`DailyLearningAssistant`
  - 说明：从工作总结、概念关联、知识讲解到日报发布，各阶段以文件产物衔接，形成可复盘的日常自动化链路。

- 中间产物契约
  - 来源：`DailyLearningAssistant`
  - 说明：`prework` 中的工作总结、概念关联和知识讲解作为流水线输入输出，使下游任务能稳定读取上游结果。

- 公共设计系统
  - 来源：`DailyLearningAssistant`
  - 说明：日报页面从私有 CSS 转向复用根目录公共样式，有助于主页、归档、日报和教学记录保持一致视觉语言。

- 渐进披露
  - 来源：`DailyLearningAssistant`
  - 说明：简读/精读模式让同一篇日报同时支持快速回顾和深入学习，按用户注意力深度分层呈现内容。

### 大语言模型

- AI 决策边界
  - 来源：`AInote`
  - 说明：页面布局、React 组件、测试和文档可更多交给 AI；认证、权限、安全、Agent 状态机和数据库 schema 需要更高强度的人类审查。

- Prompt 职责边界
  - 来源：`DailyLearningAssistant`、`AInote`
  - 说明：不同自动化 prompt 明确输入、输出、日期口径和职责范围，降低多 Agent 流水线中的上下文污染和任务越界。

- LLM 草稿抽取
  - 来源：`ResearchPaperBase_codex`
  - 说明：当 PDF 元数据解析和外部数据源补全仍不完整时，LLM 可生成候选草稿，但最终仍需用户确认。

- 人机协作审核
  - 来源：`AInote`、`ResearchPaperBase_codex`
  - 说明：AI 生成或修改内容时，需要可审核 diff、验收条件、人工确认和覆盖保护来控制质量与安全风险。

## 概念关联图谱

```text
契约式开发
  -> 依赖 API 契约、数据模型与 Schema 分层、功能需求边界
  -> 支撑 AI 决策边界、人机协作审核、垂直切片开发

多阶段自动化流水线
  -> 依赖 中间产物契约、Prompt 职责边界、Manifest 驱动导航
  -> 延伸到 教学记录、公共设计系统、渐进披露

MVP 范围控制
  -> 依赖 优先级分层、验收标准设计、功能需求边界
  -> 降低 状态机、并发锁、内容修改保护 的实现风险

元数据抽取与补全
  -> 组合 PDF 解析、外部数据源、LLM 草稿抽取、人工确认
  -> 受 鉴权与签名 URL、验收标准设计 约束
```

## 概念关联表

| 概念 A | 关系 | 概念 B | 说明 |
| --- | --- | --- | --- |
| 契约式开发 | 依赖 | API 契约 | AI 协作开发需要先固定接口职责、数据形状和业务边界，否则生成结果容易把前后端、数据和 UI 混在一起。 |
| 功能需求边界 | 区分 | 数据模型与 Schema 分层 | FR 描述用户可见能力和规则，字段名、JSON schema、表结构、索引与约束应进入 API 或数据契约层。 |
| 垂直切片开发 | 验证 | 契约式开发 | 一条完整功能链可以同时检验产品说明、API、数据、UI 和测试是否互相闭合。 |
| AI 决策边界 | 约束 | 人机协作审核 | 高风险区域需要人工确认，低风险实现也应通过可审核 diff 和测试边界控制质量。 |
| Prompt 职责边界 | 组织 | 多阶段自动化流水线 | 四段自动化 prompt 分别负责总结、提炼、讲解和发布，清晰职责能减少重复工作和产物错位。 |
| 中间产物契约 | 衔接 | 多阶段自动化流水线 | `work_summary_*.md`、`concept_relevance.md` 和 `knowledge_explaination.md` 让每个阶段能稳定消费上游结果。 |
| Manifest 驱动导航 | 服务于 | 静态站点学习资产管理 | 日报和教学记录的归档、默认展示与入口状态由 manifest 管理，避免导航逻辑散落在页面内容中。 |
| 公共设计系统 | 支撑 | 渐进披露 | 简读/精读、课程卡片和知识讲解样式复用同一公共样式系统，保证不同阅读深度下视觉一致。 |
| MVP 范围控制 | 使用 | 优先级分层 | P0/P1/P2 把必需能力和增强能力分开，避免首版被复制、重跑、回退、差异等复杂功能拖厚。 |
| 验收标准设计 | 具体化 | 安全和权限边界 | 会话失效、管理员并发、密钥脱敏、PDF 鉴权等规则进入验收标准后，安全要求才能被测试。 |
| 并发锁 | 保护 | 状态机 | Project 级锁避免重复 active Run，状态机则定义 Run 在创建、取消、暂停、恢复和失败之间如何迁移。 |
| 内容修改保护 | 防止 | 人工内容被静默覆盖 | 跨 Agent 修改保护把用户确认与变更历史作为安全基座，适合多 Agent 论文管理系统。 |
| 元数据抽取与补全 | 组合 | LLM 草稿抽取 | PDF 解析和外部数据源补全优先，LLM 草稿用于补足仍缺失的信息，并需要人工确认。 |
| 容量估算 | 约束 | 运维部署设计 | 用户数、Project 数、论文数和 PDF 大小形成资源基线，帮助判断存储、清理策略和硬件配置是否够用。 |

## 后续知识讲解建议

建议优先讲解以下三个概念：

1. **契约式开发**：它能把 `AInote` 的 API 契约、FR 边界、数据分层和 AI 决策边界串起来，也能解释为什么 AI 协作需要先固定系统边界。
2. **多阶段自动化流水线**：它是 `DailyLearningAssistant` 的核心工程模式，适合讲清楚中间产物契约、prompt 职责边界、manifest 导航和学习资产沉淀。
3. **状态机与并发锁**：它来自 `ResearchPaperBase_codex` 的运行态风险审计，适合解释长任务系统为什么不能只靠“按钮触发”，而要显式管理状态迁移与并发保护。

数学方面可在讲解 `容量估算` 和 `优先级分层` 时轻量带入数量级估算和排序思想；物理方面今日未发现明确线索，不建议强行扩展。
