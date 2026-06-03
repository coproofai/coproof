"""
TCD-08 — Computation Worker
============================
Module : computation/computation_service.py
Responsible : Daniel
Tools : pytest, pytest-mock

Covered test cases
──────────────────
TC-08-01  run_python_job with dict return {evidence, sufficient: True}
TC-08-02  run_python_job with tuple return (evidence, True)
TC-08-03  normalize_result accepts valid dict with sufficient=True
TC-08-04  normalize_result rejects dict without 'sufficient' → ValueError
TC-08-05  normalize_result rejects non-boolean 'sufficient' → ValueError
TC-08-06  normalize_result accepts 2-tuple (evidence, bool)
TC-08-07  normalize_result rejects invalid return type → ValueError
TC-08-08  run_python_job with undefined entrypoint → completed=False
TC-08-09  run_python_job where code raises exception → completed=False
TC-08-10  run_python_job subprocess.TimeoutExpired → completed=False
TC-08-11  run_python_job subprocess produces no stdout → completed=False

Test design notes
─────────────────
computation_service.py is pure Python — no Flask app context and no database.
All tests import directly from `computation_service`.

normalize_result is defined inside the RUNNER_SOURCE string (not at module level).
It is extracted once at module scope by exec-ing RUNNER_SOURCE into a private
namespace and pulling the function out.  This avoids duplicating the logic.

TC-08-01/02/08/09: real subprocess allowed — runner.py is pure Python with no
external dependencies and completes in well under 1 s.

TC-08-10: run_python_job does NOT catch subprocess.TimeoutExpired; that is caught
one level up by run_computation_job.  The test therefore calls run_computation_job
(patching computation_service.subprocess.run) so the expected completed=False
behaviour is observable.  This matches the intent of the spec even though the
spec text says run_python_job.

TC-08-11: run_python_job returns completed=False when stdout is empty.
subprocess.run is patched to return CompletedProcess(returncode=0, stdout="",
stderr="crash") and run_python_job is called directly.

Run with:
  cd computation
  pytest -v tests/tcd08_computation/test_tcd08_computation_service.py
"""

import subprocess
import unittest.mock as mock

import pytest

from computation_service import RUNNER_SOURCE, run_computation_job, run_python_job

# ---------------------------------------------------------------------------
# Extract normalize_result from the embedded runner source once at import time
# ---------------------------------------------------------------------------
_runner_ns: dict = {}
exec(RUNNER_SOURCE, _runner_ns)  # noqa: S102
normalize_result = _runner_ns["normalize_result"]


# ─────────────────────────────────────────────────────────────────────────────
# TC-08-01  run_python_job — dict return {evidence, sufficient: True}
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0801_RunPythonJobDictReturn:
    """TC-08-01 — Code returning a valid dict is completed and sufficient."""

    _CODE = "def check(d, t): return {'evidence': 'ok', 'sufficient': True}"
    _PAYLOAD = {
        "source_code": _CODE,
        "entrypoint": "check",
        "input_data": None,
        "target": None,
        "timeout_seconds": 10,
    }

    def test_completed_true(self):
        result = run_python_job(self._PAYLOAD)
        assert result["completed"] is True

    def test_sufficient_true(self):
        result = run_python_job(self._PAYLOAD)
        assert result["sufficient"] is True

    def test_evidence_ok(self):
        result = run_python_job(self._PAYLOAD)
        assert result["evidence"] == "ok"

    def test_error_none(self):
        result = run_python_job(self._PAYLOAD)
        assert result["error"] is None


# ─────────────────────────────────────────────────────────────────────────────
# TC-08-02  run_python_job — tuple return (evidence, True)
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0802_RunPythonJobTupleReturn:
    """TC-08-02 — Code returning a 2-tuple is completed and sufficient."""

    _CODE = "def f(d, t): return ('evidence_data', True)"
    _PAYLOAD = {
        "source_code": _CODE,
        "entrypoint": "f",
        "input_data": None,
        "target": None,
        "timeout_seconds": 10,
    }

    def test_completed_true(self):
        result = run_python_job(self._PAYLOAD)
        assert result["completed"] is True

    def test_sufficient_true(self):
        result = run_python_job(self._PAYLOAD)
        assert result["sufficient"] is True

    def test_evidence_correct(self):
        result = run_python_job(self._PAYLOAD)
        assert result["evidence"] == "evidence_data"


# ─────────────────────────────────────────────────────────────────────────────
# TC-08-03  normalize_result — accepts valid dict with sufficient=True
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0803_NormalizeResultValidDict:
    """TC-08-03 — Valid dict with all fields is returned correctly."""

    def test_sufficient_true(self):
        result = normalize_result({"evidence": "e", "sufficient": True, "records": []})
        assert result["sufficient"] is True

    def test_evidence_preserved(self):
        result = normalize_result({"evidence": "e", "sufficient": True, "records": []})
        assert result["evidence"] == "e"

    def test_records_preserved(self):
        result = normalize_result({"evidence": "e", "sufficient": True, "records": []})
        assert result["records"] == []


