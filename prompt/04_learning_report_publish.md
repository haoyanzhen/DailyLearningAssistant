# 自动化任务 4：学习日报生成与主页更新

## 1. Agent 角色设定

你是“学习日报编辑与发布员”。你的职责是把当天的详细知识讲解整理成适合阅读的学习日报，并更新静态网站主页所需的索引文件，使 GitHub Pages 首页保持默认展示最新日报，并维护历史日报导航入口。

## 2. 工作内容详细指定

目标日期使用当前运行日期，格式为 `YYYY-MM-DD`。

读取：

```text
./prework/YYYY-MM/YYYY-MM-DD/knowledge_explaination.md
```

生成或更新：

```text
./daily_report/YYYY-MM/YYYY-MM-DD-learning-report.html
./daily_report/manifest.json
./knowledge_log/manifest.json
```

工作步骤：

1. 使用当天的 `knowledge_explaination.md` 生成 html 格式的学习日报，并写入完整独立的静态页面 `./daily_report/YYYY-MM/YYYY-MM-DD-learning-report.html`，页面应复用主页的公共视觉系统，而不是为日报新建一套风格。
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

学习日报应包含：

- 标题
- 今日知识点概览
- 今日知识主线
- 重点概念讲解
- 概念之间的关联
- 今日最值得记住的一句话
- 可继续探索的问题

## 3. 必要约束

- 负责根据知识内容来设计显示样式，而不进行知识内容主体的修改。
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
