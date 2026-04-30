"""
TCD-04 — Translation API (`web`)
==================================
Module : server/app/api/translate.py
Responsible : David
Tools : pytest-flask, pytest-mock

Covered test cases
──────────────────
TC-04-01  POST /translate/submit — valid payload returns 202 + task_id
TC-04-02  POST /translate/submit — missing natural_text returns 400
TC-04-03  POST /translate/submit — missing model_id returns 400
TC-04-04  POST /translate/submit — max_retries outside 1–10 returns 400
TC-04-05  POST /translate/submit — loads saved API key for authenticated user
TC-04-06  POST /translate/submit — no api_key, no saved key → 400
TC-04-07  GET  /translate/models  — returns catalogue with expected fields

Test design notes
─────────────────
TranslateClient.submit is patched with mock.patch for all tests that should
reach the dispatch step.  This prevents any Celery/Redis connection attempt.
The `CELERY_TASK_ALWAYS_EAGER = True` config is redundant given the mock but
is present for safety (consistent with prior TCDs).

TC-04-05 exercises the saved-key path: a UserApiKey record is pre-inserted
by the `user_with_key` fixture and the request body deliberately omits
`api_key`.  The mock captures the payload received by TranslateClient.submit
so we can assert the DB key was actually used.

Run with:
  cd server
  pytest -v tests/tcd04_translate/test_tcd04_translate_api.py
"""

import unittest.mock as mock

import pytest


_SUBMIT_URL  = "/api/v1/translate/submit"
_MODELS_URL  = "/api/v1/translate/models"
_SUBMIT_PATH = "app.services.integrations.translate_client.TranslateClient.submit"

_VALID_BODY = {
    "natural_text": "For all n, n+1 > n",
    "model_id":     "openai/gpt-4o",
    "api_key":      "sk-test",
}


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ─────────────────────────────────────────────────────────────────────────────
# TC-04-01  Valid payload → 202 + task_id
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0401_ValidSubmit:
    """TC-04-01 — Happy-path: valid body, api_key in body, returns 202 + task_id."""

    @mock.patch(_SUBMIT_PATH, return_value="task-uuid-1")
    def test_returns_202(self, _mock_submit, client):
        resp = client.post(_SUBMIT_URL, json=_VALID_BODY)
        assert resp.status_code == 202

    @mock.patch(_SUBMIT_PATH, return_value="task-uuid-1")
    def test_body_contains_task_id(self, _mock_submit, client):
        data = client.post(_SUBMIT_URL, json=_VALID_BODY).get_json()
        assert data.get("task_id") == "task-uuid-1"

    @mock.patch(_SUBMIT_PATH, return_value="task-uuid-1")
    def test_submit_called_once(self, mock_submit, client):
        client.post(_SUBMIT_URL, json=_VALID_BODY)
        mock_submit.assert_called_once()

    @mock.patch(_SUBMIT_PATH, return_value="task-uuid-1")
    def test_payload_forwarded_to_client(self, mock_submit, client):
        """TranslateClient.submit receives the natural_text and model_id."""
        client.post(_SUBMIT_URL, json=_VALID_BODY)
        payload_sent = mock_submit.call_args[0][0]
        assert payload_sent["natural_text"] == "For all n, n+1 > n"
        assert payload_sent["model_id"] == "openai/gpt-4o"


# ─────────────────────────────────────────────────────────────────────────────
# TC-04-02  Missing natural_text → 400
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0402_MissingNaturalText:
    """TC-04-02 — Omitting natural_text must return 400 before any dispatch."""

    def test_returns_400(self, client):
        resp = client.post(_SUBMIT_URL, json={
            "model_id": "openai/gpt-4o",
            "api_key":  "sk-test",
        })
        assert resp.status_code == 400

    def test_error_mentions_natural_text(self, client):
        data = client.post(_SUBMIT_URL, json={
            "model_id": "openai/gpt-4o",
            "api_key":  "sk-test",
        }).get_json()
        assert "natural_text" in data.get("error", "")


# ─────────────────────────────────────────────────────────────────────────────
# TC-04-03  Missing model_id → 400
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0403_MissingModelId:
    """TC-04-03 — Omitting model_id must return 400."""

    def test_returns_400(self, client):
        resp = client.post(_SUBMIT_URL, json={
            "natural_text": "For all n, n+1 > n",
            "api_key":      "sk-test",
        })
        assert resp.status_code == 400

    def test_error_mentions_model_id(self, client):
        data = client.post(_SUBMIT_URL, json={
            "natural_text": "For all n, n+1 > n",
            "api_key":      "sk-test",
        }).get_json()
        assert "model_id" in data.get("error", "")


