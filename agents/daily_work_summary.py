#!/usr/bin/env python3
"""Generate daily Git work summaries for local repositories.

This is the first independent local agent. It reads Git evidence from the
repositories under ~/projects by default and writes one Markdown summary per
repository into prework/YYYY-MM/YYYY-MM-DD/.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from orchestrator.llm import LLMRetryPolicy, call_chat_completion
DEFAULT_REPOSITORIES = [
    "AInote",
    "DailyLearningAssistant",
    "interview_prepare",
    "mcp",
    "ResearchPaperBase_cc",
    "ResearchPaperBase_codex",
]


@dataclass
class RepositoryConfig:
    name: str
    path: Path


@dataclass
class RemoteRepositoryConfig:
    name: str
    output_name: str
    urls: list[str]
    refs: list[str]


@dataclass
class CommitInfo:
    full_hash: str
    short_hash: str
    date: str
    author: str
    refs: str
    subject: str
    files: list[str]
    stat: str


@dataclass
class ChangeIgnoreRules:
    enabled: bool
    commit_subject_prefixes: tuple[str, ...]
    path_prefixes: tuple[str, ...]
    exact_paths: tuple[str, ...]


@dataclass
class WorktreeInfo:
    path: Path
    branch: str
    head: str
    status: list[str]


@dataclass
class SummaryEvidence:
    markdown: str
    has_confirmed_commits: bool
    has_primary_uncommitted_changes: bool
    has_branch_tip_changes: bool
    has_worktree_candidate_changes: bool
    evidence_type: str
    has_remote_ref_changes: bool = False

    @property
    def should_call_llm(self) -> bool:
        return any(
            (
                self.has_confirmed_commits,
                self.has_primary_uncommitted_changes,
                self.has_branch_tip_changes,
                self.has_worktree_candidate_changes,
                self.has_remote_ref_changes,
            )
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate work_summary_[repo].md files from local Git evidence.")
    parser.add_argument("--date", help="Target output date in YYYY-MM-DD format. Defaults to today in configured timezone.")
    parser.add_argument("--config", default=str(PROJECT_ROOT / "config.json"), help="Optional config JSON path.")
    parser.add_argument("--projects-root", default="~/projects", help="Directory containing default repositories.")
    parser.add_argument("--output-root", default=str(PROJECT_ROOT), help="Root where prework/ will be written.")
    parser.add_argument("--timezone", help="Timezone override, e.g. Asia/Shanghai.")
    parser.add_argument("--no-llm", action="store_true", help="Write the deterministic Git evidence summary directly.")
    parser.add_argument("--timeout", type=int, default=120, help="LLM request timeout in seconds.")
    parser.add_argument("--llm-retries", type=int, default=3, help="Maximum LLM attempts per repository.")
    parser.add_argument("--llm-retry-delay", type=float, default=3.0, help="Initial LLM retry delay in seconds.")
    return parser.parse_args()


def run_git(repo_path: Path, args: list[str], check: bool = False) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", "-C", str(repo_path), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or f"git {' '.join(args)} failed")
    return result


def run_git_ls_remote(url: str, ref: str, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "ls-remote", url, ref],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )


def load_config(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"[错误] 配置文件不是合法 JSON: {path} ({exc})")


def require_llm_config(config: dict) -> dict | None:
    llm = config.get("llm") or {}
    required = ("api_url", "api_key", "model")
    if not all(llm.get(key) for key in required):
        return None
    if str(llm["api_key"]).startswith("YOUR_"):
        return None
    return llm


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


def resolve_repositories(args: argparse.Namespace, config: dict) -> list[RepositoryConfig]:
    configured = config.get("repositories")
    repos: list[RepositoryConfig] = []

    if isinstance(configured, list) and configured:
        for item in configured:
            if isinstance(item, str):
                path = Path(os.path.expanduser(item)).resolve()
                repos.append(RepositoryConfig(path.name, path))
            elif isinstance(item, dict):
                name = item.get("name")
                raw_path = item.get("path")
                if not name or not raw_path:
                    raise SystemExit("[错误] repositories 中的对象必须包含 name 和 path。")
                repos.append(RepositoryConfig(str(name), Path(os.path.expanduser(str(raw_path))).resolve()))
        return repos

    projects_root = Path(os.path.expanduser(args.projects_root)).resolve()
    return [RepositoryConfig(name, projects_root / name) for name in DEFAULT_REPOSITORIES]


def detect_access_type(url: str) -> str:
    if url.startswith(("http://", "https://")):
        return "http_git"
    if url.startswith("ssh://") or re.match(r"^[^@\s]+@[^:\s]+:.+", url):
        return "ssh_git"
    return "git"


def sanitize_url_for_status(url: str) -> str:
    if not url.startswith(("http://", "https://")):
        return url
    parts = urlsplit(url)
    host = parts.netloc.rsplit("@", 1)[-1]
    return urlunsplit((parts.scheme, host, parts.path, "", ""))


def repo_name_from_url(url: str) -> str:
    if url.startswith(("http://", "https://", "ssh://")):
        path = urlsplit(url).path
    elif ":" in url and "@" in url.split(":", 1)[0]:
        path = url.split(":", 1)[1]
    else:
        path = url
    name = Path(path.rstrip("/")).name
    return name.removesuffix(".git") or "remote-repository"


def ref_display_name(ref: str) -> str:
    for prefix in ("refs/heads/", "refs/tags/"):
        if ref.startswith(prefix):
            return ref.removeprefix(prefix)
    return ref.removeprefix("refs/") or "ref"


def safe_output_name(name: str) -> str:
    cleaned = name.replace("/", "-").replace(":", "_")
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", cleaned).strip("._-")
    return cleaned or "remote_repository"


def resolve_remote_repositories(config: dict, local_repos: list[RepositoryConfig]) -> list[RemoteRepositoryConfig]:
    configured = config.get("remote_repositories") or []
    if not isinstance(configured, list):
        raise SystemExit("[错误] remote_repositories 必须是列表。")

    used_output_names = {safe_output_name(repo.name) for repo in local_repos}
    remotes: list[RemoteRepositoryConfig] = []

    for index, item in enumerate(configured, start=1):
        if not isinstance(item, dict):
            raise SystemExit(f"[错误] remote_repositories 第 {index} 项必须是对象。")
        if item.get("enabled", True) is False:
            continue

        raw_urls = item.get("urls") or []
        if isinstance(raw_urls, str):
            raw_urls = [raw_urls]
        urls = [str(url).strip() for url in raw_urls if str(url).strip()]
        if not urls:
            raise SystemExit(f"[错误] remote_repositories 第 {index} 项缺少 urls。")

        raw_refs = item.get("refs") or []
        if isinstance(raw_refs, str):
            raw_refs = [raw_refs]
        refs = [str(ref).strip() for ref in raw_refs if str(ref).strip()]
        if not refs:
            refs = ["refs/heads/main"]

        explicit_name = str(item.get("name") or "").strip()
        if explicit_name:
            name = explicit_name
            output_name = safe_output_name(explicit_name)
            if output_name in used_output_names:
                raise SystemExit(f"[错误] 远端仓库输出名重复: {output_name}")
            used_output_names.add(output_name)
            remotes.append(RemoteRepositoryConfig(name, output_name, urls, refs))
            continue

        base_name = repo_name_from_url(urls[0])
        for ref in refs:
            display_name = f"{base_name}:{ref_display_name(ref)}"
            output_name = safe_output_name(display_name)
            if output_name in used_output_names:
                raise SystemExit(f"[错误] 远端仓库输出名重复: {output_name}")
            used_output_names.add(output_name)
            remotes.append(RemoteRepositoryConfig(display_name, output_name, urls, [ref]))

    return remotes


def day_window(target_date: str, timezone: ZoneInfo) -> tuple[datetime, datetime]:
    target = datetime.strptime(target_date, "%Y-%m-%d").date()
    previous_day = target - timedelta(days=1)
    start = datetime.combine(previous_day, time.min, timezone)
    end = datetime.combine(target, time.min, timezone)
    return start, end


def is_git_repository(path: Path) -> bool:
    if not path.exists():
        return False
    result = run_git(path, ["rev-parse", "--is-inside-work-tree"])
    return result.returncode == 0 and result.stdout.strip() == "true"


def current_branch(path: Path) -> str:
    result = run_git(path, ["branch", "--show-current"])
    branch = result.stdout.strip()
    if branch:
        return branch
    result = run_git(path, ["rev-parse", "--short", "HEAD"])
    return f"detached@{result.stdout.strip()}" if result.returncode == 0 else "未知"


def git_status(path: Path) -> list[str]:
    result = run_git(path, ["status", "--short"])
    if result.returncode != 0:
        return [f"[读取失败] {result.stderr.strip()}"]
    return [line for line in result.stdout.splitlines() if line.strip()]


def diff_name_status(path: Path, cached: bool) -> list[str]:
    args = ["diff", "--name-status"]
    if cached:
        args.insert(1, "--cached")
    result = run_git(path, args)
    if result.returncode != 0:
        return [f"[读取失败] {result.stderr.strip()}"]
    return [line for line in result.stdout.splitlines() if line.strip()]


def diff_stat(path: Path, cached: bool, paths: list[str] | None = None) -> str:
    args = ["diff", "--stat"]
    if cached:
        args.insert(1, "--cached")
    if paths is not None:
        if not paths:
            return ""
        args.extend(["--", *paths])
    result = run_git(path, args)
    return result.stdout.strip() if result.returncode == 0 else result.stderr.strip()


def publish_commit_prefixes(config: dict) -> tuple[str, ...]:
    configured = ((config.get("publish") or {}).get("commit_message") or "").strip()
    prefixes = ["Publish daily learning report"]
    if configured:
        prefix = configured.split("{", 1)[0].strip()
        if prefix:
            prefixes.append(prefix)
    return tuple(dict.fromkeys(prefixes))


def publish_artifact_matchers(config: dict) -> tuple[tuple[str, ...], tuple[str, ...]]:
    configured_paths = ((config.get("publish") or {}).get("paths") or []) if isinstance(config, dict) else []
    raw_paths = configured_paths or [
        "daily_report/{year_month}/{date}-learning-report.html",
        "daily_report/manifest.json",
        "knowledge_log/{year_month}-knowledge-log.md",
        "knowledge_log/{year_month}-question-threads.json",
        "knowledge_log/manifest.json",
        "index.html",
    ]

    prefixes: list[str] = []
    exact_paths: list[str] = []
    for raw_path in raw_paths:
        path_text = str(raw_path).strip().lstrip("./")
        if not path_text:
            continue
        if "{" in path_text:
            prefix = path_text.split("{", 1)[0]
            if prefix:
                prefixes.append(prefix)
        else:
            exact_paths.append(path_text)
    return tuple(dict.fromkeys(prefixes)), tuple(dict.fromkeys(exact_paths))


def build_ignore_rules(repo: RepositoryConfig, config: dict) -> ChangeIgnoreRules:
    try:
        is_self_repo = repo.path.resolve() == PROJECT_ROOT.resolve()
    except OSError:
        is_self_repo = repo.name == PROJECT_ROOT.name
    if repo.name == PROJECT_ROOT.name:
        is_self_repo = True

    prefixes, exact_paths = publish_artifact_matchers(config)
    return ChangeIgnoreRules(
        enabled=is_self_repo,
        commit_subject_prefixes=publish_commit_prefixes(config),
        path_prefixes=prefixes,
        exact_paths=exact_paths,
    )


def normalize_git_path(path_text: str) -> str:
    return path_text.strip().strip('"').lstrip("./")


def change_paths_from_name_status(line: str) -> list[str]:
    parts = line.split("\t")
    if len(parts) >= 3 and parts[0].startswith(("R", "C")):
        return [normalize_git_path(parts[1]), normalize_git_path(parts[2])]
    if len(parts) >= 2:
        return [normalize_git_path(parts[-1])]
    return [normalize_git_path(line)]


def change_paths_from_status(line: str) -> list[str]:
    path_text = line[3:] if len(line) > 3 else line
    if " -> " in path_text:
        return [normalize_git_path(part) for part in path_text.split(" -> ", 1)]
    return [normalize_git_path(path_text)]


def path_matches_publish_artifact(path_text: str, rules: ChangeIgnoreRules) -> bool:
    normalized = normalize_git_path(path_text)
    return normalized in rules.exact_paths or any(normalized.startswith(prefix) for prefix in rules.path_prefixes)


def all_paths_match_publish_artifacts(paths: list[str], rules: ChangeIgnoreRules) -> bool:
    return bool(paths) and all(path_matches_publish_artifact(path, rules) for path in paths)


def should_ignore_publish_commit(commit: CommitInfo, rules: ChangeIgnoreRules) -> bool:
    if not rules.enabled:
        return False
    if not any(commit.subject.startswith(prefix) for prefix in rules.commit_subject_prefixes):
        return False
    changed_paths: list[str] = []
    for line in commit.files:
        changed_paths.extend(change_paths_from_name_status(line))
    return all_paths_match_publish_artifacts(changed_paths, rules)


def filter_publish_artifact_lines(lines: list[str], rules: ChangeIgnoreRules, path_parser) -> tuple[list[str], list[str]]:
    if not rules.enabled:
        return lines, []
    kept: list[str] = []
    ignored: list[str] = []
    for line in lines:
        paths = path_parser(line)
        if all_paths_match_publish_artifacts(paths, rules):
            ignored.append(line)
        else:
            kept.append(line)
    return kept, ignored


def parse_commits(raw: str) -> list[tuple[str, str, str, str, str, str]]:
    commits = []
    for record in raw.split("\x1e"):
        record = record.strip("\n")
        if not record:
            continue
        parts = record.split("\x1f")
        if len(parts) >= 6:
            commits.append(tuple(parts[:6]))
    return commits


def collect_commits(path: Path, start: datetime, end: datetime) -> list[CommitInfo]:
    pretty = "%H%x1f%h%x1f%ad%x1f%an%x1f%D%x1f%s%x1e"
    result = run_git(
        path,
        [
            "log",
            "--all",
            f"--since={start.isoformat()}",
            f"--until={end.isoformat()}",
            "--date=iso-strict",
            f"--pretty=format:{pretty}",
        ],
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())

    commits: list[CommitInfo] = []
    for full_hash, short_hash, date, author, refs, subject in parse_commits(result.stdout):
        files_result = run_git(path, ["show", "--format=", "--name-status", "--find-renames", full_hash])
        stat_result = run_git(path, ["show", "--format=", "--stat", "--find-renames", full_hash])
        files = [line for line in files_result.stdout.splitlines() if line.strip()] if files_result.returncode == 0 else []
        stat = stat_result.stdout.strip() if stat_result.returncode == 0 else stat_result.stderr.strip()
        commits.append(CommitInfo(full_hash, short_hash, date, author, refs, subject, files, stat))
    return commits


def collect_recent_branch_tips(path: Path, start: datetime, end: datetime, rules: ChangeIgnoreRules) -> list[str]:
    result = run_git(path, ["for-each-ref", "refs/heads", "--format=%(refname:short)%09%(objectname:short)%09%(committerdate:iso-strict)%09%(subject)"])
    if result.returncode != 0:
        return [f"[读取失败] {result.stderr.strip()}"]

    branch_lines: list[str] = []
    for line in result.stdout.splitlines():
        parts = line.split("\t", 3)
        if len(parts) != 4:
            continue
        name, head, date_text, subject = parts
        try:
            tip_date = datetime.fromisoformat(date_text)
        except ValueError:
            continue
        if rules.enabled and any(subject.startswith(prefix) for prefix in rules.commit_subject_prefixes):
            continue
        if start <= tip_date < end:
            branch_lines.append(f"- `{name}` @ `{head}` ({date_text})：{subject}")
    return branch_lines


def parse_worktree_blocks(raw: str) -> list[dict[str, str]]:
    blocks: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for line in raw.splitlines():
        if not line.strip():
            if current:
                blocks.append(current)
                current = {}
            continue
        key, _, value = line.partition(" ")
        if key == "worktree" and current:
            blocks.append(current)
            current = {}
        current[key] = value
    if current:
        blocks.append(current)
    return blocks


def collect_worktrees(path: Path, rules: ChangeIgnoreRules) -> list[WorktreeInfo]:
    result = run_git(path, ["worktree", "list", "--porcelain"])
    if result.returncode != 0:
        return [WorktreeInfo(path, "读取失败", "", [result.stderr.strip()])]

    worktrees: list[WorktreeInfo] = []
    for block in parse_worktree_blocks(result.stdout):
        wt_path = Path(block.get("worktree", "")).expanduser()
        if not wt_path.exists():
            continue
        branch_ref = block.get("branch", "")
        branch = branch_ref.removeprefix("refs/heads/") if branch_ref else "detached"
        head = block.get("HEAD", "")
        status, _ = filter_publish_artifact_lines(git_status(wt_path), rules, change_paths_from_status)
        worktrees.append(WorktreeInfo(wt_path, branch, head[:12], status))
    return worktrees


def render_list(items: list[str], empty_text: str) -> str:
    if not items:
        return empty_text
    return "\n".join(f"- `{item}`" for item in items)


def render_commit(commit: CommitInfo) -> str:
    refs = f"；引用：{commit.refs}" if commit.refs else ""
    files = "\n".join(f"  - `{line}`" for line in commit.files[:80]) or "  - 未记录文件列表"
    if len(commit.files) > 80:
        files += f"\n  - ... 另有 {len(commit.files) - 80} 条文件记录"
    stat = commit.stat or "无统计信息"
    return f"""### `{commit.short_hash}`：{commit.subject}

