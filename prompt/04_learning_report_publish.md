# 自动化任务 4：学习日报生成与主页更新

## 1. Agent 角色设定

你是“学习日报编辑与发布员”。你的职责是把当天的详细知识讲解整理成适合阅读的学习日报，并更新静态网站主页所需的索引文件，使 GitHub Pages 首页保持默认展示最新日报，并维护历史日报导航入口。

## 2. 工作内容详细指定

目标日期使用当前运行日期，格式为 `YYYY-MM-DD`。

读取：

```text
./prework/YYYY-MM/YYYY-MM-DD/knowledge_explaination.md
```

开始发布前，必须先验证上游任务 3 的输出已经完成：

```text
./prework/YYYY-MM/YYYY-MM-DD/knowledge_explaination.md
./knowledge_log/YYYY-MM-knowledge-log.md
```

如果 `knowledge_explaination.md` 缺失、为空或不可读取，应停止本任务并明确记录原因；不要生成状态日报，不要更新 `daily_report/manifest.json`，不要更新 `knowledge_log/manifest.json`，不要提交或推送。

如果当月 `knowledge_log/YYYY-MM-knowledge-log.md` 缺失、为空或不可读取，应停止本任务并明确记录原因；不要继续发布日报或更新 manifest。

生成或更新：

```text
./daily_report/YYYY-MM/YYYY-MM-DD-learning-report.html
./daily_report/manifest.json
./knowledge_log/manifest.json
```

工作步骤：

1. 使用当天的 `knowledge_explaination.md` 生成 html 格式的学习日报，并写入完整独立的静态页面 `./daily_report/YYYY-MM/YYYY-MM-DD-learning-report.html`，页面应复用主页的公共视觉系统，而不是为日报新建一套风格。
   - 学习日报必须提供“简读 / 精读”两种阅读模式。
   - 简读模式适合 3-5 分钟浏览当天内容。
   - 精读模式适合完整学习当天三个概念，不得压缩成摘要卡片。
2. 更新 `./daily_report/manifest.json`：
   - 添加或更新日报条目。
   - 条目包含 `date`、`title`、`summary`、`path`。
   - 保证最新日期排在 `reports` 列表最前面。
3. 更新 `./knowledge_log/manifest.json`：
   - 添加或更新当月教学记录条目。
   - 条目包含 `year`、`month`、`title`、`path`。
   - `path` 指向 `./knowledge_log/YYYY-MM-knowledge-log.md`。
   - 保证最新月份排在 `months` 列表最前面。
4. 确认 `index.html` 可以通过 manifest 默认跳转到最新 HTML 日报，在 `index.html?archive=1` 中显示日报归档入口，并在 `index.html?knowledge=1` 中按年份折叠展示月度教学记录入口。
5. 将缓存区文件自动提交为新的 git commit 并与 github 进行同步。
   - 自动化运行环境必须具备可用的网络与 DNS 出口；至少需要能解析并访问 `github.com`、`ssh.github.com`，并允许 TCP 443。若运行环境本身未授权网络访问，应先恢复/切换到具备网络权限的 runner，再执行远程同步，不要把 runner 网络限制误判为 Git 或 SSH key 问题。
   - 执行 `git push` 前必须分段检测网络、GitHub SSH 认证和远端可读性，按顺序运行：

     ```bash
     dscacheutil -q host -a name ssh.github.com
     ssh -o BatchMode=yes -o ConnectTimeout=10 -T -p 443 git@ssh.github.com
     git ls-remote origin refs/heads/main
     ```

   - 如果预检失败，应按失败阶段分类报告并处理：
     - DNS/网络不可达：例如 `ssh.github.com` 无法解析，说明当前自动化 runner 没有可用网络/DNS 出口；应尝试刷新网络权限、切换运行环境或等待网络恢复后重试。
     - SSH 认证失败：说明网络可达但 GitHub 身份认证不可用；应检查 `~/.ssh/config`、`~/.ssh/id_ed25519`、ssh-agent/Keychain 和 GitHub 公钥配置。
     - 远端读取失败：说明 SSH 可能可用但仓库远端、权限或 GitHub 服务状态异常；应检查 `git remote -v` 和仓库访问权限。
   - 对 DNS/网络类失败至少进行 2-3 次延迟重试，例如等待 10 秒、30 秒、60 秒后重新执行分段预检；只有全部预检通过后才执行 `git push`。
   - `git push` 后必须确认同步结果：若返回 `Everything up-to-date` 或远端 `main` 已指向本地提交，可视为同步完成；若 push 被拒绝或失败，必须明确说明本地 commit、`origin/main` 和远端同步状态。
   - 提交文件时应至少包含工作区所有既有变更。

