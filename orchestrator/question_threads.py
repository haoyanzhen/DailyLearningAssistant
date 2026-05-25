"""Question-thread helpers for cross-day learning continuity."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path


QUESTION_THREAD_VERSION = 1


@dataclass
class QuestionThreadSelection:
    status: str
    files: list[str]
    open_count: int
    selected_count: int
    questions: list[dict]


def question_thread_path(root: Path, year_month: str) -> Path:
    return root / "knowledge_log" / f"{year_month}-question-threads.json"


def load_question_threads(path: Path, *, allow_missing: bool = True) -> dict:
    if not path.exists():
        if allow_missing:
            return {"version": QUESTION_THREAD_VERSION, "year_month": _year_month_from_path(path), "threads": []}
        raise FileNotFoundError(f"{path} 不存在")

    content = path.read_text(encoding="utf-8")
    if not content.strip():
        return {"version": QUESTION_THREAD_VERSION, "year_month": _year_month_from_path(path), "threads": []}

    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} 不是合法 JSON: {exc}") from exc

    validate_question_threads(data, path)
    return data


def validate_question_threads(data: dict, path: Path | None = None) -> None:
    label = str(path) if path else "question threads"
    if not isinstance(data, dict):
        raise ValueError(f"{label} 必须是 JSON object。")
    if data.get("version") != QUESTION_THREAD_VERSION:
        raise ValueError(f"{label} version 必须是 {QUESTION_THREAD_VERSION}。")
    year_month = data.get("year_month")
    if not isinstance(year_month, str) or not re.fullmatch(r"\d{4}-\d{2}", year_month):
        raise ValueError(f"{label} year_month 必须是 YYYY-MM。")
    threads = data.get("threads")
    if not isinstance(threads, list):
        raise ValueError(f"{label} threads 必须是数组。")

    seen_ids: set[str] = set()
    required = ("id", "question", "source_date", "source_concept", "domain", "status", "created_at", "updated_at")
    for index, thread in enumerate(threads, start=1):
        if not isinstance(thread, dict):
            raise ValueError(f"{label} threads[{index}] 必须是 object。")
        missing = [key for key in required if not thread.get(key)]
        if missing:
            raise ValueError(f"{label} threads[{index}] 缺少字段: {', '.join(missing)}")
        if thread["id"] in seen_ids:
            raise ValueError(f"{label} 存在重复 thread id: {thread['id']}")
        seen_ids.add(thread["id"])
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(thread["source_date"])):
            raise ValueError(f"{label} threads[{index}].source_date 必须是 YYYY-MM-DD。")
        if thread["status"] not in {"open", "closed"}:
            raise ValueError(f"{label} threads[{index}].status 必须是 open 或 closed。")


def write_question_threads(path: Path, data: dict) -> None:
    validate_question_threads(data, path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(".json.tmp")
    temp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp_path.replace(path)


def collect_recent_open_questions(root: Path, target_date: str, *, days: int = 7) -> QuestionThreadSelection:
    target = datetime.strptime(target_date, "%Y-%m-%d").date()
    start = target - timedelta(days=days)
    end = target - timedelta(days=1)
    months = sorted({(start + timedelta(days=offset)).isoformat()[:7] for offset in range(days)})

    files: list[str] = []
    questions: list[dict] = []
    open_count = 0
    existing_files = 0
    empty_files = 0

    for year_month in months:
        path = question_thread_path(root, year_month)
        files.append(str(path))
        if not path.exists():
            continue
        existing_files += 1
        data = load_question_threads(path, allow_missing=True)
        if not data.get("threads"):
            empty_files += 1
        for thread in data["threads"]:
            if thread.get("status") != "open":
                continue
            open_count += 1
            source_date = datetime.strptime(thread["source_date"], "%Y-%m-%d").date()
            if start <= source_date <= end:
                questions.append(thread)

    questions.sort(key=lambda item: (item.get("source_date", ""), item.get("id", "")), reverse=True)
    if questions:
        status = "selected"
    elif existing_files:
        status = "empty" if empty_files == existing_files else "no_recent_open"
    else:
        status = "missing"
    return QuestionThreadSelection(
        status=status,
        files=files,
        open_count=open_count,
        selected_count=len(questions),
        questions=questions,
    )


def render_questions_for_prompt(selection: QuestionThreadSelection) -> str:
    if not selection.questions:
        return "最近 7 天没有可用的 open 问题。"
    lines = []
    for index, item in enumerate(selection.questions, start=1):
        lines.append(
            f"{index}. [{item['source_date']}] {item['question']} "
            f"（来源概念：{item['source_concept']}；领域：{item['domain']}；id：{item['id']}）"
        )
    return "\n".join(lines)


def upsert_questions_from_concepts(root: Path, target_date: str, concepts: list[dict], now_iso: str) -> dict:
    year_month = target_date[:7]
    path = question_thread_path(root, year_month)
    data = load_question_threads(path, allow_missing=True)
    data["version"] = QUESTION_THREAD_VERSION
    data["year_month"] = year_month

    by_id = {thread["id"]: thread for thread in data.get("threads", [])}
    upserted = 0
    for concept in concepts:
        source_concept = _clean_text(concept.get("name"))
        domain = _clean_text(concept.get("domain"))
        for question in concept.get("questions") or []:
            question_text = _clean_text(question)
            if not question_text:
                continue
            thread_id = build_question_id(target_date, source_concept, question_text)
            existing = by_id.get(thread_id)
            if existing:
                existing.update(
                    {
                        "question": question_text,
                        "source_date": target_date,
                        "source_concept": source_concept,
                        "domain": domain,
                        "status": existing.get("status") or "open",
                        "updated_at": now_iso,
                    }
                )
            else:
                by_id[thread_id] = {
                    "id": thread_id,
                    "question": question_text,
                    "source_date": target_date,
                    "source_concept": source_concept,
                    "domain": domain,
                    "status": "open",
                    "created_at": now_iso,
                    "updated_at": now_iso,
                }
            upserted += 1

    data["threads"] = sorted(by_id.values(), key=lambda item: (item.get("source_date", ""), item.get("id", "")), reverse=True)
    write_question_threads(path, data)
    today_count = sum(1 for thread in data["threads"] if thread.get("source_date") == target_date)
    return {
        "path": str(path),
        "upserted": upserted,
        "today_questions": today_count,
        "total_threads": len(data["threads"]),
    }


def build_question_id(target_date: str, concept: str, question: str) -> str:
    digest = hashlib.sha1(f"{concept}\n{question}".encode("utf-8")).hexdigest()[:10]
    return f"{target_date}-{_slugify(concept)}-{digest}"


def _slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text).strip("-")
    return slug[:40] or "concept"


def _clean_text(value: object) -> str:
    return str(value or "").strip()


def _year_month_from_path(path: Path) -> str:
    match = re.search(r"(\d{4}-\d{2})-question-threads\.json$", path.name)
    return match.group(1) if match else "1970-01"
