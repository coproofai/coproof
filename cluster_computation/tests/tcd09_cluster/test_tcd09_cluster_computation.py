"""
TCD-09 — Cluster Computation Worker
=====================================
Module : cluster_computation/computation_service.py
Responsible : Emiliano
Tools : pytest, responses, pytest-mock

Covered test cases
──────────────────
TC-09-01  run_cluster_job submits and polls until COMPLETED
TC-09-02  run_cluster_job returns error when cluster API unreachable
TC-09-03  run_cluster_job returns error when API returns no job_id
TC-09-04  run_cluster_job returns error for FAILED terminal state
TC-09-05  run_cluster_job returns error for TIMEOUT terminal state
TC-09-06  run_cluster_job returns error for NODE_FAIL terminal state
TC-09-07  run_cluster_job deadline exceeded → local timeout error
TC-09-08  _headers includes X-API-Key when CLUSTER_API_KEY is set
TC-09-09  _headers omits X-API-Key when CLUSTER_API_KEY is empty
TC-09-10  run_cluster_job COMPLETED job with null result → error

Test design notes
─────────────────
cluster_computation/computation_service.py is a pure HTTP client — no Flask
app context and no database.  All tests import directly from
`computation_service`.

All HTTP calls to the cluster REST API are intercepted by the `responses`
library.  `@responses.activate` is applied per-method for full isolation
(rsps.calls is reset between tests).

TC-09-08/09 test `_headers()` by patching the module-level
`computation_service.CLUSTER_API_KEY` variable directly with
`mock.patch(..., new=...)`.  The module reads the env var once at import
time and stores it as a plain string; patching the variable (not os.environ)
is the correct approach.

TC-09-07 (deadline exceeded): `computation_service.time.perf_counter` is
patched with a side_effect that simulates time advancing past the deadline
after one poll cycle, making the test run instantly without a real 1-second
wait.  `computation_service.POLL_INTERVAL` is also patched to 0 to suppress
the `time.sleep` call.  The call sequence of perf_counter inside
`run_cluster_job` is:
  [0] start = perf_counter()            → 0.0
  [1] deadline = perf_counter() + 1     → 0.0 → deadline = 1.0
  [2] loop check 1: perf_counter() > 1  → 0.5  → False  (poll happens)
  [3] loop check 2: perf_counter() > 1  → 2.0  → True   (return error)
  [4] _error_result: perf_counter()      → 2.0  (processing_time calc)

TC-09-01: two responses registered for GET /jobs/job-1 — first returns
RUNNING, second returns COMPLETED.  The responses library consumes them
in FIFO order.

Run with:
  cd cluster_computation
  pytest -v tests/tcd09_cluster/test_tcd09_cluster_computation.py
"""

import unittest.mock as mock

import pytest
import requests
import responses as rsps_lib

from computation_service import _headers, run_cluster_job

_BASE = "http://192.168.0.17:8765"
_JOBS_URL = f"{_BASE}/jobs"

_GOOD_RESULT = {
    "completed": True,
    "sufficient": True,
    "evidence": "ok",
    "summary": None,
    "records": [],
    "stdout": "",
    "stderr": "",
    "error": None,
}

_VALID_PAYLOAD = {
    "source_code": "def f(d, t): return {'evidence': 'ok', 'sufficient': True}",
    "entrypoint": "f",
    "timeout_seconds": 10,
}


# ─────────────────────────────────────────────────────────────────────────────
# TC-09-01  run_cluster_job submits and polls until COMPLETED
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0901_RunClusterJobCompleted:
    """TC-09-01 — Happy path: submit → RUNNING → COMPLETED with result."""

    @rsps_lib.activate
    def test_completed_true(self):
        rsps_lib.add(rsps_lib.POST, _JOBS_URL, json={"job_id": "job-1"})
        rsps_lib.add(rsps_lib.GET, f"{_JOBS_URL}/job-1", json={"status": "RUNNING"})
        rsps_lib.add(rsps_lib.GET, f"{_JOBS_URL}/job-1",
                     json={"status": "COMPLETED", "result": _GOOD_RESULT})
        result = run_cluster_job(_VALID_PAYLOAD)
        assert result["completed"] is True

    @rsps_lib.activate
    def test_slurm_state_completed(self):
        rsps_lib.add(rsps_lib.POST, _JOBS_URL, json={"job_id": "job-1"})
        rsps_lib.add(rsps_lib.GET, f"{_JOBS_URL}/job-1", json={"status": "RUNNING"})
        rsps_lib.add(rsps_lib.GET, f"{_JOBS_URL}/job-1",
                     json={"status": "COMPLETED", "result": _GOOD_RESULT})
        result = run_cluster_job(_VALID_PAYLOAD)
        assert result["slurm_state"] == "COMPLETED"

    @rsps_lib.activate
    def test_slurm_job_id(self):
        rsps_lib.add(rsps_lib.POST, _JOBS_URL, json={"job_id": "job-1"})
        rsps_lib.add(rsps_lib.GET, f"{_JOBS_URL}/job-1", json={"status": "RUNNING"})
        rsps_lib.add(rsps_lib.GET, f"{_JOBS_URL}/job-1",
                     json={"status": "COMPLETED", "result": _GOOD_RESULT})
        result = run_cluster_job(_VALID_PAYLOAD)
        assert result["slurm_job_id"] == "job-1"


