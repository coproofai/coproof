"""
TCD-11 — Agents Worker
=======================
Module : agents/agents_service.py
Responsible : Jesús
Tools : pytest, responses, unittest.mock

Covered test cases
──────────────────
TC-11-01  suggest openai/gpt-4o returns model response
TC-11-02  suggest anthropic/claude returns text
TC-11-03  suggest google/gemini returns text
TC-11-04  suggest deepseek/deepseek-chat returns text
TC-11-05  suggest mock/test calls Copilot proxy
TC-11-06  suggest injects default system prompt when none provided
TC-11-07  suggest uses custom system prompt when provided
TC-11-08  suggest prepends context to user message
TC-11-09  _call_openai_compat raises RuntimeError on HTTP 429
TC-11-10  suggest raises requests.exceptions.Timeout when LLM call times out

Test design notes
─────────────────
agents_service.py is pure Python — no Flask, no DB, no Celery broker needed.
The public API function is `suggest()` (not `suggest_text`).  It returns:
  { "suggestion": str, "model_id": str, "processing_time_seconds": float }

TC-11-01 to TC-11-04/09/10: `@responses.activate` per method; HTTP calls mocked.

TC-11-05 (mock/Copilot provider): `COPILOT_BASE_URL` is read once at module
import.  Patch `agents_service.COPILOT_BASE_URL` to `http://test-copilot:9999`
and register that URL in `responses`.

TC-11-06/07/08: After calling `suggest()`, inspect the captured request body via
`json.loads(responses.calls[0].request.body)` to assert message structure.

TC-11-09: Mock returns HTTP 429 → `RuntimeError` with "429" in message.

TC-11-10: `responses.add(..., body=requests.exceptions.Timeout())` makes the
HTTP call raise `Timeout` directly; `suggest()` does not catch it, so it
propagates to the caller.

Google URL (TC-11-03) embeds the API key as a query parameter; `re.compile` is
used to match any key value.

Run with:
  cd agents
  pytest -v tests/tcd11_agents/test_tcd11_agents_service.py
"""

import json
import re
import unittest.mock as mock

import pytest
import requests
import responses as rsps_lib

from agents_service import (
    DEFAULT_SYSTEM_PROMPT,
    _call_openai_compat,
    suggest,
)

_OPENAI_URL = "https://api.openai.com/v1/chat/completions"
_ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
_DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"
_GOOGLE_URL_RE = re.compile(r"https://generativelanguage\.googleapis\.com/.*")
_COPILOT_BASE = "http://test-copilot:9999"
_COPILOT_URL = f"{_COPILOT_BASE}/copilot"

_SUGGESTION = "Consider using induction."
_OAI_RESP = {"choices": [{"message": {"content": _SUGGESTION}}]}
_ANT_RESP = {"content": [{"text": _SUGGESTION}]}
_GGL_RESP = {"candidates": [{"content": {"parts": [{"text": _SUGGESTION}]}}]}
_CPL_RESP = {"answer": _SUGGESTION}


# ─────────────────────────────────────────────────────────────────────────────
# TC-11-01  suggest with openai/gpt-4o returns the model response
# ─────────────────────────────────────────────────────────────────────────────

class TestTC1101_SuggestOpenAI:
    """TC-11-01 — OpenAI provider: returned suggestion matches mocked content."""

    @rsps_lib.activate
    def test_returns_suggestion(self):
        rsps_lib.add(rsps_lib.POST, _OPENAI_URL, json=_OAI_RESP)
        result = suggest("Suggest a lemma for...", model_id="openai/gpt-4o", api_key="sk-x")
        assert result["suggestion"] == _SUGGESTION


# ─────────────────────────────────────────────────────────────────────────────
# TC-11-02  suggest with anthropic/claude returns text
# ─────────────────────────────────────────────────────────────────────────────

