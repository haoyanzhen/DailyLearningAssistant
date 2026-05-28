#!/usr/bin/env python3
"""Inspect daily local agent pipeline status."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from collections import Counter

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator.config import PROJECT_ROOT, day_dir, load_config, resolve_target_date, resolve_timezone
from orchestrator.state import is_success, load_status, summarize_agents


REQUIRED_AGENTS = [
    "daily_work_summary",
    "concept_relevance",
    "knowledge_explaination",
    "learning_report_publish",
    "daily_email_send",
]


def summarize_llm_trace(trace_path: Path) -> dict:
    if not trace_path.exists():
        return {"path": str(trace_path), "exists": False}
    attempts = []
    calls = []
    for line in trace_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if item.get("event") == "llm_attempt":
            attempts.append(item)
        elif item.get("event") == "llm_call":
            calls.append(item)
    by_status = Counter(str(item.get("status")) for item in attempts)
    by_agent = Counter(str(item.get("agent")) for item in attempts)
    by_trust_env_proxy = Counter(str(item.get("trust_env_proxy")) for item in attempts if "trust_env_proxy" in item)
    error_types = Counter(str(item.get("error_type")) for item in attempts if item.get("error_type"))
    return {
        "path": str(trace_path),
        "exists": True,
        "attempt_count": len(attempts),
        "call_count": len(calls),
        "attempts_by_status": dict(by_status),
        "attempts_by_agent": dict(by_agent),
        "attempts_by_trust_env_proxy": dict(by_trust_env_proxy),
        "error_types": dict(error_types),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check daily agent run status.")
    parser.add_argument("--date", help="Target date in YYYY-MM-DD format. Defaults to today in configured timezone.")
    parser.add_argument("--config", default=str(PROJECT_ROOT / "config.json"), help="Config JSON path.")
    parser.add_argument("--output-root", default=str(PROJECT_ROOT), help="Root containing prework status files.")
    parser.add_argument("--timezone", help="Timezone override.")
    parser.add_argument("--json", action="store_true", help="Print JSON only.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_config(Path(args.config).expanduser().resolve())
    timezone = resolve_timezone(config, args.timezone)
    target_date = resolve_target_date(args.date, timezone)
    output_root = Path(args.output_root).expanduser().resolve()
    status_path = day_dir(output_root, target_date) / "run_status.json"
    status_data = load_status(status_path, target_date)
    payload = {
        "date": target_date,
        "status_path": str(status_path),
        "complete": is_success(status_data, REQUIRED_AGENTS),
        "agents": summarize_agents(status_data),
        "orchestrator": status_data.get("orchestrator"),
        "orchestrator_runs": status_data.get("orchestrator_runs") or {},
        "llm_trace": summarize_llm_trace(status_path.parent / "llm_trace.jsonl"),
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"日期: {target_date}")
        print(f"状态文件: {status_path}")
        print(f"完整成功: {'是' if payload['complete'] else '否'}")
        for name, item in payload["agents"].items():
            print(f"- {name}: {item['status']} / llm={item.get('llm')}")
            for problem in item.get("problems") or []:
                print(f"  - {problem}")
        trace = payload["llm_trace"]
        runs = payload["orchestrator_runs"]
        if runs:
            print("Orchestrator runs:")
            for key, item in runs.items():
                print(f"- {key}: {item.get('status')} steps={item.get('selected_steps')}")
        if trace.get("exists"):
            print(
                f"LLM trace: attempts={trace['attempt_count']} calls={trace['call_count']} "
                f"proxy={trace.get('attempts_by_trust_env_proxy') or {}} "
                f"errors={trace.get('error_types') or {}}"
            )
    return 0 if payload["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
