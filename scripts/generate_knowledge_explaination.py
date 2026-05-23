#!/usr/bin/env python3
"""Generate daily knowledge explanations with the configured chat LLM.

The script is intentionally small and dependency-free so it can run in the
same automation environment as the other daily tasks.
"""

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
KNOWLEDGE_LOG_HEADERS = ("日期", "概念", "领域", "难度", "一句话解释", "下一次讲解参考")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate knowledge_explaination.md and monthly knowledge log with config.json llm settings."
    )
    parser.add_argument("--date", help="Target date in YYYY-MM-DD format. Defaults to schedule.timezone today.")
    parser.add_argument("--config", default=str(PROJECT_ROOT / "config.json"), help="Path to config JSON.")
    parser.add_argument(
        "--input-root",
        default=str(PROJECT_ROOT),
        help="Root to read prework/YYYY-MM/YYYY-MM-DD/concept_relevance.md from.",
    )
    parser.add_argument(
        "--output-root",
        help="Optional test output root. When set, generated files are written under this directory.",
    )
    parser.add_argument("--timeout", type=int, default=120, help="LLM request timeout in seconds.")
    parser.add_argument("--llm-retries", type=int, default=3, help="Maximum LLM generation attempts.")
    parser.add_argument("--llm-retry-delay", type=float, default=3.0, help="Initial LLM retry delay in seconds.")
    return parser.parse_args()


def load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"[错误] 配置文件不存在: {path}")
        print("请先复制并填写配置文件: cp config.example.json config.json")
        sys.exit(1)
    except json.JSONDecodeError as exc:
        print(f"[错误] 配置文件不是合法 JSON: {path} ({exc})")
        sys.exit(1)


def require_llm_config(config):
    llm = config.get("llm") or {}
    missing = [key for key in ("api_url", "api_key", "model") if not llm.get(key)]
    if missing:
        print(f"[错误] config.json 缺少 llm 配置项: {', '.join(missing)}")
        sys.exit(1)
    if str(llm["api_key"]).startswith("YOUR_"):
        print("[错误] llm.api_key 仍是示例占位符，请在 config.json 中填入真实密钥。")
        sys.exit(1)
    return llm


def resolve_target_date(arg_date, config):
    if arg_date:
        return arg_date

    timezone_name = (config.get("schedule") or {}).get("timezone", "Asia/Shanghai")
    try:
        timezone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        print(f"[警告] 未识别的时区配置 {timezone_name!r}，改用系统本地日期。")
        return datetime.now().date().isoformat()
    return datetime.now(timezone).date().isoformat()


def read_text(path, required=True):
    if not path.exists():
        if required:
            print(f"[错误] 必要输入文件不存在: {path}")
            sys.exit(1)
        return ""
    return path.read_text(encoding="utf-8")


def strip_markdown_fence(text):
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def parse_llm_json(text):
    text = strip_markdown_fence(text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.S)
        if match:
            return json.loads(match.group(0))
        raise


def build_knowledge_log_validation_spec(target_date):
    year_month = target_date[:7]
    year, month = year_month.split("-")
    report_href = f"../daily_report/{year_month}/{target_date}-learning-report.html"
    headers = "、".join(KNOWLEDGE_LOG_HEADERS)
    return f"""HTML 表格校验规范（knowledge_log_md 必须逐条满足）：
- 文件标题必须是 `# {year}年{int(month)}月教学记录`。
- 必须使用 HTML `<table>...</table>`，禁止使用 Markdown 表格，禁止放入 markdown 代码块。
- 表头字段必须完整且只使用这 6 项：{headers}。
- 当天 {target_date} 必须固定生成 3 行，对应 `knowledge_explaination_md` 中正式讲解的 3 个概念。
- 当天日期单元格只能出现在当天 3 行的第一行，必须写成 `<td rowspan="3">`，其中 `rowspan="3"` 必须使用双引号。
- 当天日期文字必须是链接：`<a href="{report_href}">{target_date}</a>`。
- 当天第 2、3 行不得重复写日期单元格，只保留概念、领域、难度、一句话解释、下一次讲解参考这 5 个单元格。
- 如果已有同一天记录，必须替换原日期块，不得重复追加第二个 {target_date} 日期块。
- 当月不同日期块按日期倒序排列，最新日期在最上方。
- 每个 `<tr>`、`<td>`、`<th>` 标签必须闭合，表格内容应保持可直接嵌入 Markdown 文件。"""


