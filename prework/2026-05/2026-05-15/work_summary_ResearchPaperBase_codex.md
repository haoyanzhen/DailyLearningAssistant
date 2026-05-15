# 2026-05-15 ResearchPaperBase_codex 工作总结

本总结基于 `ResearchPaperBase_codex` 仓库在 2026-05-14 00:00 至 2026-05-15 00:00（Asia/Shanghai）的 Git 提交记录生成。

## 提交概览

| 项目 | 内容 |
| --- | --- |
| 仓库 | `ResearchPaperBase_codex` |
| 统计窗口 | 2026-05-14 00:00 至 2026-05-15 00:00 |
| 提交数量 | 1 次 |
| 涉及文件 | `docs/VibeCodingRecord/VibeCoding_record.md`、`docs/design/00_index.md`、`docs/design/01_functional_requirements.md`、`docs/design/06_data_requirements.md`、`docs/design/10_operations_deployment.md`、`docs/design/12_gap_decisions.md` |
| 核心主题 | FR 测试边界补全、PDF-only 元数据解析、Project 私人资产清理、文件生命周期 |

- `415aaa4`（20:50）：更新功能需求文档和相关设计文件，围绕 FR 审计结果补齐测试边界，并把 Project 私人资产清理、PDF-only 上传元数据解析和文件存储生命周期写得更明确。

## 关键文件变更

### `docs/VibeCodingRecord/VibeCoding_record.md`

追加了前一天的设计讨论记录。讨论重点包括：手动上传论文的元数据解析是否应拆成独立 LLM 调用函数、PDF-only 上传时为什么不能在没有 DOI/arXiv ID/标题/作者等查询锚点的情况下直接依赖外部 API、以及如何根据 FR 审计结果逐条更新需求文档。

### `docs/design/01_functional_requirements.md`

功能需求文档版本从 `v1.34` 更新到 `v1.36`，并大量补充验收边界和测试场景。可确认的新增重点包括：

- 禁用账号使用既有访问令牌访问受保护页面、业务数据或 API 时必须被拒绝。
- LLM 配置、论文数据源配置、邮件配置、管理员操作、系统级限制等 FR 增加更明确的失败分类和测试要求。
- Project 增加“私人资产清理”能力：可清理 Project 私有记录、历史 Run/Session、Project-Paper 关联、PDF、解析文本、向量索引、图谱文件和临时任务产物，但不得删除全局论文身份与基础元数据、其他 Project 引用或其他用户数据。
- PDF-only 上传流程被收紧：必须先从 PDF 本身提取候选元数据；只有得到 DOI、arXiv ID、可信标题或标题+作者等查询锚点后，才调用外部数据源补全；关键元数据仍缺失时，LLM 只能生成待确认的结构化草稿，不能直接视为用户确认结果。
- 多个 FR 补上测试清单，例如 Project 状态切换、私人资产清理、调度锁竞争、Workspace 恢复、取消/暂停/重试幂等、内容覆盖确认、Knowledge Version 发布条件、邮件推送部分失败、Graph-RAG 流式中断、综述章节互斥等。

### `docs/design/00_index.md`

索引文档同步调整数据模型层的删除语义：删除 Project 默认先进入软删除状态；用户可选择清理 Project 私人资产；全局 `papers` 不因某个 Project 移除关联或清理私人资产而被删除；导出产物默认不随 Project 私人资产清理删除。

### `docs/design/06_data_requirements.md`

数据需求文档同步强调 `papers` 表只存储可复用论文身份与基础元数据。PDF、解析文本、AI 分析等 Project 派生资产应按 Project 私有范围保存；`project_paper_relations` 属于 Project 私人资产，可随 Project 私人资产清理删除。

### `docs/design/10_operations_deployment.md`

运维部署文档更新容量上限与清理策略，将 PDF、解析文本、历史 Run/Session、Project-Paper 关联、任务临时产物、向量库 namespace/collection、图谱文件等归入 Project 私人资产清理范围。导出文件则被定义为用户主动生成的保留产物，默认不随 Project 私人资产清理删除。

### `docs/design/12_gap_decisions.md`

Gap decisions 中的文件存储和导出生命周期问题被进一步细化：文件与向量/图谱 namespace 应以 user/project 或等效 Project 私有边界组织，方便用户按 Project 清理私人资产；导出产物应使用独立目录、对象前缀或生命周期标记。

## 主要工作主题

### 从“需求描述”推进到“可测试需求”

这次提交最明显的推进是为大量 FR 补充验收和测试边界。文档开始从“系统应该支持某能力”转向“哪些异常、边界、权限、幂等和失败场景必须被覆盖”。

### PDF-only 上传流程被拆成确定性解析、外部补全和 LLM 草稿

设计明确了 PDF-only 上传不能盲目调用外部 API。系统应先从文件自身提取候选元数据，再在有查询锚点时使用外部数据源补全，最后才用 LLM 生成待确认草稿。这避免把 LLM 或外部 API 当成无条件可靠的元数据来源。

### Project 私人资产与全局论文身份分离

提交把全局 `papers` 和 Project 私有派生资产切开：论文身份与基础元数据可复用，PDF、解析文本、向量索引、图谱、Project-Paper 关联和运行历史则属于 Project 私人资产。这个区分直接影响删除、清理、权限、存储容量和导出生命周期。

### 运维容量与产品删除语义打通

清理策略不再只是运维层的“磁盘不够了怎么办”，而是和产品中的 Project 状态、私人资产清理、导出中心、Knowledge Version、向量库和图谱文件组织方式连起来。

## 可能涉及的知识点线索

- 需求工程中的验收标准与测试覆盖
- PDF 元数据解析、外部 API 补全与 LLM 结构化抽取
- 全局实体与租户/Project 私有资产分离
- 软删除、二次确认和影响范围预览
- 文件存储生命周期与导出生命周期
- 向量库 namespace、图谱文件和 Project 数据隔离
- 幂等操作、失败分类和边界测试

## 对后续概念提炼任务有帮助的备注

这次提交适合提炼“可测试需求”“Project 私人资产清理”“PDF-only 元数据解析流水线”“全局元数据与私有派生资产分离”。其中“可测试需求”与 `DailyLearningAssistant` 的“发布前置校验”存在强关联：二者都是把模糊的成功条件拆成可验证的边界。

数据来源：`git log --since="2026-05-14 00:00:00 +0800" --until="2026-05-15 00:00:00 +0800"`，以及提交 `415aaa4` 对 `docs/VibeCodingRecord/VibeCoding_record.md`、`docs/design/00_index.md`、`docs/design/01_functional_requirements.md`、`docs/design/06_data_requirements.md`、`docs/design/10_operations_deployment.md`、`docs/design/12_gap_decisions.md` 的修改。
