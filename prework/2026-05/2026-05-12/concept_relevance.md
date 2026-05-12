# 2026-05-12 概念与关联提炼

## 输入文件

- `work_summary_AInote.md`
- `work_summary_DailyLearningAssistant.md`
- `work_summary_interview_prepare.md`
- `work_summary_ResearchPaperBase_cc.md`
- `work_summary_ResearchPaperBase_codex.md`

## 当日核心主题总览

今天可确认的概念线索主要来自两个仓库：

1. `DailyLearningAssistant`：完成每日学习推送助手的静态站点与四阶段自动化流程初始化，核心主题是 Git 提交记录到学习日报发布之间的流水线工程化、manifest 索引、静态资源路径和多 Agent prompt 分工。
2. `interview_prepare`：把学习检查从“每日新增进度”升级为“全量完成质量审计”，并新增覆盖机器学习、算法、Python 基础、深度学习和模型压缩的知识总结页，核心主题是材料一致性校验、练习答案对齐、算法状态维护和考前知识压缩。

`AInote`、`ResearchPaperBase_cc`、`ResearchPaperBase_codex` 在统计窗口内没有可确认提交，因此只作为“无新增概念线索”的输入记录，不额外扩展概念。

## 概念清单

### 数学

- 距离度量与邻域
  - 来源：`interview_prepare`
  - 说明：KNN、KMeans、DBSCAN 和 IOU 都依赖“距离、邻域、中心或重叠比例”来判断样本之间的关系。

- 线性代数运算
  - 来源：`interview_prepare`
  - 说明：点积、矩阵乘法、矩阵转置、矩阵求逆和岭回归闭式解都需要把数据表示为向量或矩阵并进行代数计算。

- 损失函数与优化
  - 来源：`interview_prepare`
  - 说明：MSE、BCE、梯度下降、SGD 和 L2 正则共同描述模型如何衡量误差、更新参数以及控制复杂度。

- 概率输出与分类指标
  - 来源：`interview_prepare`
  - 说明：sigmoid 输出二分类概率，混淆矩阵和 F1 用于从预测结果中评估分类质量。

### 物理

- 未发现明确线索。

### 计算机科学

- 输入解析与状态维护
  - 来源：`interview_prepare`
  - 说明：机考题实现需要清楚识别输入维度、循环变量、中间状态和输出格式，避免代码只通过公开样例。

- 图遍历与密度扩展
  - 来源：`interview_prepare`
  - 说明：DBSCAN 的簇扩展过程可以类比为从核心点出发沿邻域关系进行 BFS 或 DFS。

- 动态规划
  - 来源：`interview_prepare`
  - 说明：`note/total_difficulty.md` 中“状态转移规划”的难点描述指向 DP；原文记录为 `DB`，这里仅按上下文作为 DP 线索处理。

- 树结构与剪枝
  - 来源：`interview_prepare`
  - 说明：决策树构建需要维护节点划分信息，剪枝需要根据条件控制树的规模和泛化能力。

- 文本向量化与相似度
  - 来源：`interview_prepare`
  - 说明：tokenize、TF、DF、IDF 和余弦相似度把文本转换为可计算的向量空间表示。

- 静态资源寻址
  - 来源：`DailyLearningAssistant`
  - 说明：GitHub Pages 上的 HTML、CSS、JS、JSON 和日报页面都依赖稳定的相对路径加载。

- manifest 索引模式
  - 来源：`DailyLearningAssistant`
  - 说明：`daily_report/manifest.json` 将日报列表从页面代码中抽离出来，成为静态站点的数据入口。

- 树形归档结构
  - 来源：`DailyLearningAssistant`
  - 说明：日报按年、月、日组织，归档导航本质上是从扁平条目构造层级结构。

- URL 查询参数状态
  - 来源：`DailyLearningAssistant`
  - 说明：`?archive=1` 和 `?date=...` 用 URL 记录页面模式与选中日期，使静态页面也能表达简单路由状态。

