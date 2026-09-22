# 2026年9月教学记录

<table>
  <thead>
    <tr>
      <th>日期</th>
      <th>概念</th>
      <th>领域</th>
      <th>难度</th>
      <th>一句话解释</th>
      <th>下一次讲解参考</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td rowspan="3">
        <a href="../daily_report/2026-09/2026-09-23-learning-report.html">2026-09-23</a>
      </td>
      <td>角色资产包作为交付单元</td>
      <td>软件工程</td>
      <td>★★</td>
      <td>角色资产包作为交付单元，就是让一个角色的概念图、战斗素材、动画帧、UI、特效、配置和审查记录按固定目录组成一个完整交付物。</td>
      <td>下一次可以讲角色资产包契约 schema：用 JSON 定义每个角色必须包含哪些目录、文件、配置和审查状态，并让检查脚本输出 missing_file、missing_review、naming_violation 等结构化失败原因。</td>
    </tr>
    <tr>
      <td>本地引用名称与远端 ref 变化的证据边界</td>
      <td>计算机科学 / 软件工程</td>
      <td>★★★</td>
      <td>本地引用名称与远端 ref 变化的证据边界，就是把 origin/main 等引用名称指向某个 SHA 只当作指向关系证据，而不是远端 ref 在检查窗口内变化的证据。</td>
      <td>下一次可以讲 ref 证据分级报告字段：local_ref_points_to、remote_ref_current_sha、remote_ref_baseline_sha、remote_ref_change_status 和 push_evidence 如何组合，并避免把本地引用名写成远端变化。</td>
    </tr>
    <tr>
      <td>文档状态与资产交付同步</td>
      <td>软件工程</td>
      <td>★★★★</td>
      <td>文档状态与资产交付同步，就是让文档中的阶段完成状态、角色资产包提交和工具管线提交相互对齐，共同构成可追溯的阶段完成证据。</td>
      <td>下一次可以讲阶段完成状态机：pending_art、assets_submitted、tools_unified、docs_updated、review_passed 如何由提交、审查文件和文档状态共同驱动，并处理部分完成与审查未通过的情况。</td>
    </tr>
<tr>
      <td rowspan="3">
        <a href="../daily_report/2026-09/2026-09-22-learning-report.html">2026-09-22</a>
      </td>
      <td>Git commit 作为唯一变更事实源</td>
      <td>软件工程</td>
      <td>★★</td>
      <td>Git commit 作为唯一变更事实源，就是把已提交、可验证、可归属时间的 commit 当作系统结论的唯一硬证据。</td>
      <td>下一次可以讲 commit-only 报告的机器可读字段：window_commits、ref_pointer_status、workspace_clues、evidence_level 如何组合，并避免把 ref changed 直接写成 commit 详情。</td>
    </tr>
    <tr>
      <td>文件接口作为系统边界</td>
      <td>软件工程</td>
      <td>★★★</td>
      <td>文件接口作为系统边界，就是让提示词、脚本、文档和测试共同定义 Agent 能做什么、怎么做、为什么做和如何验证。</td>
      <td>下一次可以讲 Agent 文件接口的一致性检查：如何把 prompt 中的禁止项、脚本中的过滤逻辑和测试中的断言映射成同一张契约表。</td>
    </tr>
    <tr>
      <td>LLM 输出可靠性与证据约束</td>
      <td>大语言模型 / 软件工程</td>
      <td>★★★★</td>
      <td>LLM 输出可靠性与证据约束，就是让模型只在可确认证据范围内生成结论，并把弱证据明确标注为待确认。</td>
      <td>下一次可以讲 LLM 证据引用与拒绝回答机制：如何设计输出 schema，要求每条结论附带 evidence_type、evidence_id、confidence 和 forbidden_inference 检查。</td>
    </tr>
<tr>
      <td rowspan="3">
        <a href="../daily_report/2026-09/2026-09-21-learning-report.html">2026-09-21</a>
      </td>
      <td>成功读取与 unchanged 的证据条件</td>
      <td>计算机科学 / 软件工程</td>
      <td>★★</td>
      <td>成功读取与 unchanged 的证据条件，就是只有成功读到当前 SHA、有历史 SHA 可比、且两者相同，才能把状态写成 unchanged。</td>
      <td>下一次可以讲三值或四值状态字段：read_failed、baseline_missing、unchanged、changed 如何映射到退出码、重试策略和人工确认入口。</td>
    </tr>
    <tr>
      <td>Git worktree 与多工作区状态归属</td>
      <td>计算机科学 / 软件工程</td>
      <td>★★★</td>
      <td>Git worktree 与多工作区状态归属，就是把 Git 状态绑定到具体工作区、分支 tip 和当前差异，而不是只按仓库名判断变化。</td>
      <td>下一次可以讲多 worktree 报告字段：worktree_path、branch_tip、staged、unstaged、untracked、window_commits 如何组合成机器可读状态。</td>
    </tr>
    <tr>
      <td>资产合同检查与交付审查</td>
      <td>软件工程</td>
      <td>★★★★</td>
      <td>资产合同检查与交付审查，就是把角色资产约定变成可执行检查，并用检查结果和人工复核状态决定产物能否进入交付。</td>
      <td>下一次可以讲交付审查状态机：pending_check、check_failed、contract_violation、needs_review、approved 如何由检查输出、QA 报告和人工确认共同驱动。</td>
    </tr>