def build_prompt(target_date, concept_relevance, existing_log):
    year_month = target_date[:7]
    return f"""你是“亲和的知识讲解专业老师”。请根据当天的概念与关联文件，从易到难选择三个概念进行完整讲解。

重要理念：
- 以输入的概念及关联文件为参考，其中“概念”作为主要选择参考，“关联”作为次要内容参考。
- 你的核心任务是为学习者提供连贯且生动易懂的知识讲解，而不是复述工程变更、生成教学教案或扩写项目复盘。
- 选择概念时，优先选择概念清单和候选摘要中最适合展开讲清楚的知识点；概念之间的关联用于帮助组织讲解顺序、说明概念联系，但不要让关联描述喧宾夺主。
- 如果某个关联只是弱线索或待确认线索，应谨慎使用，并明确“这里基于当日材料可确认的是……”。

目标日期：{target_date}
目标月份：{year_month}

输入一：当天概念与关联文件 concept_relevance.md

```markdown
{concept_relevance}
```

输入二：当月已有教学记录 knowledge_log（只作为避免重复概念与深化讲解的参考，不需要你改写）

```markdown
{existing_log or "(当月教学记录尚不存在)"}
```

请只生成结构化内容块，不要生成完整 Markdown 文件，不要生成 HTML 表格，不要生成日报 HTML。

内容要求：
- 必须选择 3 个概念。
- 面向仅有高中基础知识的读者，讲清底层理念、原理和逻辑。
- 每个概念必须包含：概念名称、领域、五颗星难度评级、亲和完整讲解、有趣事例、常见误区、与前一天工作内容的关系、一个具体例子、与其他概念的关联、可继续深入学习的问题、一句话解释、下一次讲解参考。
- `difficulty` 使用 `★★☆☆☆` 这种五颗星格式。
- `connections` 和 `questions` 必须是字符串数组，每项完整成句。
- 只能基于当天 concept_relevance.md 中可确认的概念与关联展开，不要把历史主题伪装成当天新内容。
- 如果遇到已讲过的重复概念，优先考虑知识点有用性，并基于上一轮内容深化，而不是机械换概念。

严格输出 JSON，不要输出 markdown 代码块，不要输出解释文字。JSON schema:

{{
  "main_thread": "今日知识主线，2-4 个自然段",
  "overall_summary": "概念之间的整体关联总结，1-3 个自然段",
  "daily_takeaways": [
    "适合放入学习日报的精简结论 1",
    "适合放入学习日报的精简结论 2",
    "适合放入学习日报的精简结论 3"
  ],
  "concepts": [
    {{
      "name": "概念名称",
      "domain": "领域",
      "difficulty": "★★★☆☆",
      "friendly_explanation": "亲和完整讲解",
      "story": "有趣事例",
      "misconception": "常见误区",
      "previous_relation": "与前一天工作内容的关系",
      "example": "一个具体例子",
      "connections": ["与其他概念的关联 1", "与其他概念的关联 2"],
      "questions": ["可继续深入学习的问题 1", "可继续深入学习的问题 2", "可继续深入学习的问题 3"],
      "one_sentence": "一句话解释",
      "next_reference": "下一次讲解参考"
    }}
  ]
}}
"""


def call_llm(llm, prompt, timeout, retries, retry_delay):
    return call_chat_completion(
        llm,
        [{"role": "user", "content": prompt}],
        timeout=timeout,
        retry_policy=LLMRetryPolicy(attempts=retries, initial_delay=retry_delay),
        temperature=llm.get("temperature", 0.7),
    )


