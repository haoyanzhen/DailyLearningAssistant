#!/usr/bin/env python3
"""Generate the daily HTML learning report and update site manifests."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from orchestrator.llm import LLMRetryPolicy, RetryPolicy, call_chat_completion, retry_call
from orchestrator.manifest import update_daily_manifest, update_knowledge_manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate daily_report HTML and update manifests.")
    parser.add_argument("--date", help="Target date in YYYY-MM-DD format. Defaults to schedule.timezone today.")
    parser.add_argument("--config", default=str(PROJECT_ROOT / "config.json"), help="Path to config JSON.")
    parser.add_argument(
        "--input-root",
        default=str(PROJECT_ROOT),
        help="Root to read prework/YYYY-MM/YYYY-MM-DD and knowledge_log from.",
    )
    parser.add_argument(
        "--output-root",
        default=str(PROJECT_ROOT),
        help="Root to write daily_report and manifest files to.",
    )
    parser.add_argument("--timeout", type=int, default=180, help="LLM request timeout in seconds.")
    parser.add_argument("--llm-retries", type=int, default=3, help="Maximum LLM attempts.")
    parser.add_argument("--llm-retry-delay", type=float, default=3.0, help="Initial LLM retry delay in seconds.")
    return parser.parse_args()


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"[错误] 配置文件不存在: {path}")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"[错误] 配置文件不是合法 JSON: {path} ({exc})")


def require_llm_config(config: dict) -> dict:
    llm = config.get("llm") or {}
    missing = [key for key in ("api_url", "api_key", "model") if not llm.get(key)]
    if missing:
        raise SystemExit(f"[错误] config.json 缺少 llm 配置项: {', '.join(missing)}")
    if str(llm["api_key"]).startswith("YOUR_"):
        raise SystemExit("[错误] llm.api_key 仍是示例占位符，请在 config.json 中填入真实密钥。")
    return llm


def resolve_target_date(arg_date: str | None, config: dict) -> str:
    if arg_date:
        try:
            datetime.strptime(arg_date, "%Y-%m-%d")
        except ValueError:
            raise SystemExit("[错误] --date 必须使用 YYYY-MM-DD 格式。")
        return arg_date

    timezone_name = (config.get("schedule") or {}).get("timezone", "Asia/Shanghai")
    try:
        timezone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        raise SystemExit(f"[错误] 未识别的时区配置: {timezone_name}")
    return datetime.now(timezone).date().isoformat()


def read_required_text(path: Path, label: str) -> str:
    if not path.exists():
        raise SystemExit(f"[错误] 必要输入文件不存在: {path}")
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SystemExit(f"[错误] 必要输入文件不可读取: {path} ({exc})")
    if not content.strip():
        raise SystemExit(f"[错误] 必要输入文件为空: {path}")
    print(f"[输入] 已读取 {label}: {path}")
    return content


def strip_markdown_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def parse_llm_json(text: str) -> dict:
    text = strip_markdown_fence(text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.S)
        if match:
            return json.loads(match.group(0))
        raise


def parse_tagged_report(text: str) -> dict:
    def extract(tag: str) -> str:
        match = re.search(rf"<{tag}>\s*([\s\S]*?)\s*</{tag}>", text, flags=re.I)
        return match.group(1).strip() if match else ""

    data = {
        "title": extract("report_title"),
        "summary": extract("report_summary"),
        "html": extract("report_html"),
    }
    if all(data.values()):
        return data
    return {}


def parse_llm_report(text: str) -> dict:
    tagged = parse_tagged_report(text)
    if tagged:
        return tagged
    return parse_llm_json(text)


def build_prompt(target_date: str, knowledge_explaination: str, knowledge_log: str, style_css: str) -> str:
    year_month = target_date[:7]
    css_excerpt = style_css[-30000:]
    return f"""你是“学习日报页面编辑”。请根据当天知识讲解文件，生成学习日报所需的结构化内容块。

目标日期：{target_date}
目标月份：{year_month}

输入一：当天知识讲解 `prework/{year_month}/{target_date}/knowledge_explaination.md`

```markdown
{knowledge_explaination}
```

输入二：当月教学记录 `knowledge_log/{year_month}-knowledge-log.md`

```markdown
{knowledge_log}
```

输入三：当前公共样式文件 `style/main.css`。HTML 页面必须复用这些类名和视觉系统，不要新建页面私有 CSS，也不要内联 CSS。

```css
{css_excerpt}
```