<tr>
      <td rowspan="3">
        <a href="../daily_report/2026-09/2026-09-20-learning-report.html">2026-09-20</a>
      </td>
      <td>角色资产目录结构作为产物接口边界</td>
      <td>计算机科学 / 软件工程</td>
      <td>★★</td>
      <td>角色资产目录结构作为产物接口边界，就是让不同阶段的角色产物按固定目录存放，使后续工具能按路径约定读取和检查。</td>
      <td>下一次可以讲目录契约如何变成机器可读规则：例如用 JSON schema 或配置表规定每个角色必须包含哪些目录和文件，并让检查脚本输出缺失项。</td>
    </tr>
    <tr>
      <td>资产契约检查与 QA 审计</td>
      <td>软件工程</td>
      <td>★★★</td>
      <td>资产契约检查与 QA 审计，就是把角色资产应满足的约定变成可执行检查，并把检查结果记录成可追溯的审计报告。</td>
      <td>下一次可以讲契约字段如何设计成机器可读 schema，并让检查脚本输出结构化失败原因，例如 missing_file、invalid_field、naming_violation。</td>
    </tr>
    <tr>
      <td>批量生成与后处理管线</td>
      <td>软件工程 / 计算机科学</td>
      <td>★★★★</td>
      <td>批量生成与后处理管线，就是把角色资产的计划、生成、后处理、审查和报告串成一条有明确输入输出和可追溯产物的处理链。</td>
      <td>下一次可以讲管线状态机：每个角色资产在批量流程中如何从 pending 到 running、success、failed、needs_review，以及如何用 batch report 和测试输出驱动状态迁移。</td>
    </tr>
<tr>
      <td rowspan="3">
        <a href="../daily_report/2026-09/2026-09-19-learning-report.html">2026-09-19</a>
      </td>
      <td>Git 远端引用与 SHA 指针</td>
      <td>计算机科学 / 软件工程</td>
      <td>★★</td>
      <td>Git 远端引用与 SHA 指针，就是用可改写的 ref 名字指向某个 SHA，从而让系统有一个可比较的仓库位置坐标。</td>
      <td>下一次可以讲从 ref 指针 unchanged 到触发对象查询的决策链：在什么证据等级下才 fetch 提交对象，以及如何在报告中区分指针变化、内容变化和未知。</td>
    </tr>
    <tr>
      <td>git ls-remote 元数据读取边界</td>
      <td>计算机科学 / 软件工程</td>
      <td>★★★</td>
      <td>git ls-remote 元数据读取边界，就是只读远端 ref 指向的 SHA，不下载对象，因此只能证明指针位置是否变化。</td>
      <td>下一次可以讲只读监控的升级读取策略：从 ref 指针变化到按需 fetch 提交对象或文件树，应满足哪些证据等级、权限边界和失败回退条件。</td>
    </tr>
    <tr>
      <td>已提交事实与待确认工作区线索的证据分层</td>
      <td>软件工程</td>
      <td>★★★★</td>
      <td>已提交事实与待确认工作区线索的证据分层，就是把窗口内提交、远端指针状态和当前工作区痕迹按可确认程度分开，不把草稿写成已完成。</td>
      <td>下一次可以讲证据升级流程：从工作区待确认线索到暂存、提交、远端 ref 变化，分别需要什么证据，以及如何在自动化报告中保留确认状态和人工复核入口。</td>
    </tr>
<tr>
      <td rowspan="3">
        <a href="../daily_report/2026-09/2026-09-18-learning-report.html">2026-09-18</a>
      </td>
      <td>提交窗口与时间归属</td>
      <td>软件工程</td>
      <td>★★</td>
      <td>提交窗口与时间归属，就是只有落在检查窗口内的提交才能作为已确认事实，工作区变更只能作为待确认线索。</td>
      <td>下一次可以讲提交窗口边界与报告字段：窗口内提交、窗口外提交、跨窗口提交、读取失败和工作区未提交如何映射到机器可读状态。</td>
    </tr>
    <tr>
      <td>远端 ref 指针一致性</td>
      <td>计算机科学 / 软件工程</td>
      <td>★★★</td>
      <td>远端 ref 指针一致性，就是多个 ref 当前指向同一个 SHA，只能证明指针位置一致，不能证明推送、同步或发布过程。</td>
      <td>下一次可以讲 ref 一致性证据与过程证据的分离：如何用推送日志、接收端 ref 更新时间和检查窗口共同确认一次推送，而不是只依赖本地与远端 SHA 相同。</td>
    </tr>
    <tr>
      <td>超时控制与调用可靠性</td>
      <td>软件工程</td>
      <td>★★★★</td>
      <td>超时控制与调用可靠性，就是给外部调用设置等待上限，让系统能在超时后停止等待并进入明确的失败处理路径。</td>
      <td>下一次可以讲 timeout 类型识别与测试策略：网络超时、任务超时、模型调用超时分别如何设计可测的失败边界，并避免把主题中的 timeout 直接误判为 LLM failover。</td>
    </tr>
