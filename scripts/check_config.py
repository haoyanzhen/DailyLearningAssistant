#!/usr/bin/env python3
"""Validate DailyLearningAssistant local-agent configuration."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
TIME_RE = re.compile(r"^\d{2}:\d{2}$")
URL_RE = re.compile(r"^https?://")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check local DailyLearningAssistant config.json.")
    parser.add_argument("--config", default="config.json", help="Config JSON path.")
    parser.add_argument("--strict", action="store_true", help="Require real LLM and email credentials.")
    return parser.parse_args()


def load_config(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"配置文件不存在: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"配置文件不是合法 JSON: {path} ({exc})") from exc
    if not isinstance(data, dict):
        raise ValueError("配置文件顶层必须是 JSON object")
    return data


def check_schedule(config: dict) -> list[str]:
    problems: list[str] = []
    schedule = config.get("schedule")
    if not isinstance(schedule, dict):
        return ["schedule 必须是 object"]
    for key in ("daily_run_time", "html_run_time", "email_send_time"):
        run_time = schedule.get(key)
        if run_time is None and key != "daily_run_time":
            continue
        if not isinstance(run_time, str) or not TIME_RE.fullmatch(run_time):
            problems.append(f"schedule.{key} 必须是 HH:MM")
        else:
            hour, minute = map(int, run_time.split(":"))
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                problems.append(f"schedule.{key} 小时必须为 00-23，分钟必须为 00-59")
    timezone_name = schedule.get("timezone")
    if not isinstance(timezone_name, str) or not timezone_name.strip():
        problems.append("schedule.timezone 不能为空")
    else:
        try:
            ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError:
            problems.append(f"schedule.timezone 无法识别: {timezone_name}")
    return problems


def check_repositories(config: dict) -> list[str]:
    problems: list[str] = []
    repositories = config.get("repositories")
    if not isinstance(repositories, list) or not repositories:
        return ["repositories 必须是非空列表"]
    seen: set[str] = set()
    for index, item in enumerate(repositories):
        prefix = f"repositories[{index}]"
        if not isinstance(item, dict):
            problems.append(f"{prefix} 必须是 object")
            continue
        name = item.get("name")
        raw_path = item.get("path")
        if not isinstance(name, str) or not name.strip():
            problems.append(f"{prefix}.name 不能为空")
        elif name in seen:
            problems.append(f"{prefix}.name 重复: {name}")
        else:
            seen.add(name)
        if not isinstance(raw_path, str) or not raw_path.strip():
            problems.append(f"{prefix}.path 不能为空")
            continue
        path = Path(raw_path).expanduser()
        if not path.exists():
            problems.append(f"{prefix}.path 不存在: {path}")
        elif not (path / ".git").exists():
            git_file = path / ".git"
            if not git_file.exists():
                problems.append(f"{prefix}.path 不是可识别的 Git 工作区: {path}")
    return problems


def check_llm(config: dict, strict: bool) -> list[str]:
    problems: list[str] = []
    try:
        import httpx  # noqa: F401
    except ImportError:
        problems.append("缺少 Python 依赖 httpx，请运行: python3 -m pip install -r requirements.txt")
    llm = config.get("llm")
    if not isinstance(llm, dict):
        return ["llm 必须是 object"]
    for key in ("api_url", "api_key", "model"):
        value = llm.get(key)
        if not isinstance(value, str) or not value.strip():
            problems.append(f"llm.{key} 不能为空")
    api_url = llm.get("api_url")
    if isinstance(api_url, str) and api_url and not URL_RE.search(api_url):
        problems.append("llm.api_url 必须是 http(s) URL")
    api_key = str(llm.get("api_key") or "")
    if strict and (not api_key or api_key.startswith("YOUR_")):
        problems.append("llm.api_key 不能是示例占位符")
    return problems


def check_email(config: dict, strict: bool) -> list[str]:
    problems: list[str] = []
    email = config.get("email")
    if not isinstance(email, dict):
        return ["email 必须是 object"]
    for key in ("smtp_server", "smtp_port", "sender_email", "sender_name", "sender_password", "target_emails"):
        if key not in email:
            problems.append(f"email.{key} 缺失")
    if not isinstance(email.get("smtp_port"), int):
        problems.append("email.smtp_port 必须是整数")
    sender_email = email.get("sender_email")
    if not isinstance(sender_email, str) or not EMAIL_RE.fullmatch(sender_email):
        problems.append("email.sender_email 必须是合法邮箱")
    password = str(email.get("sender_password") or "")
    if strict and (not password or password.startswith("YOUR_")):
        problems.append("email.sender_password 不能是示例占位符")
    targets = email.get("target_emails")
    if not isinstance(targets, list) or not targets:
        problems.append("email.target_emails 必须是非空列表")
    else:
        for index, target in enumerate(targets):
            if not isinstance(target, str) or not EMAIL_RE.fullmatch(target):
                problems.append(f"email.target_emails[{index}] 不是合法邮箱")
    if "imap_server" in email or "imap_port" in email or "imap_user" in email or "imap_password" in email:
        for key in ("imap_server", "imap_port", "imap_user", "imap_password"):
            if key not in email:
                problems.append(f"配置 IMAP 验收时 email.{key} 必须同时存在")
        if "imap_port" in email and not isinstance(email.get("imap_port"), int):
            problems.append("email.imap_port 必须是整数")
    return problems


def check_site(config: dict) -> list[str]:
    site = config.get("site")
    if not isinstance(site, dict):
        return ["site 必须是 object"]
    base_url = site.get("base_url")
    if not isinstance(base_url, str) or not URL_RE.search(base_url):
        return ["site.base_url 必须是 http(s) URL"]
    return []


def check_publish(config: dict) -> list[str]:
    publish = config.get("publish")
    if publish is None:
        return []
    problems: list[str] = []
    if not isinstance(publish, dict):
        return ["publish 必须是 object"]
    for key in ("remote", "branch", "commit_message"):
        value = publish.get(key)
        if value is not None and (not isinstance(value, str) or not value.strip()):
            problems.append(f"publish.{key} 必须是非空字符串")
    paths = publish.get("paths")
    if paths is not None:
        if not isinstance(paths, list):
            problems.append("publish.paths 必须是字符串列表")
        else:
            for index, item in enumerate(paths):
                if not isinstance(item, str) or not item.strip():
                    problems.append(f"publish.paths[{index}] 必须是非空字符串")
    return problems


def main() -> int:
    args = parse_args()
    config_path = Path(args.config).expanduser().resolve()
    try:
        config = load_config(config_path)
    except (FileNotFoundError, ValueError) as exc:
        print(f"[错误] {exc}")
        return 1

    problems = []
    problems.extend(check_schedule(config))
    problems.extend(check_repositories(config))
    problems.extend(check_llm(config, args.strict))
    problems.extend(check_email(config, args.strict))
    problems.extend(check_site(config))
    problems.extend(check_publish(config))

    if problems:
        print(f"[失败] 配置检查未通过: {config_path}")
        for problem in problems:
            print(f"- {problem}")
        return 1
    print(f"[通过] 配置检查通过: {config_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
