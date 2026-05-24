#!/usr/bin/env python3
"""Run the local DailyLearningAssistant agent pipeline."""

from __future__ import annotations

import argparse
import json
import sys
import shutil
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator.config import PROJECT_ROOT, day_dir, load_config, resolve_target_date, resolve_timezone
from orchestrator.lifecycle import AgentSpec, build_agent_command, run_agent
from orchestrator.state import load_status, summarize_agents, update_orchestrator


AGENTS = [
    AgentSpec(1, "daily_work_summary", PROJECT_ROOT / "agents" / "daily_work_summary.py", requires_input_root=False, supports_llm_retry=True, supports_no_llm=True),
    AgentSpec(2, "concept_relevance", PROJECT_ROOT / "agents" / "concept_relevance.py", supports_llm_retry=True),
    AgentSpec(3, "knowledge_explaination", PROJECT_ROOT / "agents" / "knowledge_explaination.py", supports_llm_retry=True),
    AgentSpec(4, "learning_report_publish", PROJECT_ROOT / "agents" / "learning_report_publish.py", supports_llm_retry=True),
    AgentSpec(5, "daily_email_send", PROJECT_ROOT / "agents" / "daily_email_send.py", supports_llm_retry=True, supports_dry_run=True, supports_no_llm=True),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the local daily learning agent pipeline.")
    parser.add_argument("--date", help="Target date in YYYY-MM-DD format. Defaults to today in configured timezone.")
    parser.add_argument("--today", action="store_true", help="Use today's date in configured timezone.")
    parser.add_argument("--from-step", type=int, choices=range(1, 6), help="First step to run.")
    parser.add_argument("--to-step", type=int, choices=range(1, 6), help="Last step to run.")
    parser.add_argument("--only-step", type=int, choices=range(1, 6), help="Run only one step.")
    parser.add_argument(
        "--generation-only",
        action="store_true",
        help="Run the HTML generation/publish pipeline, steps 1-4, without treating it as a manual stage override.",
    )
    parser.add_argument("--config", default=str(PROJECT_ROOT / "config.json"), help="Config JSON path.")
    parser.add_argument(
        "--input-root",
        help="Root used by downstream agents as input. Defaults to --output-root so pipeline stages chain together.",
    )
    parser.add_argument("--output-root", default=str(PROJECT_ROOT), help="Root where pipeline outputs are written.")
    parser.add_argument("--timezone", help="Timezone override, e.g. Asia/Shanghai.")
    parser.add_argument("--timeout", type=int, default=180, help="Per-agent LLM timeout.")
    parser.add_argument("--llm-retries", type=int, default=3, help="LLM retry attempts for supported agents.")
    parser.add_argument("--llm-retry-delay", type=float, default=3.0, help="Initial LLM retry delay.")
    parser.add_argument("--dry-run", action="store_true", help="Print commands and update orchestrator status without running agents.")
    parser.add_argument("--no-llm", action="store_true", help="Pass --no-llm to agents that support it.")
    parser.add_argument("--publish", action="store_true", help="After step 4 succeeds, commit and push generated site artifacts before step 5.")
    parser.add_argument("--send-email", action="store_true", help="Allow step 5 to send email. By default step 5 runs as dry-run.")
    parser.add_argument("--continue-on-failure", action="store_true", help="Continue running later agents after a failure.")
    return parser.parse_args()


def has_manual_stage_override(args: argparse.Namespace) -> bool:
    return args.only_step is not None or args.from_step is not None or args.to_step is not None


def selected_agents(args: argparse.Namespace) -> list[AgentSpec]:
    if args.only_step:
        return [agent for agent in AGENTS if agent.step == args.only_step]
    default_from = 1
    default_to = 4 if args.generation_only else 5
    from_step = args.from_step or default_from
    to_step = args.to_step or default_to
    return [agent for agent in AGENTS if from_step <= agent.step <= to_step]


def daily_work_summary_complete(agent_status: dict) -> bool:
    if agent_status.get("status") != "success":
        return False
    repositories = agent_status.get("repositories") or []
    for repo in repositories:
        if not isinstance(repo, dict):
            return False
        if repo.get("status") != "success":
            return False
        llm_status = (repo.get("llm") or {}).get("status")
        evidence_type = repo.get("evidence_type")
        if evidence_type != "no_change" and llm_status != "success":
            return False
    return True


def agent_step_complete(status_data: dict, spec: AgentSpec) -> bool:
    agent_status = (status_data.get("agents") or {}).get(spec.name) or {}
    if not isinstance(agent_status, dict):
        return False
    if spec.name == "daily_work_summary":
        return daily_work_summary_complete(agent_status)
    return agent_status.get("status") == "success"


def apply_resume_filter(steps: list[AgentSpec], status_data: dict) -> tuple[list[AgentSpec], list[dict]]:
    skipped = []
    remaining = list(steps)
    while remaining and agent_step_complete(status_data, remaining[0]):
        spec = remaining.pop(0)
        skipped.append(
            {
                "step": spec.step,
                "agent": spec.name,
                "reason": "previous_success",
            }
        )
    return remaining, skipped


def previous_publish_success(status_data: dict, run_key: str) -> bool:
    run = (status_data.get("orchestrator_runs") or {}).get(run_key) or {}
    publish_events = run.get("publish_events") or []
    return any(
        isinstance(event, dict) and event.get("status") in {"success", "skipped_previous_success"}
        for event in publish_events
    )


def orchestrator_run_key(args: argparse.Namespace, steps: list[AgentSpec]) -> str:
    step_numbers = [agent.step for agent in steps]
    if step_numbers == [1, 2, 3, 4] and args.publish:
        return "html_publish"
    if step_numbers == [5]:
        return "email_send"
    if step_numbers == [1, 2, 3, 4, 5]:
        return "full"
    return "custom_" + "_".join(str(step) for step in step_numbers)


def step_by_number(step: int) -> AgentSpec:
    return next(agent for agent in AGENTS if agent.step == step)


def format_failure_reason(orchestrator: dict | None) -> str:
    if not isinstance(orchestrator, dict):
        return ""
    failures = orchestrator.get("failures") or []
    if failures:
        first = failures[0] or {}
        agent = first.get("agent") or f"step {first.get('step')}"
        diagnostic = str(first.get("diagnostic") or "").strip()
        return f"{agent}: {diagnostic}" if diagnostic else str(agent)
    publish_events = orchestrator.get("publish_events") or []
    for event in publish_events:
        if isinstance(event, dict) and event.get("status") == "failed":
            return f"发布失败: {event.get('error') or '未知错误'}"
    status = orchestrator.get("status")
    if status and status != "success":
        return f"HTML 生成发布任务状态为 {status}"
    return ""


def previous_generation_failure_reason(status_data: dict) -> str:
    runs = status_data.get("orchestrator_runs") or {}
    generation = runs.get("html_publish") or runs.get("full")
    if isinstance(generation, dict):
        if generation.get("status") != "success":
            return format_failure_reason(generation) or "HTML 生成发布任务尚未成功完成。"
        return ""

    latest = status_data.get("orchestrator") or {}
    if isinstance(latest, dict) and latest.get("selected_steps") != [5] and latest.get("status") != "success":
        return format_failure_reason(latest) or "HTML 生成发布任务尚未成功完成。"
    return ""


def exact_report_exists(input_root: Path, target_date: str) -> bool:
    manifest_path = input_root / "daily_report" / "manifest.json"
    if not manifest_path.exists():
        return False
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    for report in data.get("reports") or []:
        if not isinstance(report, dict) or report.get("date") != target_date:
            continue
        report_path = str(report.get("path") or "")
        return bool(report_path and (input_root / report_path.lstrip("./")).exists())
    return False


def daily_work_has_no_changes(status_data: dict) -> bool:
    daily = (status_data.get("agents") or {}).get("daily_work_summary") or {}
    if daily.get("status") not in {"success", "partial_success"}:
        return False
    repositories = daily.get("repositories") or []
    return bool(repositories) and all(repo.get("evidence_type") == "no_change" for repo in repositories)


def find_previous_knowledge_source(target_date: str, roots: list[Path]) -> tuple[str, Path, Path] | None:
    current = datetime.strptime(target_date, "%Y-%m-%d").date()
    for offset in range(1, 370):
        candidate = (current - timedelta(days=offset)).isoformat()
        year_month = candidate[:7]
        for root in roots:
            knowledge_path = root / "prework" / year_month / candidate / "knowledge_explaination.md"
            log_path = root / "knowledge_log" / f"{year_month}-knowledge-log.md"
            if knowledge_path.exists() and knowledge_path.read_text(encoding="utf-8").strip() and log_path.exists():
                return candidate, knowledge_path, log_path
    return None


def prepare_no_change_fallback(target_date: str, output_root: Path, input_root: Path) -> dict:
    source = find_previous_knowledge_source(target_date, [output_root, input_root, PROJECT_ROOT])
    if not source:
        raise RuntimeError("无变更日需要复用上一日第三步结果，但未找到上一份有效 knowledge_explaination.md")
    source_date, source_knowledge, source_log = source
    output_dir = day_dir(output_root, target_date)
    output_dir.mkdir(parents=True, exist_ok=True)
    target_knowledge = output_dir / "knowledge_explaination.md"
    target_log = output_root / "knowledge_log" / f"{target_date[:7]}-knowledge-log.md"
    source_content = source_knowledge.read_text(encoding="utf-8").rstrip()
    note = f"""# {target_date} 无新增变更复用说明

当日第一步 Git 证据显示所有仓库均无新增变更，因此第二步概念提炼和第三步知识讲解不生成新的正式内容。

本文件复用上一份有效第三步结果：`{source_knowledge}`。

后续第四步生成日报时应遵循：

- 若接收的概念列表与已经讲过的概念部分重复，优先考虑知识点有用性，而不是机械追求“全新概念”。
- 遇到重复概念时，应根据上一轮已经讲过的内容进行深化，例如补充更底层的原理、更清晰的例子、常见误区或跨领域联系。
- 不要把“无新增变更”伪装成新的项目进展，应明确这是复习、深化或延展型日报。

---

{source_content}
"""
    target_knowledge.write_text(note.rstrip() + "\n", encoding="utf-8")
    target_log.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_log, target_log)
    return {
        "source_date": source_date,
        "source_knowledge_path": str(source_knowledge),
        "target_knowledge_path": str(target_knowledge),
        "source_log_path": str(source_log),
        "target_log_path": str(target_log),
    }