生成要求：
- 只根据 `knowledge_explaination.md` 的知识内容组织页面，不修改知识主体含义，不编造第四个概念。
- 不要输出完整 HTML，不要输出 CSS，不要输出 `<style>`，不要输出内联 style。
- 必须提供 3 个知识点，顺序与 `knowledge_explaination.md` 保持一致。
- 简读内容包含：一句话解释、核心要点、小例子、记忆句。
- 精读内容包含：完整讲解、原理逻辑、具体例子、常见误区、概念关联、继续深入问题。
- 精读内容不要出现“与当天工作内容的关系”或“与前一天工作内容的关系”章节。

manifest 要求：
- `title` 使用中文，适合作为日报标题，建议格式：`{target_date} 学习笔记日报`。
- `summary` 控制在 40-80 个中文字符，说明当天三个概念或主线。

严格输出 JSON，不要输出 markdown 代码块，不要输出解释文字。JSON schema:

{{
  "title": "{target_date} 学习笔记日报",
  "summary": "40-80 个中文字符摘要",
  "hero_title": "页面主标题",
  "hero_intro": "页面导语，1-2 句",
  "theme": "今日主题",
  "learning_path": "学习路径，例如 检查 → 停止 → 关联",
  "overview": "今日知识点概览段落",
  "main_thread": "今日知识主线段落",
  "association": "概念之间的关联段落",
  "best_sentence": "今日最值得记住的一句话",
  "exploration_questions": ["可继续探索的问题 1", "可继续探索的问题 2", "可继续探索的问题 3"],
  "concepts": [
    {{
      "id": "stable-lowercase-id",
      "name": "概念名称",
      "english_name": "英文或拼音辅助名",
      "domain": "领域",
      "difficulty": "★★★",
      "one_sentence": "一句话解释",
      "key_points": ["核心要点 1", "核心要点 2", "核心要点 3"],
      "example": "小例子",
      "memory_sentence": "记忆句",
      "full_explanation": "完整讲解",
      "principle_logic": ["原理逻辑 1", "原理逻辑 2", "原理逻辑 3"],
      "common_misunderstandings": ["常见误区 1", "常见误区 2"],
      "connections": ["概念关联 1", "概念关联 2"],
      "deep_questions": ["继续深入问题 1", "继续深入问题 2", "继续深入问题 3"]
    }}
  ]
}}
"""


def call_llm(llm: dict, prompt: str, timeout: int, retries: int, retry_delay: float) -> str:
    return call_chat_completion(
        llm,
        [{"role": "user", "content": prompt}],
        timeout=timeout,
        retry_policy=LLMRetryPolicy(attempts=retries, initial_delay=retry_delay),
        temperature=llm.get("temperature", 0.55),
    )


def normalize_text(value: object, fallback: str = "") -> str:
    return str(value or fallback).strip()


def escape_text(value: object, fallback: str = "") -> str:
    return html.escape(normalize_text(value, fallback), quote=False)


def slugify(value: str, index: int) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", normalize_text(value).lower()).strip("-")
    return slug or f"lesson-{index}"


def render_items(items: list, tag: str = "li") -> str:
    return "\n".join(f"                <{tag}>{escape_text(item)}</{tag}>" for item in items)


def render_table_rows(items: list[str]) -> str:
    rows = []
    for item in items:
        if "：" in normalize_text(item):
            left, right = normalize_text(item).split("：", 1)
        elif ":" in normalize_text(item):
            left, right = normalize_text(item).split(":", 1)
        else:
            left, right = "关联说明", normalize_text(item)
        rows.append(f"                <tr><td>{escape_text(left)}</td><td>{escape_text(right)}</td></tr>")
    return "\n".join(rows)


def validate_structured_payload(data: dict, target_date: str) -> dict:
    title = data.get("title")
    summary = data.get("summary")
    missing = [
        name
        for name, value in (
            ("title", title),
            ("summary", summary),
            ("hero_title", data.get("hero_title")),
            ("hero_intro", data.get("hero_intro")),
            ("theme", data.get("theme")),
            ("learning_path", data.get("learning_path")),
            ("overview", data.get("overview")),
            ("main_thread", data.get("main_thread")),
            ("association", data.get("association")),
            ("best_sentence", data.get("best_sentence")),
        )
        if not isinstance(value, str) or not value.strip()
    ]
    if missing:
        raise ValueError(f"LLM 输出缺少必要字段或字段为空: {', '.join(missing)}")
    if not isinstance(data.get("concepts"), list) or len(data["concepts"]) != 3:
        raise ValueError("LLM 输出 concepts 必须包含 3 个知识点。")
    if not isinstance(data.get("exploration_questions"), list) or len(data["exploration_questions"]) < 2:
        raise ValueError("LLM 输出 exploration_questions 至少包含 2 个问题。")
    for index, concept in enumerate(data["concepts"], start=1):
        if not isinstance(concept, dict):
            raise ValueError(f"concepts[{index}] 必须是 object。")
        required = (
            "name",
            "domain",
            "difficulty",
            "one_sentence",
            "key_points",
            "example",
            "memory_sentence",
            "full_explanation",
            "principle_logic",
            "common_misunderstandings",
            "connections",
            "deep_questions",
        )
        missing_concept = [key for key in required if not concept.get(key)]
        if missing_concept:
            raise ValueError(f"concepts[{index}] 缺少必要字段: {', '.join(missing_concept)}")
        for array_key in ("key_points", "principle_logic", "common_misunderstandings", "connections", "deep_questions"):
            if not isinstance(concept.get(array_key), list) or not concept[array_key]:
                raise ValueError(f"concepts[{index}].{array_key} 必须是非空数组。")
        concept["id"] = slugify(str(concept.get("id") or concept["name"]), index)
    return data


def render_report_html(data: dict, target_date: str) -> str:
    year_month = target_date[:7]
    concepts = data["concepts"]
    stat_cards = "\n".join(
        f"""          <article class="stat-card">
            <strong>{escape_text(concept["name"])}</strong>
            <span>{escape_text(concept["one_sentence"])}</span>
          </article>"""
        for concept in concepts
    )
    lesson_cards = []
    lesson_details = []
    for concept in concepts:
        lesson_cards.append(
            f"""          <article class="lesson-card" id="{escape_text(concept["id"])}">
            <header class="lesson-card-header">
              <div class="tag-row">
                <span class="tag">{escape_text(concept["domain"])}</span>
                <span class="tag warm">{escape_text(concept["difficulty"])}</span>
              </div>
              <h3>{escape_text(concept["name"])}</h3>
              <p>{escape_text(concept.get("english_name"), concept["name"])}</p>
            </header>

            <div class="lesson-brief">
              <p class="lesson-summary">{escape_text(concept["one_sentence"])}</p>
              <h4>核心要点</h4>
              <ul>
{render_items(concept["key_points"])}
              </ul>
              <h4>小例子</h4>
              <p>{escape_text(concept["example"])}</p>
              <div class="highlight">记忆句：{escape_text(concept["memory_sentence"])}</div>
            </div>

            <button class="lesson-expand" type="button" data-lesson="{escape_text(concept["id"])}" aria-expanded="false">阅读精读</button>
          </article>"""
        )
        lesson_details.append(
            f"""            <article class="lesson-detail" data-lesson-detail="{escape_text(concept["id"])}">
              <header class="lesson-detail-header">
                <p class="eyebrow">精读文章 · {escape_text(concept["domain"])}</p>
                <h3>{escape_text(concept["name"])}</h3>
                <button class="lesson-close" type="button">收起精读</button>
              </header>

              <h4>完整讲解</h4>
              <p>{escape_text(concept["full_explanation"])}</p>

              <h4>原理逻辑</h4>
              <ol>
{render_items(concept["principle_logic"])}
              </ol>

              <h4>具体例子</h4>
              <p>{escape_text(concept["example"])}</p>

              <h4>常见误区</h4>
              <ul>
{render_items(concept["common_misunderstandings"])}
              </ul>

              <h4>概念关联</h4>
              <table class="mini-table">
                <tr><th>关联概念</th><th>关系说明</th></tr>
{render_table_rows(concept["connections"])}
              </table>

              <h4>继续深入问题</h4>
              <ol>
{render_items(concept["deep_questions"])}
              </ol>
            </article>"""
        )
    questions = "\n".join(f"            <li>{escape_text(item)}</li>" for item in data["exploration_questions"])
    lesson_cards_html = "\n".join(lesson_cards)
    lesson_details_html = "\n".join(lesson_details)
    return f"""<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{escape_text(data["title"])}</title>
    <meta name="description" content="{escape_text(data["summary"])}" />
    <link rel="stylesheet" href="../../style/main.css?v={target_date.replace("-", "")}" />
  </head>
  <body>
    <main class="page">
      <header class="topbar" aria-label="学习日报导航">
        <a class="brand" href="../../index.html" aria-label="返回最新学习日报">
          <span class="brand-mark" aria-hidden="true">日</span>
          <span>
            <strong>每日拾光学习簿</strong>
            <small>把今天学到的东西，留成明天能继续走的路</small>
          </span>
        </a>
        <nav class="topnav" aria-label="快速入口">
          <a href="../../index.html">最新日报</a>
          <a href="../../index.html?archive=1">学习归档</a>
          <a href="../../index.html?knowledge=1">教学记录</a>
        </nav>
      </header>

      <section class="hero">
        <p class="eyebrow">Learning Report · {target_date}</p>
        <h1>{escape_text(data["hero_title"])}</h1>
        <p>{escape_text(data["hero_intro"])}</p>
        <div class="meta-grid">
          <div class="meta-item"><span class="meta-label">今日主题</span><span class="meta-value">{escape_text(data["theme"])}</span></div>
          <div class="meta-item"><span class="meta-label">阅读模式</span><span class="meta-value">简读 / 精读</span></div>
          <div class="meta-item"><span class="meta-label">知识点</span><span class="meta-value">3 个并列讲解</span></div>
          <div class="meta-item"><span class="meta-label">学习路径</span><span class="meta-value">{escape_text(data["learning_path"])}</span></div>
        </div>
      </section>

      <section class="section panel">
        <h2 class="section-title">今日知识点概览</h2>
        <p class="lead">{escape_text(data["overview"])}</p>
        <div class="stat-grid">
{stat_cards}
        </div>
      </section>

      <section class="section panel">
        <h2 class="section-title">今日知识主线</h2>
        <p class="lead">{escape_text(data["main_thread"])}</p>
      </section>

      <section class="section lesson-section" data-read-mode="brief" id="lesson-section">
        <div class="lesson-toolbar panel">
          <div>
            <p class="eyebrow">Read Mode</p>
            <h2 class="section-title">今日三节小课</h2>
            <p class="lead">简读用于快速抓住三个概念；精读会在卡片下方展开完整文章。</p>
          </div>
          <div class="read-mode-toggle" role="group" aria-label="阅读模式">
            <button class="is-active" type="button" data-mode="brief">简读</button>
            <button type="button" data-mode="deep">精读</button>
          </div>
        </div>

        <div class="lesson-grid">
{lesson_cards_html}
        </div>

        <div class="lesson-detail-panel" id="lesson-detail-panel" aria-live="polite">
          <div class="lesson-detail-shell">
{lesson_details_html}
          </div>
        </div>
      </section>

      <section class="section panel">
        <h2 class="section-title">概念之间的关联</h2>
        <p class="lead">{escape_text(data["association"])}</p>
      </section>

      <section class="section panel">
        <h2 class="section-title">今日最值得记住的一句话</h2>
        <p class="lead">{escape_text(data["best_sentence"])}</p>
      </section>

      <section class="section panel">
        <h2 class="section-title">可继续探索的问题</h2>
        <ol>
{questions}
        </ol>
      </section>

      <footer class="footer-note">
        数据来源：prework/{year_month}/{target_date}/knowledge_explaination.md
      </footer>
    </main>

    <script>
      const lessonSection = document.querySelector("#lesson-section");
      const modeButtons = document.querySelectorAll("[data-mode]");
      const expandButtons = document.querySelectorAll("[data-lesson]");
      const detailPanel = document.querySelector("#lesson-detail-panel");
      const details = document.querySelectorAll("[data-lesson-detail]");
      const closeButtons = document.querySelectorAll(".lesson-close");

      function setMode(mode) {{
        lessonSection.dataset.readMode = mode;
        modeButtons.forEach((button) => button.classList.toggle("is-active", button.dataset.mode === mode));
        if (mode === "brief") {{
          detailPanel.classList.remove("is-open");
          expandButtons.forEach((button) => button.setAttribute("aria-expanded", "false"));
        }}
      }}

      function openLesson(id) {{
        setMode("deep");
        detailPanel.classList.add("is-open");
        details.forEach((detail) => detail.classList.toggle("is-active", detail.dataset.lessonDetail === id));
        expandButtons.forEach((button) => button.setAttribute("aria-expanded", String(button.dataset.lesson === id)));
        detailPanel.scrollIntoView({{ behavior: "smooth", block: "start" }});
      }}

      modeButtons.forEach((button) => button.addEventListener("click", () => setMode(button.dataset.mode)));
      expandButtons.forEach((button) => button.addEventListener("click", () => openLesson(button.dataset.lesson)));
      closeButtons.forEach((button) => button.addEventListener("click", () => setMode("brief")));
    </script>
  </body>
