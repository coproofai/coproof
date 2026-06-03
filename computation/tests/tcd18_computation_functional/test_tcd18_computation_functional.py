"""
TCD-18 — Computation Worker: Functional Execution
===================================================
Module : computation/computation_service.py
Tool   : pytest (real Python subprocess — no mocking)

Covered test cases
──────────────────
TC-18-01  Valid computation returns completed=True and correct evidence
TC-18-02  Computation returning sufficient=False is correctly relayed
TC-18-03  Entrypoint exception yields completed=False with error message
TC-18-04  Infinite-loop entrypoint is terminated by timeout_seconds
TC-18-05  Unsupported language returns completed=False immediately

Test design notes
─────────────────
All tests call `run_computation_job()` directly — no Celery broker, no
patching of `subprocess.run`.  The function spawns a real child
`python runner.py` process in a `tempfile.TemporaryDirectory`.

TC-18-04 uses `timeout_seconds=2` with a busy-loop entrypoint.  The sandbox
runner is terminated via `subprocess.TimeoutExpired`; `run_computation_job`
catches this and injects a "timeout" error string.  The test is marked with
`@pytest.mark.timeout(8)` (requires pytest-timeout) as a safety net; if
pytest-timeout is not installed the mark is ignored harmlessly.

TC-18-05 exercises the early-return branch — no subprocess is spawned so it
returns immediately regardless of the host environment.

Run with:
  cd computation
  pytest -v tests/tcd18_computation_functional/
"""

import pytest

from computation_service import run_computation_job

# ---------------------------------------------------------------------------
# TC-18-01 — Valid computation returns completed=True and correct evidence
# ---------------------------------------------------------------------------


def test_tc18_01_valid_computation():
    """A correctly implemented entrypoint returns completed=True with evidence."""
    result = run_computation_job({
        "source_code": "def compute(data, target):\n    return (42, True)",
        "entrypoint": "compute",
        "input_data": None,
        "target": None,
    })

    assert result["completed"] is True
    assert result["sufficient"] is True
    assert result["evidence"] == 42
    assert result["error"] is None


# ---------------------------------------------------------------------------
# TC-18-02 — Computation returning sufficient=False is correctly relayed
# ---------------------------------------------------------------------------


def test_tc18_02_insufficient_evidence():
    """An entrypoint returning sufficient=False is relayed without modification."""
    result = run_computation_job({
        "source_code": 'def compute(data, target):\n    return ("no evidence", False)',
        "entrypoint": "compute",
        "input_data": None,
        "target": None,
    })

    assert result["completed"] is True
    assert result["sufficient"] is False
    assert result["evidence"] == "no evidence"


# ---------------------------------------------------------------------------
# TC-18-03 — Entrypoint exception yields completed=False with error message
# ---------------------------------------------------------------------------


def test_tc18_03_entrypoint_exception():
    """An exception raised inside the entrypoint is caught and reported."""
    result = run_computation_job({
        "source_code": 'def compute(data, target):\n    raise ValueError("intentional failure")',
        "entrypoint": "compute",
        "input_data": None,
        "target": None,
    })

    assert result["completed"] is False
    assert result["sufficient"] is False
    assert result["error"] is not None
    assert "intentional failure" in result["error"]


# ---------------------------------------------------------------------------
# TC-18-04 — Infinite-loop entrypoint is terminated by timeout_seconds
# ---------------------------------------------------------------------------


@pytest.mark.timeout(8)
def test_tc18_04_timeout():
    """An infinite-loop entrypoint is killed after timeout_seconds and returns completed=False."""
    result = run_computation_job({
        "source_code": "def compute(data, target):\n    while True: pass",
        "entrypoint": "compute",
        "input_data": None,
        "target": None,
        "timeout_seconds": 2,
    })

    assert result["completed"] is False
    assert result["error"] is not None
    assert "timeout" in result["error"].lower()


# ---------------------------------------------------------------------------
# TC-18-05 — Unsupported language returns completed=False immediately
# ---------------------------------------------------------------------------


def test_tc18_05_unsupported_language():
    """Passing an unsupported language triggers the early-return branch without spawning a process."""
    result = run_computation_job({
        "language": "julia",
        "source_code": "...",
        "entrypoint": "compute",
    })

    assert result["completed"] is False
    assert result["error"] is not None
    assert "Unsupported" in result["error"]


# ---------------------------------------------------------------------------
# TC-18-06 — register_record() accumulates per-case evidence in records
# ---------------------------------------------------------------------------


def test_tc18_06_register_record():
    """register_record() calls inside user code produce entries in result['records']."""
    code = (
        "def compute(data, target):\n"
        "    for n in range(1, 4):\n"
        "        register_record(n=n, square=n*n)\n"
        "    return {'evidence': 'done', 'sufficient': True, 'records': []}\n"
    )
    result = run_computation_job({
        "source_code": code,
        "entrypoint": "compute",
        "input_data": None,
        "target": None,
    })

    assert result["completed"] is True
    records = result.get("records", [])
    assert len(records) == 3
    assert records[0] == {"n": 1, "square": 1}
    assert records[1] == {"n": 2, "square": 4}
    assert records[2] == {"n": 3, "square": 9}


# ---------------------------------------------------------------------------
# TC-18-07 — register_record() merges with explicitly returned records
# ---------------------------------------------------------------------------


def test_tc18_07_register_record_merged_with_returned_records():
    """register_record() calls are prepended to any records returned in the dict."""
    code = (
        "def compute(data, target):\n"
        "    register_record(step='before')\n"
        "    return {'evidence': 'ok', 'sufficient': True, 'records': [{'step': 'returned'}]}\n"
    )
    result = run_computation_job({
        "source_code": code,
        "entrypoint": "compute",
        "input_data": None,
        "target": None,
    })

    assert result["completed"] is True
    records = result.get("records", [])
    assert len(records) == 2
    assert records[0] == {"step": "before"}
    assert records[1] == {"step": "returned"}


# ---------------------------------------------------------------------------
# TC-18-08 — register_record() records are preserved on exception
# ---------------------------------------------------------------------------


def test_tc18_08_register_record_preserved_on_exception():
    """Records collected before an exception are returned in the error result."""
    code = (
        "def compute(data, target):\n"
        "    register_record(n=1)\n"
        "    register_record(n=2)\n"
        "    raise RuntimeError('abort')\n"
    )
    result = run_computation_job({
        "source_code": code,
        "entrypoint": "compute",
        "input_data": None,
        "target": None,
    })

    assert result["completed"] is False
    records = result.get("records", [])
    assert len(records) == 2
    assert records[0] == {"n": 1}
    assert records[1] == {"n": 2}