<tr>
      <td rowspan="3">
        <a href="../daily_report/2026-09/2026-09-17-learning-report.html">2026-09-17</a>
      </td>
      <td>配置文档与代码行为同步</td>
      <td>软件工程</td>
      <td>★★</td>
      <td>配置文档与代码行为同步，就是把配置说明、代码读取和测试验证对齐，让配置项从写在纸上变成系统真的会照做。</td>
      <td>下一次可以讲配置契约的权威来源：当文档、代码默认值、校验脚本和测试不一致时，如何建立单一事实源，并自动检测配置漂移。</td>
    </tr>
    <tr>
      <td>Agent 工作流与任务编排</td>
      <td>软件工程 / 大语言模型</td>
      <td>★★★</td>
      <td>Agent 工作流与任务编排，就是把多个 LLM 任务放进统一调度层，让配置、失败处理和运行状态在多个任务路径之间保持一致。</td>
      <td>下一次可以讲 Agent 编排中的配置继承与例外：全局 LLM 配置如何被单个 agent 覆盖，以及覆盖规则如何被文档、校验和测试共同约束。</td>
    </tr>
    <tr>
      <td>LLM failover timeout 配置与生效路径</td>
      <td>大语言模型 / 软件工程</td>
      <td>★★★★</td>
      <td>LLM failover timeout 配置与生效路径，是让主模型失败后最多等多久再切换备用模型这一配置真正进入编排层、调用链和测试，而不是只停留在文档里。</td>
      <td>下一次可以讲 LLM failover 状态机：成功、可重试失败、不可重试失败、超时切换、全链失败分别如何记录，并与配置校验和回归测试配合。</td>
    </tr>
<tr>
      <td rowspan="3">
        <a href="../daily_report/2026-09/2026-09-16-learning-report.html">2026-09-16</a>
      </td>
      <td>读取失败不等于未变化</td>
      <td>计算机科学 / 软件工程</td>
      <td>★★</td>
      <td>读取失败只能说明这次没拿到当前 SHA，不能说明远端没有变化；只有成功读取并比较 SHA，才能得出 unchanged 或 changed。</td>
      <td>下一次可以讲三值状态如何映射到报告字段和退出码，并设计失败重试、未知保留和证据升级流程。</td>
    </tr>
    <tr>
      <td>首次观测基线与旧基线保留</td>
      <td>软件工程 / 计算机科学</td>
      <td>★★★</td>
      <td>首次观测只是建立参照点，不是变化事件；变化需要两个可比观测，失败时保留旧基线才能继续比较。</td>
      <td>下一次可以讲多 ref 基线与状态迁移：首次发现、正常更新、删除 ref、读取失败分别进入什么状态。</td>
    </tr>
    <tr>
      <td>只读远端监控的访问路径与凭据边界</td>
      <td>软件工程 / 安全</td>
      <td>★★★★</td>
      <td>只读远端监控能否读到 ref，取决于访问路径和凭据边界；它只带来最小可观察性，不应泄露秘密，也不能把访问失败误判成仓库变化。</td>
      <td>下一次可以讲只读凭据生命周期与降级策略：deploy key、短期 token、SSH agent 失败时如何安全重试、保留旧基线并标记未判定。</td>
    </tr>
<tr>
      <td rowspan="3">
        <a href="../daily_report/2026-09/2026-09-15-learning-report.html">2026-09-15</a>
      </td>
      <td>数据驱动配置与配置注册</td>
      <td>计算机科学 / 软件工程</td>
      <td>★★</td>
      <td>数据驱动配置与配置注册，就是先用一份数据说明书定义表现参数，再把这份说明书接入运行时，让代码读取配置而不是硬编码。</td>
      <td>下一次可以讲 schema 版本演进与配置迁移：字段新增、重命名、废弃时，注册表和测试如何避免旧配置静默失效。</td>
    </tr>
    <tr>
      <td>配置校验与配置契约</td>
      <td>软件工程</td>
      <td>★★★</td>
      <td>配置校验与配置契约，就是在系统真正使用配置前，用可执行检查确认它符合约定结构，把运行时错误尽量提前暴露。</td>
      <td>下一次可以讲配置迁移与版本化校验：新增、重命名、废弃字段时，示例、文档、校验脚本和调用方如何同步演进。</td>
    </tr>
    <tr>
      <td>有序 LLM provider 故障转移</td>
      <td>大语言模型 / 软件工程</td>
      <td>★★★★</td>
      <td>有序 LLM provider 故障转移，就是把多个大模型服务提供方按顺序排成候选链，当前提供方不能完成调用时按顺序转到下一个，以提高 LLM 调用的可靠性。</td>
      <td>下一次可以讲 failover 状态机与错误分类：成功、可重试失败、不可重试失败、全链失败分别如何记录，并如何与配置校验和回归测试配合。</td>
    </tr>