- 时间：{commit.date}
- 作者：{commit.author}{refs}
- 完整提交：`{commit.full_hash}`

变更文件：

{files}

统计信息：

```text
{stat}
```
"""


def build_summary_evidence(repo: RepositoryConfig, target_date: str, start: datetime, end: datetime, config: dict) -> SummaryEvidence:
    path = repo.path
    checked_window = f"{start.isoformat()} 至 {end.isoformat()}"
    ignore_rules = build_ignore_rules(repo, config)

    if not path.exists():
        markdown = f"""# {target_date} {repo.name} 更改总结

## 仓库状态

- 仓库路径：`{path}`
- 检查窗口：{checked_window}
- 状态：仓库目录不存在。

## 结论

未能读取该仓库的 Git 记录。后续概念提炼时应忽略该仓库的技术主题，或在仓库恢复后补跑第 1 步 Agent。
"""
        return SummaryEvidence(markdown, False, False, False, False, "unavailable")

    if not is_git_repository(path):
        markdown = f"""# {target_date} {repo.name} 更改总结

## 仓库状态

- 仓库路径：`{path}`
- 检查窗口：{checked_window}
- 状态：目录存在，但不是 Git 工作区。

## 结论

未能读取该仓库的 Git 记录。后续概念提炼时应忽略该仓库的技术主题，或在仓库恢复为 Git 仓库后补跑第 1 步 Agent。
"""
        return SummaryEvidence(markdown, False, False, False, False, "unavailable")

    try:
        commits = collect_commits(path, start, end)
        ignored_commits = [commit for commit in commits if should_ignore_publish_commit(commit, ignore_rules)]
        commits = [commit for commit in commits if not should_ignore_publish_commit(commit, ignore_rules)]
        branch_tips = collect_recent_branch_tips(path, start, end, ignore_rules)
        worktrees = collect_worktrees(path, ignore_rules)
        status, ignored_status = filter_publish_artifact_lines(git_status(path), ignore_rules, change_paths_from_status)
        unstaged, ignored_unstaged = filter_publish_artifact_lines(diff_name_status(path, cached=False), ignore_rules, change_paths_from_name_status)
        staged, ignored_staged = filter_publish_artifact_lines(diff_name_status(path, cached=True), ignore_rules, change_paths_from_name_status)
        unstaged_stat = diff_stat(path, cached=False, paths=[path for line in unstaged for path in change_paths_from_name_status(line)])
        staged_stat = diff_stat(path, cached=True, paths=[path for line in staged for path in change_paths_from_name_status(line)])
    except RuntimeError as exc:
        markdown = f"""# {target_date} {repo.name} 更改总结

