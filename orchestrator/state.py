"""Shared status-file management for local agent orchestration."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


ORCHESTRATOR_STATUS_KEY = "orchestrator"


def load_status(status_path: Path, target_date: str) -> dict:
    if not status_path.exists():
        return {"date": target_date, "agents": {}}
    try:
        data = json.loads(status_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"date": target_date, "agents": {}}
    if not isinstance(data, dict):
        return {"date": target_date, "agents": {}}
    data.setdefault("date", target_date)
    data.setdefault("agents", {})
    if not isinstance(data["agents"], dict):
        data["agents"] = {}
    return data


def write_status(status_path: Path, status_data: dict) -> None:
    status_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = status_path.with_suffix(".json.tmp")
    temp_path.write_text(json.dumps(status_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp_path.replace(status_path)


def now_iso(timezone: ZoneInfo) -> str:
    return datetime.now(timezone).isoformat()


def update_orchestrator(
    status_path: Path,
    target_date: str,
    payload: dict,
    timezone: ZoneInfo,
    run_key: str | None = None,
) -> None:
    status_data = load_status(status_path, target_date)
    status_data["date"] = target_date
    status_data["updated_at"] = now_iso(timezone)
    if "day_context" in payload:
        status_data["day_context"] = payload["day_context"]
    status_data[ORCHESTRATOR_STATUS_KEY] = payload
    if run_key:
        status_data.setdefault("orchestrator_runs", {})
        if not isinstance(status_data["orchestrator_runs"], dict):
            status_data["orchestrator_runs"] = {}
        status_data["orchestrator_runs"][run_key] = payload
    write_status(status_path, status_data)


def summarize_agents(status_data: dict) -> dict:
    agents = status_data.get("agents") or {}
    summary = {}
    for name, agent_status in agents.items():
        if not isinstance(agent_status, dict):
            summary[name] = {"status": "invalid"}
            continue
        summary[name] = {
            "status": agent_status.get("status", "unknown"),
            "llm": (agent_status.get("llm") or {}).get("status"),
            "problems": agent_status.get("problems") or [],
        }
    return summary


def is_success(status_data: dict, required_agents: list[str]) -> bool:
    agents = status_data.get("agents") or {}
    success_statuses_by_agent = {
        "daily_work_summary": {"success", "partial_success"},
    }
    for name in required_agents:
        accepted_statuses = success_statuses_by_agent.get(name, {"success"})
        if (agents.get(name) or {}).get("status") in accepted_statuses:
            continue
        return False
    return True