<tr>
      <td rowspan="3">
        <a href="../daily_report/2026-09/2026-09-14-learning-report.html">2026-09-14</a>
      </td>
      <td>工作区、暂存区与未跟踪文件的状态分类</td>
      <td>计算机科学 / 软件工程</td>
      <td>★★</td>
      <td>工作区、暂存区与未跟踪文件的状态分类，是 Git 用三个位置告诉你改动现在停在哪里，而不是判断改动有没有价值。</td>
      <td>下一次可以讲 git status --porcelain 的机器可读格式，以及已暂存、未暂存、未跟踪如何映射到自动化报告字段。</td>
    </tr>
    <tr>
      <td>基于历史基线的变更检测</td>
      <td>计算机科学 / 数学</td>
      <td>★★★</td>
      <td>基于历史基线的变更检测，就是用上次成功记录的 SHA 当参照，与这次读到的 SHA 比较，相同才叫 unchanged。</td>
      <td>下一次可以讲多 ref 基线管理和读取失败降级：首次发现、正常更新、删除 ref、读取失败分别如何表示。</td>
    </tr>
    <tr>
      <td>待确认变化线索与人工确认</td>
      <td>软件工程</td>
      <td>★★★★</td>
      <td>待确认变化线索是自动化系统当前看到但还不能确认时间与事实归属的痕迹，必须交给人工确认，而不能当成已完成的提交。</td>
      <td>下一次可以讲人工确认流程与证据升级：从工作区线索到暂存、提交、远端 ref 变化分别需要什么证据，以及报告中如何标注确认状态。</td>
    </tr>
<tr>
      <td rowspan="3">
        <a href="../daily_report/2026-09/2026-09-13-learning-report.html">2026-09-13</a>
      </td>
      <td>只读远端监控与最小权限访问</td>
      <td>软件工程 / 安全</td>
      <td>★★</td>
      <td>只读远端监控就是只用最小权限读取 ref 元数据，不下载仓库内容，从而在降低副作用的同时获得有限的指针变化信号。</td>
      <td>下一次可以讲只读凭据生命周期：只读 deploy key、短期 token、SSH agent 失败时如何安全降级，并保留旧基线避免误报。</td>
    </tr>
    <tr>
      <td>访问路径诊断与凭据边界（http_git / ssh_git）</td>
      <td>软件工程 / 安全</td>
      <td>★★★</td>
      <td>访问路径诊断说明远端 ref 监控能否成功，取决于 http_git 或 ssh_git 与相应 key、agent、token 的组合，而报告必须把这些凭据脱敏并限定在最小权限内。</td>
      <td>下一次可以讲只读凭据的生命周期管理：只读 deploy key、短期 token、凭据轮换与失败降级，以及访问失败时如何进入未判定而不是 unchanged。</td>
    </tr>
    <tr>
      <td>ref 元数据证据范围限制</td>
      <td>软件工程 / 计算机科学</td>
      <td>★★★★</td>
      <td>ref 元数据证据范围限制意味着 ref 监控只能证明被监控指针是否移动，不能证明仓库里发生了多少提交或哪些文件变化。</td>
      <td>下一次可以讲从 ref 变化线索到按需下载的决策链：什么证据等级下才触发对象查询，如何标注未知、失败和部分成功。</td>
    </tr>
<tr>
      <td rowspan="3">
        <a href="../daily_report/2026-09/2026-09-12-learning-report.html">2026-09-12</a>
      </td>
      <td>首次观测基线</td>
      <td>软件工程 / 计算机科学</td>
      <td>★★</td>
      <td>第一次看见某个 ref 只是在记录参照点，不是在宣告它刚刚发生变化。</td>
      <td>下一次可以讲多 ref 基线管理：首次发现、正常更新、删除 ref 和读取失败分别如何表示，以及如何避免把首次发现误报成新增事件。</td>
    </tr>
    <tr>
      <td>ref 指针 SHA 比较与变化检测</td>
      <td>计算机科学 / 软件工程</td>
      <td>★★★</td>
      <td>判断远端 ref 是否变化，就是比较同一个 ref 在不同时刻的 SHA 值。</td>
      <td>下一次可以讲多 ref 聚合报告：单个 ref 变化如何汇总成仓库级发布状态，以及部分成功、失败和未知如何表达。</td>
    </tr>
    <tr>
      <td>观测证据范围限制</td>
      <td>软件工程 / 计算机科学</td>
      <td>★★★★</td>
      <td>观测证据范围限制告诉我们：ref 监控能证明的是指针是否变化，而不是仓库里到底发生了什么。</td>
      <td>下一次可以讲从 ref 变化线索到按需下载的决策链：哪些变化值得进一步获取对象，哪些只应留在未判定状态。</td>
    </tr>
