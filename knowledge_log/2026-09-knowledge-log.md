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