# ─────────────────────────────────────────────────────────────────────────────
# TC-09-02  run_cluster_job returns error when cluster API is unreachable
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0902_ClusterAPIUnreachable:
    """TC-09-02 — ConnectionError on POST /jobs → completed=False."""

    @rsps_lib.activate
    def test_completed_false(self):
        rsps_lib.add(rsps_lib.POST, _JOBS_URL,
                     body=requests.exceptions.ConnectionError())
        result = run_cluster_job(_VALID_PAYLOAD)
        assert result["completed"] is False

    @rsps_lib.activate
    def test_error_mentions_failed_to_submit(self):
        rsps_lib.add(rsps_lib.POST, _JOBS_URL,
                     body=requests.exceptions.ConnectionError())
        result = run_cluster_job(_VALID_PAYLOAD)
        assert "Failed to submit" in (result.get("error") or "")


# ─────────────────────────────────────────────────────────────────────────────
# TC-09-03  run_cluster_job returns error when API returns no job_id
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0903_NoJobId:
    """TC-09-03 — POST /jobs returns {} (no job_id) → completed=False."""

    @rsps_lib.activate
    def test_completed_false(self):
        rsps_lib.add(rsps_lib.POST, _JOBS_URL, json={})
        result = run_cluster_job(_VALID_PAYLOAD)
        assert result["completed"] is False

    @rsps_lib.activate
    def test_error_mentions_no_job_id(self):
        rsps_lib.add(rsps_lib.POST, _JOBS_URL, json={})
        result = run_cluster_job(_VALID_PAYLOAD)
        assert "job_id" in (result.get("error") or "").lower()


# ─────────────────────────────────────────────────────────────────────────────
# TC-09-04  run_cluster_job returns error for FAILED terminal state
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0904_TerminalStateFailed:
    """TC-09-04 — Poll immediately returns FAILED with no result field."""

    @rsps_lib.activate
    def test_completed_false(self):
        rsps_lib.add(rsps_lib.POST, _JOBS_URL, json={"job_id": "job-1"})
        rsps_lib.add(rsps_lib.GET, f"{_JOBS_URL}/job-1", json={"status": "FAILED"})
        result = run_cluster_job(_VALID_PAYLOAD)
        assert result["completed"] is False

    @rsps_lib.activate
    def test_slurm_state_failed(self):
        rsps_lib.add(rsps_lib.POST, _JOBS_URL, json={"job_id": "job-1"})
        rsps_lib.add(rsps_lib.GET, f"{_JOBS_URL}/job-1", json={"status": "FAILED"})
        result = run_cluster_job(_VALID_PAYLOAD)
        assert result["slurm_state"] == "FAILED"


# ─────────────────────────────────────────────────────────────────────────────
# TC-09-05  run_cluster_job returns error for TIMEOUT terminal state
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0905_TerminalStateTimeout:
    """TC-09-05 — Poll returns TIMEOUT immediately."""

    @rsps_lib.activate
    def test_completed_false(self):
        rsps_lib.add(rsps_lib.POST, _JOBS_URL, json={"job_id": "job-1"})
        rsps_lib.add(rsps_lib.GET, f"{_JOBS_URL}/job-1", json={"status": "TIMEOUT"})
        result = run_cluster_job(_VALID_PAYLOAD)
        assert result["completed"] is False

    @rsps_lib.activate
    def test_slurm_state_timeout(self):
        rsps_lib.add(rsps_lib.POST, _JOBS_URL, json={"job_id": "job-1"})
        rsps_lib.add(rsps_lib.GET, f"{_JOBS_URL}/job-1", json={"status": "TIMEOUT"})
        result = run_cluster_job(_VALID_PAYLOAD)
        assert result["slurm_state"] == "TIMEOUT"