<tr>
      <td rowspan="3">
        <a href="../daily_report/2026-09/2026-09-11-learning-report.html">2026-09-11</a>
      </td>
      <td>多 ref 命名空间聚合观测</td>
      <td>软件工程 / 计算机科学</td>
      <td>★★</td>
      <td>远端发布状态是一组 ref 命名空间的联合视图，单个 main 只是其中一个信号。</td>
      <td>下一次可以讲多 ref 基线管理：首次发现、读取失败、删除 ref 分别如何表示，以及如何避免把首次发现误报成新增事件。</td>
    </tr>
    <tr>
      <td>索引/暂存区作为第三层状态边界</td>
      <td>计算机科学 / 软件工程</td>
      <td>★★★</td>
      <td>索引/暂存区是 HEAD 提交快照与工作树之间的第三层状态，决定了已暂存和未暂存的区分。</td>
      <td>下一次可以讲 clean/smudge filter 在 status、diff、checkout 中的调用时机，以及外部命令失败时为什么状态应进入未判定。</td>
    </tr>
    <tr>
      <td>观测结果的三值状态机</td>
      <td>软件工程 / 数学 / 计算机科学</td>
      <td>★★★★</td>
      <td>观测至少要有真、假、未知三值，读取失败必须留在未判定。</td>
      <td>下一次可以讲三值状态如何映射到自动化报告和退出码：成功、失败、未判定分别怎样表达，以及如何设计重试与升级策略。</td>
    </tr>
<tr>
      <td rowspan="3">
        <a href="../daily_report/2026-09/2026-09-10-learning-report.html">2026-09-10</a>
      </td>
      <td>远端 ref 指针作为仓库可观察边界</td>
      <td>软件工程</td>
      <td>★★</td>
      <td>远端仓库是否发布了新的 main 历史，可以由 main 的 ref 指针是否移动来判断；看不见完整对象不影响这个判断。</td>
      <td>下一次可以继续讲多个远端 ref 的聚合：分支、标签与远端 HEAD 分别代表什么，以及如何用一组 ref 而不是单个 ref 判断仓库的发布状态。</td>
    </tr>
    <tr>
      <td>提交对象图与工作树是两层状态</td>
      <td>计算机科学 / 软件工程</td>
      <td>★★★</td>
      <td>提交对象图是 Git 的正式历史档案，工作树是当前编辑现场；档案里没有新记录，不等于现场没有改动。</td>
      <td>下一次可以引入索引（暂存区）作为工作树与提交对象图之间的中间层，讲清未暂存、已暂存、已提交三种状态的转换边界。</td>
    </tr>
    <tr>
      <td>证据缺失不等于事件不存在</td>
      <td>软件工程</td>
      <td>★★★</td>
      <td>证据缺失不等于事件不存在；读不到工作区变化时应标成“待确认”，而不是当成“没有变化”。</td>
      <td>下一次可以深入 Git 的 clean/smudge filter 与 filter-process 生命周期，说明 status/diff/checkout 分别在哪个环节调用外部命令，以及外部命令失败时 Git 如何返回错误。</td>
    </tr>
<tr>
      <td rowspan="3">
        <a href="../daily_report/2026-09/2026-09-09-learning-report.html">2026-09-09</a>
      </td>
      <td>同一个可达闭包的两个方向：fsck 的要求存在集合与 gc 的可清理集合共享同一判定边界</td>
      <td>数学 / 计算机科学</td>
      <td>★★★</td>
      <td>一个对象是否“必须存在”与是否“可以清理”，来自同一张引用可达性地图，只是 fsck 看地图内，gc 看地图外。</td>
      <td>下一次可以沿着 gc 的保守窗口深入，讲 reflog 和 stash 等引用如何改变闭包外对象的保留资格。</td>
    </tr>
    <tr>
      <td>不可达对象的时间缓冲：gc 保留窗口让“悬空状态”成为可恢复的临时状态</td>
      <td>软件工程 / 计算机科学</td>
      <td>★★</td>
      <td>对象离开引用闭包后不会立刻消失，reflog 与保留窗口给了用户一个撤销引用操作的时间窗口。</td>
      <td>下一次可以深入 git prune 的隔离期机制，比较 gc 保留期、reflog 过期时间与 fsck 的缺失检查如何共同决定对象的最终命运。</td>
    </tr>
    <tr>
      <td>显式索引是对象库的发布边界：为什么 fsck 不靠扫描 pack 目录来发现对象</td>
      <td>计算机科学 / 软件工程</td>
      <td>★★★</td>
      <td>pack 文件写完不等于对象发布完成，只有被 idx 或 multi-pack-index 显式登记后，对象才会进入 Git 的查找与完整性检查视图。</td>
      <td>下一次可以研究 git multi-pack-index write 的原子发布过程，观察新包集合在哪个精确时刻对并发读者可见。</td>
    </tr>
