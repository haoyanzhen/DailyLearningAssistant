#!/usr/bin/env python3
"""Generate concept_relevance.md from daily work summaries.

This is the second independent local agent. It validates upstream
work_summary files, calls the configured chat LLM to extract concepts and
relationships, then records its run status in the shared daily run_status.json.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime
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
