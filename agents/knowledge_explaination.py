#!/usr/bin/env python3
"""Run the third local agent: knowledge explanation generation.

This agent validates concept_relevance.md, delegates generation to the existing
scripts/generate_knowledge_explaination.py LLM workflow, and records shared
daily run status.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


PROJECT_ROOT = Path(__file__).resolve().parent.parent
GENERATOR_SCRIPT = PROJECT_ROOT / "scripts" / "generate_knowledge_explaination.py"
sys.path.insert(0, str(PROJECT_ROOT))
from orchestrator.question_threads import load_question_threads, question_thread_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate knowledge_explaination.md via the configured LLM script.")
    parser.add_argument("--date", help="Target date in YYYY-MM-DD format. Defaults to today in configured timezone.")
    parser.add_argument("--config", default=str(PROJECT_ROOT / "config.json"), help="Config JSON path.")
    parser.add_argument("--input-root", default=str(PROJECT_ROOT), help="Root to read prework/YYYY-MM/YYYY-MM-DD from.")
    parser.add_argument("--output-root", default=str(PROJECT_ROOT), help="Root to write generated files to.")
    parser.add_argument("--timezone", help="Timezone override, e.g. Asia/Shanghai.")
    parser.add_argument("--timeout", type=int, default=180, help="LLM request timeout in seconds.")
    parser.add_argument("--llm-retries", type=int, default=3, help="Maximum LLM generation attempts.")
    parser.add_argument("--llm-retry-delay", type=float, default=3.0, help="Initial LLM retry delay in seconds.")
    return parser.parse_args()


def load_config(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"[错误] 配置文件不存在: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"[错误] 配置文件不是合法 JSON: {path} ({exc})")


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
    status_data["agents"]["knowledge_explaination"] = agent_status

    status_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = status_path.with_suffix(".json.tmp")
    temp_path.write_text(json.dumps(status_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp_path.replace(status_path)


def validate_concept_input(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"{path} 不存在")
    content = path.read_text(encoding="utf-8")
    if not content.strip():
        raise ValueError(f"{path} 为空")
    return content


def parse_question_thread_result(stdout: str) -> dict | None:
    for line in stdout.splitlines():
        if not line.startswith("[question_threads] "):
            continue
        try:
            return json.loads(line.removeprefix("[question_threads] "))
        except json.JSONDecodeError:
            return None
    return None


def main() -> int:
    args = parse_args()
    config_path = Path(args.config)
    config = load_config(config_path)
    timezone = resolve_timezone(args, config)
    target_date = resolve_target_date(args, timezone)
    started_at = datetime.now(timezone).isoformat()
    year_month = target_date[:7]

    input_root = Path(os.path.expanduser(args.input_root)).resolve()
    output_root = Path(os.path.expanduser(args.output_root)).resolve()
    input_dir = input_root / "prework" / year_month / target_date
    output_dir = output_root / "prework" / year_month / target_date
    output_dir.mkdir(parents=True, exist_ok=True)

    concept_path = input_dir / "concept_relevance.md"
    knowledge_path = output_dir / "knowledge_explaination.md"
    knowledge_log_path = output_root / "knowledge_log" / f"{year_month}-knowledge-log.md"
    question_threads_path = question_thread_path(output_root, year_month)
    status_path = output_dir / "run_status.json"

    try:
        concept_content = validate_concept_input(concept_path)
    except (FileNotFoundError, ValueError, OSError) as exc:
        finished_at = datetime.now(timezone).isoformat()
        write_agent_status(
            status_path,
            target_date,
            {
                "status": "failed",
                "started_at": started_at,
                "finished_at": finished_at,
                "timezone": str(timezone),
                "input_path": relative_to_root(concept_path, input_root),
                "output_path": relative_to_root(knowledge_path, output_root),
                "knowledge_log_path": relative_to_root(knowledge_log_path, output_root),
                "question_threads": {
                    "path": relative_to_root(question_threads_path, output_root),
                    "status": "skipped_input_invalid",
                    "upserted": 0,
                    "today_questions": 0,
                },
                "generator": relative_to_root(GENERATOR_SCRIPT),
                "llm": {
                    "enabled": True,
                    "status": "skipped_input_invalid",
                    "error": None,
                },
                "problems": [str(exc)],
            },
            finished_at,
        )
        print(f"[错误] 上游 concept_relevance.md 不可用，停止生成知识讲解。原因：{exc}")
        return 1

    cmd = [
        sys.executable,
        str(GENERATOR_SCRIPT),
        "--date",
        target_date,
        "--config",
        str(config_path),
        "--input-root",
        str(input_root),
        "--output-root",
        str(output_root),
        "--timeout",
        str(args.timeout),
        "--llm-retries",
        str(args.llm_retries),
        "--llm-retry-delay",
        str(args.llm_retry_delay),
    ]
    result = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    finished_at = datetime.now(timezone).isoformat()
    problems: list[str] = []
    status = "success"
    llm_status = "success"
    if result.returncode != 0:
        status = "failed"
        llm_status = "failed"
        problems.append((result.stderr or result.stdout).strip() or f"generator exited with {result.returncode}")
    else:
        if not knowledge_path.exists() or not knowledge_path.read_text(encoding="utf-8").strip():
            status = "failed"
            problems.append(f"{knowledge_path} 未生成或为空")
        if not knowledge_log_path.exists() or not knowledge_log_path.read_text(encoding="utf-8").strip():
            status = "failed"
            problems.append(f"{knowledge_log_path} 未生成或为空")
        question_threads_status = {
            "path": relative_to_root(question_threads_path, output_root),
            "status": "success",
            "upserted": 0,
            "today_questions": 0,
            "total_threads": 0,
        }
        try:
            thread_data = load_question_threads(question_threads_path, allow_missing=False)
            today_questions = [
                thread for thread in thread_data.get("threads", []) if thread.get("source_date") == target_date
            ]
            generator_thread_result = parse_question_thread_result(result.stdout or "") or {}
            question_threads_status.update(
                {
                    "upserted": generator_thread_result.get("upserted", len(today_questions)),
                    "today_questions": len(today_questions),
                    "total_threads": len(thread_data.get("threads", [])),
                }
            )
        except (FileNotFoundError, ValueError, OSError) as exc:
            status = "failed"
            question_threads_status.update({"status": "failed", "error": str(exc)})
            problems.append(f"问题线程文件未生成或无效: {exc}")
        if problems:
            llm_status = "output_invalid"
    if result.returncode != 0:
        question_threads_status = {
            "path": relative_to_root(question_threads_path, output_root),
            "status": "failed",
            "upserted": 0,
            "today_questions": 0,
            "error": "\n".join(problems) if problems else None,
        }

    write_agent_status(
        status_path,
        target_date,
        {
            "status": status,
            "started_at": started_at,
            "finished_at": finished_at,
            "timezone": str(timezone),
            "input_path": relative_to_root(concept_path, input_root),
            "input_chars": len(concept_content),
            "output_path": relative_to_root(knowledge_path, output_root),
            "knowledge_log_path": relative_to_root(knowledge_log_path, output_root),
            "question_threads": question_threads_status,
            "generator": relative_to_root(GENERATOR_SCRIPT),
            "llm": {
                "enabled": True,
                "status": llm_status,
                "error": "\n".join(problems) if problems else None,
            },
            "stdout": result.stdout[-4000:] if result.stdout else "",
            "stderr": result.stderr[-4000:] if result.stderr else "",
            "problems": problems,
        },
        finished_at,
    )

    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    if status != "success":
        print("[错误] 第 3 步知识讲解生成失败。")
        return 1
    print(f"[状态] 已更新: {status_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