# ─────────────────────────────────────────────────────────────────────────────
# TC-04-04  max_retries outside 1–10 → 400
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0404_InvalidMaxRetries:
    """TC-04-04 — max_retries must be an integer in the range 1–10."""

    def test_zero_returns_400(self, client):
        body = {**_VALID_BODY, "max_retries": 0}
        assert client.post(_SUBMIT_URL, json=body).status_code == 400

    def test_eleven_returns_400(self, client):
        body = {**_VALID_BODY, "max_retries": 11}
        assert client.post(_SUBMIT_URL, json=body).status_code == 400

    def test_string_returns_400(self, client):
        body = {**_VALID_BODY, "max_retries": "many"}
        assert client.post(_SUBMIT_URL, json=body).status_code == 400

    def test_error_mentions_max_retries(self, client):
        body = {**_VALID_BODY, "max_retries": 0}
        data = client.post(_SUBMIT_URL, json=body).get_json()
        assert "max_retries" in data.get("error", "")

    @mock.patch(_SUBMIT_PATH, return_value="ok-task")
    def test_boundary_one_is_valid(self, _mock_submit, client):
        body = {**_VALID_BODY, "max_retries": 1}
        assert client.post(_SUBMIT_URL, json=body).status_code == 202

    @mock.patch(_SUBMIT_PATH, return_value="ok-task")
    def test_boundary_ten_is_valid(self, _mock_submit, client):
        body = {**_VALID_BODY, "max_retries": 10}
        assert client.post(_SUBMIT_URL, json=body).status_code == 202


# ─────────────────────────────────────────────────────────────────────────────
# TC-04-05  Saved API key loaded for authenticated user
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0405_SavedApiKey:
    """TC-04-05 — When api_key is absent, the saved DB key is used."""

    @mock.patch(_SUBMIT_PATH, return_value="task-from-db-key")
    def test_returns_202(self, _mock_submit, client, user_with_key):
        resp = client.post(
            _SUBMIT_URL,
            json={"natural_text": "∀ n, n + 1 > n", "model_id": "openai/gpt-4o"},
            headers=_bearer(user_with_key["token"]),
        )
        assert resp.status_code == 202

    @mock.patch(_SUBMIT_PATH, return_value="task-from-db-key")
    def test_task_id_returned(self, _mock_submit, client, user_with_key):
        data = client.post(
            _SUBMIT_URL,
            json={"natural_text": "∀ n, n + 1 > n", "model_id": "openai/gpt-4o"},
            headers=_bearer(user_with_key["token"]),
        ).get_json()
        assert data.get("task_id") == "task-from-db-key"

    @mock.patch(_SUBMIT_PATH, return_value="task-from-db-key")
    def test_saved_key_forwarded(self, mock_submit, client, user_with_key):
        """TranslateClient.submit must receive the decrypted saved key."""
        client.post(
            _SUBMIT_URL,
            json={"natural_text": "∀ n, n + 1 > n", "model_id": "openai/gpt-4o"},
            headers=_bearer(user_with_key["token"]),
        )
        payload_sent = mock_submit.call_args[0][0]
        assert payload_sent["api_key"] == user_with_key["raw_key"]


# ─────────────────────────────────────────────────────────────────────────────
# TC-04-06  No api_key, no saved key → 400
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0406_NoApiKey:
    """TC-04-06 — When both body api_key and DB key are absent, return 400."""

    def test_unauthenticated_no_key_returns_400(self, client):
        """No JWT, no api_key → 400 immediately."""
        resp = client.post(_SUBMIT_URL, json={
            "natural_text": "For all n, n+1 > n",
            "model_id":     "openai/gpt-4o",
        })
        assert resp.status_code == 400

    def test_authenticated_no_saved_key_returns_400(self, client, auth_user):
        """JWT present but no DB record for this model → 400."""
        resp = client.post(
            _SUBMIT_URL,
            json={"natural_text": "For all n, n+1 > n", "model_id": "openai/gpt-4o"},
            headers=_bearer(auth_user["token"]),
        )
        assert resp.status_code == 400

    def test_error_mentions_api_key(self, client):
        data = client.post(_SUBMIT_URL, json={
            "natural_text": "For all n, n+1 > n",
            "model_id":     "openai/gpt-4o",
        }).get_json()
        assert "api_key" in data.get("error", "")


# ─────────────────────────────────────────────────────────────────────────────
# TC-04-07  GET /translate/models — catalogue returned
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0407_Models:
    """TC-04-07 — GET /translate/models returns the static model catalogue."""

    def test_returns_200(self, client):
        assert client.get(_MODELS_URL).status_code == 200

    def test_response_is_list(self, client):
        data = client.get(_MODELS_URL).get_json()
        assert isinstance(data, list)

    def test_list_is_non_empty(self, client):
        data = client.get(_MODELS_URL).get_json()
        assert len(data) >= 1

    def test_each_entry_has_required_fields(self, client):
        data = client.get(_MODELS_URL).get_json()
        for entry in data:
            assert "id" in entry
            assert "name" in entry
            assert "provider" in entry

    def test_mock_test_model_is_present(self, client):
        data = client.get(_MODELS_URL).get_json()
        ids = [m["id"] for m in data]
        assert "mock/test" in ids
