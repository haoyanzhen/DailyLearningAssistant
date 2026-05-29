"""LLM output and artifact validators shared by orchestration code."""

from __future__ import annotations

import json
import re
from html import unescape
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
    problems = [item for item in required if item.lower() not in lower_html]
    problems.extend(validate_relationship_map_html(html))
    return problems


def _extract_first(pattern: str, text: str, flags: int = re.I | re.S) -> str:
    match = re.search(pattern, text, flags=flags)
    return match.group(1).strip() if match else ""


def _strip_tags(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()


def _extract_lesson_titles(html: str) -> list[str]:
    return [
        unescape(_strip_tags(match.group(1)))
        for match in re.finditer(
            r'<article\b[^>]*class="[^"]*\blesson-card\b[^"]*"[^>]*>[\s\S]*?<h3[^>]*>([\s\S]*?)</h3>',
            html,
            flags=re.I,
        )
    ]


def _extract_mermaid_source(html: str) -> str:
    source = _extract_first(
        r'<pre\b[^>]*class="[^"]*\bmermaid\b[^"]*"[^>]*>([\s\S]*?)</pre>',
        html,
    )
    return unescape(source)


def _validate_mermaid_source(source: str, lesson_titles: list[str]) -> list[str]:
    problems: list[str] = []
    if not source:
        return ["关系图缺少 <pre class=\"mermaid\"> 源码块"]

    lines = [line.strip() for line in source.splitlines() if line.strip()]
    if not lines or not re.match(r"^flowchart\s+(LR|RL|TD|TB|BT)\b", lines[0]):
        problems.append("关系图 Mermaid 源码必须以 flowchart LR/RL/TD/TB/BT 开头")

    node_ids: set[str] = set()
    edge_count = 0
    for line in lines:
        node_match = re.match(r"^([A-Za-z][\w-]*)\s*(?:\[|\(\[|\(\()", line)
        if node_match:
            node_ids.add(node_match.group(1))
        edge_match = re.match(r"^([A-Za-z][\w-]*)\s*-+>+\s*([A-Za-z][\w-]*)\b", line)
        if edge_match:
            edge_count += 1
            source_id, target_id = edge_match.groups()
            if source_id not in node_ids:
                problems.append(f"关系图 Mermaid 边引用了未定义源节点: {source_id}")
            if target_id not in node_ids:
                problems.append(f"关系图 Mermaid 边引用了未定义目标节点: {target_id}")

    if edge_count < max(3, len(lesson_titles)):
        problems.append("关系图 Mermaid 连线数量不足，无法表达三张知识卡之间及相关概念关系")

    for title in lesson_titles:
        if title not in source:
            problems.append(f"关系图 Mermaid 缺少知识卡节点: {title}")

    if "classDef" not in source:
        problems.append("关系图 Mermaid 缺少 classDef 样式定义")

    related_node_count = max(0, len(node_ids) - len(lesson_titles) - 1)
    if related_node_count < 1:
        problems.append("关系图 Mermaid 缺少三张知识卡之外的相关概念节点")

    return problems


def validate_relationship_map_html(html: str) -> list[str]:
    """Validate the inline SVG relationship map in a learning report."""

    problems: list[str] = []
    lower_html = html.lower()

    required_fragments = [
        "relationship-map",
        "relationship-map-visual",
        "relationship-orbit",
        "relationship-hub",
        "relationship-node",
        "relationship-map-summary",
    ]
    problems.extend([f"关系图缺少必要片段: {item}" for item in required_fragments if item not in lower_html])
    if not re.search(r'<pre\b[^>]*class="[^"]*\bmermaid\b[^"]*"', html, flags=re.I):
        problems.append('关系图缺少必要片段: class 包含 "mermaid" 的源码块')

    toolbar_index = lower_html.find("lesson-toolbar")
    map_index = lower_html.find("relationship-map")
    grid_index = lower_html.find("lesson-grid")
    if min(toolbar_index, map_index, grid_index) == -1:
        problems.append("关系图无法确认位于小课标题栏和三张知识卡之间")
    elif not (toolbar_index < map_index < grid_index):
        problems.append("关系图必须位于“今日三节小课”标题栏和三张知识卡之间")

    lesson_titles = _extract_lesson_titles(html)
    if len(lesson_titles) != 3:
        problems.append(f"关系图校验需要恰好 3 张知识卡，当前为 {len(lesson_titles)} 张")

    mermaid_source = _extract_mermaid_source(html)
    problems.extend(_validate_mermaid_source(mermaid_source, lesson_titles))

    node_count = len(
        re.findall(r'<article\b[^>]*class="[^"]*\brelationship-node\b[^"]*"', html, flags=re.I)
    )
    if node_count != 3:
        problems.append(f"关系图需要恰好 3 个可见知识节点，当前为 {node_count} 个")

    summary_text = unescape(
        _strip_tags(
            _extract_first(
                r'<p\b[^>]*class="[^"]*\brelationship-map-summary\b[^"]*"[^>]*>([\s\S]*?)</p>',
                html,
            )
        )
    )
    if len(summary_text) < 20:
        problems.append("关系图摘要过短，无法说明三节小课的整体关联")

    return problems


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