def run_git_command(args: list[str], cwd: Path, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(args, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if check and result.returncode != 0:
        command = " ".join(args)
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"{command} 失败: {detail}")
    return result


def collect_publish_paths(output_root: Path, target_date: str, config: dict) -> list[Path]:
    year_month = target_date[:7]
    configured = ((config.get("publish") or {}).get("paths") or [])
    if configured:
        candidates = [output_root / path.format(date=target_date, year_month=year_month).lstrip("./") for path in configured]
    else:
        day_prework = output_root / "prework" / year_month / target_date
        candidates = [
            day_prework / "work_summary_AInote.md",
            day_prework / "work_summary_DailyLearningAssistant.md",
            day_prework / "work_summary_interview_prepare.md",
            day_prework / "work_summary_mcp.md",
            day_prework / "work_summary_ResearchPaperBase_cc.md",
            day_prework / "work_summary_ResearchPaperBase_codex.md",
            day_prework / "concept_relevance.md",
            day_prework / "knowledge_explaination.md",
            output_root / "daily_report" / year_month / f"{target_date}-learning-report.html",
            output_root / "daily_report" / "manifest.json",
            output_root / "knowledge_log" / f"{year_month}-knowledge-log.md",
            output_root / "knowledge_log" / "manifest.json",
            output_root / "index.html",
        ]
    seen: set[Path] = set()
    paths: list[Path] = []
    for path in candidates:
        resolved = path.expanduser().resolve()
        if resolved.exists() and resolved not in seen:
            seen.add(resolved)
            paths.append(resolved)
    return paths


def publish_generated_artifacts(output_root: Path, target_date: str, config: dict, *, dry_run: bool) -> dict:
    publish_cfg = config.get("publish") or {}
    remote = publish_cfg.get("remote") or "origin"
    branch = publish_cfg.get("branch") or "main"
    message_template = publish_cfg.get("commit_message") or "Publish daily learning report {date}"
    commit_message = message_template.format(date=target_date, year_month=target_date[:7])
    paths = collect_publish_paths(output_root, target_date, config)
    relative_paths = [str(path.relative_to(output_root)) for path in paths]
    event = {
        "enabled": True,
        "remote": remote,
        "branch": branch,
        "commit_message": commit_message,
        "paths": relative_paths,
        "dry_run": dry_run,
        "status": "pending",
    }
    if dry_run:
        event["status"] = "dry_run"
        return event
    if not paths:
        raise RuntimeError("没有找到可发布的生成文件。")

    inside = run_git_command(["git", "rev-parse", "--is-inside-work-tree"], output_root)
    if inside.stdout.strip() != "true":
        raise RuntimeError(f"{output_root} 不是 Git 工作区。")
    current_branch = run_git_command(["git", "branch", "--show-current"], output_root).stdout.strip()
    event["current_branch"] = current_branch
    if current_branch != branch:
        raise RuntimeError(f"当前分支是 {current_branch or '(detached)'}，配置要求发布分支为 {branch}。")

    run_git_command(["git", "fetch", remote, branch, "--quiet"], output_root)
    counts = run_git_command(["git", "rev-list", "--left-right", "--count", f"{remote}/{branch}...HEAD"], output_root).stdout.split()
    behind = int(counts[0]) if counts else 0
    ahead_before_commit = int(counts[1]) if len(counts) > 1 else 0
    event["ahead_before_commit"] = ahead_before_commit
    event["behind"] = behind
    if behind:
        raise RuntimeError(f"本地 {branch} 落后 {remote}/{branch} {behind} 个提交，停止自动发布。")

    run_git_command(["git", "add", "--", *relative_paths], output_root)
    staged = run_git_command(["git", "diff", "--cached", "--quiet"], output_root, check=False).returncode != 0
    event["staged_changes"] = staged
    if staged:
        commit_result = run_git_command(["git", "commit", "-m", commit_message], output_root)
        event["commit"] = run_git_command(["git", "rev-parse", "HEAD"], output_root).stdout.strip()
        event["commit_output"] = (commit_result.stdout or commit_result.stderr).strip()[-2000:]
    else:
        event["commit"] = None
        event["commit_output"] = "没有新的生成文件需要提交。"

    counts = run_git_command(["git", "rev-list", "--left-right", "--count", f"{remote}/{branch}...HEAD"], output_root).stdout.split()
    ahead = int(counts[1]) if len(counts) > 1 else 0
    event["ahead"] = ahead
    if ahead:
        push_result = run_git_command(["git", "push", remote, branch], output_root)
        event["push_output"] = (push_result.stdout or push_result.stderr).strip()[-2000:]
        event["pushed"] = True
    else:
        event["push_output"] = "远端已经是最新状态。"
        event["pushed"] = False
    event["status"] = "success"
    return event


def main() -> int:
    args = parse_args()
    if args.generation_only and args.only_step:
        print("[错误] --generation-only 不能和 --only-step 同时使用。", file=sys.stderr)
        return 2
    if args.from_step and args.to_step and args.from_step > args.to_step:
        print("[错误] --from-step 不能大于 --to-step。", file=sys.stderr)
        return 2
    config_path = Path(args.config).expanduser().resolve()
    output_root = Path(args.output_root).expanduser().resolve()
    input_root = Path(args.input_root).expanduser().resolve() if args.input_root else output_root
    config = load_config(config_path)
    timezone = resolve_timezone(config, args.timezone)
    target_date = resolve_target_date(args.date, timezone)
    status_path = day_dir(output_root, target_date) / "run_status.json"
    llm_trace_path = status_path.parent / "llm_trace.jsonl"
    requested_steps = selected_agents(args)
    manual_stage_override = has_manual_stage_override(args)
    resume_skipped_steps: list[dict] = []
    steps = requested_steps
    previous_status = load_status(status_path, target_date)
    if not manual_stage_override:
        steps, resume_skipped_steps = apply_resume_filter(requested_steps, previous_status)
        for event in resume_skipped_steps:
            print(f"[续跑] 第 {event['step']} 步 {event['agent']} 上次已成功，跳过。")
        if not steps:
            print("[续跑] 选定范围内的 Agent 均已完成，无需重跑。")
    run_key = orchestrator_run_key(args, requested_steps)

    update_orchestrator(
        status_path,
        target_date,
        {
            "status": "running" if not args.dry_run else "dry_run",
            "selected_steps": [agent.step for agent in steps],
            "requested_steps": [agent.step for agent in requested_steps],
            "manual_stage_override": manual_stage_override,
            "resume_skipped_steps": resume_skipped_steps,
            "dry_run": args.dry_run,
            "publish": args.publish,
            "send_email": args.send_email,
            "continue_on_failure": args.continue_on_failure,
            "commands": [],
            "llm_trace_path": str(llm_trace_path),
        },
        timezone,
        run_key,
    )

    commands = []
    failures = []
    fallback_events = []
    publish_events = []
    skipped_steps = []
    failure_reason = ""
    for spec in steps:
        status_data_before = load_status(status_path, target_date)
        if spec.step == 2 and daily_work_has_no_changes(status_data_before):
            try:
                event = prepare_no_change_fallback(target_date, output_root, input_root)
                event["reason"] = "daily_work_summary_all_repositories_no_change"
                fallback_events.append(event)
                skipped_steps.extend([2, 3])
                print("[回退] 第 1 步显示当日无变更，跳过第 2/3 步，复用上一份第三步结果进入第 4 步。")
            except RuntimeError as exc:
                failures.append({"step": 2, "agent": spec.name, "returncode": 1, "diagnostic": str(exc)})
                failure_reason = str(exc)
                if not args.continue_on_failure:
                    break
            continue
        if spec.step == 3 and 3 in skipped_steps:
            continue
        step_input_root = output_root if fallback_events and spec.step >= 4 else input_root
        failure_notice_reason = ""
        if spec.name == "daily_email_send" and not args.dry_run:
            failure_notice_reason = previous_generation_failure_reason(status_data_before)
            if not failure_notice_reason and not exact_report_exists(step_input_root, target_date):
                failure_notice_reason = "HTML 生成发布任务尚未成功产出当天日报。"
        command = build_agent_command(
            spec,
            target_date=target_date,
            config_path=config_path,
            input_root=step_input_root,
            output_root=output_root,
            timezone=args.timezone,
            timeout=args.timeout,
            llm_retries=args.llm_retries,
            llm_retry_delay=args.llm_retry_delay,
            dry_run=args.dry_run,
            no_llm=args.no_llm,
        )
        if failure_notice_reason:
            command.extend(["--allow-latest-fallback", "--failure-notice", "--failure-reason", failure_notice_reason])
        if spec.name == "daily_email_send" and not args.send_email and "--dry-run" not in command:
            command.append("--dry-run")
        commands.append({"step": spec.step, "agent": spec.name, "command": command})
        print(f"[运行] 第 {spec.step} 步 {spec.name}")
        if args.dry_run:
            print(" ".join(command))
        result = run_agent(spec, command, dry_run=args.dry_run)
        if result.stdout:
            print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="")
        if not result.ok:
            diagnostic = (result.stderr or result.stdout).strip()[-4000:]
            failures.append({"step": spec.step, "agent": spec.name, "returncode": result.returncode, "diagnostic": diagnostic})
            failure_reason = f"第 {spec.step} 步 {spec.name} 失败: {diagnostic}"
            if not args.continue_on_failure:
                break
        if result.ok and spec.step == 4 and args.publish:
            print("[发布] 第 4 步已完成，开始提交并推送生成文件。")
            try:
                publish_event = publish_generated_artifacts(output_root, target_date, config, dry_run=args.dry_run)
                publish_events.append(publish_event)
                print(f"[发布] 状态: {publish_event['status']}")
            except Exception as exc:
                publish_event = {
                    "enabled": True,
                    "status": "failed",
                    "error": str(exc),
                    "dry_run": args.dry_run,
                }
                publish_events.append(publish_event)
                failures.append({"step": "publish", "agent": "git_publish", "returncode": 1, "diagnostic": str(exc)})
                failure_reason = f"发布失败: {exc}"
                if not args.continue_on_failure:
                    break

    step4_requested = any(agent.step == 4 for agent in requested_steps)
    step4_skipped_by_resume = any(event.get("step") == 4 for event in resume_skipped_steps)
    if (
        args.publish
        and step4_requested
        and step4_skipped_by_resume
        and not publish_events
        and not failures
        and not previous_publish_success(previous_status, run_key)
    ):
        print("[发布] 第 4 步此前已完成但尚无成功发布记录，开始提交并推送生成文件。")
        try:
            publish_event = publish_generated_artifacts(output_root, target_date, config, dry_run=args.dry_run)
            publish_events.append(publish_event)
            print(f"[发布] 状态: {publish_event['status']}")
        except Exception as exc:
            publish_event = {
                "enabled": True,
                "status": "failed",
                "error": str(exc),
                "dry_run": args.dry_run,
            }
            publish_events.append(publish_event)
            failures.append({"step": "publish", "agent": "git_publish", "returncode": 1, "diagnostic": str(exc)})
            failure_reason = f"发布失败: {exc}"
    elif (
        args.publish
        and step4_requested
        and step4_skipped_by_resume
        and not publish_events
        and previous_publish_success(previous_status, run_key)
    ):
        publish_events.append(
            {
                "enabled": True,
                "status": "skipped_previous_success",
                "reason": "previous_publish_success",
                "dry_run": args.dry_run,
            }
        )

    status_data = load_status(status_path, target_date)
    final_status = "success" if not failures else "failed"
    if args.dry_run:
        final_status = "dry_run"
    update_orchestrator(
        status_path,
        target_date,
        {
            "status": final_status,
            "selected_steps": [agent.step for agent in steps],
            "requested_steps": [agent.step for agent in requested_steps],
            "manual_stage_override": manual_stage_override,
            "resume_skipped_steps": resume_skipped_steps,
            "dry_run": args.dry_run,
            "publish": args.publish,
            "send_email": args.send_email,
            "continue_on_failure": args.continue_on_failure,
            "commands": commands,
            "llm_trace_path": str(llm_trace_path),
            "failures": failures,
            "fallback_events": fallback_events,
            "publish_events": publish_events,
            "skipped_steps": skipped_steps,
            "agent_summary": summarize_agents(status_data),
        },
        timezone,
        run_key,
    )

    if failures and any(agent.step == 5 for agent in steps) and not args.dry_run:
        email_spec = step_by_number(5)
        email_input_root = input_root
        if not (email_input_root / "daily_report" / "manifest.json").exists():
            email_input_root = PROJECT_ROOT
        failure_email_command = build_agent_command(
            email_spec,
            target_date=target_date,
            config_path=config_path,
            input_root=email_input_root,
            output_root=output_root,
            timezone=args.timezone,
            timeout=args.timeout,
            llm_retries=args.llm_retries,
            llm_retry_delay=args.llm_retry_delay,
            dry_run=args.dry_run,
            no_llm=True,
        )
        failure_email_command.extend(["--allow-latest-fallback", "--failure-notice", "--failure-reason", failure_reason])
        if not args.send_email and "--dry-run" not in failure_email_command:
            failure_email_command.append("--dry-run")
        print("[通知] 前四步未能正常完成，发送/生成失败提醒邮件。")
        result = run_agent(email_spec, failure_email_command, dry_run=False)
        if result.stdout:
            print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="")
    print(json.dumps({"date": target_date, "status": final_status, "failures": failures}, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