def validate_knowledge_log_html(knowledge_log_md, target_date):
    year_month = target_date[:7]
    year, month = year_month.split("-")
    expected_title = f"# {year}年{int(month)}月教学记录"
    report_href = f"../daily_report/{year_month}/{target_date}-learning-report.html"

    if expected_title not in knowledge_log_md:
        raise ValueError(f"knowledge_log_md 缺少标题: {expected_title}")

    if "```" in knowledge_log_md:
        raise ValueError("knowledge_log_md 不应包含 markdown 代码块。")

    if re.search(r"^\s*\|.*日期.*概念.*\|\s*$", knowledge_log_md, flags=re.M):
        raise ValueError("knowledge_log_md 使用了 Markdown 表格，应改为 HTML <table>。")

    if "<table" not in knowledge_log_md or "</table>" not in knowledge_log_md:
        raise ValueError("knowledge_log_md 缺少完整 HTML <table>...</table>。")

    missing_headers = [header for header in KNOWLEDGE_LOG_HEADERS if header not in knowledge_log_md]
    if missing_headers:
        raise ValueError(f"knowledge_log_md 表头字段缺失: {', '.join(missing_headers)}")

    if "rowspan=\"3\"" not in knowledge_log_md:
        raise ValueError("knowledge_log_md 缺少双引号格式 rowspan=\"3\"。")

    if re.search(r"rowspan\s*=\s*'3'|rowspan\s*=\s*3(?![\"'])", knowledge_log_md):
        raise ValueError("knowledge_log_md 的 rowspan 必须写成双引号格式 rowspan=\"3\"。")

    if report_href not in knowledge_log_md:
        raise ValueError(f"knowledge_log_md 缺少当天日报链接: {report_href}")

    target_link_re = re.compile(
        rf"<a\s+[^>]*href=[\"']{re.escape(report_href)}[\"'][^>]*>\s*{re.escape(target_date)}\s*</a>",
        flags=re.S,
    )
    if len(target_link_re.findall(knowledge_log_md)) != 1:
        raise ValueError(f"knowledge_log_md 中 {target_date} 日期链接必须且只能出现一次。")

    date_cell_re = re.compile(
        rf"<td\s+[^>]*rowspan=\"3\"[^>]*>\s*<a\s+[^>]*href=[\"']{re.escape(report_href)}[\"'][^>]*>\s*{re.escape(target_date)}\s*</a>\s*</td>",
        flags=re.S,
    )
    match = date_cell_re.search(knowledge_log_md)
    if not match:
        raise ValueError(f"knowledge_log_md 中 {target_date} 日期单元格必须使用 <td rowspan=\"3\"> 包裹当天链接。")

    block_start = knowledge_log_md.rfind("<tr", 0, match.start())
    if block_start < 0:
        raise ValueError(f"knowledge_log_md 中 {target_date} 日期块缺少起始 <tr>。")
    next_date_cell = re.search(r"<td\s+[^>]*rowspan=\"3\"", knowledge_log_md[match.end() :], flags=re.S)
    block_end = match.end() + next_date_cell.start() if next_date_cell else knowledge_log_md.find("</table>", match.end())
    if block_end < 0:
        block_end = len(knowledge_log_md)
    target_block = knowledge_log_md[block_start:block_end]
    if len(re.findall(r"<tr\b", target_block)) < 3:
        raise ValueError(f"knowledge_log_md 中 {target_date} 日期块必须至少包含 3 行 <tr>。")


def normalize_text(value, fallback=""):
    return str(value or fallback).strip()


def validate_structured_output(data):
    required = ("main_thread", "overall_summary", "daily_takeaways", "concepts")
    missing = [key for key in required if key not in data]
    if missing:
        raise ValueError(f"LLM 输出缺少必要字段或字段为空: {', '.join(missing)}")
    if not isinstance(data.get("concepts"), list) or len(data["concepts"]) != 3:
        raise ValueError("LLM 输出 concepts 必须包含 3 个概念。")
    if not isinstance(data.get("daily_takeaways"), list) or len(data["daily_takeaways"]) < 3:
        raise ValueError("LLM 输出 daily_takeaways 至少包含 3 条结论。")
    for index, concept in enumerate(data["concepts"], start=1):
        if not isinstance(concept, dict):
            raise ValueError(f"concepts[{index}] 必须是 object。")
        required_concept = (
            "name",
            "domain",
            "difficulty",
            "friendly_explanation",
            "example",
            "connections",
            "questions",
            "one_sentence",
            "next_reference",
        )
        missing_concept = [key for key in required_concept if not concept.get(key)]
        if missing_concept:
            raise ValueError(f"concepts[{index}] 缺少必要字段: {', '.join(missing_concept)}")
        if not re.fullmatch(r"[★☆]{5}", normalize_text(concept.get("difficulty"))):
            raise ValueError(f"concepts[{index}].difficulty 必须是五颗星格式，例如 ★★★☆☆。")
        if not isinstance(concept.get("connections"), list) or not concept["connections"]:
            raise ValueError(f"concepts[{index}].connections 必须是非空数组。")
        if not isinstance(concept.get("questions"), list) or not concept["questions"]:
            raise ValueError(f"concepts[{index}].questions 必须是非空数组。")


