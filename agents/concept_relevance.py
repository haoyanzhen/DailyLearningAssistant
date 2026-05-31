#!/usr/bin/env python3
"""Generate concept_relevance.md from daily work summaries.

This is the second independent local agent. It validates upstream
work_summary files, calls the configured chat LLM to extract concepts and
relationships, then records its run status in the shared daily run_status.json.
"""

from __future__ import annotations

import argparse
from html.parser import HTMLParser
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from orchestrator.llm import LLMRetryPolicy, call_chat_completion
from orchestrator.question_threads import QuestionThreadSelection, collect_recent_open_questions, render_questions_for_prompt


@dataclass
class InputSummary:
    repo: str
    path: Path
    content: str


@dataclass
class ReviewSource:
    source_date: str
    concept_path: Path
    concept_content: str
    knowledge_log_path: Path
    knowledge_log_content: str
    avoided_concepts: list[str]
    log_entries: list[dict]


class TableCellParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self.current_row: list[str] | None = None
        self.current_cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self.current_row = []
        elif tag == "td" and self.current_row is not None:
            self.current_cell = []

    def handle_data(self, data: str) -> None:
        if self.current_cell is not None:
            self.current_cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "td" and self.current_cell is not None and self.current_row is not None:
            text = " ".join("".join(self.current_cell).split())
            self.current_row.append(text)
            self.current_cell = None
        elif tag == "tr" and self.current_row is not None:
            if self.current_row:
                self.rows.append(self.current_row)
            self.current_row = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate concept_relevance.md from daily work summaries.")
    parser.add_argument("--date", help="Target date in YYYY-MM-DD format. Defaults to today in configured timezone.")
    parser.add_argument("--config", default=str(PROJECT_ROOT / "config.json"), help="Config JSON path.")
    parser.add_argument("--input-root", default=str(PROJECT_ROOT), help="Root to read prework/YYYY-MM/YYYY-MM-DD from.")
    parser.add_argument("--output-root", default=str(PROJECT_ROOT), help="Root to write prework/YYYY-MM/YYYY-MM-DD to.")
    parser.add_argument("--timezone", help="Timezone override, e.g. Asia/Shanghai.")
    parser.add_argument("--timeout", type=int, default=180, help="LLM request timeout in seconds.")
    parser.add_argument("--llm-retries", type=int, default=3, help="Maximum LLM attempts.")
    parser.add_argument("--llm-retry-delay", type=float, default=3.0, help="Initial LLM retry delay in seconds.")
    return parser.parse_args()