# ─────────────────────────────────────────────────────────────────────────────
# TC-09-06  run_cluster_job returns error for NODE_FAIL terminal state
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0906_TerminalStateNodeFail:
    """TC-09-06 — Poll returns NODE_FAIL immediately."""

    @rsps_lib.activate
    def test_completed_false(self):
        rsps_lib.add(rsps_lib.POST, _JOBS_URL, json={"job_id": "job-1"})
        rsps_lib.add(rsps_lib.GET, f"{_JOBS_URL}/job-1", json={"status": "NODE_FAIL"})
        result = run_cluster_job(_VALID_PAYLOAD)
        assert result["completed"] is False

    @rsps_lib.activate
    def test_slurm_state_node_fail(self):
        rsps_lib.add(rsps_lib.POST, _JOBS_URL, json={"job_id": "job-1"})
        rsps_lib.add(rsps_lib.GET, f"{_JOBS_URL}/job-1", json={"status": "NODE_FAIL"})
        result = run_cluster_job(_VALID_PAYLOAD)
        assert result["slurm_state"] == "NODE_FAIL"


# ─────────────────────────────────────────────────────────────────────────────
# TC-09-07  run_cluster_job deadline exceeded → local timeout error
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0907_DeadlineExceeded:
    """TC-09-07 — Polling always returns RUNNING; deadline is simulated via
    time.perf_counter mock so the test runs instantly.

    perf_counter call sequence inside run_cluster_job:
      [0] start = perf_counter()              → 0.0
      [1] deadline = perf_counter() + 1       → 0.0   (deadline = 1.0)
      [2] loop check 1: perf_counter() > 1.0  → 0.5   → False  (poll runs)
      [3] loop check 2: perf_counter() > 1.0  → 2.0   → True   (exit)
      [4] _error_result: perf_counter()        → 2.0
    """

    _SIDE_EFFECT = [0.0, 0.0, 0.5, 2.0, 2.0]

    @rsps_lib.activate
    @mock.patch("computation_service.POLL_INTERVAL", new=0)
    @mock.patch("computation_service.time.perf_counter", side_effect=_SIDE_EFFECT)
    def test_completed_false(self, _mock_time):
        rsps_lib.add(rsps_lib.POST, _JOBS_URL, json={"job_id": "job-1"})
        rsps_lib.add(rsps_lib.GET, f"{_JOBS_URL}/job-1", json={"status": "RUNNING"})
        result = run_cluster_job({**_VALID_PAYLOAD, "timeout_seconds": 1})
        assert result["completed"] is False

    @rsps_lib.activate
    @mock.patch("computation_service.POLL_INTERVAL", new=0)
    @mock.patch("computation_service.time.perf_counter", side_effect=_SIDE_EFFECT)
    def test_error_mentions_timeout(self, _mock_time):
        rsps_lib.add(rsps_lib.POST, _JOBS_URL, json={"job_id": "job-1"})
        rsps_lib.add(rsps_lib.GET, f"{_JOBS_URL}/job-1", json={"status": "RUNNING"})
        result = run_cluster_job({**_VALID_PAYLOAD, "timeout_seconds": 1})
        assert "timed out" in (result.get("error") or "").lower()


# ─────────────────────────────────────────────────────────────────────────────
# TC-09-08  _headers includes X-API-Key when CLUSTER_API_KEY is set
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0908_HeadersWithApiKey:
    """TC-09-08 — Module-level CLUSTER_API_KEY patched to 'secret'."""

    @mock.patch("computation_service.CLUSTER_API_KEY", new="secret")
    def test_includes_api_key(self):
        result = _headers()
        assert result.get("X-API-Key") == "secret"


# ─────────────────────────────────────────────────────────────────────────────
# TC-09-09  _headers omits X-API-Key when CLUSTER_API_KEY is empty
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0909_HeadersWithoutApiKey:
    """TC-09-09 — Module-level CLUSTER_API_KEY patched to empty string."""

    @mock.patch("computation_service.CLUSTER_API_KEY", new="")
    def test_omits_api_key(self):
        result = _headers()
        assert "X-API-Key" not in result


# ─────────────────────────────────────────────────────────────────────────────
# TC-09-10  run_cluster_job COMPLETED job with null result → error
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0910_CompletedNullResult:
    """TC-09-10 — COMPLETED state but result is null → completed=False."""

    @rsps_lib.activate
    def test_completed_false(self):
        rsps_lib.add(rsps_lib.POST, _JOBS_URL, json={"job_id": "job-1"})
        rsps_lib.add(rsps_lib.GET, f"{_JOBS_URL}/job-1",
                     json={"status": "COMPLETED", "result": None})
        result = run_cluster_job(_VALID_PAYLOAD)
        assert result["completed"] is False

    @rsps_lib.activate
    def test_error_mentions_missing_result(self):
        rsps_lib.add(rsps_lib.POST, _JOBS_URL, json={"job_id": "job-1"})
        rsps_lib.add(rsps_lib.GET, f"{_JOBS_URL}/job-1",
                     json={"status": "COMPLETED", "result": None})
        result = run_cluster_job(_VALID_PAYLOAD)
        error = result.get("error") or ""
        assert "result" in error.lower() or "no result" in error.lower()

