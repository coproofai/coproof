"""
TCD-10 — NL2FL Worker
======================
Module : nl2fl/nl2fl_service.py
Responsible : Jesús
Tools : pytest, responses, pytest-mock

Covered test cases
──────────────────
TC-10-01  _call_openai_compat returns content on HTTP 200
TC-10-02  _call_openai_compat raises RuntimeError on non-200
TC-10-03  _call_openai_compat raises RuntimeError when choices is empty
TC-10-04  _call_anthropic returns text from content[0].text
TC-10-05  _call_anthropic raises RuntimeError when content is empty
TC-10-06  _call_google returns text from first candidate
TC-10-07  translate_and_verify OpenAI provider succeeds on first attempt
TC-10-08  translate_and_verify retries when Lean compiler returns errors
TC-10-09  translate_and_verify exhausts max_retries and returns failure
TC-10-10  _call_llm with unknown provider raises RuntimeError
TC-10-11  translate_and_verify with empty LLM response returns valid=False
TC-10-12  _extract_lean_code ignores text outside fenced block

Test design notes
─────────────────
nl2fl_service.py is pure Python with no Flask app context and no database.
All tests import directly from `nl2fl_service`.

The public API function is `translate_and_verify` (not `translate_to_lean`
as the draft spec named it).  It returns:
  { "valid": bool, "attempts": int, "final_lean": str,
    "history": [...], "processing_time_seconds": float }

TC-10-01 to TC-10-06: HTTP calls are intercepted by `responses`.
`@responses.activate` is applied per-method for full isolation.

TC-10-07 to TC-10-09/11: `nl2fl_service._call_llm` and
`nl2fl_service._verify_with_lean` are patched so no real LLM or Celery
broker is contacted.  `_verify_with_lean` is the internal helper that
dispatches to the Lean Celery worker; patching it at the module path is
required (not `celery.Celery` or `tasks.verify_snippet`).

TC-10-10: `_call_llm` is tested directly (not via `translate_and_verify`)
because `translate_and_verify` catches all exceptions from `_call_llm` and
stores them in history rather than re-raising.  Testing `_call_llm` directly
verifies the spec intent that an unknown provider raises RuntimeError.

TC-10-12: `_extract_lean_code` is a pure function — no mocking needed.

Google URL (TC-10-06) embeds the API key as a query parameter:
  https://generativelanguage.googleapis.com/v1beta/models/<model>:generateContent?key=<key>
`re.compile` is used as the URL argument to `responses.add` to match any key.

Run with:
  cd nl2fl
  pytest -v tests/tcd10_nl2fl/test_tcd10_nl2fl_service.py
"""

import re
import unittest.mock as mock

import pytest
import responses as rsps_lib

from nl2fl_service import (
    _call_anthropic,
    _call_google,
    _call_llm,
    _call_openai_compat,
    _extract_lean_code,
    translate_and_verify,
)

_OPENAI_URL = "https://api.openai.com/v1/chat/completions"
_ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
_GOOGLE_URL_RE = re.compile(r"https://generativelanguage\.googleapis\.com/.*")

_MESSAGES = [{"role": "user", "content": "For all n, n+1 > n"}]
_LEAN_BLOCK = "```lean\ntheorem t : True := trivial\n```"
_LEAN_CODE = "theorem t : True := trivial"


# ─────────────────────────────────────────────────────────────────────────────
# TC-10-01  _call_openai_compat returns content on HTTP 200
# ─────────────────────────────────────────────────────────────────────────────

class TestTC1001_CallOpenaiCompatSuccess:
    """TC-10-01 — HTTP 200 with choices returns the content string."""

    @rsps_lib.activate
    def test_returns_content_string(self):
        rsps_lib.add(rsps_lib.POST, _OPENAI_URL, json={
            "choices": [{"message": {"content": _LEAN_BLOCK}}]
        })
        result = _call_openai_compat(_MESSAGES, "gpt-4o", "sk-test", _OPENAI_URL)
        assert result == _LEAN_BLOCK