def render_list(items, ordered=False):
    lines = []
    for index, item in enumerate(items, start=1):
        prefix = f"{index}." if ordered else "-"
        lines.append(f"{prefix} {normalize_text(item)}")
    return "\n".join(lines)


def render_knowledge_markdown(data, target_date):
    year, month, day = target_date.split("-")
    title = f"# {year}年{int(month)}月{int(day)}日 知识讲解"
    sections = [title, "", "## 今日知识主线", "", normalize_text(data["main_thread"]), "", "---"]
    for index, concept in enumerate(data["concepts"], start=1):
        sections.extend(
            [
                "",
                f"## 概念{index_to_chinese(index)}：{normalize_text(concept['name'])}",
                "",
                f"- **名称**：{normalize_text(concept['name'])}  ",
                f"- **领域**：{normalize_text(concept['domain'])}  ",
                f"- **难度**：{normalize_text(concept['difficulty'])}  ",
                "",
                "### 亲和完整讲解",
                "",
                normalize_text(concept["friendly_explanation"]),
                "",
                "### 有趣事例",
                "",
                normalize_text(concept.get("story"), "这个概念可以结合当天材料中的具体场景来理解。"),
                "",
                "### 常见误区",
                "",
                normalize_text(concept.get("misconception"), "常见误区是只记住术语名称，而忽略它背后的适用边界。"),
                "",
                "### 与前一天工作内容的关系",
                "",
                normalize_text(concept.get("previous_relation"), "它延续了前一天材料中对自动化、结构化和可靠性的关注。"),
                "",
                "### 一个具体例子",
                "",
                normalize_text(concept["example"]),
                "",
                "### 与其他概念的关联",
                "",
                render_list(concept["connections"]),
                "",
                "### 可继续深入学习的问题",
                "",
                render_list(concept["questions"], ordered=True),
                "",
                "---",
            ]
        )
    sections.extend(
        [
            "",
            "## 概念之间的整体关联总结",
            "",
            normalize_text(data["overall_summary"]),
            "",
            "## 适合放入学习日报的精简结论",
            "",
            render_list(data["daily_takeaways"]),
        ]
    )
    return "\n".join(sections).rstrip() + "\n"


def index_to_chinese(index):
    return {1: "一", 2: "二", 3: "三"}.get(index, str(index))


def escape_cell(value):
    return html.escape(normalize_text(value), quote=False)


def build_today_log_rows(data, target_date):
    year_month = target_date[:7]
    report_href = f"../daily_report/{year_month}/{target_date}-learning-report.html"
    rows = []
    for index, concept in enumerate(data["concepts"]):
        first_cell = ""
        if index == 0:
            first_cell = f"""      <td rowspan="3">
        <a href="{report_href}">{target_date}</a>
      </td>
"""
        rows.append(
            "    <tr>\n"
            f"{first_cell}"
            f"      <td>{escape_cell(concept['name'])}</td>\n"
            f"      <td>{escape_cell(concept['domain'])}</td>\n"
            f"      <td>{escape_cell(concept['difficulty']).replace('☆', '')}</td>\n"
            f"      <td>{escape_cell(concept['one_sentence'])}</td>\n"
            f"      <td>{escape_cell(concept['next_reference'])}</td>\n"
            "    </tr>"
        )
    return "\n".join(rows)


def extract_existing_tbody(existing_log):
    match = re.search(r"<tbody>\s*([\s\S]*?)\s*</tbody>", existing_log or "", flags=re.I)
    return match.group(1).strip() if match else ""