<tr>
      <td rowspan="3">
        <a href="../daily_report/2026-09/2026-09-08-learning-report.html">2026-09-08</a>
      </td>
      <td>悬空关系的瞬态性：分支重新指向后对象立即重新进入可达闭包</td>
      <td>计算机科学 / 软件工程</td>
      <td>★★</td>
      <td>对象不会天生悬空，它只是暂时失去引用边；只要分支或标签重新指向它，它就会瞬间回到正式可达集合。</td>
      <td>下次可以沿着 gc 的保守窗口深入：为什么 Git 要等对象“悬空”满两周才清理，reflog 和 stash 等引用如何改变这个保留期。</td>
    </tr>
    <tr>
      <td>物理存在但不被索引发现的对象：pack 无 idx 时 fsck 面对的是目录盲区</td>
      <td>计算机科学 / 软件工程</td>
      <td>★★★</td>
      <td>fsck 不扫描硬盘上的所有字节，而是按索引目录查找对象；一个没有登记入口的 pack，即使物理存在也等于不可见。</td>
      <td>下一次可以比较三种发布 pack 的方式：单独生成 idx、写入 multi-pack-index、repack 时原子替换包集合，观察它们分别让对象在什么时刻对并发读者可见。</td>
    </tr>
    <tr>
      <td>并发写总索引时的锁边界：repack 与 multi-pack-index write 不能各自清点旧 pack</td>
      <td>软件工程 / 计算机科学</td>
      <td>★★★★</td>
      <td>要让并发的 repack 安全，锁不是锁住 pack，而是锁住“改写总索引并清点旧 pack”的入口。</td>
      <td>下一次可以研究 git multi-pack-index expire 的详细流程：它如何找出不再出现在新 midx 中的旧 pack，并用原子替换与延迟 unlink 在不打断读者的情况下清理它们。</td>
    </tr>
<tr>
      <td rowspan="3">
        <a href="../daily_report/2026-09/2026-09-07-learning-report.html">2026-09-07</a>
      </td>
      <td>被引用边界与悬空对象：什么对象缺失才值得让完整性检查报错</td>
      <td>计算机科学 / 软件工程</td>
      <td>★★</td>
      <td>完整性检查不是要求“所有对象都可读”，而是要求“被已发布引用可达的对象必须可解析”。</td>
      <td>下次可以深入 git prune 与 gc 的隔离期机制，看 Git 如何保护未满两周的对象不被误清，以及 reflog、stash 等非 refs 引用如何影响对象的保留资格。</td>
    </tr>
    <tr>
      <td>引用可达性决定“缺失”分类：git fsck 的 missing 与 corrupt 判定</td>
      <td>计算机科学 / 软件工程</td>
      <td>★★★</td>
      <td>fsck 用引用可达性定义“必须存在”，找不到是 missing，内容与 ID 不一致是 corrupt。</td>
      <td>下次可以继续比较 git fsck 与 git index-pack 对同一 pack 错误的报告差异，理解为什么 index-pack 会在验证阶段就发现某些 corrupt，而 fsck 要到可达遍历时才暴露 missing。</td>
    </tr>
    <tr>
      <td>并发仓库维护中的旧 pack 回收所有权：谁可以安全删除仍在延迟让位的旧文件</td>
      <td>软件工程 / 计算机科学</td>
      <td>★★★★</td>
      <td>旧 pack 能否删除，不是由单个维护进程“我觉得它旧了”决定，而是由系统内唯一有效的“当前包集合所有权”判定。</td>
      <td>下次可以深入 multi-pack-index 的 expire 命令：它如何通过原子更新总索引，找出不再被任何 midx 引用的 pack 并清理，以及 expire 与 repack 之间的锁顺序。</td>
    </tr>
<tr>
      <td rowspan="3">
        <a href="../daily_report/2026-09/2026-09-06-learning-report.html">2026-09-06</a>
      </td>
      <td>未完成发布不等于对象库损坏：中间态与真实损坏在完整性检查中的分类</td>
      <td>计算机科学 / 软件工程</td>
      <td>★★★</td>
      <td>文件不成对未必是坏了，也可能只是发布到一半；完整性检查要把“未完成”和“已损坏”分开看待。</td>
      <td>下一次可深入 git fsck 的 missing 与 corrupt 分类，看它如何通过引用图判断哪些对象必须可解析，并比较 fsck 和 index-pack 对同类错误的报告差异。</td>
    </tr>
    <tr>
      <td>没有“删除后仍可读”时，旧 pack 如何延迟让位：从 unlink 到按读者生命周期删除</td>
      <td>计算机科学 / 软件工程</td>
      <td>★★★★</td>
      <td>没有“删除后仍可读”语义时，旧 pack 不能立刻删，而应等到所有拿着旧文件描述符的读者离开后再回收。</td>
      <td>下一次可以研究 Git 在 Windows 和网络文件系统上如何处理打开文件的删除限制，比如 rename 成临时名后再延迟 unlink，以及 lockfile/tempfile 如何绑定进程生命周期。</td>
    </tr>
    <tr>
      <td>同一 ref 的 ok/ng 冲突：为什么不能用“最后一条”而要绑定逻辑命令</td>
      <td>软件工程 / 计算机科学</td>
      <td>★★★★★</td>
      <td>同一 ref 的 ok/ng 冲突不能按到达顺序选结果，而要绑定到同一次逻辑命令并保守地不宣告成功。</td>
      <td>下一次可以沿用这个结论进入退出码压缩问题：单 ref 成败确定后，多个 ref 的部分成功如何映射成脚本可用的进程退出码。</td>
    </tr>