# ─────────────────────────────────────────────────────────────────────────────
# TC-10-02  _call_openai_compat raises RuntimeError on non-200
# ─────────────────────────────────────────────────────────────────────────────

class TestTC1002_CallOpenaiCompatNon200:
    """TC-10-02 — HTTP 401 raises RuntimeError with status in message."""

    @rsps_lib.activate
    def test_raises_runtime_error(self):
        rsps_lib.add(rsps_lib.POST, _OPENAI_URL, status=401, json={"error": "Unauthorized"})
        with pytest.raises(RuntimeError, match="401"):
            _call_openai_compat(_MESSAGES, "gpt-4o", "sk-test", _OPENAI_URL)


# ─────────────────────────────────────────────────────────────────────────────
# TC-10-03  _call_openai_compat raises RuntimeError when choices is empty
# ─────────────────────────────────────────────────────────────────────────────

class TestTC1003_CallOpenaiCompatEmptyChoices:
    """TC-10-03 — HTTP 200 with choices=[] raises RuntimeError."""

    @rsps_lib.activate
    def test_raises_runtime_error(self):
        rsps_lib.add(rsps_lib.POST, _OPENAI_URL, json={"choices": []})
        with pytest.raises(RuntimeError):
            _call_openai_compat(_MESSAGES, "gpt-4o", "sk-test", _OPENAI_URL)


# ─────────────────────────────────────────────────────────────────────────────
# TC-10-04  _call_anthropic returns text from content[0].text
# ─────────────────────────────────────────────────────────────────────────────

class TestTC1004_CallAnthropicSuccess:
    """TC-10-04 — HTTP 200 with content[0].text returns the text string."""

    @rsps_lib.activate
    def test_returns_text(self):
        rsps_lib.add(rsps_lib.POST, _ANTHROPIC_URL, json={
            "content": [{"text": _LEAN_BLOCK}]
        })
        result = _call_anthropic(_MESSAGES, "claude-3-5-sonnet-20241022", "sk-ant-test")
        assert result == _LEAN_BLOCK


# ─────────────────────────────────────────────────────────────────────────────
# TC-10-05  _call_anthropic raises RuntimeError when content is empty
# ─────────────────────────────────────────────────────────────────────────────

class TestTC1005_CallAnthropicEmptyContent:
    """TC-10-05 — HTTP 200 with content=[] raises RuntimeError."""

    @rsps_lib.activate
    def test_raises_runtime_error(self):
        rsps_lib.add(rsps_lib.POST, _ANTHROPIC_URL, json={"content": []})
        with pytest.raises(RuntimeError):
            _call_anthropic(_MESSAGES, "claude-3-5-sonnet-20241022", "sk-ant-test")


# ─────────────────────────────────────────────────────────────────────────────
# TC-10-06  _call_google returns text from first candidate
# ─────────────────────────────────────────────────────────────────────────────

class TestTC1006_CallGoogleSuccess:
    """TC-10-06 — HTTP 200 with candidates[0].content.parts[0].text returns text."""

    @rsps_lib.activate
    def test_returns_text(self):
        rsps_lib.add(rsps_lib.POST, _GOOGLE_URL_RE, json={
            "candidates": [{"content": {"parts": [{"text": _LEAN_BLOCK}]}}]
        })
        result = _call_google(_MESSAGES, "gemini-flash-lite-latest", "api-key")
        assert result == _LEAN_BLOCK


# ─────────────────────────────────────────────────────────────────────────────
# TC-10-07  translate_and_verify — OpenAI provider succeeds on first attempt
# ─────────────────────────────────────────────────────────────────────────────

