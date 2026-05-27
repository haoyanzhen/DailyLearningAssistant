"""Reusable network access helpers with retry support.

The name is kept as llm.py because this module started as the shared LLM
client. It now also owns SMTP/IMAP retry primitives so individual agents do
not carry their own reconnect loops.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, TypeVar

import httpx


T = TypeVar("T")


@dataclass
class LLMRetryPolicy:
    attempts: int = 3
    initial_delay: float = 3.0
    backoff: float = 2.0


@dataclass
class RetryPolicy:
    attempts: int = 3
    initial_delay: float = 3.0
    backoff: float = 2.0
    label: str = "network operation"


def retry_call(operation: Callable[[], T], policy: RetryPolicy) -> T:
    attempts = max(1, policy.attempts)
    delay = max(0.0, policy.initial_delay)
    errors: list[str] = []
    for attempt in range(1, attempts + 1):
        try:
            return operation()
        except Exception as exc:
            errors.append(str(exc))
            if attempt >= attempts:
                break
            wait_seconds = delay * (policy.backoff ** (attempt - 1))
            print(f"[重试] {policy.label} 失败，第 {attempt}/{attempts} 次：{exc}")
            print(f"[重试] 等待 {wait_seconds:.1f} 秒后再次尝试。")
            if wait_seconds:
                time.sleep(wait_seconds)
    raise RuntimeError("; ".join(errors[-3:]))


def _trace_path() -> Path | None:
    raw_path = os.environ.get("DLA_LLM_TRACE_PATH")
    return Path(raw_path).expanduser() if raw_path else None


def _append_trace(event: dict) -> None:
    path = _trace_path()
    if not path:
        return
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": os.environ.get("DLA_AGENT_NAME"),
        **event,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _error_type(exc: BaseException) -> str:
    if isinstance(exc, httpx.TimeoutException):
        return "timeout"
    if isinstance(exc, httpx.ConnectError):
        return "connect_error"
    if isinstance(exc, httpx.ReadError):
        return "read_error"
    if isinstance(exc, httpx.RemoteProtocolError):
        return "remote_protocol_error"
    if isinstance(exc, httpx.HTTPStatusError):
        return f"http_{exc.response.status_code}"
    if isinstance(exc, json.JSONDecodeError):
        return "json_decode_error"
    return exc.__class__.__name__


def retry_optional(operation: Callable[[], T | None], policy: RetryPolicy) -> tuple[T | None, str | None]:
    try:
        return retry_call(
            lambda: _require_optional_result(operation(), policy.label),
            policy,
        ), None
    except Exception as exc:
        return None, str(exc)


def _require_optional_result(value: T | None, label: str) -> T:
    if value is None:
        raise RuntimeError(f"{label} returned no content")
    return value


def wait_until(operation: Callable[[], T], *, timeout: int, interval: float, label: str) -> T:
    deadline = time.monotonic() + max(1, timeout)
    attempts = 0
    last_error = None
    while True:
        attempts += 1
        try:
            return operation()
        except Exception as exc:
            last_error = exc
            if time.monotonic() >= deadline:
                raise RuntimeError(f"{label} 超时，尝试 {attempts} 次后仍未成功: {last_error}") from exc
            time.sleep(max(1.0, interval))


def require_llm_config(config: dict) -> dict:
    llm = config.get("llm") or {}
    missing = [key for key in ("api_url", "api_key", "model") if not llm.get(key)]
    if missing:
        raise ValueError(f"config.json 缺少 llm 配置项: {', '.join(missing)}")
    if str(llm["api_key"]).startswith("YOUR_"):
        raise ValueError("llm.api_key 仍是示例占位符，请在 config.json 中填入真实密钥。")
    return llm


def call_chat_completion_once(
    llm: dict,
    messages: list[dict],
    *,
    timeout: int,
    temperature: float | None = None,
    attempt: int | None = None,
    max_attempts: int | None = None,
) -> str:
    payload = {
        "model": llm["model"],
        "temperature": llm.get("temperature", 0.5) if temperature is None else temperature,
        "messages": messages,
    }
    if llm.get("max_tokens"):
        payload["max_tokens"] = llm["max_tokens"]
    if llm.get("response_format"):
        payload["response_format"] = llm["response_format"]
    headers = {
        "Authorization": f"Bearer {llm['api_key']}",
        "content-type": "application/json",
    }
    timeout_config = httpx.Timeout(
        timeout=float(timeout),
        connect=float(llm.get("connect_timeout", min(30, max(5, timeout // 4)))),
        read=float(llm.get("read_timeout", timeout)),
        write=float(llm.get("write_timeout", min(30, max(5, timeout // 4)))),
        pool=float(llm.get("pool_timeout", 5)),
    )

    started = time.monotonic()
    try:
        with httpx.Client(timeout=timeout_config, http2=False) as client:
            response = client.post(llm["api_url"], headers=headers, json=payload)
            response.raise_for_status()
            result = response.json()
    except httpx.HTTPStatusError as exc:
        elapsed_ms = int((time.monotonic() - started) * 1000)
        body = exc.response.text[:2000]
        _append_trace(
            {
                "event": "llm_attempt",
                "status": "failed",
                "error_type": _error_type(exc),
                "attempt": attempt,
                "max_attempts": max_attempts,
                "elapsed_ms": elapsed_ms,
                "model": llm.get("model"),
                "api_url": llm.get("api_url"),
                "http_status": exc.response.status_code,
            }
        )
        raise RuntimeError(f"LLM HTTP 调用失败: {exc.response.status_code} {exc.response.reason_phrase}\n{body}") from exc
    except (httpx.HTTPError, json.JSONDecodeError) as exc:
        elapsed_ms = int((time.monotonic() - started) * 1000)
        _append_trace(
            {
                "event": "llm_attempt",
                "status": "failed",
                "error_type": _error_type(exc),
                "attempt": attempt,
                "max_attempts": max_attempts,
                "elapsed_ms": elapsed_ms,
                "model": llm.get("model"),
                "api_url": llm.get("api_url"),
            }
        )
        raise RuntimeError(f"LLM 调用失败: {exc}") from exc

    elapsed_ms = int((time.monotonic() - started) * 1000)
    _append_trace(
        {
            "event": "llm_attempt",
            "status": "success",
            "attempt": attempt,
            "max_attempts": max_attempts,
            "elapsed_ms": elapsed_ms,
            "model": llm.get("model"),
            "api_url": llm.get("api_url"),
            "input_messages": len(messages),
        }
    )

    try:
        return result["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        _append_trace(
            {
                "event": "llm_attempt",
                "status": "failed",
                "error_type": "invalid_chat_completion_response",
                "attempt": attempt,
                "max_attempts": max_attempts,
                "elapsed_ms": elapsed_ms,
                "model": llm.get("model"),
                "api_url": llm.get("api_url"),
            }
        )
        raise RuntimeError("LLM 响应格式不符合 chat completions 约定。") from exc


def call_chat_completion(
    llm: dict,
    messages: list[dict],
    *,
    timeout: int,
    retry_policy: LLMRetryPolicy | None = None,
    temperature: float | None = None,
) -> str:
    policy = retry_policy or LLMRetryPolicy()
    attempts = max(1, policy.attempts)
    delay = max(0.0, policy.initial_delay)
    errors: list[str] = []
    total_started = time.monotonic()
    for attempt in range(1, attempts + 1):
        try:
            content = call_chat_completion_once(
                llm,
                messages,
                timeout=timeout,
                temperature=temperature,
                attempt=attempt,
                max_attempts=attempts,
            )
            _append_trace(
                {
                    "event": "llm_call",
                    "status": "success",
                    "attempts": attempt,
                    "elapsed_ms": int((time.monotonic() - total_started) * 1000),
                    "model": llm.get("model"),
                    "api_url": llm.get("api_url"),
                }
            )
            return content
        except Exception as exc:
            errors.append(str(exc))
            if attempt >= attempts:
                break
            wait_seconds = delay * (policy.backoff ** (attempt - 1))
            print(f"[重试] LLM 调用 失败，第 {attempt}/{attempts} 次：{exc}")
            print(f"[重试] 等待 {wait_seconds:.1f} 秒后再次尝试。")
            if wait_seconds:
                time.sleep(wait_seconds)
    _append_trace(
        {
            "event": "llm_call",
            "status": "failed",
            "attempts": attempts,
            "elapsed_ms": int((time.monotonic() - total_started) * 1000),
            "model": llm.get("model"),
            "api_url": llm.get("api_url"),
            "error": "; ".join(errors[-3:]),
        }
    )
    raise RuntimeError("; ".join(errors[-3:]))