<tr>
      <td rowspan="3">
        <a href="../daily_report/2026-09/2026-09-05-learning-report.html">2026-09-05</a>
      </td>
      <td>仓库格式的版本门槛：为什么对象格式要在读取对象之前被宣布</td>
      <td>计算机科学 / 软件工程</td>
      <td>★★</td>
      <td>Git 不会靠对象 ID 的长相猜哈希；它会先看仓库格式的声明，看不懂就拒绝打开仓库。</td>
      <td>下一次可以深入 Git 的 extension.objectformat 解析规则，以及 SHA-1 对象库与 SHA-256 对象库在互相访问接口上的拒绝边界。</td>
    </tr>
    <tr>
      <td>原子重命名与已打开文件描述符：删除旧 pack 不等于切断旧读者</td>
      <td>计算机科学 / 软件工程</td>
      <td>★★★</td>
      <td>删掉旧 pack 的名字不等于切断所有读者，已经打开旧文件描述符的进程还能继续读旧数据，这为 Git 在运行中替换文件提供了并发安全基础。</td>
      <td>下一次可以专门比较 Windows 与 Linux 在文件删除或打开文件语义上的差异，并讨论网络文件系统不提供“删除后仍可读”时，git gc 的并发安全设计需要怎样调整。</td>
    </tr>
    <tr>
      <td>状态行顺序不保证时的按 ref 聚合：部分成功推送怎样变成客户端结论</td>
      <td>软件工程 / 计算机科学</td>
      <td>★★★★</td>
      <td>推送结果像散装回执，不能按到达顺序“以最后一条为准”，必须先按 ref 把状态收齐再聚合，才能得出全部成功、部分成功或全部失败。</td>
      <td>下一次可以讨论客户端聚合出部分成功或全失败后，不同 Git 命令的退出码约定，以及如何在用户界面中准确呈现哪些 ref 成功、哪些 ref 被拒绝。</td>
    </tr>
<tr>
      <td rowspan="3">
        <a href="../daily_report/2026-09/2026-09-04-learning-report.html">2026-09-04</a>
      </td>
      <td>SHA-256 对象格式与哈希迁移后的对象寻址空间</td>
      <td>数学 / 计算机科学</td>
      <td>★★★</td>
      <td>哈希迁移把对象 ID 的门牌号空间从 160 位扩展到 256 位，降低的是内容撞名的概率，而对象格式的统一决定了这套更长门牌号能不能在仓库内一致使用。</td>
      <td>下一次可以接着讲 Git 对 extension.objectformat 的解析规则，以及 SHA-1 对象库与 SHA-256 对象库在互相访问接口上的拒绝边界。</td>
    </tr>
    <tr>
      <td>压缩流解压失败与内容哈希失配：pack 验证路径上的两类损坏信号</td>
      <td>计算机科学 / 软件工程</td>
      <td>★★★</td>
      <td>解压失败是压缩数据已经取不出来，哈希失配是数据能取出来但不是它声称的那个对象；两者分别位于验证路径的第一道和第二道关。</td>
      <td>下一次可以继续讲 index-pack 在命令行上分别使用哪些校验函数、在哪个阶段调用，并比较 git fsck 与 git index-pack 对这些错误的报告格式。</td>
    </tr>
    <tr>
      <td>delta 对象的外部依赖：基对象缺失时数据补全的边界</td>
      <td>计算机科学 / 软件工程</td>
      <td>★★★★</td>
      <td>delta 对象是“配方”而不是“成品”，对象文件存在只能说明配方还在，配方依赖的基对象缺失时内容依然无法完整还原。</td>
      <td>下一次可以沿着这个边界讲 thin pack 的补全机制：index-pack 找外部基对象时以什么顺序搜索、找不到时如何报告失败，以及哪些命令能帮助把 thin pack 修复成自包含 pack。</td>
    </tr>
