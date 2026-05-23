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


def update_orchestrator(status_path: Path, target_date: str, payload: dict, timezone: ZoneInfo) -> None:
    status_data = load_status(status_path, target_date)
    status_data["date"] = target_date
    status_data["updated_at"] = now_iso(timezone)
    status_data[ORCHESTRATOR_STATUS_KEY] = payload
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
    orchestrator = status_data.get(ORCHESTRATOR_STATUS_KEY) or {}
    skipped_steps = set(orchestrator.get("skipped_steps") or [])
    fallback_events = orchestrator.get("fallback_events") or []
    skippable_agents = {
        "concept_relevance": 2,
        "knowledge_explaination": 3,
    }
    for name in required_agents:
        if (agents.get(name) or {}).get("status") == "success":
            continue
        if (
            orchestrator.get("status") == "success"
            and fallback_events
            and skippable_agents.get(name) in skipped_steps
        ):
            continue
        return False
    return True
