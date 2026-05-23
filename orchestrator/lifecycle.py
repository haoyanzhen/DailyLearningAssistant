"""Lifecycle primitives for invoking local agents."""

from __future__ import annotations

import subprocess
import sys
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AgentSpec:
    step: int
    name: str
    script: Path
    requires_input_root: bool = True
    supports_llm_retry: bool = False
    supports_dry_run: bool = False
    supports_no_llm: bool = False


@dataclass
class AgentRunResult:
    spec: AgentSpec
    command: list[str]
    returncode: int
    stdout: str
    stderr: str
    dry_run: bool = False

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def build_agent_command(
    spec: AgentSpec,
    *,
    target_date: str,
    config_path: Path,
    input_root: Path,
    output_root: Path,
    timezone: str | None,
    timeout: int,
    llm_retries: int,
    llm_retry_delay: float,
    dry_run: bool,
    no_llm: bool,
) -> list[str]:
    cmd = [
        sys.executable,
        str(spec.script),
        "--date",
        target_date,
        "--config",
        str(config_path),
        "--output-root",
        str(output_root),
        "--timeout",
        str(timeout),
    ]
    if spec.requires_input_root:
        cmd.extend(["--input-root", str(input_root)])
    if timezone:
        cmd.extend(["--timezone", timezone])
    if spec.supports_llm_retry:
        cmd.extend(["--llm-retries", str(llm_retries), "--llm-retry-delay", str(llm_retry_delay)])
    if dry_run and spec.supports_dry_run:
        cmd.append("--dry-run")
    if no_llm and spec.supports_no_llm:
        cmd.append("--no-llm")
    return cmd


def run_agent(spec: AgentSpec, command: list[str], *, dry_run: bool) -> AgentRunResult:
    if dry_run:
        return AgentRunResult(spec=spec, command=command, returncode=0, stdout="", stderr="", dry_run=True)
    env = os.environ.copy()
    env["DLA_AGENT_NAME"] = spec.name
    if "DLA_LLM_TRACE_PATH" not in env:
        try:
            target_date = command[command.index("--date") + 1]
            output_root = Path(command[command.index("--output-root") + 1])
            env["DLA_LLM_TRACE_PATH"] = str(output_root / "prework" / target_date[:7] / target_date / "llm_trace.jsonl")
        except (ValueError, IndexError):
            pass
    result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    return AgentRunResult(
        spec=spec,
        command=command,
        returncode=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
    )
