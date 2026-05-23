# 2026-05-23 ResearchPaperBase_codex 工作总结

本总结基于 `ResearchPaperBase_codex` 仓库在目标日期前一天的 Git 提交记录生成。统计窗口为 `2026-05-22 00:00:00 +0800` 至 `2026-05-23 00:00:00 +0800`。

## 提交概览

| 项目 | 内容 |
| --- | --- |
| 仓库 | `ResearchPaperBase_codex` |
| 日期 | 2026-05-23 |
| 统计窗口 | 2026-05-22 00:00 至 2026-05-22 23:59（Asia/Shanghai） |
| 提交数量 | 2 |
| 涉及范围 | 第一次提交重排 22 个设计文件，2751 行新增、2335 行删除；第二次提交修改 4 个文件，99 行新增、19 行删除 |
| 核心主题 | 将 Research Paper Base 设计文档按分层架构重组，并补强 Project 权限模型 |

- `1db6888`（10:00）：`docs: align layered design domain docs`，围绕分层设计重写和拆分设计文档，新增 Domain Core、API Contracts、Application Use Cases、Agent & Knowledge Services、Data Persistence 和 SQL schema 等文件。
- `e9ddd24`（17:21）：`Update design docs with Project permission model`，新增设计文件映射表，并在 FR、分层总览和 Domain Core 中明确 Project 权限模型。

## 一、前一天新变化与收益

5 月 22 日的两次提交连成一条主线：先把旧的设计文档集从“文件堆叠和历史大表”重排成按架构层分工的设计体系，再把 Project 作为长期研究容器时必须具备的权限边界补进 FR 和领域模型。这让 Research Paper Base 从需求文档逐步走向可实现的架构契约。

### 分层设计文档成型

`1db6888` 大幅调整 `docs/design/`：旧的 `03_architecture_decisions.md`、`05_state_workflow.md`、`11_design_audit.md`、`12_gap_decisions.md` 被删除或迁移；新的 `02_domain_core.md`、`04_api_contracts.md`、`05_application_use_cases.md`、`06_agent_knowledge_services.md`、`07_data_persistence.md`、`07_data_schema.sql` 等文件承担更清晰的职责。

这次重构把系统拆为 `UI / Workspace -> API Boundary / Contracts -> Application Use Cases -> Domain Core -> Agent & Knowledge Services -> Infrastructure Adapters`，并把 AuthZ、State & Locks、Runtime Config Snapshot、Content & Version Protection 作为横切约束。

### Domain Core 开始承接不可绕过的业务规则

新增的 `02_domain_core.md` 不再只是罗列实体，而是定义用户、配置、Project、ConstructionWorkspace、Run/Session、PaperIdentity、ProjectPaper、KnowledgeVersion、内容保护、锁与互斥等核心对象和不变量。它明确：Domain Core 只回答“业务世界如何成立”，不定义 UI、API、数据库字段或 Provider SDK 细节。

### Project 权限模型补齐

`e9ddd24` 在 FR 和 Domain Core 中加入 `ProjectPermission`：权限分为 `access`、`use`、`delete`。Owner 在账号有效时必须始终拥有自己 Project 的全部权限；跨用户访问和使用授权被标记为 P2 预留能力；P0 阶段未实现共享协作授权时，非 Owner 用户不得访问或使用他人 Project。

这个模型把“进入 Workspace”“触发 Agent Run/Session”“软删除或清理私人资产”拆成不同权限层级，为后续 API 鉴权、UI 禁用态、应用用例检查和审计日志提供稳定依据。

## 二、提交详情

### `1db6888`：按分层架构重组设计文档

第一笔提交是一次结构性文档迁移。`docs/design/README.md` 被改写为新版设计文档入口，明确 `01_functional_requirements.md` 和 `00_layers.md` 是权威基线，其余文件是按层展开的设计说明。旧的大接口清单、质量控制和数据模型被移入 `backup/` 作为参考，不再作为权威契约。

核心新增文件包括：

- `01-01-FR-reference.md`：承接 FR 参考与追溯。
- `02_domain_core.md`：定义核心领域对象、状态、生命周期、不变量和领域事件。
- `04_api_contracts.md`：定义 HTTP/SSE/API 错误信封、资源命名、鉴权入口和文件访问边界。
- `05_application_use_cases.md`：定义命令/查询、状态推进、任务提交、锁、幂等和失败诊断。
- `06_agent_knowledge_services.md`：定义 Construction、Research、Review、Graph-RAG、Knowledge Version、引用证据等服务能力。
- `07_data_persistence.md` 和 `07_data_schema.sql`：定义关系库、文件、向量、图谱、同步状态和 MVP SQL schema。
- `12_gap_decisions_review.md`：保留旧缺口决策的迁移审核结果。

从设计收益看，这次提交降低了旧文档互相覆盖的风险：FR 管需求含义，Domain Core 管业务事实，API 管边界协议，Application Use Cases 管编排，Agent & Knowledge 管智能服务，Data Persistence 管存储。

