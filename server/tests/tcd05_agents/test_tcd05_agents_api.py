"""
TCD-05 — Agents API (`web`)
=============================
Module : server/app/api/agents.py
Responsible : David
Tools : pytest-flask, pytest-mock

Covered test cases
──────────────────
TC-05-01  POST /agents/suggest/submit — valid payload returns 202 + task_id
TC-05-02  POST /agents/suggest/submit — missing prompt returns 400
TC-05-03  POST /agents/suggest/submit — missing model_id returns 400
TC-05-04  POST /agents/suggest/submit — no api_key, no saved key → 400
TC-05-05  POST /agents/suggest/submit — loads saved API key for authenticated user
TC-05-06  GET  /agents/suggest/<task_id>/result — completed task returns 200 + result

Test design notes
─────────────────
The agents blueprint is structurally identical to the translate blueprint:
  - Same optional-JWT + saved-key lookup pattern
  - Same AgentsClient.submit / AgentsClient.get_result interface
  - Same "error" key in JSON (not "message")

AgentsClient.submit and AgentsClient.get_result are patched at their class
path to prevent any Celery/Redis connection attempt.

TC-05-01 also verifies the forwarded payload contains prompt and model_id,
and that optional fields (system_prompt, context) are included when supplied.

TC-05-04 mirrors TCD-04 TC-04-06: two sub-cases — unauthenticated with no key,
and authenticated with no DB record for the model.

TC-05-05 asserts the decrypted DB key is forwarded to AgentsClient.submit.

TC-05-06 tests both the SUCCESS path (200 + result body) and the PENDING path
(202 + {"status": "pending"}) by mocking AgentsClient.get_result.

Run with:
  cd server
  pytest -v tests/tcd05_agents/test_tcd05_agents_api.py
"""

import unittest.mock as mock

import pytest


_SUBMIT_URL   = "/api/v1/agents/suggest/submit"
_RESULT_URL   = "/api/v1/agents/suggest/{task_id}/result"
_SUBMIT_PATH  = "app.services.integrations.agents_client.AgentsClient.submit"
_RESULT_PATH  = "app.services.integrations.agents_client.AgentsClient.get_result"

_VALID_BODY = {
    "prompt":   "Suggest a lemma for proving Fermat's Last Theorem.",
    "model_id": "openai/gpt-4o",
    "api_key":  "sk-test",
}


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ─────────────────────────────────────────────────────────────────────────────
# TC-05-01  Valid payload → 202 + task_id
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0501_ValidSubmit:
    """TC-05-01 — Happy-path: required fields + api_key in body → 202 + task_id."""

    @mock.patch(_SUBMIT_PATH, return_value="agent-task-1")
    def test_returns_202(self, _mock_submit, client):
        assert client.post(_SUBMIT_URL, json=_VALID_BODY).status_code == 202

    @mock.patch(_SUBMIT_PATH, return_value="agent-task-1")
    def test_body_contains_task_id(self, _mock_submit, client):
        data = client.post(_SUBMIT_URL, json=_VALID_BODY).get_json()
        assert data.get("task_id") == "agent-task-1"

    @mock.patch(_SUBMIT_PATH, return_value="agent-task-1")
    def test_submit_called_once(self, mock_submit, client):
        client.post(_SUBMIT_URL, json=_VALID_BODY)
        mock_submit.assert_called_once()

    @mock.patch(_SUBMIT_PATH, return_value="agent-task-1")
    def test_payload_contains_prompt_and_model(self, mock_submit, client):
        client.post(_SUBMIT_URL, json=_VALID_BODY)
        payload = mock_submit.call_args[0][0]
        assert payload["prompt"] == _VALID_BODY["prompt"]
        assert payload["model_id"] == "openai/gpt-4o"

    @mock.patch(_SUBMIT_PATH, return_value="agent-task-1")
    def test_optional_fields_forwarded(self, mock_submit, client):
        """system_prompt and context in body must be forwarded to AgentsClient."""
        body = {**_VALID_BODY, "system_prompt": "Be concise.", "context": "Lean 4 project."}
        client.post(_SUBMIT_URL, json=body)
        payload = mock_submit.call_args[0][0]
        assert payload.get("system_prompt") == "Be concise."
        assert payload.get("context") == "Lean 4 project."


# ─────────────────────────────────────────────────────────────────────────────
# TC-05-02  Missing prompt → 400
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0502_MissingPrompt:
    """TC-05-02 — Omitting prompt must return 400 before any dispatch."""

    def test_returns_400(self, client):
        assert client.post(_SUBMIT_URL, json={
            "model_id": "openai/gpt-4o",
            "api_key":  "sk-test",
        }).status_code == 400

    def test_error_mentions_prompt(self, client):
        data = client.post(_SUBMIT_URL, json={
            "model_id": "openai/gpt-4o",
            "api_key":  "sk-test",
        }).get_json()
        assert "prompt" in data.get("error", "")