### 软件工程

- 多阶段自动化流水线
  - 来源：`DailyLearningAssistant`
  - 说明：每日流程被拆为仓库总结、概念关联、知识讲解、HTML 发布四个阶段，每个阶段都有明确输入和输出。

- 中间产物契约
  - 来源：`DailyLearningAssistant`
  - 说明：`work_summary_*.md`、`concept_relevance.md`、`knowledge_explaination.md` 是阶段之间传递信息的可复盘文件。

- 职责边界
  - 来源：`DailyLearningAssistant`
  - 说明：`prework`、`daily_report`、`prompt`、`style` 分别承载准备材料、发布产物、自动化提示词和前端资源，减少目录语义混杂。

- 自动化上下文隔离
  - 来源：`DailyLearningAssistant`
  - 说明：不同 Agent 扮演不同角色并拥有独立上下文，有助于降低跨阶段干扰。

- 自动化检查报告
  - 来源：`interview_prepare`
  - 说明：`checklog/index.html` 用静态 HTML 展示扫描结果、结构质量、测试统计和学习风险。

- 材料一致性校验
  - 来源：`interview_prepare`
  - 说明：Markdown 源、notebook、索引和参考答案需要一一对应；数量一致不能替代结构一致。

- 测试口径设计
  - 来源：`interview_prepare`
  - 说明：报告区分“用户自带 EXPECT 通过”和“参考答案 EXPECTED 对齐”，体现测试标准会影响质量判断。

- 风险分级
  - 来源：`interview_prepare`
  - 说明：完成情况被拆成结构合格、参考答案通过、用户答案对齐、错位和未完成等层级，便于确定修复优先级。

### 大语言模型与深度学习

- Prompt 分工
  - 来源：`DailyLearningAssistant`
  - 说明：四个自动化 prompt 分别承担观察、提炼、讲解和发布职责，是多 Agent 工作流中的角色分配。

- 约束驱动生成
  - 来源：`DailyLearningAssistant`
  - 说明：prompt 明确“只基于当日文件”“不要编造”等边界，用工程约束降低生成幻觉风险。

- 上下文压缩与信息契约
  - 来源：`DailyLearningAssistant`
  - 说明：前一阶段把仓库变更压缩成结构化 Markdown，后一阶段可以基于中间文件继续处理，而不必重复读取全部提交细节。

- 注意力机制
  - 来源：`interview_prepare`
  - 说明：Q/K/V、缩放点积注意力、多头注意力和 mask 是把序列中不同位置的信息按相关性加权汇聚的机制。

- 混合专家模型
  - 来源：`interview_prepare`
  - 说明：MOE 通过 top-k expert 选择和门控，让不同专家网络处理不同输入模式。

- LSTM 状态更新
  - 来源：`interview_prepare`
  - 说明：LSTM 单步实现需要维护隐藏状态和细胞状态，适合考察序列模型中的状态传递。

- 模型量化与剪枝
  - 来源：`interview_prepare`
  - 说明：INT8、scale、zero-point、反量化、L1 和剪枝都服务于模型压缩与推理成本控制。

## 概念关联图谱