class TestTC1007_TranslateAndVerifySuccessFirst:
    """TC-10-07 — LLM returns valid code, verifier confirms → valid=True, attempts=1."""

    @mock.patch("nl2fl_service._verify_with_lean", return_value={"valid": True, "errors": []})
    @mock.patch("nl2fl_service._call_llm", return_value=_LEAN_BLOCK)
    def test_valid_true(self, _mock_llm, _mock_verify):
        result = translate_and_verify(
            "For all n, n+1 > n", model_id="openai/gpt-4o", api_key="sk-x"
        )
        assert result["valid"] is True

    @mock.patch("nl2fl_service._verify_with_lean", return_value={"valid": True, "errors": []})
    @mock.patch("nl2fl_service._call_llm", return_value=_LEAN_BLOCK)
    def test_attempts_one(self, _mock_llm, _mock_verify):
        result = translate_and_verify(
            "For all n, n+1 > n", model_id="openai/gpt-4o", api_key="sk-x"
        )
        assert result["attempts"] == 1

    @mock.patch("nl2fl_service._verify_with_lean", return_value={"valid": True, "errors": []})
    @mock.patch("nl2fl_service._call_llm", return_value=_LEAN_BLOCK)
    def test_final_lean_contains_code(self, _mock_llm, _mock_verify):
        result = translate_and_verify(
            "For all n, n+1 > n", model_id="openai/gpt-4o", api_key="sk-x"
        )
        assert _LEAN_CODE in result["final_lean"]


# ─────────────────────────────────────────────────────────────────────────────
# TC-10-08  translate_and_verify — retries when Lean compiler returns errors
# ─────────────────────────────────────────────────────────────────────────────

class TestTC1008_TranslateAndVerifyRetries:
    """TC-10-08 — First verify fails, second succeeds → valid=True, attempts=2.
    The second LLM call must include the compiler error in its messages.
    """

    _ERRORS = [{"line": 1, "column": 0, "message": "type mismatch"}]

    @mock.patch("nl2fl_service._verify_with_lean", side_effect=[
        {"valid": False, "errors": [{"line": 1, "column": 0, "message": "type mismatch"}]},
        {"valid": True, "errors": []},
    ])
    @mock.patch("nl2fl_service._call_llm", return_value=_LEAN_BLOCK)
    def test_valid_true(self, _mock_llm, _mock_verify):
        result = translate_and_verify(
            "For all n, n+1 > n", model_id="openai/gpt-4o", api_key="sk-x", max_retries=3
        )
        assert result["valid"] is True

    @mock.patch("nl2fl_service._verify_with_lean", side_effect=[
        {"valid": False, "errors": [{"line": 1, "column": 0, "message": "type mismatch"}]},
        {"valid": True, "errors": []},
    ])
    @mock.patch("nl2fl_service._call_llm", return_value=_LEAN_BLOCK)
    def test_attempts_two(self, _mock_llm, _mock_verify):
        result = translate_and_verify(
            "For all n, n+1 > n", model_id="openai/gpt-4o", api_key="sk-x", max_retries=3
        )
        assert result["attempts"] == 2

    @mock.patch("nl2fl_service._verify_with_lean", side_effect=[
        {"valid": False, "errors": [{"line": 1, "column": 0, "message": "type mismatch"}]},
        {"valid": True, "errors": []},
    ])
    @mock.patch("nl2fl_service._call_llm", return_value=_LEAN_BLOCK)
    def test_second_call_includes_error_feedback(self, mock_llm, _mock_verify):
        translate_and_verify(
            "For all n, n+1 > n", model_id="openai/gpt-4o", api_key="sk-x", max_retries=3
        )
        second_messages = mock_llm.call_args_list[1][0][0]
        roles = [m["role"] for m in second_messages]
        assert "assistant" in roles
        user_texts = " ".join(m["content"] for m in second_messages if m["role"] == "user")
        assert "type mismatch" in user_texts


# ─────────────────────────────────────────────────────────────────────────────
# TC-10-09  translate_and_verify — exhausts max_retries and returns failure
# ─────────────────────────────────────────────────────────────────────────────