### `e9ddd24`：补强 Project 权限模型

第二笔提交新增 `00-00_layer_design_file_mapping.md`，把当前 `docs/design/` 下实际存在的设计文件与各层职责建立对应表，避免引用已删除或改名的旧文件。

更重要的是，它在 `01_functional_requirements.md` 与 `02_domain_core.md` 中明确 Project 权限：

- `access`：允许进入 Workspace 和查看 Project 资产。
- `use`：允许创建、启动、继续或操作 Run/Session，上传补充资料和触发生成。
- `delete`：允许软删除 Project、清理 Project 私人资产或执行等效高风险删除操作。

同时，Owner 默认拥有自己 Project 的全部权限，并且只要账号有效，这些权限不得被撤销、降级或被共享授权覆盖。P0 不实现共享协作授权时，系统应只保证 Owner 主流程可用，不把 P2 共享机制提前塞进 MVP。

## 三、关键文件变更

| 文件 | 变更 |
| --- | --- |
| `docs/design/00_layers.md` | 更新分层总览、依赖方向、横切约束，并增加对当前文件结构的映射。 |
| `docs/design/00-00_layer_design_file_mapping.md` | 新增层级到实际设计文件的对应表。 |
| `docs/design/01_functional_requirements.md` | 更新到 v1.39，补充 Project 权限、Project Workspace 和 Agent 实例化原则。 |
| `docs/design/02_domain_core.md` | 新增/更新核心领域模型，包含 ProjectPermission、Project 状态、不变量、Run/Session 生命周期与锁。 |
| `docs/design/03_ui_workspace.md` | 由旧信息架构文档重命名而来，承接 UI / Workspace 层职责。 |
| `docs/design/04_api_contracts.md` | 新增 API Boundary / Contracts 设计。 |
| `docs/design/05_application_use_cases.md` | 新增应用编排层设计。 |
| `docs/design/06_agent_knowledge_services.md` | 新增 Agent 与 Knowledge 服务层设计。 |
| `docs/design/07_data_persistence.md`、`docs/design/07_data_schema.sql` | 新增持久化设计和 SQL schema 草案。 |
| `docs/design/backup/*` | 保留旧数据模型、数据需求、API 契约和质量文档作为参考。 |

## 四、相关架构设计知识点

### 1. 分层架构不是目录整理，而是责任裁剪

本次重构的关键不是把文件名换漂亮，而是把“需求、领域、接口、用例、智能服务、持久化”各自能决定什么、不能决定什么讲清楚。这样后续实现 API 或数据库时，不会让表结构反向定义业务规则。

### 2. Domain Core 应表达不变量

`02_domain_core.md` 中大量“不得”“必须”不是文档语气，而是业务约束。比如用户密钥不得明文暴露、同一 Project 只能有一个 active ConstructionRun 写知识库、Workspace 上下文恢复不得触发重跑等，都应成为后续代码和测试的核心边界。

### 3. API Boundary 不承载业务规则

`04_api_contracts.md` 的定位是把 UI 操作稳定映射为命令/查询，统一错误信封、鉴权入口和 SSE 协议。真正的 Project 状态机、内容保护、配置解析、锁获取、Agent 调用和数据写入规则应落在 Application Use Cases 与 Domain Core 中。

### 4. Project 权限需要按操作能力拆分

单一“是否有权限”不足以支撑 Project Workspace。进入 Workspace、使用 Agent、删除或清理资产的风险等级不同，因此拆成 `access`、`use`、`delete` 更利于 UI 禁用态、API 鉴权和审计日志。

### 5. Owner 默认权限是系统不变量

Owner 对自己 Project 的默认全权限不能被共享授权覆盖，这是权限模型里的安全底线。否则后续 P2 协作能力可能反过来破坏 P0 的单用户主流程。

### 6. 备份旧设计有助于迁移，但不能继续作为权威

旧文档被迁到 `backup/` 后仍可查证历史语义，但 README 明确它们不再作为权威契约。这种做法降低了“一边迁移一边丢知识”的风险，也避免旧文档继续和新分层设计抢裁决权。

## 五、对后续概念提炼任务有帮助的备注

本仓库当天最值得提炼的概念包括：分层架构、Domain Core、API Boundary、Application Use Cases、Agent & Knowledge Services、横切约束、权限模型、Owner 不变量、Project Workspace、Run/Session 生命周期、锁与互斥、知识库版本绑定、内容保护。它们之间的主线是“用分层边界把 AI Agent 论文系统从需求文档推进到可实现架构”。

数据来源：`git show --stat --name-status 1db6888 e9ddd24`，以及提交中 `README.md`、`00_layers.md`、`00-00_layer_design_file_mapping.md`、`01_functional_requirements.md`、`02_domain_core.md` 的内容。