def remove_date_block(tbody, target_date):
    if not tbody:
        return ""
    pattern = re.compile(
        rf"\s*<tr>\s*<td\s+rowspan=\"3\">\s*<a\s+href=\"../daily_report/{re.escape(target_date[:7])}/{re.escape(target_date)}-learning-report\.html\">\s*{re.escape(target_date)}\s*</a>\s*</td>[\s\S]*?(?=\n\s*<tr>\s*<td\s+rowspan=\"3\">|\s*$)",
        flags=re.I,
    )
    return pattern.sub("", tbody).strip()


def render_knowledge_log(data, target_date, existing_log):
    year_month = target_date[:7]
    year, month = year_month.split("-")
    existing_tbody = remove_date_block(extract_existing_tbody(existing_log), target_date)
    today_rows = build_today_log_rows(data, target_date)
    body_parts = [today_rows]
    if existing_tbody:
        body_parts.append(existing_tbody)
    tbody = "\n".join(body_parts)
    return f"""# {year}年{int(month)}月教学记录

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
{tbody}
  </tbody>
</table>
"""


def validate_rendered_output(data, target_date, existing_log):
    validate_structured_output(data)
    knowledge_md = render_knowledge_markdown(data, target_date)
    knowledge_log_md = render_knowledge_log(data, target_date, existing_log)
    validate_knowledge_log_html(knowledge_log_md, target_date)
    return {
        "knowledge_explaination_md": knowledge_md,
        "knowledge_log_md": knowledge_log_md,
    }


def generate_validated_output(llm, prompt, target_date, existing_log, timeout, retries, retry_delay):
    def operation():
        raw_content = call_llm(llm, prompt, timeout, 1, 0)
        try:
            data = parse_llm_json(raw_content)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"LLM 输出不是可解析 JSON: {exc}\n{raw_content[:2000]}") from exc
        try:
            return validate_rendered_output(data, target_date, existing_log)
        except ValueError as exc:
            raise RuntimeError(str(exc)) from exc

    return retry_call(
        operation,
        RetryPolicy(attempts=retries, initial_delay=retry_delay, label="知识讲解 LLM 生成与校验"),
    )


def main():
    args = parse_args()
    config = load_json(Path(args.config))
    target_date = resolve_target_date(args.date, config)
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", target_date):
        print("[错误] --date 必须使用 YYYY-MM-DD 格式。")
        sys.exit(1)

    year_month = target_date[:7]
    input_root = Path(args.input_root)
    if not input_root.is_absolute():
        input_root = PROJECT_ROOT / input_root
    daily_dir = input_root / "prework" / year_month / target_date
    concept_path = daily_dir / "concept_relevance.md"
    official_output_path = PROJECT_ROOT / "prework" / year_month / target_date / "knowledge_explaination.md"
    official_log_path = PROJECT_ROOT / "knowledge_log" / f"{year_month}-knowledge-log.md"

    if args.output_root:
        output_root = Path(args.output_root)
        if not output_root.is_absolute():
            output_root = PROJECT_ROOT / output_root
        output_path = output_root / "prework" / year_month / target_date / "knowledge_explaination.md"
        log_path = output_root / "knowledge_log" / f"{year_month}-knowledge-log.md"
    else:
        output_path = official_output_path
        log_path = official_log_path

    llm = require_llm_config(config)
    concept_relevance = read_text(concept_path, required=True)
    existing_log = read_text(official_log_path, required=False)

    prompt = build_prompt(target_date, concept_relevance, existing_log)
    try:
        data = generate_validated_output(llm, prompt, target_date, existing_log, args.timeout, args.llm_retries, args.llm_retry_delay)
    except RuntimeError as exc:
        print(f"[错误] LLM 生成或校验失败: {exc}")
        sys.exit(1)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(data["knowledge_explaination_md"].rstrip() + "\n", encoding="utf-8")
    log_path.write_text(data["knowledge_log_md"].rstrip() + "\n", encoding="utf-8")

    print(f"[完成] 已生成: {output_path}")
    print(f"[完成] 已更新: {log_path}")


if __name__ == "__main__":
    main()