## 仓库状态

- 仓库路径：`{path}`
- 检查窗口：{checked_window}
- 当前分支：`{current_branch(path)}`
- 状态：Git 读取失败。

## 错误信息

```text
{exc}
```
"""
        return SummaryEvidence(markdown, False, False, False, False, "unavailable")

    ignored_note_lines = []
    if ignore_rules.enabled:
        ignored_count = len(ignored_commits) + len(ignored_status) + len(ignored_unstaged) + len(ignored_staged)
        if ignored_count:
            ignored_note_lines.append(
                f"- 已忽略自身自动发布日报产生的 Git 变更：{len(ignored_commits)} 个自动发布提交，"
                f"{len(ignored_status)} 条工作区状态，{len(ignored_staged)} 条已暂存记录，{len(ignored_unstaged)} 条未暂存记录。"
            )
    ignored_note = "\n".join(ignored_note_lines)

    changed_worktrees = [wt for wt in worktrees if wt.status]
    primary_clean = not status
    has_branch_or_worktree_change = bool(branch_tips or changed_worktrees)

    if not commits and not status and not has_branch_or_worktree_change:
        markdown = f"""# {target_date} {repo.name} 更改总结

## 结论

当日无变更。

## 基本信息

| 项目 | 内容 |
| --- | --- |
| 仓库 | `{repo.name}` |
| 路径 | `{path}` |
| 当前分支 | `{current_branch(path)}` |
| 检查窗口 | {checked_window} |
| 窗口内提交数 | 0 |
| 主工作区状态 | 干净 |
| 存在待确认变化线索的 worktree 数 | 0 |