def load_config(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"[错误] 配置文件不存在: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
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


def resolve_timezone(args: argparse.Namespace, config: dict) -> ZoneInfo:
    timezone_name = args.timezone or (config.get("schedule") or {}).get("timezone") or "Asia/Shanghai"
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        raise SystemExit(f"[错误] 未识别的时区: {timezone_name}")


def resolve_target_date(args: argparse.Namespace, timezone: ZoneInfo) -> str:
    if args.date:
        try:
            datetime.strptime(args.date, "%Y-%m-%d")
        except ValueError:
            raise SystemExit("[错误] --date 必须使用 YYYY-MM-DD 格式。")
        return args.date
    return datetime.now(timezone).date().isoformat()


def relative_to_root(path: Path, root: Path = PROJECT_ROOT) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def load_status_file(path: Path, target_date: str) -> dict:
    if not path.exists():
        return {"date": target_date, "agents": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"date": target_date, "agents": {}}
    if not isinstance(data, dict):
        return {"date": target_date, "agents": {}}
    data.setdefault("date", target_date)
    data.setdefault("agents", {})
    if not isinstance(data["agents"], dict):
        data["agents"] = {}
    return data


def write_agent_status(status_path: Path, target_date: str, agent_status: dict, now_iso: str) -> None:
    status_data = load_status_file(status_path, target_date)
    status_data["date"] = target_date
    status_data["updated_at"] = now_iso
    status_data.setdefault("agents", {})
    status_data["agents"]["concept_relevance"] = agent_status

    status_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = status_path.with_suffix(".json.tmp")
    temp_path.write_text(json.dumps(status_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp_path.replace(status_path)


def validate_inputs(input_dir: Path) -> tuple[list[InputSummary], list[str]]:
    summaries: list[InputSummary] = []
    problems: list[str] = []

    paths = sorted(input_dir.glob("work_summary_*.md"))
    if not paths:
        return [], [f"{input_dir} 中没有 work_summary_*.md 输入文件"]

    for path in paths:
        repo = path.stem.removeprefix("work_summary_")
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as exc:
            problems.append(f"{path} 不可读取: {exc}")
            continue
        if not content.strip():
            problems.append(f"{path} 为空")
            continue
        summaries.append(InputSummary(repo=repo, path=path, content=content))

    return summaries, problems


def has_nonempty_file(path: Path) -> bool:
    try:
        return path.exists() and bool(path.read_text(encoding="utf-8").strip())
    except OSError:
        return False


def unique_roots(*roots: Path) -> list[Path]:
    seen: set[Path] = set()
    result: list[Path] = []
    for root in roots:
        resolved = root.expanduser().resolve()
        if resolved not in seen:
            seen.add(resolved)
            result.append(resolved)
    return result


def daily_work_has_no_changes(status_data: dict) -> bool:
    daily = (status_data.get("agents") or {}).get("daily_work_summary") or {}
    if daily.get("status") not in {"success", "partial_success"}:
        return False
    repositories = daily.get("repositories") or []
    return bool(repositories) and all(repo.get("evidence_type") == "no_change" for repo in repositories)


def extract_log_entries_for_date(log_content: str, source_date: str) -> list[dict]:
    parser = TableCellParser()
    parser.feed(log_content)
    entries: list[dict] = []
    active_date: str | None = None
    for row in parser.rows:
        if not row:
            continue
        first_date = re.search(r"\d{4}-\d{2}-\d{2}", row[0])
        if first_date:
            active_date = first_date.group(0)
            cells = row[1:]
        else:
            cells = row
        if active_date != source_date or len(cells) < 4:
            continue
        entries.append(
            {
                "concept": cells[0],
                "domain": cells[1] if len(cells) > 1 else "",
                "difficulty": cells[2] if len(cells) > 2 else "",
                "summary": cells[3] if len(cells) > 3 else "",
                "follow_up": cells[4] if len(cells) > 4 else "",
            }
        )
    return entries


def extract_concept_candidates(concept_content: str) -> list[str]:
    concepts: list[str] = []
    in_concept_list = False
    for line in concept_content.splitlines():
        if re.search(r"^##\s*概念\s*清单", line):
            in_concept_list = True
            continue
        if in_concept_list and line.startswith("## "):
            break
        if not in_concept_list:
            continue
        match = re.search(r"^\s*\d+[.)、]\s+\*\*(.+?)\*\*", line)
        if not match:
            match = re.search(r"^\s*[-*]\s+\*\*(.+?)\*\*", line)
        if match:
            concepts.append(match.group(1).strip())
    return concepts


def normalize_concept_name(value: str) -> str:
    return re.sub(r"\s+", "", value).lower()


def filter_available_candidates(candidates: list[str], avoided_concepts: list[str]) -> list[str]:
    avoided = {normalize_concept_name(name) for name in avoided_concepts}
    return [name for name in candidates if normalize_concept_name(name) not in avoided]


def find_recent_review_source(target_date: str, roots: list[Path]) -> ReviewSource | None:
    target = datetime.strptime(target_date, "%Y-%m-%d").date()
    for offset in range(1, 370):
        candidate = (target - timedelta(days=offset)).isoformat()
        year_month = candidate[:7]
        for root in roots:
            concept_path = root / "prework" / year_month / candidate / "concept_relevance.md"
            log_path = root / "knowledge_log" / f"{year_month}-knowledge-log.md"
            if not (has_nonempty_file(concept_path) and has_nonempty_file(log_path)):
                continue
            concept_content = concept_path.read_text(encoding="utf-8")
            log_content = log_path.read_text(encoding="utf-8")
            entries = extract_log_entries_for_date(log_content, candidate)
            avoided = [entry["concept"] for entry in entries if entry.get("concept")]
            return ReviewSource(
                source_date=candidate,
                concept_path=concept_path,
                concept_content=concept_content,
                knowledge_log_path=log_path,
                knowledge_log_content=log_content,
                avoided_concepts=avoided,
                log_entries=entries,
            )
    return None


def render_log_entries(entries: list[dict]) -> str:
    if not entries:
        return "最近有效日知识日志中未解析到该日的具体讲解条目。"
    lines = []
    for index, entry in enumerate(entries, start=1):
        lines.append(
            "\n".join(
                [
                    f"{index}. 概念：{entry.get('concept') or '未命名'}",
                    f"   - 领域：{entry.get('domain') or '未记录'}",
                    f"   - 摘要：{entry.get('summary') or '未记录'}",
                    f"   - 后续：{entry.get('follow_up') or '未记录'}",
                ]
            )
        )
    return "\n".join(lines)


def review_source_status(source: ReviewSource | None, input_root: Path) -> dict:
    if not source:
        return {"status": "missing"}
    candidates = extract_concept_candidates(source.concept_content)
    available_candidates = filter_available_candidates(candidates, source.avoided_concepts)
    return {
        "status": "selected",
        "source_date": source.source_date,
        "source_concept_path": relative_to_root(source.concept_path, input_root),
        "source_knowledge_log_path": relative_to_root(source.knowledge_log_path, input_root),
        "avoided_concepts": source.avoided_concepts,
        "avoided_count": len(source.avoided_concepts),
        "candidate_count": len(candidates),
        "available_candidate_count": len(available_candidates),
        "log_entry_count": len(source.log_entries),
    }


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


def call_llm(llm: dict, prompt: str, timeout: int) -> str:
    return call_chat_completion(
        llm,
        [{"role": "user", "content": prompt}],
        timeout=timeout,
        retry_policy=LLMRetryPolicy(attempts=1, initial_delay=0),
        temperature=llm.get("temperature", 0.45),
    )


def question_thread_status(selection: QuestionThreadSelection, root: Path) -> dict:
    return {
        "status": selection.status,
        "files": [relative_to_root(Path(path), root) for path in selection.files],
        "open_count": selection.open_count,
        "selected_count": selection.selected_count,
        "selected_ids": [item.get("id") for item in selection.questions],
    }


def build_prompt(target_date: str, summaries: list[InputSummary], input_root: Path, question_selection: QuestionThreadSelection) -> str:
    files_block = "\n".join(
        f"- `{relative_to_root(summary.path, input_root)}`（仓库：{summary.repo}）" for summary in summaries
    )
    content_blocks = "\n\n".join(
        f"## 输入：{summary.repo}\n\n来源文件：`{relative_to_root(summary.path, input_root)}`\n\n```markdown\n{summary.content}\n```"
        for summary in summaries
    )
    question_threads_block = render_questions_for_prompt(question_selection)

    return f"""你是“有过工程经验的专职科普老师”，但本任务的边界非常明确：只做概念与知识点提炼，不生成教学教案、讲解顺序、学习路径、练习题或教学建议。请阅读当天全部仓库的前一日更改总结，从中提炼数学、物理、计算机科学、软件工程以及大语言模型相关的概念，并梳理概念之间自然、连贯的知识关系。

目标日期：{target_date}

输入文件列表：
{files_block}

硬性边界：
- 只能基于下面提供的当日 `work_summary_*.md` 内容提炼，不要读取或引用其他日期内容。
- “最近 7 天 open 问题”只作为历史学习线索，用来判断当天概念是否能自然回应或延伸旧问题；不得把旧问题伪装成当天新增工作、当天新概念或当天已确认事实。
- 不要编造与当日工作无关的概念。
- 如果某个领域在更改总结中没有明确线索，应写“未发现明确线索”，不要强行凑概念。
- 概念名称要准确、可解释，避免只写“代码”“学习”“工具”等宽泛词。
- 概念关系必须说明原因，不能只列两个词。
- 如果某个仓库写明“当日无变更”，应在核心主题总览中说明它没有新增技术线索，不要从该仓库强行提炼概念。
- 如果输入提到“待确认变化线索”，必须明确其不是已确认提交事实；可以作为候选线索，但需要标注“待确认”。
- 输出必须是完整 Markdown 文件内容，不要输出 JSON，不要包裹 markdown 代码块。
- 输出重心应放在“当天材料中能确认哪些概念、这些概念属于什么领域、概念之间为什么有关”，而不是项目管理、工程交付复盘或教学设计。
- 软件工程类概念也要转写成理论化的知识点，例如“前置条件背后的契约思想”“文件接口如何形成系统边界”“LLM 输出可靠性与证据约束的关系”，避免只写“完成了某项工程实践”。
- 不要输出练习题、训练任务、作业、实践项目、验收标准、能力编号表、教学计划、讲解顺序、学习路径、推荐课程或后续教学建议。
- 尽量保留人工整理感：语言应像一位老师在整理当天值得讲清楚的知识线索，允许有适度的取舍、解释和过渡，不要写成模板化的项目报告。

输出文件必须包含：
- 日期
- 输入文件列表
- 当日核心主题总览
- 概念清单
- 分领域线索（数学、物理、计算机科学、软件工程、大语言模型）
- 跨领域关联图（放在“分领域线索”之后，用文本图或 Mermaid 展示领域与概念之间的整体关联）
- 概念关联图谱或关联表
- 最近 open 问题与当天概念的关联：如果没有稳定关联，写“最近 7 天 open 问题未发现与当天材料的稳定关联”；如果有关联，必须写清历史问题、来源日期、当天相关概念、关联原因、是否适合进入后续知识讲解。
- 详细关联描述
- 可供后续知识讲解使用的概念候选摘要（只列候选概念和依据，不写教学建议）

最近 7 天 open 问题如下：

{question_threads_block}

当天 work summary 输入如下：

{content_blocks}
"""


def build_no_change_review_prompt(
    target_date: str,
    summaries: list[InputSummary],
    input_root: Path,
    question_selection: QuestionThreadSelection,
    review_source: ReviewSource,
) -> str:
    files_block = "\n".join(
        f"- `{relative_to_root(summary.path, input_root)}`（仓库：{summary.repo}）" for summary in summaries
    )
    evidence_blocks = "\n\n".join(
        f"## 当日无变更证据：{summary.repo}\n\n来源文件：`{relative_to_root(summary.path, input_root)}`\n\n```markdown\n{summary.content}\n```"
        for summary in summaries
    )
    question_threads_block = render_questions_for_prompt(question_selection)
    log_entries_block = render_log_entries(review_source.log_entries)
    avoided_block = "\n".join(f"- {name}" for name in review_source.avoided_concepts) or "- 未解析到需要避开的已讲概念"
    candidates = extract_concept_candidates(review_source.concept_content)
    available_candidates = filter_available_candidates(candidates, review_source.avoided_concepts)
    candidate_block = "\n".join(f"- {name}" for name in available_candidates) or "- 最近有效日概念候选均已讲过，请围绕 open 问题做问题延展。"

    return f"""你是“有过工程经验的专职科普老师”，本任务处于无变更日复习选题模式。今天的 Git 证据显示全部仓库没有新增变化，因此不要把今天写成新增工程进展；你的任务是基于最近有效日的概念关联文件、最近 7 天 open 问题和最近有效日知识日志，生成今天新的 `concept_relevance.md`，为后续知识讲解提供不同于上一日的复习、深化或延展主题。

目标日期：{target_date}
复习来源日期：{review_source.source_date}

当日 work summary 输入文件列表（只作为无新增变化证据）：
{files_block}

最近有效日概念关联文件：`{relative_to_root(review_source.concept_path, input_root)}`
最近有效日知识日志：`{relative_to_root(review_source.knowledge_log_path, input_root)}`

硬性边界：
- 今天是无变更日；不得宣称今天发生了新的提交、新的实现、新的项目进展或新的技术事实。
- 当日 `work_summary_*.md` 只用于确认无新增变化，不作为新概念来源。
- 必须避开“最近有效日知识日志已讲概念”中的概念标题，不要把这些标题作为今天最终选中的知识讲解概念。
- 如果候选概念只是已讲概念的近义改写、上位/下位表述或同一主题换名，也视为已讲过，应继续避开。
- 优先从“最近有效日概念候选”中尚未讲过的候选概念里选择今天的概念。
- 如果可选候选概念不足，应围绕最近 7 天 open 问题做问题延展，生成标题不同、角度不同的新深入概念。
- “最近 7 天 open 问题”可以关联已讲过概念，但问题表述、探讨方向和候选概念标题必须与最近有效日知识日志有所区分。
- 不要输出练习题、训练任务、作业、实践项目、验收标准、能力编号表、教学计划、讲解顺序、学习路径、推荐课程或后续教学建议。
- 输出必须是完整 Markdown 文件内容，不要输出 JSON，不要包裹 markdown 代码块。
- 输出重心应放在“复习日可继续讲清楚哪些不同概念、这些概念与来源概念和 open 问题为什么有关”，而不是项目管理或交付复盘。

输出文件必须包含：
- 日期
- 输入文件列表
- 当日核心主题总览，并明确说明今天是无变更复习日
- 概念清单
- 分领域线索（数学、物理、计算机科学、软件工程、大语言模型）
- 跨领域关联图（放在“分领域线索”之后，用文本图或 Mermaid 展示领域与概念之间的整体关联）
- 概念关联图谱或关联表
- 最近 open 问题与当天概念的关联：如果没有稳定关联，写“最近 7 天 open 问题未发现与当天复习概念的稳定关联”；如果有关联，必须写清历史问题、来源日期、当天相关概念、关联原因、是否适合进入后续知识讲解
- 详细关联描述
- 可供后续知识讲解使用的概念候选摘要（只列候选概念和依据，不写教学建议）

最近有效日知识日志已讲概念（今天应避开这些标题）：
{avoided_block}

最近有效日知识日志讲解历史：
{log_entries_block}

最近有效日中尚未讲过的概念候选：
{candidate_block}

最近 7 天 open 问题如下：

{question_threads_block}

最近有效日 concept_relevance.md 全文如下：

```markdown
{review_source.concept_content}
```

当日 work summary 无变更证据如下：

{evidence_blocks}
"""


def validate_output(content: str) -> list[str]:
    required_sections = [
        ("概念清单", re.compile(r"概念\s*清单")),
        ("当日核心主题", re.compile(r"当日\s*核心\s*主题")),
        ("跨领域关联", re.compile(r"跨领域\s*关联")),
        (
            "最近 open 问题",
            re.compile(
                r"(?:最近|过去|历史)\s*(?:\d+|[一二三四五六七八九十]+)?\s*(?:天|日)?\s*open\s*问题|"
                r"open\s*问题\s*与\s*当天\s*概念|"
                r"问题\s*与\s*当天\s*概念\s*的?\s*关联",
                re.IGNORECASE,
            ),
        ),
        ("详细关联", re.compile(r"详细\s*关联")),
    ]
    problems = [label for label, pattern in required_sections if not pattern.search(content)]
    if not content.strip():
        problems.append("输出为空")
    return problems


def generate_valid_content(llm: dict, prompt: str, timeout: int, retries: int, retry_delay: float) -> str:
    attempts = max(1, retries)
    delay = max(0.0, retry_delay)
    errors: list[str] = []
    for attempt in range(1, attempts + 1):
        try:
            content = strip_markdown_fence(call_llm(llm, prompt, timeout))
            output_problems = validate_output(content)
            if output_problems:
                raise RuntimeError(f"LLM 输出缺少必要章节: {', '.join(output_problems)}")
            return content
        except RuntimeError as exc:
            errors.append(str(exc))
            if attempt >= attempts:
                break
            wait_seconds = delay * (2 ** (attempt - 1))
            print(f"[重试] 概念提炼生成失败，第 {attempt}/{attempts} 次：{exc}")
            print(f"[重试] 等待 {wait_seconds:.1f} 秒后再次尝试。")
            if wait_seconds:
                time.sleep(wait_seconds)
    raise RuntimeError("; ".join(errors[-3:]))


def main() -> int:
    args = parse_args()
    config = load_config(Path(args.config))
    llm = require_llm_config(config)
    timezone = resolve_timezone(args, config)
    target_date = resolve_target_date(args, timezone)
    started_at = datetime.now(timezone).isoformat()

    input_root = Path(os.path.expanduser(args.input_root)).resolve()
    output_root = Path(os.path.expanduser(args.output_root)).resolve()
    input_dir = input_root / "prework" / target_date[:7] / target_date
    output_dir = output_root / "prework" / target_date[:7] / target_date
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "concept_relevance.md"
    status_path = output_dir / "run_status.json"
    status_data = load_status_file(status_path, target_date)
    no_change_day = daily_work_has_no_changes(status_data)
    mode = "no_change_review" if no_change_day else "normal"
    review_source: ReviewSource | None = None
    review_status: dict = {"status": "not_applicable"}

    try:
        question_selection = collect_recent_open_questions(input_root, target_date, days=7)
        question_status = question_thread_status(question_selection, input_root)
    except (ValueError, OSError) as exc:
        finished_at = datetime.now(timezone).isoformat()
        question_status = {
            "status": "invalid",
            "files": [],
            "open_count": 0,
            "selected_count": 0,
            "selected_ids": [],
            "error": str(exc),
        }
        write_agent_status(
            status_path,
            target_date,
            {
                "status": "failed",
                "started_at": started_at,
                "finished_at": finished_at,
                "timezone": str(timezone),
                "input_dir": relative_to_root(input_dir, input_root),
                "output_path": relative_to_root(output_path, output_root),
                "mode": mode,
                "day_context": {
                    "no_change_day": no_change_day,
                    "reason": "daily_work_summary_all_repositories_no_change" if no_change_day else None,
                },
                "review_source": review_status,
                "question_threads": question_status,
                "llm": {
                    "enabled": True,
                    "configured": True,
                    "model": llm.get("model"),
                    "retries": args.llm_retries,
                    "retry_delay_seconds": args.llm_retry_delay,
                    "status": "skipped_question_threads_invalid",
                    "error": None,
                },
                "inputs": [],
                "problems": [str(exc)],
            },
            finished_at,
        )
        print(f"[错误] 历史问题线程不可用，停止生成 concept_relevance.md。原因：{exc}")
        return 1

    summaries, input_problems = validate_inputs(input_dir)
    if input_problems:
        finished_at = datetime.now(timezone).isoformat()
        write_agent_status(
            status_path,
            target_date,
            {
                "status": "failed",
                "started_at": started_at,
                "finished_at": finished_at,
                "timezone": str(timezone),
                "input_dir": relative_to_root(input_dir, input_root),
                "output_path": relative_to_root(output_path, output_root),
                "mode": mode,
                "day_context": {
                    "no_change_day": no_change_day,
                    "reason": "daily_work_summary_all_repositories_no_change" if no_change_day else None,
                },
                "review_source": review_status,
                "question_threads": question_status,
                "llm": {
                    "enabled": True,
                    "configured": True,
                    "model": llm.get("model"),
                    "retries": args.llm_retries,
                    "retry_delay_seconds": args.llm_retry_delay,
                    "status": "skipped_input_invalid",
                    "error": None,
                },
                "inputs": [
                    {
                        "repo": summary.repo,
                        "path": relative_to_root(summary.path, input_root),
                        "chars": len(summary.content),
                    }
                    for summary in summaries
                ],
                "problems": input_problems,
            },
            finished_at,
        )
        print("[错误] 上游 work summary 输入不完整，停止生成 concept_relevance.md。")
        for problem in input_problems:
            print(f"- {problem}")
        return 1

    if no_change_day:
        review_source = find_recent_review_source(
            target_date,
            unique_roots(input_root, output_root, PROJECT_ROOT),
        )
        review_status = review_source_status(review_source, input_root)
        if review_source is None:
            problem = "无变更日复习选题需要最近有效 concept_relevance.md 和对应 knowledge_log，但未找到可用来源。"
            finished_at = datetime.now(timezone).isoformat()
            write_agent_status(
                status_path,
                target_date,
                {
                    "status": "failed",
                    "started_at": started_at,
                    "finished_at": finished_at,
                    "timezone": str(timezone),
                    "input_dir": relative_to_root(input_dir, input_root),
                    "output_path": relative_to_root(output_path, output_root),
                    "mode": mode,
                    "day_context": {
                        "no_change_day": no_change_day,
                        "reason": "daily_work_summary_all_repositories_no_change",
                    },
                    "review_source": review_status,
                    "question_threads": question_status,
                    "llm": {
                        "enabled": True,
                        "configured": True,
                        "model": llm.get("model"),
                        "retries": args.llm_retries,
                        "retry_delay_seconds": args.llm_retry_delay,
                        "status": "skipped_review_source_missing",
                        "error": None,
                    },
                    "inputs": [
                        {
                            "repo": summary.repo,
                            "path": relative_to_root(summary.path, input_root),
                            "chars": len(summary.content),
                        }
                        for summary in summaries
                    ],
                    "problems": [problem],
                },
                finished_at,
            )
            print(f"[错误] {problem}")
            return 1
        prompt = build_no_change_review_prompt(target_date, summaries, input_root, question_selection, review_source)
    else:
        prompt = build_prompt(target_date, summaries, input_root, question_selection)

    llm_status = "success"
    llm_error = None
    output_problems: list[str] = []

    try:
        content = generate_valid_content(llm, prompt, args.timeout, args.llm_retries, args.llm_retry_delay)
    except RuntimeError as exc:
        llm_status = "failed"
        llm_error = str(exc)
        finished_at = datetime.now(timezone).isoformat()
        write_agent_status(
            status_path,
            target_date,
            {
                "status": "failed",
                "started_at": started_at,
                "finished_at": finished_at,
                "timezone": str(timezone),
                "input_dir": relative_to_root(input_dir, input_root),
                "output_path": relative_to_root(output_path, output_root),
                "mode": mode,
                "day_context": {
                    "no_change_day": no_change_day,
                    "reason": "daily_work_summary_all_repositories_no_change" if no_change_day else None,
                },
                "review_source": review_status,
                "question_threads": question_status,
                "llm": {
                    "enabled": True,
                    "configured": True,
                    "model": llm.get("model"),
                    "retries": args.llm_retries,
                    "retry_delay_seconds": args.llm_retry_delay,
                    "status": llm_status,
                    "error": llm_error,
                },
                "inputs": [
                    {
                        "repo": summary.repo,
                        "path": relative_to_root(summary.path, input_root),
                        "chars": len(summary.content),
                    }
                    for summary in summaries
                ],
                "problems": output_problems,
            },
            finished_at,
        )
        print(f"[错误] LLM 概念提炼失败，未生成 concept_relevance.md。原因：{exc}")
        return 1

    output_path.write_text(content.rstrip() + "\n", encoding="utf-8")
    finished_at = datetime.now(timezone).isoformat()
    write_agent_status(
        status_path,
        target_date,
        {
            "status": "success",
            "started_at": started_at,
            "finished_at": finished_at,
            "timezone": str(timezone),
            "input_dir": relative_to_root(input_dir, input_root),
            "output_path": relative_to_root(output_path, output_root),
            "mode": mode,
            "day_context": {
                "no_change_day": no_change_day,
                "reason": "daily_work_summary_all_repositories_no_change" if no_change_day else None,
            },
            "review_source": review_status,
            "question_threads": question_status,
            "llm": {
                "enabled": True,
                "configured": True,
                "model": llm.get("model"),
                "retries": args.llm_retries,
                "retry_delay_seconds": args.llm_retry_delay,
                "status": llm_status,
                "error": llm_error,
            },
            "inputs": [
                {
                    "repo": summary.repo,
                    "path": relative_to_root(summary.path, input_root),
                    "chars": len(summary.content),
                }
                for summary in summaries
            ],
            "output": {
                "chars": len(content),
            },
            "problems": [],
        },
        finished_at,
    )
    print(f"[完成] 已生成: {output_path}")
    print(f"[状态] 已更新: {status_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
