#!/usr/bin/env python3
"""Run the local DailyLearningAssistant agent pipeline."""

from __future__ import annotations

import argparse
import json
import sys
import shutil
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
    parser.add_argument("--from-step", type=int, default=1, choices=range(1, 6), help="First step to run.")
    parser.add_argument("--to-step", type=int, default=5, choices=range(1, 6), help="Last step to run.")
    parser.add_argument("--only-step", type=int, choices=range(1, 6), help="Run only one step.")
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
    parser.add_argument("--send-email", action="store_true", help="Allow step 5 to send email. By default step 5 runs as dry-run.")
    parser.add_argument("--continue-on-failure", action="store_true", help="Continue running later agents after a failure.")
    return parser.parse_args()


def selected_agents(args: argparse.Namespace) -> list[AgentSpec]:
    if args.only_step:
        return [agent for agent in AGENTS if agent.step == args.only_step]
    return [agent for agent in AGENTS if args.from_step <= agent.step <= args.to_step]


def step_by_number(step: int) -> AgentSpec:
    return next(agent for agent in AGENTS if agent.step == step)


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


def main() -> int:
    args = parse_args()
    config_path = Path(args.config).expanduser().resolve()
    output_root = Path(args.output_root).expanduser().resolve()
    input_root = Path(args.input_root).expanduser().resolve() if args.input_root else output_root
    config = load_config(config_path)
    timezone = resolve_timezone(config, args.timezone)
    target_date = resolve_target_date(args.date, timezone)
    status_path = day_dir(output_root, target_date) / "run_status.json"
    llm_trace_path = status_path.parent / "llm_trace.jsonl"
    steps = selected_agents(args)

    update_orchestrator(
        status_path,
        target_date,
        {
            "status": "running" if not args.dry_run else "dry_run",
            "selected_steps": [agent.step for agent in steps],
            "dry_run": args.dry_run,
            "send_email": args.send_email,
            "continue_on_failure": args.continue_on_failure,
            "commands": [],
            "llm_trace_path": str(llm_trace_path),
        },
        timezone,
    )

    commands = []
    failures = []
    fallback_events = []
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
            "dry_run": args.dry_run,
            "send_email": args.send_email,
            "continue_on_failure": args.continue_on_failure,
            "commands": commands,
            "llm_trace_path": str(llm_trace_path),
            "failures": failures,
            "fallback_events": fallback_events,
            "skipped_steps": skipped_steps,
            "agent_summary": summarize_agents(status_data),
        },
        timezone,
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