## 对后续概念提炼任务的备注

- 该仓库在检查窗口内无 Git 提交。
- 主工作区无未提交变更。
- 未发现窗口内更新的本地分支或包含待确认变化线索的 worktree。
- 后续概念提炼可将该仓库视为“当日无新增技术线索”。
{ignored_note}
"""
        return SummaryEvidence(markdown, False, False, False, False, "no_change")

    if commits:
        headline = f"检查窗口内发现 {len(commits)} 个提交。"
    elif status:
        headline = "检查窗口内未发现提交，但主工作区存在未提交变更。"
    elif has_branch_or_worktree_change:
        headline = "主路径无未提交变更，但其他 branch 或 worktree 存在待确认变化线索。"
    else:
        headline = "检查窗口内未发现提交，主路径、分支提示和 worktree 均未发现明确变化。"

    commit_section = "\n".join(render_commit(commit) for commit in commits) if commits else "检查窗口内未发现任何本地分支可达的提交。"
    branch_section = "\n".join(branch_tips) if branch_tips else "未发现 tip 时间落在检查窗口内的本地分支。"

    worktree_lines = []
    for wt in worktrees:
        state = "存在当前待确认变化线索" if wt.status else "干净"
        worktree_lines.append(f"### `{wt.branch}` @ `{wt.head}`")
        worktree_lines.append(f"- 路径：`{wt.path}`")
        worktree_lines.append(f"- 状态：{state}")
        if wt.status:
            worktree_lines.append("")
            worktree_lines.append(render_list(wt.status, "无未提交变更。"))
        worktree_lines.append("")
    worktree_section = "\n".join(worktree_lines).strip() or "未读取到 worktree 信息。"

    themes = infer_theme_lines(commits, status, branch_tips, changed_worktrees)

    markdown = f"""# {target_date} {repo.name} 更改总结

本总结由本地第 1 步 Agent 基于 Git 证据生成。目标日期为 `{target_date}`，实际检查的是目标日期前一天的提交窗口。

## 提交概览