class TestTC1009_TranslateAndVerifyExhausted:
    """TC-10-09 — Verifier always returns False with max_retries=2 → valid=False, attempts=2."""

    @mock.patch("nl2fl_service._verify_with_lean",
                return_value={"valid": False, "errors": [{"line": 1, "column": 0, "message": "err"}]})
    @mock.patch("nl2fl_service._call_llm", return_value=_LEAN_BLOCK)
    def test_valid_false(self, _mock_llm, _mock_verify):
        result = translate_and_verify(
            "For all n, n+1 > n", model_id="openai/gpt-4o", api_key="sk-x", max_retries=2
        )
        assert result["valid"] is False

    @mock.patch("nl2fl_service._verify_with_lean",
                return_value={"valid": False, "errors": [{"line": 1, "column": 0, "message": "err"}]})
    @mock.patch("nl2fl_service._call_llm", return_value=_LEAN_BLOCK)
    def test_attempts_equals_max_retries(self, _mock_llm, _mock_verify):
        result = translate_and_verify(
            "For all n, n+1 > n", model_id="openai/gpt-4o", api_key="sk-x", max_retries=2
        )
        assert result["attempts"] == 2

    @mock.patch("nl2fl_service._verify_with_lean",
                return_value={"valid": False, "errors": [{"line": 1, "column": 0, "message": "err"}]})
    @mock.patch("nl2fl_service._call_llm", return_value=_LEAN_BLOCK)
    def test_history_has_two_entries(self, _mock_llm, _mock_verify):
        result = translate_and_verify(
            "For all n, n+1 > n", model_id="openai/gpt-4o", api_key="sk-x", max_retries=2
        )
        assert len(result["history"]) == 2


# ─────────────────────────────────────────────────────────────────────────────
# TC-10-10  _call_llm with unknown provider raises RuntimeError
# ─────────────────────────────────────────────────────────────────────────────

class TestTC1010_UnknownProvider:
    """TC-10-10 — _call_llm raises RuntimeError for an unrecognised provider.

    Note: translate_and_verify catches all LLM exceptions internally and
    stores them in history rather than re-raising.  Testing _call_llm directly
    is the correct way to verify the spec's intent.
    """

    def test_raises_runtime_error(self):
        with pytest.raises(RuntimeError):
            _call_llm(_MESSAGES, "unknown/model", "key")

    def test_message_mentions_provider(self):
        with pytest.raises(RuntimeError, match="unknown"):
            _call_llm(_MESSAGES, "unknown/model", "key")


# ─────────────────────────────────────────────────────────────────────────────
# TC-10-11  translate_and_verify — empty LLM response returns valid=False
# ─────────────────────────────────────────────────────────────────────────────

class TestTC1011_EmptyLLMResponse:
    """TC-10-11 — _call_llm returns "" → _extract_lean_code returns "" →
    verification fails → valid=False.
    """

    @mock.patch("nl2fl_service._verify_with_lean",
                return_value={"valid": False, "errors": []})
    @mock.patch("nl2fl_service._call_llm", return_value="")
    def test_valid_false(self, _mock_llm, _mock_verify):
        result = translate_and_verify(
            "For all n, n+1 > n", model_id="openai/gpt-4o", api_key="sk-x", max_retries=1
        )
        assert result["valid"] is False


# ─────────────────────────────────────────────────────────────────────────────
# TC-10-12  _extract_lean_code ignores text outside fenced block
# ─────────────────────────────────────────────────────────────────────────────

class TestTC1012_ExtractLeanCode:
    """TC-10-12 — Only the content inside ```lean ... ``` is returned."""

    def test_extracts_fenced_content(self):
        raw = (
            "Here is your proof:\n"
            "```lean\n"
            "theorem t := trivial\n"
            "```\n"
            "Hope that helps!"
        )
        result = _extract_lean_code(raw)
        assert result == "theorem t := trivial"

    def test_no_surrounding_text(self):
        raw = "Preamble\n```lean\ntheorem x : Nat := 0\n```\nPostamble"
        result = _extract_lean_code(raw)
        assert "Preamble" not in result
        assert "Postamble" not in result

