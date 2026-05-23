"""Shared configuration helpers for the local agent orchestrator."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TIMEZONE = "Asia/Shanghai"


def load_config(config_path: Path) -> dict:
    if not config_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")
    try:
        return json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"配置文件不是合法 JSON: {config_path} ({exc})") from exc


def resolve_timezone(config: dict, timezone_name: str | None = None) -> ZoneInfo:
    name = timezone_name or (config.get("schedule") or {}).get("timezone") or DEFAULT_TIMEZONE
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"未识别的时区: {name}") from exc


def resolve_target_date(date_arg: str | None, timezone: ZoneInfo) -> str:
    if date_arg:
        try:
            datetime.strptime(date_arg, "%Y-%m-%d")
        except ValueError as exc:
            raise ValueError("--date 必须使用 YYYY-MM-DD 格式。") from exc
        return date_arg
    return datetime.now(timezone).date().isoformat()


def day_dir(root: Path, target_date: str) -> Path:
    year_month = target_date[:7]
    return root / "prework" / year_month / target_date


def relative_to_root(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)

