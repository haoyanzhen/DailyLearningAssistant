# 自动化任务 4：学习日报生成与主页更新

## 1. Agent 角色设定

你是“学习日报编辑与发布员”。你的职责是调用本项目 `config.json` 中 `llm` 配置的外部大模型，把当天的详细知识讲解整理成结构化页面内容块，再由本地脚本使用固定 HTML 模板生成学习日报，并更新静态网站主页所需的索引文件。

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

1. 使用当天的 `knowledge_explaination.md` 和当前公共样式文件 `./style/main.css` 生成结构化页面内容块，再由程序模板渲染 HTML 学习日报，并写入完整独立的静态页面 `./daily_report/YYYY-MM/YYYY-MM-DD-learning-report.html`，页面应复用主页的公共视觉系统，而不是为日报新建一套风格。
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
5. 写入本地运行状态 `./prework/YYYY-MM/YYYY-MM-DD/run_status.json`。Git commit、push 和邮件通知不属于本 Agent 的职责，应交给后续“发布集成”步骤统一处理。

学习日报应包含：

- 标题
- 今日知识主线
- 阅读模式切换控件：`简读` / `精读`
- 重点概念讲解：三个知识点必须在同一网页中并列展示
- 概念之间的关联
- 今日最值得记住的一句话
- 可继续探索的问题

## 3. 必要约束

- 必须优先使用 `scripts/generate_learning_report.py` 调用 `config.json` 中配置的 LLM，不要默认由 Codex 直接撰写正式 HTML 日报正文。
- LLM 不应直接输出完整 HTML；脚本应要求 LLM 返回标题、摘要、hero 文案、三个知识点的简读/精读内容块，再由程序模板生成 HTML。
- 负责根据知识内容来设计显示样式，而不进行知识内容主体的修改。
- 只有在当日 `knowledge_explaination.md` 和当月 `knowledge_log/YYYY-MM-knowledge-log.md` 都存在、非空且可读取后，才允许生成日报和更新 manifest。
- 每个重点概念都必须同时生成 `简读` 和 `精读` 两套文本：
  - 简读卡片只保留：概念标签、标题、英文名或辅助名、一句话记忆、精读入口。
  - 简读卡片不要展示核心要点、小例子或长摘要，避免与顶部概览和精读内容重复。
  - 精读保留：完整讲解、核心要点、原理逻辑、具体例子、常见误区、概念关联、继续深入问题。
  - 精读内容必须来自 `knowledge_explaination.md` 中对应概念主体信息，不得只抽取摘要。
  - 精读内容不要包含“与当天工作内容的关系”或“与前一天工作内容的关系”章节。
- UI 必须采用混合阅读模式：
  - 顶部提供全局 `简读 / 精读` 切换。
  - 不再单独渲染“今日知识点概览”区块，三个知识卡片承担概览入口职责。
  - “今日三节小课”标题下不要放简读/精读说明文案，并尽量压缩标题区与三张知识卡之间的空隙。
  - “今日三节小课”标题栏、阅读模式切换和三张知识卡必须合并在同一个外框中，形成“概览卡-精读界面”的整体入口。
  - “今日三节小课”和三张知识卡之间必须嵌入 Mermaid + HTML 关系图：Mermaid 负责展示三张知识卡之间及其相关概念的节点连线，HTML 说明区负责解释每条关系。
  - 三个知识卡片只承载概览式记忆内容和精读入口，不要把核心要点、小例子或长篇精读正文放在窄卡片里。
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
- HTML 页面结构、导航、公共 CSS 引用、`lesson-section`、`lesson-detail-panel`、阅读模式脚本等硬格式由程序模板保证，不能依赖 LLM 自行拼写。
- 学习日报页面必须引用根目录公共样式 `../../style/main.css`（可附加版本查询参数用于缓存刷新），并尽量复用主页已有的结构类名，例如 `page-shell`、`topbar`、`brand`、`topnav`、`reader`、`reader-hero`、`date-line`、`intro`、`report-card`。
- 不要在 `daily_report/YYYY-MM/` 下为新日报创建新的私有 CSS 目录或风格文件。只有公共样式确实缺少可复用能力时，才允许小范围扩展 `./style/main.css`。
- 每个日报页面应提供返回归档入口，例如链接到 `../../index.html?archive=1`。
- 每个日报页面的顶部导航应提供教学记录入口，例如链接到 `../../index.html?knowledge=1`。
- 不要修改 `index.html` 或 `style/app.js`，除非主页结构确实无法支持 manifest 展示。
- 修改 `style/main.css` 时必须保持主页与日报共享同一套视觉语言，不得引入与主页明显不一致的独立配色、圆角、字体或背景系统。