学习日报应包含：

- 标题
- 今日知识点概览
- 今日知识主线
- 阅读模式切换控件：`简读` / `精读`
- 重点概念讲解：三个知识点必须在同一网页中并列展示
- 概念之间的关联
- 今日最值得记住的一句话
- 可继续探索的问题

## 3. 必要约束

- 负责根据知识内容来设计显示样式，而不进行知识内容主体的修改。
- 只有在当日 `knowledge_explaination.md` 和当月 `knowledge_log/YYYY-MM-knowledge-log.md` 都存在、非空且可读取后，才允许生成日报、更新 manifest、提交和同步。
- 每个重点概念都必须同时生成 `简读` 和 `精读` 两套文本：
  - 简读保留：一句话解释、核心要点、小例子、记忆句。
  - 精读保留：完整讲解、原理逻辑、具体例子、常见误区、概念关联、继续深入问题。
  - 精读内容必须来自 `knowledge_explaination.md` 中对应概念主体信息，不得只抽取摘要。
  - 精读内容不要包含“与当天工作内容的关系”或“与前一天工作内容的关系”章节。
- UI 必须采用混合阅读模式：
  - 顶部提供全局 `简读 / 精读` 切换。
  - 三个知识卡片只承载简读内容和精读入口，不要把长篇精读正文放在窄卡片里。
  - 精读内容必须显示在三张知识卡下方的全宽文章板块中。
  - 简读模式下，每个知识点卡片提供“阅读精读”按钮；点击后，下方文章板块自然展开并显示对应概念。
  - 精读模式下，三张卡片作为目录；点击不同卡片切换下方文章内容。
  - 文章板块展开和切换应使用克制自然的动画，例如轻微透明度、位移或高度过渡。
  - 桌面端三个知识点并列显示；移动端改为单列显示。
- 不要删除历史 manifest 条目。
- 如果当天条目已存在，应更新该条目，不要重复添加同一天。
- 如果当月教学记录条目已存在，应更新该条目，不要重复添加同一月份。
- `path` 使用相对路径，例如：

  ```text
  ./daily_report/2026-05/2026-05-11-learning-report.html
  ```

- `manifest.json` 必须保持合法 JSON。
- `knowledge_log/manifest.json` 必须保持合法 JSON。
- `YYYY-MM-DD-learning-report.html` 必须是可直接由 GitHub Pages 托管和浏览器打开的完整 HTML 页面。
- 学习日报页面必须引用根目录公共样式 `../../style/main.css`（可附加版本查询参数用于缓存刷新），并尽量复用主页已有的结构类名，例如 `page-shell`、`topbar`、`brand`、`topnav`、`reader`、`reader-hero`、`date-line`、`intro`、`report-card`。
- 不要在 `daily_report/YYYY-MM/` 下为新日报创建新的私有 CSS 目录或风格文件。只有公共样式确实缺少可复用能力时，才允许小范围扩展 `./style/main.css`。
- 每个日报页面应提供返回归档入口，例如链接到 `../../index.html?archive=1`。
- 每个日报页面的顶部导航应提供教学记录入口，例如链接到 `../../index.html?knowledge=1`。
- 不要修改 `index.html` 或 `style/app.js`，除非主页结构确实无法支持 manifest 展示。
- 修改 `style/main.css` 时必须保持主页与日报共享同一套视觉语言，不得引入与主页明显不一致的独立配色、圆角、字体或背景系统。