| 项目 | 内容 |
| --- | --- |
| 仓库 | `{repo.name}` |
| 路径 | `{path}` |
| 当前分支 | `{current_branch(path)}` |
| 检查窗口 | {checked_window} |
| 窗口内提交数 | {len(commits)} |
| 主工作区状态 | {"干净" if primary_clean else "存在未提交变更"} |
| 存在待确认变化线索的 worktree 数 | {len(changed_worktrees)} |

{headline}

## 一、窗口内提交记录

{commit_section}

## 二、主工作区未提交变更

### 状态摘要

{render_list(status, "主工作区当前无未提交变更。")}

### 已暂存文件

{render_list(staged, "无已暂存变更。")}

### 未暂存文件

{render_list(unstaged, "无未暂存变更。")}

### 已暂存统计

```text
{staged_stat or "无"}
```

### 未暂存统计

```text
{unstaged_stat or "无"}
```

## 三、分支与 worktree 线索

### 检查窗口内更新的本地分支

{branch_section}

### Worktree 状态（当前待确认变化线索）

{worktree_section}

## 四、主要工作主题

{themes}

## 五、可能涉及的知识点线索

{infer_concept_lines(commits, status, branch_tips, changed_worktrees)}

## 六、对后续概念提炼任务的备注

- 本文件只基于 Git 提交、工作区状态、分支和 worktree 元数据生成。
- Git 无法可靠证明未提交变更发生的具体日期，因此 worktree 未提交变更只作为“当前待确认变化线索”，不要等同于目标窗口内已经完成的提交事实。
- 如果主路径无变化但 branch 或 worktree 有待确认变化线索，后续任务应优先关注对应分支/worktree 的提交主题和文件路径，并在必要时人工确认时间归属。
{ignored_note}
"""
    if commits:
        evidence_type = "confirmed_change"
    else:
        evidence_type = "candidate_change"

    return SummaryEvidence(
        markdown=markdown,
        has_confirmed_commits=bool(commits),
        has_primary_uncommitted_changes=bool(status),
        has_branch_tip_changes=bool(branch_tips),
        has_worktree_candidate_changes=bool(changed_worktrees),
        evidence_type=evidence_type,
    )


def stderr_excerpt(text: str, limit: int = 600) -> str:
    one_line = " ".join((text or "").split())
    return one_line[:limit]


def classify_remote_failure(result: subprocess.CompletedProcess[str]) -> str:
    blob = f"{result.stderr}\n{result.stdout}".lower()
    if any(token in blob for token in ("permission denied", "authentication failed", "could not read username", "access denied")):
        return "auth_failed"
    if any(token in blob for token in ("repository not found", "not found", "does not appear to be a git repository")):
        return "repo_missing"
    if any(token in blob for token in ("could not resolve host", "failed to connect", "connection timed out", "network is unreachable", "tls", "ssl")):
        return "network_failed"
    return "command_failed"


def parse_ls_remote_sha(stdout: str, ref: str) -> str | None:
    for line in stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1] == ref:
            return parts[0]
    return None


def previous_remote_sha(output_root: Path, target_date: str, remote_name: str, ref: str) -> str | None:
    prework_root = output_root / "prework"
    if not prework_root.exists():
        return None

    try:
        target = datetime.strptime(target_date, "%Y-%m-%d").date()
    except ValueError:
        return None

    candidates: list[Path] = []
    for status_path in prework_root.glob("????-??/????-??-??/run_status.json"):
        try:
            candidate_date = datetime.strptime(status_path.parent.name, "%Y-%m-%d").date()
        except ValueError:
            continue
        if candidate_date < target:
            candidates.append(status_path)

    for status_path in sorted(candidates, key=lambda path: path.parent.name, reverse=True):
        try:
            data = json.loads(status_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        repositories = (((data.get("agents") or {}).get("daily_work_summary") or {}).get("repositories") or [])
        for repo in repositories:
            if not isinstance(repo, dict) or repo.get("source") != "remote" or repo.get("name") != remote_name:
                continue
            if repo.get("status") != "success":
                continue
            for ref_status in ((repo.get("remote") or {}).get("refs") or []):
                if not isinstance(ref_status, dict):
                    continue
                if ref_status.get("ref") == ref and ref_status.get("status") in {"first_seen", "unchanged", "changed"}:
                    sha = ref_status.get("current_sha")
                    if sha:
                        return str(sha)
    return None


def check_remote_ref(remote: RemoteRepositoryConfig, ref: str, output_root: Path, target_date: str) -> dict:
    attempts: list[dict] = []
    selected_access = None
    current_sha = None
    missing_attempt = False

    for url in remote.urls:
        access = detect_access_type(url)
        safe_url = sanitize_url_for_status(url)
        try:
            result = run_git_ls_remote(url, ref)
        except subprocess.TimeoutExpired as exc:
            attempts.append(
                {
                    "access": access,
                    "url": safe_url,
                    "status": "network_failed",
                    "returncode": None,
                    "remote_ref": ref,
                    "sha": None,
                    "stderr_excerpt": stderr_excerpt(str(exc)),
                }
            )
            continue

        sha = parse_ls_remote_sha(result.stdout, ref) if result.returncode == 0 else None
        if result.returncode == 0 and sha:
            attempts.append(
                {
                    "access": access,
                    "url": safe_url,
                    "status": "success",
                    "returncode": result.returncode,
                    "remote_ref": ref,
                    "sha": sha,
                    "stderr_excerpt": stderr_excerpt(result.stderr),
                }
            )
            selected_access = access
            current_sha = sha
            break

        if result.returncode == 0:
            missing_attempt = True
            status = "ref_missing"
        else:
            status = classify_remote_failure(result)
        attempts.append(
            {
                "access": access,
                "url": safe_url,
                "status": status,
                "returncode": result.returncode,
                "remote_ref": ref,
                "sha": sha,
                "stderr_excerpt": stderr_excerpt(result.stderr or result.stdout),
            }
        )

    if current_sha:
        for skipped_url in remote.urls[len(attempts) :]:
            attempts.append(
                {
                    "access": detect_access_type(skipped_url),
                    "url": sanitize_url_for_status(skipped_url),
                    "status": "skipped_after_success",
                }
            )

        previous_sha = previous_remote_sha(output_root, target_date, remote.name, ref)
        if previous_sha is None:
            status = "first_seen"
            changed = False
        elif previous_sha == current_sha:
            status = "unchanged"
            changed = False
        else:
            status = "changed"
            changed = True
        return {
            "ref": ref,
            "status": status,
            "previous_sha": previous_sha,
            "current_sha": current_sha,
            "changed": changed,
            "selected_access": selected_access,
            "attempts": attempts,
        }

    return {
        "ref": ref,
        "status": "ref_missing" if missing_attempt else "failed",
        "previous_sha": previous_remote_sha(output_root, target_date, remote.name, ref),
        "current_sha": None,
        "changed": False,
        "selected_access": None,
        "attempts": attempts,
    }


def render_remote_attempts(attempts: list[dict]) -> str:
    if not attempts:
        return "- 未记录访问尝试。"
    lines = []
    for attempt in attempts:
        detail = f"- `{attempt.get('access')}` `{attempt.get('url')}`：{attempt.get('status')}"
        if attempt.get("sha"):
            detail += f"，SHA `{str(attempt['sha'])[:12]}`"
        if attempt.get("stderr_excerpt"):
            detail += f"，诊断：{attempt['stderr_excerpt']}"
        lines.append(detail)
    return "\n".join(lines)


def build_remote_summary_evidence(remote: RemoteRepositoryConfig, target_date: str, output_root: Path) -> tuple[SummaryEvidence, dict]:
    ref_statuses = [check_remote_ref(remote, ref, output_root, target_date) for ref in remote.refs]
    changed_refs = [item for item in ref_statuses if item.get("changed")]
    failed_refs = [item for item in ref_statuses if item.get("status") in {"failed", "ref_missing"}]
    successful_refs = [item for item in ref_statuses if item.get("status") in {"first_seen", "unchanged", "changed"}]

    rows = []
    sections = []
    for item in ref_statuses:
        previous_sha = item.get("previous_sha") or "无历史记录"
        current_sha = item.get("current_sha") or "未读取到"
        rows.append(
            f"| `{item['ref']}` | {item['status']} | `{str(previous_sha)[:12]}` | `{str(current_sha)[:12]}` | "
            f"{'是' if item.get('changed') else '否'} | {item.get('selected_access') or '无'} |"
        )
        sections.append(
            f"""### `{item['ref']}`