<tr>
      <td rowspan="3">
        <a href="../daily_report/2026-09/2026-09-03-learning-report.html">2026-09-03</a>
      </td>
      <td>对象 ID 的指纹本质：SHA-1 碰撞与内容同一性的概率保证</td>
      <td>数学 / 计算机科学</td>
      <td>★★</td>
      <td>对象ID是内容的定长指纹而不是内容本身，Git把“同ID即同内容”当作极低碰撞概率下的工程约定来使用。</td>
      <td>下一次可以沿着哈希迁移方向讲SHA-256对象格式与新旧对象库的共存机制，看Git如何把概率保证升级为更强的实际保障。</td>
    </tr>
    <tr>
      <td>pack 的尾部校验与对象损坏的可检测边界：index-pack 能识别什么、不能恢复什么</td>
      <td>计算机科学 / 软件工程</td>
      <td>★★★</td>
      <td>pack的校验和让Git能发现损坏并大致定位问题，但无法从校验和中倒推出原始内容；可检测与可恢复之间的空隙，决定了pack修复能力的上限。</td>
      <td>下一次可以深入thin pack与--fix-thin的补全机制，看当对象以delta形式存在且基对象不在包中时，Git如何借助外部对象把数据补回来。</td>
    </tr>
    <tr>
      <td>multi-pack-index 的映射数据与包集合的原子替换：一份总目录如何随 repack 保持正确</td>
      <td>计算机科学 / 软件工程</td>
      <td>★★★★</td>
      <td>multi-pack-index是对每个对象ID记录“在哪个包、偏移多少”的总映射表，它必须像一次原子替换一样与repack后的真实pack集合同步，才能让查找始终落在一个存在且完整的数据位置上。</td>
      <td>下一次可以讲git multi-pack-index的增量写入与过期pack清理机制，看Git如何在包集合持续变动时维护这张总表而不产生长时间错位。</td>
    </tr>
<tr>
      <td rowspan="3">
        <a href="../daily_report/2026-09/2026-09-02-learning-report.html">2026-09-02</a>
      </td>
      <td>内容寻址对象库中的重复对象同一性：隔离区迁移的去重边界</td>
      <td>计算机科学 / 软件工程</td>
      <td>★★</td>
      <td>Git 不按文件名或物理位置判定重复，而按内容算出的对象 ID 判定，相同内容的对象永远是同一个对象。</td>
      <td>下一次可以沿着 receive-pack 的完整推送流程，讲 quarantine 中的对象 ID 检查与引用更新顺序。</td>
    </tr>
    <tr>
      <td>从 pack 重建缺失的 idx：派生索引与包数据的恢复关系</td>
      <td>计算机科学 / 软件工程</td>
      <td>★★★</td>
      <td>idx 只是 pack 的目录，目录丢了可以从正文重新写目录，真正不能丢的是 pack 数据。</td>
      <td>下一次可以深入 git index-pack 的校验与恢复边界，讲 pack 完整性验证和薄包修复。</td>
    </tr>
    <tr>
      <td>multi-pack-index：对象查找入口从单个 idx 到聚合索引的切换</td>
      <td>计算机科学 / 软件工程</td>
      <td>★★★★</td>
      <td>多个 pack 就像多个分仓库，multi-pack-index 是总目录，它让 Git 先查总目录再进分仓库。</td>
      <td>下一次可以讲 repack 与 multi-pack-index 的原子发布顺序，以及对象查找在包集合切换窗口中的一致性。</td>
    </tr>
<tr>
      <td rowspan="3">
        <a href="../daily_report/2026-09/2026-09-01-learning-report.html">2026-09-01</a>
      </td>
      <td>quarantine 对象迁移失败后的残留清理与推送幂等恢复</td>
      <td>计算机科学 / 软件工程</td>
      <td>★★</td>
      <td>隔离区对象在确认迁移到主对象库前不算正式对象，迁移失败留下的残留只是待清理垃圾，不会破坏仓库状态。</td>
      <td>可以继续深入了解 receive-pack 的完整推送流程，以及 quarantine 目录的生命周期管理细节。</td>
    </tr>
    <tr>
      <td>pack 与 idx 的发布顺序：索引缺失窗口中的对象查找一致性</td>
      <td>计算机科学 / 软件工程</td>
      <td>★★★</td>
      <td>Git 通过“只通过索引找对象”这一约定，让 pack 和 idx 的短暂脱节不会造成不一致。</td>
      <td>可以深入讲解 multi-pack-index 在对象查找中的定位作用，这是候选摘要中与对象定位直接相关的主题。</td>
    </tr>
    <tr>
      <td>虚拟合并基构造中的冲突传播与处理</td>
      <td>数学 / 计算机科学</td>
      <td>★★★★</td>
      <td>当最佳共同祖先不止一个时，Git 会先把它们合成一个虚拟合并基，合成过程中的冲突不会被丢弃，而是作为历史分歧继续影响最终合并。</td>
      <td>可以深入探索 ort 合并策略如何优化虚拟合并基构造和冲突传播，以及它对合并性能的影响。</td>
    </tr>
  </tbody>
</table>