class TestTC1102_SuggestAnthropic:
    """TC-11-02 — Anthropic provider: returns non-empty suggestion string."""

    @rsps_lib.activate
    def test_returns_non_empty(self):
        rsps_lib.add(rsps_lib.POST, _ANTHROPIC_URL, json=_ANT_RESP)
        result = suggest("Suggest a lemma.", model_id="anthropic/claude-3-5-sonnet-20241022", api_key="sk-ant")
        assert result["suggestion"]


# ─────────────────────────────────────────────────────────────────────────────
# TC-11-03  suggest with google/gemini returns text
# ─────────────────────────────────────────────────────────────────────────────

class TestTC1103_SuggestGoogle:
    """TC-11-03 — Google Gemini provider: returns non-empty suggestion string."""

    @rsps_lib.activate
    def test_returns_non_empty(self):
        rsps_lib.add(rsps_lib.POST, _GOOGLE_URL_RE, json=_GGL_RESP)
        result = suggest("Suggest a lemma.", model_id="google/gemini-flash-lite-latest", api_key="gkey")
        assert result["suggestion"]


# ─────────────────────────────────────────────────────────────────────────────
# TC-11-04  suggest with deepseek/deepseek-chat returns text
# ─────────────────────────────────────────────────────────────────────────────

class TestTC1104_SuggestDeepSeek:
    """TC-11-04 — DeepSeek (OpenAI-compatible) provider: returns non-empty suggestion."""

    @rsps_lib.activate
    def test_returns_non_empty(self):
        rsps_lib.add(rsps_lib.POST, _DEEPSEEK_URL, json=_OAI_RESP)
        result = suggest("Suggest a lemma.", model_id="deepseek/deepseek-chat", api_key="ds-key")
        assert result["suggestion"]


# ─────────────────────────────────────────────────────────────────────────────
# TC-11-05  suggest with mock/test calls Copilot proxy
# ─────────────────────────────────────────────────────────────────────────────

class TestTC1105_SuggestMockCopilot:
    """TC-11-05 — mock provider: request goes to COPILOT_BASE_URL/copilot; answer returned."""

    @rsps_lib.activate
    @mock.patch("agents_service.COPILOT_BASE_URL", _COPILOT_BASE)
    def test_calls_copilot_proxy(self):
        rsps_lib.add(rsps_lib.POST, _COPILOT_URL, json=_CPL_RESP)
        result = suggest("Suggest a lemma.", model_id="mock/test", api_key="ignored")
        assert result["suggestion"] == _SUGGESTION

    @rsps_lib.activate
    @mock.patch("agents_service.COPILOT_BASE_URL", _COPILOT_BASE)
    def test_request_goes_to_copilot_url(self):
        rsps_lib.add(rsps_lib.POST, _COPILOT_URL, json=_CPL_RESP)
        suggest("Suggest a lemma.", model_id="mock/test", api_key="ignored")
        assert rsps_lib.calls[0].request.url.startswith(_COPILOT_URL)


# ─────────────────────────────────────────────────────────────────────────────
# TC-11-06  suggest injects DEFAULT_SYSTEM_PROMPT when none is provided
# ─────────────────────────────────────────────────────────────────────────────

class TestTC1106_DefaultSystemPrompt:
    """TC-11-06 — No system_prompt arg → DEFAULT_SYSTEM_PROMPT used in messages[0]."""

    @rsps_lib.activate
    def test_default_system_prompt_in_request(self):
        rsps_lib.add(rsps_lib.POST, _OPENAI_URL, json=_OAI_RESP)
        suggest("Suggest a lemma.", model_id="openai/gpt-4o", api_key="sk-x")
        body = json.loads(rsps_lib.calls[0].request.body)
        system_msgs = [m for m in body["messages"] if m["role"] == "system"]
        assert system_msgs
        assert system_msgs[0]["content"] == DEFAULT_SYSTEM_PROMPT


# ─────────────────────────────────────────────────────────────────────────────
# TC-11-07  suggest uses custom system prompt when provided
# ─────────────────────────────────────────────────────────────────────────────