- 状态：{item['status']}
- 历史 SHA：`{previous_sha}`
- 当前 SHA：`{current_sha}`
- 是否发现远端 ref 指针变化：{'是' if item.get('changed') else '否'}

访问尝试：

{render_remote_attempts(item.get('attempts') or [])}
"""
        )

    if changed_refs:
        conclusion = f"发现 {len(changed_refs)} 个远端 ref 指针变化。"
        evidence_type = "remote_ref_change"
    elif successful_refs and not failed_refs:
        conclusion = "未发现远端 ref 指针变化；首次看到的 ref 只记录基线，不视为新增提交。"
        evidence_type = "no_change"
    elif successful_refs:
        conclusion = "部分远端 ref 已读取，部分 ref 读取失败或不存在。"
        evidence_type = "unavailable"
    else:
        conclusion = "所有远端 ref 均读取失败或不存在。"
        evidence_type = "unavailable"

    markdown = f"""# {target_date} {remote.name} 更改总结

本总结由第 1 步 Agent 基于远端 Git ref 元数据生成。远端仓库只通过 `git ls-remote` 读取 ref 指针，不 clone、不 fetch、不下载提交对象、文件树或工作区内容。

## 结论

{conclusion}

## 基本信息

| 项目 | 内容 |
| --- | --- |
| 仓库 | `{remote.name}` |
| 来源 | 远端 Git |
| 访问 URL 数 | {len(remote.urls)} |
| 监控 ref 数 | {len(remote.refs)} |

## Ref 检查结果

| Ref | 状态 | 历史 SHA | 当前 SHA | 指针变化 | 成功访问方式 |
| --- | --- | --- | --- | --- | --- |
{chr(10).join(rows)}

## 访问诊断

{chr(10).join(sections)}

## 主要工作主题

- 远端监控只能证明 ref 指针是否变化，不能证明新增提交数量、提交信息、作者、文件列表或 diff 内容。
- 若状态为 `changed`，后续概念提炼只能表述为“远端版本变化线索”或“ref 指针变化”，不要编造具体提交详情。

## 可能涉及的知识点线索

- Git 远端引用、分支和 tag 指针
- 只读仓库监控、最小权限访问
- 基于历史状态的变更检测

## 对后续概念提炼任务的备注