# ─────────────────────────────────────────────────────────────────────────────
# TC-05-03  Missing model_id → 400
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0503_MissingModelId:
    """TC-05-03 — Omitting model_id must return 400."""

    def test_returns_400(self, client):
        assert client.post(_SUBMIT_URL, json={
            "prompt":  "Suggest something.",
            "api_key": "sk-test",
        }).status_code == 400

    def test_error_mentions_model_id(self, client):
        data = client.post(_SUBMIT_URL, json={
            "prompt":  "Suggest something.",
            "api_key": "sk-test",
        }).get_json()
        assert "model_id" in data.get("error", "")


# ─────────────────────────────────────────────────────────────────────────────
# TC-05-04  No api_key, no saved key → 400
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0504_NoApiKey:
    """TC-05-04 — When both body api_key and DB key are absent, return 400."""

    def test_unauthenticated_no_key_returns_400(self, client):
        assert client.post(_SUBMIT_URL, json={
            "prompt":   "Suggest something.",
            "model_id": "openai/gpt-4o",
        }).status_code == 400

    def test_authenticated_no_saved_key_returns_400(self, client, auth_user):
        assert client.post(
            _SUBMIT_URL,
            json={"prompt": "Suggest something.", "model_id": "openai/gpt-4o"},
            headers=_bearer(auth_user["token"]),
        ).status_code == 400

    def test_error_mentions_api_key(self, client):
        data = client.post(_SUBMIT_URL, json={
            "prompt":   "Suggest something.",
            "model_id": "openai/gpt-4o",
        }).get_json()
        assert "api_key" in data.get("error", "")


# ─────────────────────────────────────────────────────────────────────────────
# TC-05-05  Saved API key loaded for authenticated user
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0505_SavedApiKey:
    """TC-05-05 — When api_key is absent, the saved DB key is used."""

    @mock.patch(_SUBMIT_PATH, return_value="task-from-db-key")
    def test_returns_202(self, _mock_submit, client, user_with_key):
        resp = client.post(
            _SUBMIT_URL,
            json={"prompt": "Suggest a lemma.", "model_id": "openai/gpt-4o"},
            headers=_bearer(user_with_key["token"]),
        )
        assert resp.status_code == 202

    @mock.patch(_SUBMIT_PATH, return_value="task-from-db-key")
    def test_task_id_returned(self, _mock_submit, client, user_with_key):
        data = client.post(
            _SUBMIT_URL,
            json={"prompt": "Suggest a lemma.", "model_id": "openai/gpt-4o"},
            headers=_bearer(user_with_key["token"]),
        ).get_json()
        assert data.get("task_id") == "task-from-db-key"

    @mock.patch(_SUBMIT_PATH, return_value="task-from-db-key")
    def test_saved_key_forwarded(self, mock_submit, client, user_with_key):
        """AgentsClient.submit must receive the decrypted saved key."""
        client.post(
            _SUBMIT_URL,
            json={"prompt": "Suggest a lemma.", "model_id": "openai/gpt-4o"},
            headers=_bearer(user_with_key["token"]),
        )
        payload = mock_submit.call_args[0][0]
        assert payload["api_key"] == user_with_key["raw_key"]


# ─────────────────────────────────────────────────────────────────────────────
# TC-05-06  GET /agents/suggest/<task_id>/result — task result polling
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0506_GetResult:
    """TC-05-06 — Polling the result endpoint returns 200 when complete, 202 while pending."""

    @mock.patch(_RESULT_PATH, return_value={"status": "SUCCESS", "result": "Consider induction."})
    def test_completed_returns_200(self, _mock_result, client):
        resp = client.get(_RESULT_URL.format(task_id="agent-task-1"))
        assert resp.status_code == 200

    @mock.patch(_RESULT_PATH, return_value={"status": "SUCCESS", "result": "Consider induction."})
    def test_completed_body_matches_mock(self, _mock_result, client):
        data = client.get(_RESULT_URL.format(task_id="agent-task-1")).get_json()
        assert data.get("status") == "SUCCESS"
        assert data.get("result") == "Consider induction."

    @mock.patch(_RESULT_PATH, return_value=None)
    def test_pending_returns_202(self, _mock_result, client):
        resp = client.get(_RESULT_URL.format(task_id="agent-task-pending"))
        assert resp.status_code == 202

    @mock.patch(_RESULT_PATH, return_value=None)
    def test_pending_body_has_status_pending(self, _mock_result, client):
        data = client.get(_RESULT_URL.format(task_id="agent-task-pending")).get_json()
        assert data.get("status") == "pending"