class TestTC1107_CustomSystemPrompt:
    """TC-11-07 — system_prompt arg overrides the default in the outgoing messages."""

    _CUSTOM = "You are a geometry expert."

    @rsps_lib.activate
    def test_custom_system_prompt_in_request(self):
        rsps_lib.add(rsps_lib.POST, _OPENAI_URL, json=_OAI_RESP)
        suggest("Suggest a lemma.", model_id="openai/gpt-4o", api_key="sk-x",
                system_prompt=self._CUSTOM)
        body = json.loads(rsps_lib.calls[0].request.body)
        system_msgs = [m for m in body["messages"] if m["role"] == "system"]
        assert system_msgs[0]["content"] == self._CUSTOM


# ─────────────────────────────────────────────────────────────────────────────
# TC-11-08  suggest prepends context to the user message
# ─────────────────────────────────────────────────────────────────────────────

class TestTC1108_ContextPrepended:
    """TC-11-08 — context is prepended to the user message in the outgoing request."""

    _CONTEXT = "The project proves Fermat's Last Theorem."
    _PROMPT = "Suggest a lemma."

    @rsps_lib.activate
    def test_user_message_contains_context(self):
        rsps_lib.add(rsps_lib.POST, _OPENAI_URL, json=_OAI_RESP)
        suggest(self._PROMPT, model_id="openai/gpt-4o", api_key="sk-x", context=self._CONTEXT)
        body = json.loads(rsps_lib.calls[0].request.body)
        user_msgs = [m for m in body["messages"] if m["role"] == "user"]
        assert self._CONTEXT in user_msgs[0]["content"]

    @rsps_lib.activate
    def test_user_message_contains_prompt(self):
        rsps_lib.add(rsps_lib.POST, _OPENAI_URL, json=_OAI_RESP)
        suggest(self._PROMPT, model_id="openai/gpt-4o", api_key="sk-x", context=self._CONTEXT)
        body = json.loads(rsps_lib.calls[0].request.body)
        user_msgs = [m for m in body["messages"] if m["role"] == "user"]
        assert self._PROMPT in user_msgs[0]["content"]


# ─────────────────────────────────────────────────────────────────────────────
# TC-11-09  _call_openai_compat raises RuntimeError on HTTP 429
# ─────────────────────────────────────────────────────────────────────────────

class TestTC1109_RateLimit:
    """TC-11-09 — HTTP 429 response → RuntimeError with "429" in message."""

    @rsps_lib.activate
    def test_raises_runtime_error(self):
        rsps_lib.add(rsps_lib.POST, _OPENAI_URL, status=429,
                     json={"error": {"message": "Rate limit exceeded"}})
        with pytest.raises(RuntimeError):
            _call_openai_compat(
                [{"role": "user", "content": "hello"}],
                "gpt-4o", "sk-x", _OPENAI_URL,
            )

    @rsps_lib.activate
    def test_message_mentions_429(self):
        rsps_lib.add(rsps_lib.POST, _OPENAI_URL, status=429,
                     json={"error": {"message": "Rate limit exceeded"}})
        with pytest.raises(RuntimeError, match="429"):
            _call_openai_compat(
                [{"role": "user", "content": "hello"}],
                "gpt-4o", "sk-x", _OPENAI_URL,
            )


# ─────────────────────────────────────────────────────────────────────────────
# TC-11-10  suggest propagates requests.exceptions.Timeout
# ─────────────────────────────────────────────────────────────────────────────

class TestTC1110_Timeout:
    """TC-11-10 — When the HTTP call raises Timeout, suggest() lets it propagate."""

    @rsps_lib.activate
    def test_raises_timeout(self):
        rsps_lib.add(rsps_lib.POST, _OPENAI_URL,
                     body=requests.exceptions.Timeout())
        with pytest.raises(requests.exceptions.Timeout):
            suggest("Suggest a lemma.", model_id="openai/gpt-4o", api_key="sk-x")