- 本文件和本地仓库的 `work_summary_*.md` 一样进入后续输入，但内容来源仅限远端 ref 元数据。
- 对私人仓库，SSH 成功通常依赖本机 SSH key 或 SSH agent；状态文件不会记录密钥。
- HTTP(S) URL 中的用户名、token 或密码在状态记录中会被脱敏。
"""

    status = "success" if not failed_refs else ("failed" if not successful_refs else "degraded")
    return (
        SummaryEvidence(
            markdown=markdown,
            has_confirmed_commits=False,
            has_primary_uncommitted_changes=False,
            has_branch_tip_changes=False,
            has_worktree_candidate_changes=False,
            evidence_type=evidence_type,
            has_remote_ref_changes=bool(changed_refs),
        ),
        {
            "name": remote.name,
            "source": "remote",
            "status": status,
            "evidence_type": evidence_type,
            "remote": {
                "urls": [sanitize_url_for_status(url) for url in remote.urls],
                "refs": ref_statuses,
            },
        },
    )


def infer_theme_lines(
    commits: list[CommitInfo],
    status: list[str],
    branch_tips: list[str],
    changed_worktrees: list[WorktreeInfo],
) -> str:
    lines: list[str] = []
    if commits:
        subjects = "; ".join(commit.subject for commit in commits[:8])
        lines.append(f"- 提交主题：{subjects}")
    if status:
        lines.append("- 主工作区存在未提交变更，需要后续确认这些变更是否属于当天正式工作。")
    if branch_tips:
        lines.append("- 有本地分支 tip 落在检查窗口内，说明工作可能发生在非当前分支。")
    if changed_worktrees:
        names = ", ".join(wt.branch for wt in changed_worktrees)
        lines.append(f"- 有 worktree 存在当前待确认变化线索：{names}。")
    if not lines:
        lines.append("- 未发现明确工作主题。")
    return "\n".join(lines)


def infer_concept_lines(
    commits: list[CommitInfo],
    status: list[str],
    branch_tips: list[str],
    changed_worktrees: list[WorktreeInfo],
) -> str:
    paths = []
    for commit in commits:
        paths.extend(commit.files)
    paths.extend(status)

    lower_blob = "\n".join(paths + [commit.subject for commit in commits]).lower()
    concepts: list[str] = []

    keyword_map = [
        ("prompt", "提示词工程、任务约束设计"),
        ("agent", "Agent 工作流、任务编排"),
        ("workflow", "自动化工作流、流水线设计"),
        ("manifest", "静态站点索引、发布契约"),
        ("html", "静态页面生成、前端呈现"),
        ("css", "视觉系统、响应式布局"),
        ("python", "脚本化自动化、文件处理"),
        ("test", "测试与回归验证"),
        ("llm", "大语言模型调用与输出约束"),
        ("git", "版本控制、变更追踪"),
    ]
    for keyword, concept in keyword_map:
        if keyword in lower_blob and concept not in concepts:
            concepts.append(concept)

    if branch_tips:
        concepts.append("分支隔离、并行开发")
    if changed_worktrees:
        concepts.append("Git worktree、多工作区协作")
    if status and not commits:
        concepts.append("未提交变更管理、工作区状态审计")

    if not concepts:
        return "- 未发现明确知识点线索。"
    return "\n".join(f"- {concept}" for concept in concepts)


def strip_markdown_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def call_llm(llm: dict, prompt: str, timeout: int, retries: int, retry_delay: float) -> str:
    return call_chat_completion(
        llm,
        [{"role": "user", "content": prompt}],
        timeout=timeout,
        retry_policy=LLMRetryPolicy(attempts=retries, initial_delay=retry_delay),
        temperature=llm.get("temperature", 0.4),
    )


def build_llm_prompt(repo: RepositoryConfig, target_date: str, evidence_markdown: str) -> str:
    return f"""你是“每日代码变更观察员”。请基于下面的 Git 证据草稿，生成一份适合后续概念提炼任务使用的正式 Markdown 工作总结。

仓库：{repo.name}
目标日期：{target_date}

重要边界：
- 只能基于证据草稿中可确认的信息总结，不要编造提交内容、文件变化或技术意图。
- “窗口内提交记录”是目标日期前一天的已确认提交事实。
- “主工作区未提交变更”和“worktree 状态”只能作为当前待确认变化线索；Git 不能证明它们一定发生在目标日期前一天，因此不要写成已经完成的昨日事实。
- 如果证据来自远端仓库监控，只能说明远端 ref 指针是否变化；不能编造提交详情、作者、文件列表、diff 或新增提交数量。
- 如果没有提交，也要保留“无提交记录”的结论；如果只有待确认变化线索，要明确标注“待确认”。
- 输出必须是完整 Markdown 文件内容，不要输出 JSON，不要包裹 markdown 代码块。
- 文件应包含：仓库名称、日期、当日提交概览、关键文件变更、主要工作主题、可能涉及的知识点线索、对后续概念提炼任务有帮助的备注。
- 语气清晰、可复盘，不要只写流水账；但所有推断都必须能从证据草稿找到依据。

Git 证据草稿：

