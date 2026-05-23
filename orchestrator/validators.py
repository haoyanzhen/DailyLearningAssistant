"""LLM output and artifact validators shared by orchestration code."""

from __future__ import annotations

import json
import re
from pathlib import Path

from orchestrator.manifest import validate_daily_manifest, validate_knowledge_manifest


def require_nonempty_file(path: Path, label: str | None = None) -> str:
    if not path.exists():
        raise FileNotFoundError(f"{label or path} 不存在: {path}")
    content = path.read_text(encoding="utf-8")
    if not content.strip():
        raise ValueError(f"{label or path} 为空: {path}")
    return content


def parse_json_or_tagged(text: str, tag_names: tuple[str, ...]) -> dict:
    tagged = {}
    for tag in tag_names:
        match = re.search(rf"<{tag}>\s*([\s\S]*?)\s*</{tag}>", text, flags=re.I)
        if match:
            tagged[tag] = match.group(1).strip()
    if len(tagged) == len(tag_names):
        return tagged

    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", stripped, flags=re.S)
        if match:
            return json.loads(match.group(0))
        raise


def validate_learning_report_html(html: str, target_date: str) -> list[str]:
    required = [
        "<!doctype html>",
        '<html lang="zh-CN"',
        "../../style/main.css",
        "../../index.html?archive=1",
        "../../index.html?knowledge=1",
        "简读",
        "精读",
        "lesson-section",
        "lesson-detail-panel",
        target_date,
    ]
    lower_html = html.lower()
    return [item for item in required if item.lower() not in lower_html]


def validate_manifest(path: Path, key: str) -> list[str]:
    if not path.exists():
        return [f"{path} 不存在"]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"{path} 不是合法 JSON: {exc}"]
    if key == "reports":
        return validate_daily_manifest(data, path)
    if key == "months":
        return validate_knowledge_manifest(data, path)
    if not isinstance(data.get(key), list):
        return [f"{path} 缺少 {key} 列表"]
    return []
