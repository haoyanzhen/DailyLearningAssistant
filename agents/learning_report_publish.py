#!/usr/bin/env python3
"""Run the fourth local agent: learning report HTML publishing."""

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
GENERATOR_SCRIPT = PROJECT_ROOT / "scripts" / "generate_learning_report.py"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate HTML learning report and update manifests.")
    parser.add_argument("--date", help="Target date in YYYY-MM-DD format. Defaults to today in configured timezone.")
    parser.add_argument("--config", default=str(PROJECT_ROOT / "config.json"), help="Config JSON path.")
    parser.add_argument("--input-root", default=str(PROJECT_ROOT), help="Root to read prework and knowledge_log from.")
    parser.add_argument("--output-root", default=str(PROJECT_ROOT), help="Root to write daily_report and manifests to.")
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
    status_data["agents"]["learning_report_publish"] = agent_status

    status_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = status_path.with_suffix(".json.tmp")
    temp_path.write_text(json.dumps(status_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp_path.replace(status_path)


def validate_required_input(path: Path) -> int:
    if not path.exists():
        raise FileNotFoundError(f"{path} 不存在")
    content = path.read_text(encoding="utf-8")
    if not content.strip():
        raise ValueError(f"{path} 为空")
    return len(content)


def main() -> int:
    args = parse_args()
    config_path = Path(args.config).expanduser().resolve()
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

    knowledge_path = input_dir / "knowledge_explaination.md"
    knowledge_log_path = input_root / "knowledge_log" / f"{year_month}-knowledge-log.md"
    report_path = output_root / "daily_report" / year_month / f"{target_date}-learning-report.html"
    daily_manifest_path = output_root / "daily_report" / "manifest.json"
    knowledge_manifest_path = output_root / "knowledge_log" / "manifest.json"
    status_path = output_dir / "run_status.json"

    problems: list[str] = []
    input_chars = 0
    log_chars = 0
    try:
        input_chars = validate_required_input(knowledge_path)
        log_chars = validate_required_input(knowledge_log_path)
    except (FileNotFoundError, ValueError, OSError) as exc:
        problems.append(str(exc))
        finished_at = datetime.now(timezone).isoformat()
        write_agent_status(
            status_path,
            target_date,
            {
                "status": "failed",
                "started_at": started_at,
                "finished_at": finished_at,
                "timezone": str(timezone),
                "input_path": relative_to_root(knowledge_path, input_root),
                "knowledge_log_path": relative_to_root(knowledge_log_path, input_root),
                "output_path": relative_to_root(report_path, output_root),
                "daily_manifest_path": relative_to_root(daily_manifest_path, output_root),
                "knowledge_manifest_path": relative_to_root(knowledge_manifest_path, output_root),
                "generator": relative_to_root(GENERATOR_SCRIPT),
                "llm": {
                    "enabled": True,
                    "status": "skipped_input_invalid",
                    "error": None,
                },
                "problems": problems,
            },
            finished_at,
        )
        print(f"[错误] 上游知识讲解或教学记录不可用，停止发布日报。原因：{exc}")
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
    status = "success"
    llm_status = "success"
    if result.returncode != 0:
        status = "failed"
        llm_status = "failed"
        problems.append((result.stderr or result.stdout).strip() or f"generator exited with {result.returncode}")
    else:
        expected_outputs = (report_path, daily_manifest_path, knowledge_manifest_path)
        for path in expected_outputs:
            if not path.exists() or not path.read_text(encoding="utf-8").strip():
                status = "failed"
                problems.append(f"{path} 未生成或为空")
        if problems:
            llm_status = "output_invalid"

    write_agent_status(
        status_path,
        target_date,
        {
            "status": status,
            "started_at": started_at,
            "finished_at": finished_at,
            "timezone": str(timezone),
            "input_path": relative_to_root(knowledge_path, input_root),
            "input_chars": input_chars,
            "knowledge_log_path": relative_to_root(knowledge_log_path, input_root),
            "knowledge_log_chars": log_chars,
            "output_path": relative_to_root(report_path, output_root),
            "daily_manifest_path": relative_to_root(daily_manifest_path, output_root),
            "knowledge_manifest_path": relative_to_root(knowledge_manifest_path, output_root),
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
        print("[错误] 第 4 步学习日报发布失败。")
        return 1
    print(f"[状态] 已更新: {status_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