```markdown
{evidence_markdown}
```
"""


def generate_llm_summary(
    repo: RepositoryConfig,
    target_date: str,
    evidence: str,
    llm: dict,
    timeout: int,
    retries: int,
    retry_delay: float,
) -> str:
    prompt = build_llm_prompt(repo, target_date, evidence)
    content = strip_markdown_fence(call_llm(llm, prompt, timeout, retries, retry_delay))
    if not content.strip():
        raise RuntimeError("LLM 返回空内容。")
    if "待确认" not in content and "worktree" in evidence.lower():
        content += "\n\n## 自动校验备注\n\n- 证据草稿包含 worktree 信息；其中未提交变更只能视为当前待确认变化线索，不应等同于目标窗口内的提交事实。\n"
    return content.rstrip() + "\n"


def relative_to_root(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
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


def write_agent_status(
    status_path: Path,
    target_date: str,
    agent_status: dict,
    now_iso: str,
) -> None:
    status_data = load_status_file(status_path, target_date)
    status_data["date"] = target_date
    status_data["updated_at"] = now_iso
    status_data.setdefault("agents", {})
    status_data["agents"]["daily_work_summary"] = agent_status

    status_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = status_path.with_suffix(".json.tmp")
    temp_path.write_text(json.dumps(status_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp_path.replace(status_path)


def summarize_agent_status(repositories: list[dict]) -> str:
    if any(repo["status"] == "failed" for repo in repositories):
        return "failed"
    if any(repo["status"] == "degraded" for repo in repositories):
        return "partial_success"
    return "success"


def summarize_repository_statuses(repositories: list[dict]) -> dict:
    summary = {
        "local_repositories": 0,
        "remote_repositories": 0,
        "ssh_git_success": 0,
        "http_git_success": 0,
        "remote_failed_refs": 0,
        "remote_changed_refs": 0,
    }
    for repo in repositories:
        if repo.get("source") == "remote":
            summary["remote_repositories"] += 1
            for ref_status in ((repo.get("remote") or {}).get("refs") or []):
                if ref_status.get("status") in {"failed", "ref_missing"}:
                    summary["remote_failed_refs"] += 1
                if ref_status.get("changed"):
                    summary["remote_changed_refs"] += 1
                selected = ref_status.get("selected_access")
                if selected == "ssh_git":
                    summary["ssh_git_success"] += 1
                elif selected == "http_git":
                    summary["http_git_success"] += 1
        else:
            summary["local_repositories"] += 1
    return summary


def main() -> int:
    args = parse_args()
    config = load_config(Path(args.config))
    timezone = resolve_timezone(args, config)
    target_date = resolve_target_date(args, timezone)
    start, end = day_window(target_date, timezone)
    started_at = datetime.now(timezone).isoformat()

    output_root = Path(os.path.expanduser(args.output_root)).resolve()
    output_dir = output_root / "prework" / target_date[:7] / target_date
    output_dir.mkdir(parents=True, exist_ok=True)
    status_path = output_dir / "run_status.json"

    repos = resolve_repositories(args, config)
    llm = None if args.no_llm else require_llm_config(config)
    if args.no_llm:
        print("[信息] 已启用 --no-llm，将直接写入 Git 证据总结。")
    elif not llm:
        print("[警告] config.json 中未找到可用 llm 配置，将直接写入 Git 证据总结。")

    remote_repos = resolve_remote_repositories(config, repos)
    repository_statuses: list[dict] = []

    for repo in repos:
        evidence = build_summary_evidence(repo, target_date, start, end, config)
        evidence_markdown = evidence.markdown.rstrip() + "\n"
        content = evidence_markdown
        repo_status = "success"
        llm_status = "skipped_disabled" if args.no_llm else "skipped_unconfigured"
        llm_error = None

        if llm and evidence.should_call_llm:
            try:
                content = generate_llm_summary(
                    repo,
                    target_date,
                    evidence_markdown,
                    llm,
                    args.timeout,
                    args.llm_retries,
                    args.llm_retry_delay,
                )
                print(f"[LLM] {repo.name}: 已生成正式总结。")
                llm_status = "success"
            except RuntimeError as exc:
                llm_error = str(exc)
                llm_status = "failed"
                repo_status = "degraded"
                print(f"[警告] {repo.name}: LLM 总结失败，改写入 Git 证据总结。原因：{exc}")
        elif llm:
            llm_status = "skipped_no_change"
            print(f"[跳过] {repo.name}: 未发现提交或待确认变化线索，不调用 LLM。")

        output_path = output_dir / f"work_summary_{repo.name}.md"
        output_path.write_text(content, encoding="utf-8")
        print(f"[完成] {repo.name}: {output_path}")

        repository_statuses.append(
            {
                "name": repo.name,
                "source": "local",
                "path": str(repo.path),
                "status": repo_status,
                "evidence_type": evidence.evidence_type,
                "output_path": relative_to_root(output_path),
                "llm": {
                    "status": llm_status,
                    "error": llm_error,
                },
                "signals": {
                    "has_confirmed_commits": evidence.has_confirmed_commits,
                    "has_primary_uncommitted_changes": evidence.has_primary_uncommitted_changes,
                    "has_branch_tip_changes": evidence.has_branch_tip_changes,
                    "has_worktree_candidate_changes": evidence.has_worktree_candidate_changes,
                },
            }
        )

    for remote in remote_repos:
        evidence, remote_status_base = build_remote_summary_evidence(remote, target_date, output_root)
        evidence_markdown = evidence.markdown.rstrip() + "\n"
        content = evidence_markdown
        repo_status = remote_status_base["status"]
        llm_status = "skipped_disabled" if args.no_llm else "skipped_unconfigured"
        llm_error = None

        if llm and evidence.should_call_llm:
            try:
                content = generate_llm_summary(
                    remote,  # type: ignore[arg-type]
                    target_date,
                    evidence_markdown,
                    llm,
                    args.timeout,
                    args.llm_retries,
                    args.llm_retry_delay,
                )
                print(f"[LLM] {remote.name}: 已生成正式总结。")
                llm_status = "success"
            except RuntimeError as exc:
                llm_error = str(exc)
                llm_status = "failed"
                repo_status = "degraded" if repo_status == "success" else repo_status
                print(f"[警告] {remote.name}: LLM 总结失败，改写入远端 Git 证据总结。原因：{exc}")
        elif llm:
            llm_status = "skipped_no_change"
            print(f"[跳过] {remote.name}: 未发现远端 ref 指针变化，不调用 LLM。")

        output_path = output_dir / f"work_summary_{remote.output_name}.md"
        output_path.write_text(content, encoding="utf-8")
        print(f"[完成] {remote.name}: {output_path}")

        remote_status = {
            **remote_status_base,
            "status": repo_status,
            "output_path": relative_to_root(output_path),
            "llm": {
                "status": llm_status,
                "error": llm_error,
            },
            "signals": {
                "has_confirmed_commits": evidence.has_confirmed_commits,
                "has_primary_uncommitted_changes": evidence.has_primary_uncommitted_changes,
                "has_branch_tip_changes": evidence.has_branch_tip_changes,
                "has_worktree_candidate_changes": evidence.has_worktree_candidate_changes,
                "has_remote_ref_changes": evidence.has_remote_ref_changes,
            },
        }
        repository_statuses.append(remote_status)

    finished_at = datetime.now(timezone).isoformat()
    repository_summary = summarize_repository_statuses(repository_statuses)
    agent_status = {
        "status": summarize_agent_status(repository_statuses),
        "started_at": started_at,
        "finished_at": finished_at,
        "timezone": str(timezone),
        "window": {
            "start": start.isoformat(),
            "end": end.isoformat(),
        },
        "output_dir": relative_to_root(output_dir),
        "llm": {
            "enabled": not args.no_llm,
            "configured": bool(llm),
            "model": llm.get("model") if llm else None,
            "retries": args.llm_retries,
            "retry_delay_seconds": args.llm_retry_delay,
        },
        "repositories": repository_statuses,
        "repository_summary": repository_summary,
    }
    write_agent_status(status_path, target_date, agent_status, finished_at)
    print(f"[状态] 已更新: {status_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
