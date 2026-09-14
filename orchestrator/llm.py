"""Reusable network access helpers with retry support.

The name is kept as llm.py because this module started as the shared LLM
client. It now also owns SMTP/IMAP retry primitives so individual agents do
not carry their own reconnect loops.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, TypeVar

import httpx


T = TypeVar("T")

LLM_REQUIRED_FIELDS = ("api_url", "api_key", "model")
LLM_FAILOVER_TIMEOUT_SECONDS = 60.0


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
    if isinstance(exc, (asyncio.TimeoutError, TimeoutError, httpx.TimeoutException)):
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


def _validate_llm_provider(provider: dict, label: str) -> None:
    missing = [
        key
        for key in LLM_REQUIRED_FIELDS
        if not isinstance(provider.get(key), str) or not str(provider[key]).strip()
    ]
    if missing:
        raise ValueError(f"config.json 缺少或未正确填写 {label} 配置项: {', '.join(missing)}")
    if not str(provider["api_url"]).startswith(("http://", "https://")):
        raise ValueError(f"{label}.api_url 必须是 http(s) URL。")
    if str(provider["api_key"]).startswith("YOUR_"):
        raise ValueError(f"{label}.api_key 仍是示例占位符，请在 config.json 中填入真实密钥。")
    if "timeout_seconds" in provider:
        _positive_timeout(provider["timeout_seconds"], f"{label}.timeout_seconds")


def resolve_llm_providers(llm: dict) -> list[dict]:
    """Return validated providers with shared LLM settings merged into each one.

    A legacy single-provider object remains supported. In multi-provider mode,
    top-level request settings such as ``temperature`` and
    ``trust_env_proxy`` are inherited by every provider and may be overridden
    inside an individual provider entry.
    """

    if not isinstance(llm, dict):
        raise ValueError("config.json 中的 llm 必须是 object。")

    configured = llm.get("providers")
    if configured is None:
        provider = dict(llm)
        provider.setdefault("name", "primary")
        _validate_llm_provider(provider, "llm")
        return [provider]

    if not isinstance(configured, list) or not configured:
        raise ValueError("config.json 中的 llm.providers 必须是非空列表。")
    if "failover_timeout_seconds" in llm:
        _positive_timeout(llm["failover_timeout_seconds"], "llm.failover_timeout_seconds")

    shared = {
        key: value
        for key, value in llm.items()
        if key not in {"providers", "failover_timeout_seconds"}
    }
    providers: list[dict] = []
    seen_names: set[str] = set()
    for index, item in enumerate(configured):
        label = f"llm.providers[{index}]"
        if not isinstance(item, dict):
            raise ValueError(f"config.json 中的 {label} 必须是 object。")
        name = item.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"config.json 中的 {label}.name 不能为空。")
        name = name.strip()
        if name in seen_names:
            raise ValueError(f"config.json 中的 llm provider 名称重复: {name}")
        seen_names.add(name)
        provider = {**shared, **item, "name": name}
        _validate_llm_provider(provider, label)
        providers.append(provider)
    return providers


def require_llm_config(config: dict) -> dict:
    llm = config.get("llm") or {}
    resolve_llm_providers(llm)
    return llm


def primary_llm_model(llm: dict) -> str | None:
    """Return the first configured model for backward-compatible status fields."""

    try:
        return str(resolve_llm_providers(llm)[0]["model"])
    except (ValueError, IndexError, KeyError):
        return None


def trust_env_proxy_enabled(llm: dict) -> bool:
    value = llm.get("trust_env_proxy", False)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _positive_timeout(value: object, label: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{label} 必须是正数。")
    try:
        timeout = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} 必须是正数。") from exc
    if timeout <= 0:
        raise ValueError(f"{label} 必须是正数。")
    return timeout


def _provider_timeout(llm: dict, provider: dict, requested_timeout: int | float) -> float:
    requested = _positive_timeout(requested_timeout, "LLM request timeout")
    multi_provider = llm.get("providers") is not None
    configured = provider.get("timeout_seconds")
    if configured is None and multi_provider:
        configured = llm.get("failover_timeout_seconds", LLM_FAILOVER_TIMEOUT_SECONDS)
    if configured is None:
        return requested
    provider_timeout = _positive_timeout(
        configured,
        f"LLM provider {provider.get('name')!r} timeout_seconds",
    )
    return min(requested, provider_timeout)


def _phase_timeout(llm: dict, key: str, default: float, request_timeout: float) -> float:
    value = _positive_timeout(llm.get(key, default), f"llm.{key}")
    return min(value, request_timeout)


async def _post_with_deadline(
    api_url: str,
    *,
    headers: dict,
    payload: dict,
    timeout_config: httpx.Timeout,
    request_timeout: float,
    trust_env_proxy: bool,
) -> httpx.Response:
    async with httpx.AsyncClient(timeout=timeout_config, http2=False, trust_env=trust_env_proxy) as client:
        return await asyncio.wait_for(
            client.post(api_url, headers=headers, json=payload),
            timeout=request_timeout,
        )


def call_chat_completion_once(
    llm: dict,
    messages: list[dict],
    *,
    timeout: int,
    temperature: float | None = None,
    attempt: int | None = None,
    max_attempts: int | None = None,
    provider_index: int | None = None,
    provider_count: int | None = None,
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
    request_timeout = _positive_timeout(timeout, "LLM request timeout")
    timeout_config = httpx.Timeout(
        timeout=request_timeout,
        connect=_phase_timeout(llm, "connect_timeout", min(30, max(5, request_timeout / 4)), request_timeout),
        read=_phase_timeout(llm, "read_timeout", request_timeout, request_timeout),
        write=_phase_timeout(llm, "write_timeout", min(30, max(5, request_timeout / 4)), request_timeout),
        pool=_phase_timeout(llm, "pool_timeout", 5, request_timeout),
    )
    trust_env_proxy = trust_env_proxy_enabled(llm)
    trace_base = {
        "provider_name": llm.get("name") or llm.get("model"),
        "provider_index": provider_index,
        "provider_count": provider_count,
        "model": llm.get("model"),
        "api_url": llm.get("api_url"),
        "trust_env_proxy": trust_env_proxy,
    }

    started = time.monotonic()
    try:
        response = asyncio.run(
            _post_with_deadline(
                llm["api_url"],
                headers=headers,
                payload=payload,
                timeout_config=timeout_config,
                request_timeout=request_timeout,
                trust_env_proxy=trust_env_proxy,
            )
        )
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
                **trace_base,
                "http_status": exc.response.status_code,
            }
        )
        raise RuntimeError(f"LLM HTTP 调用失败: {exc.response.status_code} {exc.response.reason_phrase}\n{body}") from exc
    except (asyncio.TimeoutError, TimeoutError, httpx.HTTPError, json.JSONDecodeError) as exc:
        elapsed_ms = int((time.monotonic() - started) * 1000)
        _append_trace(
            {
                "event": "llm_attempt",
                "status": "failed",
                "error_type": _error_type(exc),
                "attempt": attempt,
                "max_attempts": max_attempts,
                "elapsed_ms": elapsed_ms,
                **trace_base,
            }
        )
        raise RuntimeError(f"LLM 调用失败: {exc}") from exc

    elapsed_ms = int((time.monotonic() - started) * 1000)
    try:
        content = result["choices"][0]["message"]["content"]
        if not isinstance(content, str) or not content.strip():
            raise TypeError("message content is empty")
    except (KeyError, IndexError, TypeError) as exc:
        _append_trace(
            {
                "event": "llm_attempt",
                "status": "failed",
                "error_type": "invalid_chat_completion_response",
                "attempt": attempt,
                "max_attempts": max_attempts,
                "elapsed_ms": elapsed_ms,
                **trace_base,
            }
        )
        raise RuntimeError("LLM 响应格式不符合 chat completions 约定。") from exc

    _append_trace(
        {
            "event": "llm_attempt",
            "status": "success",
            "attempt": attempt,
            "max_attempts": max_attempts,
            "elapsed_ms": elapsed_ms,
            **trace_base,
            "input_messages": len(messages),
        }
    )
    return content


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
    providers = resolve_llm_providers(llm)
    errors: list[str] = []
    total_started = time.monotonic()
    for attempt in range(1, attempts + 1):
        for provider_index, provider in enumerate(providers, start=1):
            provider_name = str(provider.get("name") or provider.get("model"))
            provider_timeout = _provider_timeout(llm, provider, timeout)
            try:
                content = call_chat_completion_once(
                    provider,
                    messages,
                    timeout=provider_timeout,
                    temperature=temperature,
                    attempt=attempt,
                    max_attempts=attempts,
                    provider_index=provider_index,
                    provider_count=len(providers),
                )
                _append_trace(
                    {
                        "event": "llm_call",
                        "status": "success",
                        "attempts": attempt,
                        "provider_attempts": (attempt - 1) * len(providers) + provider_index,
                        "elapsed_ms": int((time.monotonic() - total_started) * 1000),
                        "provider_name": provider_name,
                        "provider_index": provider_index,
                        "provider_count": len(providers),
                        "model": provider.get("model"),
                        "api_url": provider.get("api_url"),
                        "trust_env_proxy": trust_env_proxy_enabled(provider),
                    }
                )
                return content
            except Exception as exc:
                errors.append(f"{provider_name}: {exc}")
                has_next_provider = provider_index < len(providers)
                if has_next_provider:
                    next_provider = providers[provider_index]
                    next_name = str(next_provider.get("name") or next_provider.get("model"))
                    print(
                        f"[故障转移] LLM provider {provider_name!r} 失败（最多等待 {provider_timeout:g} 秒）：{exc}"
                    )
                    print(f"[故障转移] 切换到下一个 provider {next_name!r}。")
                    _append_trace(
                        {
                            "event": "llm_failover",
                            "status": "switching",
                            "attempt": attempt,
                            "max_attempts": attempts,
                            "from_provider": provider_name,
                            "to_provider": next_name,
                            "provider_index": provider_index,
                            "provider_count": len(providers),
                            "error": str(exc),
                        }
                    )

        if attempt >= attempts:
            break
        wait_seconds = delay * (policy.backoff ** (attempt - 1))
        print(f"[重试] 所有 LLM provider 均失败，第 {attempt}/{attempts} 轮结束。")
        print(f"[重试] 等待 {wait_seconds:.1f} 秒后重新尝试整条候选链。")
        if wait_seconds:
            time.sleep(wait_seconds)

    _append_trace(
        {
            "event": "llm_call",
            "status": "failed",
            "attempts": attempts,
            "provider_attempts": len(errors),
            "elapsed_ms": int((time.monotonic() - total_started) * 1000),
            "provider_count": len(providers),
            "providers": [str(item.get("name") or item.get("model")) for item in providers],
            "error": "; ".join(errors[-max(3, len(providers)) :]),
        }
    )
    raise RuntimeError("; ".join(errors[-max(3, len(providers)) :]))
