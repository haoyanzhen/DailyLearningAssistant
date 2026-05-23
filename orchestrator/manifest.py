"""Strict manifest loading, validation, and update helpers."""

from __future__ import annotations

import json
import re
from pathlib import Path


DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
YEAR_RE = re.compile(r"^\d{4}$")
MONTH_RE = re.compile(r"^(0[1-9]|1[0-2])$")


def _read_json(path: Path, root_key: str) -> dict:
    if not path.exists():
        return {root_key: []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} 不是合法 JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{path} 顶层必须是 JSON object")
    if root_key not in data:
        data[root_key] = []
    if not isinstance(data[root_key], list):
        raise ValueError(f"{path} 的 {root_key} 必须是列表")
    return data


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp_path.replace(path)


def validate_daily_manifest(data: dict, path: Path | None = None, root: Path | None = None, allow_empty: bool = True) -> list[str]:
    label = str(path) if path else "daily_report manifest"
    reports = data.get("reports")
    problems: list[str] = []
    if not isinstance(reports, list):
        return [f"{label} 缺少 reports 列表"]
    if not reports and not allow_empty:
        problems.append(f"{label} 的 reports 不能为空")

    seen_dates: set[str] = set()
    sort_keys: list[str] = []
    for index, report in enumerate(reports):
        prefix = f"{label} reports[{index}]"
        if not isinstance(report, dict):
            problems.append(f"{prefix} 必须是 object")
            continue
        date = report.get("date")
        title = report.get("title")
        summary = report.get("summary")
        report_path = report.get("path")
        if not isinstance(date, str) or not DATE_RE.fullmatch(date):
            problems.append(f"{prefix}.date 必须是 YYYY-MM-DD")
            continue
        if date in seen_dates:
            problems.append(f"{prefix}.date 重复: {date}")
        seen_dates.add(date)
        sort_keys.append(date)
        if not isinstance(title, str) or not title.strip():
            problems.append(f"{prefix}.title 不能为空")
        if not isinstance(summary, str) or not summary.strip():
            problems.append(f"{prefix}.summary 不能为空")
        elif not 10 <= len(summary.strip()) <= 120:
            problems.append(f"{prefix}.summary 长度应在 10-120 字符之间")
        expected_path = f"./daily_report/{date[:7]}/{date}-learning-report.html"
        if report_path != expected_path:
            problems.append(f"{prefix}.path 应为 {expected_path}")
        if root and isinstance(report_path, str):
            local_path = root / report_path.lstrip("./")
            if not local_path.exists():
                problems.append(f"{prefix}.path 指向的文件不存在: {local_path}")
            elif not local_path.read_text(encoding="utf-8").strip():
                problems.append(f"{prefix}.path 指向的文件为空: {local_path}")

    if sort_keys != sorted(sort_keys, reverse=True):
        problems.append(f"{label} reports 必须按 date 倒序排列")
    return problems


def validate_knowledge_manifest(data: dict, path: Path | None = None, root: Path | None = None, allow_empty: bool = True) -> list[str]:
    label = str(path) if path else "knowledge_log manifest"
    months = data.get("months")
    problems: list[str] = []
    if not isinstance(months, list):
        return [f"{label} 缺少 months 列表"]
    if not months and not allow_empty:
        problems.append(f"{label} 的 months 不能为空")

    seen_months: set[str] = set()
    sort_keys: list[str] = []
    for index, item in enumerate(months):
        prefix = f"{label} months[{index}]"
        if not isinstance(item, dict):
            problems.append(f"{prefix} 必须是 object")
            continue
        year = str(item.get("year", ""))
        month = str(item.get("month", "")).zfill(2)
        title = item.get("title")
        log_path = item.get("path")
        if not YEAR_RE.fullmatch(year):
            problems.append(f"{prefix}.year 必须是四位年份")
            continue
        if not MONTH_RE.fullmatch(month):
            problems.append(f"{prefix}.month 必须是 01-12")
            continue
        year_month = f"{year}-{month}"
        if year_month in seen_months:
            problems.append(f"{prefix} 月份重复: {year_month}")
        seen_months.add(year_month)
        sort_keys.append(year_month)
        expected_title = f"{year}年{int(month)}月教学记录"
        if title != expected_title:
            problems.append(f"{prefix}.title 应为 {expected_title}")
        expected_path = f"./knowledge_log/{year_month}-knowledge-log.md"
        if log_path != expected_path:
            problems.append(f"{prefix}.path 应为 {expected_path}")
        if root and isinstance(log_path, str):
            local_path = root / log_path.lstrip("./")
            if not local_path.exists():
                problems.append(f"{prefix}.path 指向的文件不存在: {local_path}")
            elif not local_path.read_text(encoding="utf-8").strip():
                problems.append(f"{prefix}.path 指向的文件为空: {local_path}")

    if sort_keys != sorted(sort_keys, reverse=True):
        problems.append(f"{label} months 必须按月份倒序排列")
    return problems


def load_daily_manifest(path: Path, root: Path | None = None, allow_empty: bool = True) -> dict:
    data = _read_json(path, "reports")
    problems = validate_daily_manifest(data, path, root, allow_empty)
    if problems:
        raise ValueError("; ".join(problems))
    return data


def load_knowledge_manifest(path: Path, root: Path | None = None, allow_empty: bool = True) -> dict:
    data = _read_json(path, "months")
    problems = validate_knowledge_manifest(data, path, root, allow_empty)
    if problems:
        raise ValueError("; ".join(problems))
    return data


def update_daily_manifest(path: Path, target_date: str, title: str, summary: str, report_path: str, root: Path | None = None) -> None:
    manifest = load_daily_manifest(path, root=None, allow_empty=True)
    reports = [item for item in manifest["reports"] if item.get("date") != target_date]
    reports.append({"date": target_date, "title": title, "summary": summary, "path": report_path})
    manifest["reports"] = sorted(reports, key=lambda item: item.get("date", ""), reverse=True)
    problems = validate_daily_manifest(manifest, path, root, allow_empty=False)
    if problems:
        raise ValueError("; ".join(problems))
    _write_json(path, manifest)


def update_knowledge_manifest(path: Path, year_month: str, root: Path | None = None) -> None:
    year, month = year_month.split("-")
    month = month.zfill(2)
    manifest = load_knowledge_manifest(path, root=None, allow_empty=True)
    months = [
        item
        for item in manifest["months"]
        if not (str(item.get("year")) == year and str(item.get("month")).zfill(2) == month)
    ]
    months.append(
        {
            "year": year,
            "month": month,
            "title": f"{year}年{int(month)}月教学记录",
            "path": f"./knowledge_log/{year_month}-knowledge-log.md",
        }
    )
    manifest["months"] = sorted(months, key=lambda item: f"{item.get('year')}-{str(item.get('month')).zfill(2)}", reverse=True)
    problems = validate_knowledge_manifest(manifest, path, root, allow_empty=False)
    if problems:
        raise ValueError("; ".join(problems))
    _write_json(path, manifest)


def select_report(reports: list[dict], target_date: str, allow_latest_fallback: bool = False) -> tuple[dict | None, str]:
    exact = next((report for report in reports if report.get("date") == target_date), None)
    if exact:
        return exact, "exact_date"
    if not allow_latest_fallback:
        return None, "missing_exact_date"
    eligible = [report for report in reports if isinstance(report.get("date"), str) and report["date"] <= target_date]
    if not eligible:
        return None, "latest_available"
    return max(eligible, key=lambda report: report["date"]), "latest_available"
