#!/usr/bin/env python3
"""Generate daily knowledge explanations with the configured chat LLM.

The script is intentionally small and dependency-free so it can run in the
same automation environment as the other daily tasks.
"""

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate knowledge_explaination.md and monthly knowledge log with config.json llm settings."
    )
    parser.add_argument("--date", help="Target date in YYYY-MM-DD format. Defaults to schedule.timezone today.")
    parser.add_argument("--config", default=str(PROJECT_ROOT / "config.json"), help="Path to config JSON.")
    parser.add_argument(
        "--output-root",
        help="Optional test output root. When set, generated files are written under this directory.",
    )
    parser.add_argument("--timeout", type=int, default=120, help="LLM request timeout in seconds.")
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


def build_prompt(target_date, concept_relevance, existing_log):
    year_month = target_date[:7]
    return f"""你是“亲和的知识讲解专业老师”。请根据当天的概念与关联文件，从易到难选择三个概念进行完整讲解，并更新当月教学记录。

目标日期：{target_date}
目标月份：{year_month}

输入一：当天概念与关联文件 concept_relevance.md

```markdown
{concept_relevance}
```

输入二：当月已有教学记录 knowledge_log（可能为空）

```markdown
{existing_log or "(当月教学记录尚不存在)"}
```

请完成两份文件：

1. `knowledge_explaination_md`
   - 保存为 `./prework/{year_month}/{target_date}/knowledge_explaination.md`
   - 使用 Markdown。
   - 包含：日期、今日知识主线、三个概念的详细讲解、概念之间的整体关联总结、适合放入学习日报的精简结论。
   - 每个概念必须包含：概念名称、领域、五颗星难度评级、亲和完整讲解、有趣事例（可选）、常见误区（可选）、与前一天工作内容的关系（可选）、一个具体例子、与其他概念的关联、可继续深入学习的问题。
   - 面向仅有高中基础知识的读者，讲清底层理念、原理和逻辑。
   - 不要为了生动牺牲技术正确性；不确定处写“这里基于当日材料可确认的是……”。
   - 只能基于当天 concept_relevance.md 中可确认的概念与关联展开，不要把历史主题伪装成当天新内容。

2. `knowledge_log_md`
   - 保存为 `./knowledge_log/{year_month}-knowledge-log.md`
   - 返回当月教学记录的完整文件内容，不是增量片段。
   - 文件标题使用 `# YYYY年M月教学记录`。
   - 表格必须使用 HTML `<table>`，字段固定为：`日期`、`概念`、`领域`、`难度`、`一句话解释`、`下一次讲解参考`。
   - 每天固定 3 行，日期列用 `rowspan="3"` 合并。
   - 日期文字必须链接到 `../daily_report/{year_month}/{target_date}-learning-report.html`。
   - 如果已有同一天记录，应更新该日期块，不要重复追加。
   - 当月表格按日期倒序排列，最新日期在最上方。
   - `一句话解释` 简明，适合主页表格阅读；不要把完整长篇讲解塞进教学记录。

严格输出 JSON，不要输出 markdown 代码块，不要输出解释文字。JSON schema:

{{
  "knowledge_explaination_md": "完整 Markdown 文件内容",
  "knowledge_log_md": "完整 Markdown/HTML 教学记录文件内容"
}}
"""


def call_llm(llm, prompt, timeout):
    payload = {
        "model": llm["model"],
        "temperature": llm.get("temperature", 0.7),
        "messages": [{"role": "user", "content": prompt}],
    }
    if llm.get("max_tokens"):
        payload["max_tokens"] = llm["max_tokens"]
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(llm["api_url"], data=body, method="POST")
    req.add_header("Authorization", f"Bearer {llm['api_key']}")
    req.add_header("content-type", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        print(f"[错误] LLM HTTP 调用失败: {exc.code} {exc.reason}\n{detail}")
        sys.exit(1)
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        print(f"[错误] LLM 调用失败: {exc}")
        sys.exit(1)

    try:
        return result["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        print("[错误] LLM 响应格式不符合 chat completions 约定。")
        print(json.dumps(result, ensure_ascii=False)[:2000])
        sys.exit(1)


def validate_output(data):
    required = ("knowledge_explaination_md", "knowledge_log_md")
    missing = [key for key in required if not isinstance(data.get(key), str) or not data[key].strip()]
    if missing:
        print(f"[错误] LLM 输出缺少必要字段或字段为空: {', '.join(missing)}")
        sys.exit(1)

    if "<table" not in data["knowledge_log_md"] or "rowspan=\"3\"" not in data["knowledge_log_md"]:
        print("[错误] LLM 输出的 knowledge_log_md 不符合 HTML 表格记录要求。")
        sys.exit(1)


def main():
    args = parse_args()
    config = load_json(Path(args.config))
    target_date = resolve_target_date(args.date, config)
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", target_date):
        print("[错误] --date 必须使用 YYYY-MM-DD 格式。")
        sys.exit(1)

    year_month = target_date[:7]
    daily_dir = PROJECT_ROOT / "prework" / year_month / target_date
    concept_path = daily_dir / "concept_relevance.md"
    official_output_path = daily_dir / "knowledge_explaination.md"
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
    raw_content = call_llm(llm, prompt, args.timeout)
    try:
        data = parse_llm_json(raw_content)
    except json.JSONDecodeError as exc:
        print(f"[错误] LLM 输出不是可解析 JSON: {exc}")
        print(raw_content[:2000])
        sys.exit(1)

    validate_output(data)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(data["knowledge_explaination_md"].rstrip() + "\n", encoding="utf-8")
    log_path.write_text(data["knowledge_log_md"].rstrip() + "\n", encoding="utf-8")

    print(f"[完成] 已生成: {output_path}")
    print(f"[完成] 已更新: {log_path}")


if __name__ == "__main__":
    main()
