from __future__ import annotations

import asyncio
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

from orchestrator.llm import (
    LLMRetryPolicy,
    _post_with_deadline,
    call_chat_completion,
    require_llm_config,
    resolve_llm_providers,
)
from scripts.check_config import check_llm


def multi_llm_config() -> dict:
    return {
        "failover_timeout_seconds": 60,
        "trust_env_proxy": False,
        "providers": [
            {
                "name": "primary-vllm",
                "api_url": "http://192.0.2.10:8000/v1/chat/completions",
                "api_key": "primary-key",
                "model": "primary-model",
            },
            {
                "name": "backup-openwebui",
                "api_url": "http://192.0.2.11:3000/api/chat/completions",
                "api_key": "backup-key",
                "model": "backup-model",
            },
        ],
    }


class LLMProviderConfigTests(unittest.TestCase):
    def test_legacy_single_provider_remains_supported(self) -> None:
        llm = {
            "api_url": "https://example.test/v1/chat/completions",
            "api_key": "secret",
            "model": "legacy-model",
        }

        resolved = require_llm_config({"llm": llm})
        providers = resolve_llm_providers(resolved)

        self.assertEqual(llm, resolved)
        self.assertEqual(1, len(providers))
        self.assertEqual("primary", providers[0]["name"])
        self.assertEqual("legacy-model", providers[0]["model"])

    def test_multi_provider_inherits_shared_settings(self) -> None:
        llm = multi_llm_config()
        llm["temperature"] = 0.25
        llm["providers"][1]["trust_env_proxy"] = True

        providers = resolve_llm_providers(llm)

        self.assertEqual(0.25, providers[0]["temperature"])
        self.assertFalse(providers[0]["trust_env_proxy"])
        self.assertTrue(providers[1]["trust_env_proxy"])

    def test_duplicate_provider_names_are_rejected(self) -> None:
        llm = multi_llm_config()
        llm["providers"][1]["name"] = "primary-vllm"

        with self.assertRaisesRegex(ValueError, "名称重复"):
            resolve_llm_providers(llm)

    def test_config_checker_accepts_multi_provider_config(self) -> None:
        self.assertEqual([], check_llm({"llm": multi_llm_config()}, strict=True))

    def test_config_checker_rejects_invalid_failover_timeout(self) -> None:
        llm = multi_llm_config()
        llm["failover_timeout_seconds"] = 0

        self.assertIn(
            "llm.failover_timeout_seconds 必须是正数",
            check_llm({"llm": llm}, strict=True),
        )


class LLMFailoverTests(unittest.TestCase):
    def test_complete_http_request_has_a_hard_deadline(self) -> None:
        class SlowAsyncClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, traceback):
                return False

            async def post(self, api_url, *, headers, json):
                await asyncio.sleep(1)
                raise AssertionError("deadline did not cancel the slow request")

        with patch("orchestrator.llm.httpx.AsyncClient", return_value=SlowAsyncClient()):
            with self.assertRaises(asyncio.TimeoutError):
                asyncio.run(
                    _post_with_deadline(
                        "https://example.test/v1/chat/completions",
                        headers={},
                        payload={},
                        timeout_config=httpx.Timeout(1),
                        request_timeout=0.01,
                        trust_env_proxy=False,
                    )
                )

    def test_failure_switches_to_next_provider_with_sixty_second_timeout(self) -> None:
        llm = multi_llm_config()
        with patch(
            "orchestrator.llm.call_chat_completion_once",
            side_effect=[RuntimeError("primary unavailable"), "backup response"],
        ) as call_once:
            result = call_chat_completion(
                llm,
                [{"role": "user", "content": "hello"}],
                timeout=180,
                retry_policy=LLMRetryPolicy(attempts=1, initial_delay=0),
            )

        self.assertEqual("backup response", result)
        self.assertEqual(
            ["primary-vllm", "backup-openwebui"],
            [call.args[0]["name"] for call in call_once.call_args_list],
        )
        self.assertEqual([60, 60], [call.kwargs["timeout"] for call in call_once.call_args_list])
        self.assertEqual([1, 2], [call.kwargs["provider_index"] for call in call_once.call_args_list])

    def test_retry_restarts_the_entire_provider_chain(self) -> None:
        llm = multi_llm_config()
        with patch(
            "orchestrator.llm.call_chat_completion_once",
            side_effect=[
                RuntimeError("primary round one"),
                RuntimeError("backup round one"),
                RuntimeError("primary round two"),
                "backup round two response",
            ],
        ) as call_once, patch("orchestrator.llm.time.sleep") as sleep:
            result = call_chat_completion(
                llm,
                [{"role": "user", "content": "hello"}],
                timeout=180,
                retry_policy=LLMRetryPolicy(attempts=2, initial_delay=3),
            )

        self.assertEqual("backup round two response", result)
        self.assertEqual(
            ["primary-vllm", "backup-openwebui", "primary-vllm", "backup-openwebui"],
            [call.args[0]["name"] for call in call_once.call_args_list],
        )
        self.assertEqual([1, 1, 2, 2], [call.kwargs["attempt"] for call in call_once.call_args_list])
        sleep.assert_called_once_with(3)

    def test_all_provider_errors_are_reported(self) -> None:
        llm = multi_llm_config()
        with patch(
            "orchestrator.llm.call_chat_completion_once",
            side_effect=[RuntimeError("primary down"), RuntimeError("backup down")],
        ):
            with self.assertRaisesRegex(RuntimeError, "primary-vllm: primary down.*backup-openwebui: backup down"):
                call_chat_completion(
                    llm,
                    [{"role": "user", "content": "hello"}],
                    timeout=180,
                    retry_policy=LLMRetryPolicy(attempts=1, initial_delay=0),
                )

    def test_trace_records_provider_switch_and_selected_provider(self) -> None:
        llm = multi_llm_config()
        with tempfile.TemporaryDirectory() as temp_dir:
            trace_path = Path(temp_dir) / "llm_trace.jsonl"
            with patch.dict(os.environ, {"DLA_LLM_TRACE_PATH": str(trace_path)}, clear=False), patch(
                "orchestrator.llm.call_chat_completion_once",
                side_effect=[RuntimeError("primary unavailable"), "backup response"],
            ):
                call_chat_completion(
                    llm,
                    [{"role": "user", "content": "hello"}],
                    timeout=180,
                    retry_policy=LLMRetryPolicy(attempts=1, initial_delay=0),
                )

            events = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]

        failover = next(item for item in events if item["event"] == "llm_failover")
        completed = next(item for item in events if item["event"] == "llm_call")
        self.assertEqual("primary-vllm", failover["from_provider"])
        self.assertEqual("backup-openwebui", failover["to_provider"])
        self.assertEqual("backup-openwebui", completed["provider_name"])


if __name__ == "__main__":
    unittest.main()