| 概念 A | 关系 | 概念 B | 说明 |
| --- | --- | --- | --- |
| 多阶段自动化流水线 | 组织 | Prompt 分工 | 每个 prompt 对应流水线中的一个独立 Agent 角色，使复杂任务可以分段完成。 |
| 多阶段自动化流水线 | 依赖 | 中间产物契约 | 后一阶段需要读取前一阶段生成的 Markdown 文件，稳定的文件契约是自动化接力的基础。 |
| 中间产物契约 | 支撑 | 上下文压缩与信息契约 | 仓库变更被压缩为总结文件后，后续 Agent 只需读取结构化摘要即可继续工作。 |
| 约束驱动生成 | 约束 | 上下文压缩与信息契约 | prompt 要求只基于当日 `work_summary_*.md`，避免后续阶段越界读取或补充无依据内容。 |
| 职责边界 | 配合 | 多阶段自动化流水线 | 目录边界与流程阶段对齐，让准备材料、发布页面和提示词各自承担清晰职责。 |
| manifest 索引模式 | 服务于 | 静态资源寻址 | 静态站点通过相对路径读取 manifest，再根据 manifest 定位日报 HTML 文件。 |
| 树形归档结构 | 派生自 | manifest 索引模式 | manifest 中的日期条目可以按年、月、日分组，生成归档导航。 |
| URL 查询参数状态 | 控制 | 树形归档结构 | `?archive=1` 决定是否进入归档模式，`?date=...` 可表示归档中的选中日报。 |
| 自动化检查报告 | 呈现 | 材料一致性校验 | 检查页把源文件、notebook、参考答案和用户答案的对应关系可视化为质量报告。 |
| 材料一致性校验 | 区分于 | 测试口径设计 | 一致性校验关注材料是否配套，测试口径关注“通过”的判定标准是否可靠。 |
| 测试口径设计 | 影响 | 风险分级 | 如果只看用户自带样例，风险会被低估；与参考答案对齐能暴露更真实的缺口。 |
| 输入解析与状态维护 | 共同支撑 | 动态规划 | DP 实现依赖正确解析输入，并维护状态数组、转移顺序和边界条件。 |
| 输入解析与状态维护 | 共同支撑 | 图遍历与密度扩展 | DBSCAN 扩展或 BFS/DFS 都要求维护访问状态、候选集合和扩展过程。 |
| 图遍历与密度扩展 | 类比 | 距离度量与邻域 | DBSCAN 先用距离定义邻域，再沿邻域关系扩展簇，数学邻域转化为图上的连通扩展。 |
| 树结构与剪枝 | 依赖 | 风险分级 | 决策树相关练习被标为高风险，原因是节点信息维护和剪枝条件容易出错。 |
| 文本向量化与相似度 | 依赖 | 线性代数运算 | TF-IDF 后的文本向量需要通过点积和范数计算余弦相似度。 |
| 损失函数与优化 | 依赖 | 线性代数运算 | 线性模型、岭回归和梯度更新都需要矩阵或向量形式的参数计算。 |
| 概率输出与分类指标 | 延伸 | 损失函数与优化 | sigmoid 和 BCE 用于训练二分类模型，混淆矩阵和 F1 用于评估分类结果。 |
| 注意力机制 | 依赖 | 线性代数运算 | Q/K/V 投影和缩放点积注意力都以矩阵乘法、点积和归一化为核心。 |
| 混合专家模型 | 相关 | 注意力机制 | 两者都通过权重或门控选择信息路径，但注意力选择 token 间信息，MOE 选择专家网络。 |
| LSTM 状态更新 | 类比 | 输入解析与状态维护 | LSTM 的隐藏状态和细胞状态维护，与算法题中的循环状态维护有相似的实现要求。 |
| 模型量化与剪枝 | 共同服务于 | 风险分级 | 量化剪枝是知识总结中的重点模块，若实现 scale、zero-point 或剪枝规则错误，会成为练习风险。 |

## 后续知识讲解建议

1. 优先讲解“从 Git 提交到学习日报的多 Agent 自动化流水线”，把 prompt 分工、中间产物契约、manifest 索引和静态站点发布串成一条完整链路。
2. 重点讲解“材料一致性校验为什么比数量统计更重要”，结合 Markdown 源、notebook、参考答案和用户答案的对应关系说明质量审计思路。
3. 对 `interview_prepare` 中的算法与数学概念做分组讲解：距离与聚类、线性代数与损失优化、图遍历与 DP、树结构与剪枝、文本向量化。
4. 单独讲解深度学习实现中的状态与路由：注意力的 Q/K/V 信息路由、MOE 的专家路由、LSTM 的序列状态维护、量化剪枝的压缩思路。
5. 物理方向今天没有明确材料支撑，后续知识讲解不应强行加入物理概念。