</html>"""


def validate_report_payload(data: dict, target_date: str) -> tuple[str, str, str]:
    data = validate_structured_payload(data, target_date)
    title = normalize_text(data["title"])
    summary = normalize_text(data["summary"])
    html = render_report_html(data, target_date)

    required_html = [
        "<!doctype html>",
        '<html lang="zh-CN"',
        "../../style/main.css",
        "../../index.html?archive=1",
        "../../index.html?knowledge=1",
        "简读",
        "精读",
        "lesson-section",
        "lesson-detail-panel",
        target_date,
    ]
    lower_html = html.lower()
    missing_html = [item for item in required_html if item.lower() not in lower_html]
    if missing_html:
        raise ValueError(f"HTML 日报缺少必要片段: {', '.join(missing_html)}")

    if "<script" not in lower_html:
        raise ValueError("HTML 日报缺少阅读模式切换脚本。")
    if re.search(r"<style\b|\sstyle\s*=", html, flags=re.I):
        raise ValueError("HTML 日报不应包含内联 CSS，应复用 ../../style/main.css。")
    if re.search(r"<link[^>]+stylesheet[^>]+daily_report", html, flags=re.I):
        raise ValueError("HTML 日报不应引用 daily_report 下的私有样式文件。")

    return title.strip(), summary.strip(), html.strip()


def generate_validated_report(llm: dict, prompt: str, target_date: str, timeout: int, retries: int, retry_delay: float) -> tuple[str, str, str]:
    def operation() -> tuple[str, str, str]:
        raw_content = call_llm(llm, prompt, timeout, 1, 0)
        try:
            data = parse_llm_json(raw_content)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"LLM 输出不是可解析 JSON: {exc}\n{raw_content[:2000]}") from exc
        if not data:
            raise RuntimeError(f"LLM 输出为空。\n{raw_content[:2000]}")
        return validate_report_payload(data, target_date)

    return retry_call(
        operation,
        RetryPolicy(attempts=retries, initial_delay=retry_delay, label="学习日报 HTML LLM 生成与校验"),
    )


def main() -> int:
    args = parse_args()
    config_path = Path(args.config).expanduser().resolve()
    input_root = Path(args.input_root).expanduser().resolve()
    output_root = Path(args.output_root).expanduser().resolve()
    config = load_json(config_path)
    llm = require_llm_config(config)
    target_date = resolve_target_date(args.date, config)
    year_month = target_date[:7]

    knowledge_path = input_root / "prework" / year_month / target_date / "knowledge_explaination.md"
    knowledge_log_path = input_root / "knowledge_log" / f"{year_month}-knowledge-log.md"
    style_path = PROJECT_ROOT / "style" / "main.css"

    knowledge_explaination = read_required_text(knowledge_path, "knowledge_explaination.md")
    knowledge_log = read_required_text(knowledge_log_path, "knowledge_log")
    style_css = read_required_text(style_path, "style/main.css")

    prompt = build_prompt(target_date, knowledge_explaination, knowledge_log, style_css)
    try:
        title, summary, html = generate_validated_report(
            llm, prompt, target_date, args.timeout, args.llm_retries, args.llm_retry_delay
        )
    except RuntimeError as exc:
        raise SystemExit(f"[错误] LLM 生成或校验失败: {exc}")

    report_path = output_root / "daily_report" / year_month / f"{target_date}-learning-report.html"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(html.rstrip() + "\n", encoding="utf-8")

    daily_manifest_path = output_root / "daily_report" / "manifest.json"
    knowledge_manifest_path = output_root / "knowledge_log" / "manifest.json"
    relative_report_path = f"./daily_report/{year_month}/{target_date}-learning-report.html"
    try:
        update_daily_manifest(daily_manifest_path, target_date, title, summary, relative_report_path, root=output_root)
        update_knowledge_manifest(knowledge_manifest_path, year_month, root=output_root)
    except ValueError as exc:
        raise SystemExit(f"[错误] manifest 更新或校验失败: {exc}")

    print(f"[完成] 已生成: {report_path}")
    print(f"[完成] 已更新: {daily_manifest_path}")
    print(f"[完成] 已更新: {knowledge_manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