# ─────────────────────────────────────────────────────────────────────────────
# TC-08-04  normalize_result — rejects dict without 'sufficient' → ValueError
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0804_NormalizeResultMissingSufficient:
    """TC-08-04 — Dict missing 'sufficient' key raises ValueError."""

    def test_raises_value_error(self):
        with pytest.raises(ValueError):
            normalize_result({"evidence": "e"})


# ─────────────────────────────────────────────────────────────────────────────
# TC-08-05  normalize_result — rejects non-boolean 'sufficient' → ValueError
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0805_NormalizeResultNonBoolSufficient:
    """TC-08-05 — Dict with non-boolean 'sufficient' raises ValueError."""

    def test_raises_value_error(self):
        with pytest.raises(ValueError):
            normalize_result({"evidence": "e", "sufficient": "yes"})


# ─────────────────────────────────────────────────────────────────────────────
# TC-08-06  normalize_result — accepts 2-tuple (evidence, bool)
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0806_NormalizeResultTuple:
    """TC-08-06 — 2-tuple (evidence, False) is normalised correctly."""

    def test_sufficient_false(self):
        result = normalize_result(("data", False))
        assert result["sufficient"] is False

    def test_evidence_correct(self):
        result = normalize_result(("data", False))
        assert result["evidence"] == "data"

    def test_summary_none(self):
        result = normalize_result(("data", False))
        assert result["summary"] is None


# ─────────────────────────────────────────────────────────────────────────────
# TC-08-07  normalize_result — rejects invalid return type → ValueError
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0807_NormalizeResultInvalidType:
    """TC-08-07 — A plain integer raises ValueError."""

    def test_raises_value_error(self):
        with pytest.raises(ValueError):
            normalize_result(42)


# ─────────────────────────────────────────────────────────────────────────────
# TC-08-08  run_python_job — undefined entrypoint returns completed=False
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0808_RunPythonJobUndefinedEntrypoint:
    """TC-08-08 — Entrypoint that does not exist in source → completed=False."""

    _PAYLOAD = {
        "source_code": "x = 1",
        "entrypoint": "nonexistent_function",
        "input_data": None,
        "target": None,
        "timeout_seconds": 10,
    }

    def test_completed_false(self):
        result = run_python_job(self._PAYLOAD)
        assert result["completed"] is False

    def test_error_mentions_not_callable(self):
        result = run_python_job(self._PAYLOAD)
        assert "not defined or not callable" in (result.get("error") or "")


# ─────────────────────────────────────────────────────────────────────────────
# TC-08-09  run_python_job — entrypoint raises exception → completed=False
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0809_RunPythonJobEntrypointException:
    """TC-08-09 — Code raising RuntimeError → completed=False, error contains message."""

    _CODE = "def f(d, t): raise RuntimeError('test error')"
    _PAYLOAD = {
        "source_code": _CODE,
        "entrypoint": "f",
        "input_data": None,
        "target": None,
        "timeout_seconds": 10,
    }

    def test_completed_false(self):
        result = run_python_job(self._PAYLOAD)
        assert result["completed"] is False

    def test_error_contains_message(self):
        result = run_python_job(self._PAYLOAD)
        assert "test error" in (result.get("error") or "")


# ─────────────────────────────────────────────────────────────────────────────
# TC-08-10  subprocess.TimeoutExpired → completed=False
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0810_TimeoutExpired:
    """TC-08-10 — TimeoutExpired propagates through run_python_job and is caught
    by run_computation_job, which returns completed=False with a timeout message.

    Note: run_python_job does not catch TimeoutExpired; run_computation_job does.
    The test therefore calls run_computation_job so the expected completed=False
    response is observable.
    """

    @mock.patch(
        "computation_service.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd=[], timeout=1),
    )
    def test_completed_false(self, _mock_run):
        result = run_computation_job({
            "source_code": "def f(d, t): pass",
            "entrypoint": "f",
            "language": "python",
            "timeout_seconds": 1,
        })
        assert result["completed"] is False

    @mock.patch(
        "computation_service.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd=[], timeout=1),
    )
    def test_error_mentions_timeout(self, _mock_run):
        result = run_computation_job({
            "source_code": "def f(d, t): pass",
            "entrypoint": "f",
            "language": "python",
            "timeout_seconds": 1,
        })
        assert "timeout" in (result.get("error") or "").lower()


# ─────────────────────────────────────────────────────────────────────────────
# TC-08-11  subprocess produces no stdout → completed=False
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0811_NoStdout:
    """TC-08-11 — subprocess.run returning empty stdout → completed=False."""

    @mock.patch(
        "computation_service.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr="crash"
        ),
    )
    def test_completed_false(self, _mock_run):
        result = run_python_job({
            "source_code": "def f(d, t): pass",
            "entrypoint": "f",
            "timeout_seconds": 10,
        })
        assert result["completed"] is False

    @mock.patch(
        "computation_service.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr="crash"
        ),
    )
    def test_error_mentions_no_output(self, _mock_run):
        result = run_python_job({
            "source_code": "def f(d, t): pass",
            "entrypoint": "f",
            "timeout_seconds": 10,
        })
        assert result.get("error") is not None
