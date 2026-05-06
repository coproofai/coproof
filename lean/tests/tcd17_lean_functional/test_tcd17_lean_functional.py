"""
TCD-17 — Lean Worker: Functional Verification
===============================================
Module : lean/lean_service.py
Tool   : pytest (real Lean 4 compiler — no subprocess mocking)

Covered test cases
──────────────────
TC-17-01  Valid trivial theorem verifies successfully
TC-17-02  Theorem using `sorry` compiles but emits a warning
TC-17-03  Code with a type mismatch returns verified=False with error diagnostics
TC-17-04  Multi-theorem snippet: all declarations are detected
TC-17-05  Response dict always contains all required keys

Test design notes
─────────────────
All tests invoke `verify_lean_proof()` directly — no Celery broker, no
patching of `subprocess.run`.  Lean 4 must be reachable via `find_lean_executable()`.

All snippets are `import Mathlib`-free (stdlib/builtin only) so each call
completes in < 5 s on a machine where the Lean executable is already
installed via `elan`.

The `lean_available` autouse fixture skips every test in this module when
the Lean 4 binary cannot be found, so the suite stays green on developer
machines that do not have `elan` installed.

Run with:
  cd lean
  pytest -v tests/tcd17_lean_functional/
"""

import pytest

from lean_service import find_lean_executable, verify_lean_proof

# ---------------------------------------------------------------------------
# Module-level skip when Lean is not installed
# ---------------------------------------------------------------------------

pytestmark = pytest.mark.skipif(
    find_lean_executable() is None,
    reason="Lean 4 executable not found — skipping functional tests",
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REQUIRED_KEYS = {"verified", "returnCode", "theorems", "messages", "feedback", "processingTimeSeconds"}
REQUIRED_FEEDBACK_KEYS = {"stdout", "stderr"}


# ---------------------------------------------------------------------------
# TC-17-01 — Valid trivial theorem verifies successfully
# ---------------------------------------------------------------------------


def test_tc17_01_valid_theorem():
    """verify_lean_proof returns verified=True for a trivially correct theorem."""
    result = verify_lean_proof("theorem hello : True := trivial")

    assert result["verified"] is True
    assert result["returnCode"] == 0

    names = [t["name"] for t in result["theorems"]]
    assert "hello" in names


# ---------------------------------------------------------------------------
# TC-17-02 — Theorem using `sorry` compiles but emits a warning
# ---------------------------------------------------------------------------


def test_tc17_02_sorry_warning():
    """sorry tactic compiles (returnCode 0) but produces a sorry-related warning."""
    result = verify_lean_proof("theorem sorry_ex : 1 = 2 := by sorry")

    assert result["verified"] is True
    assert result["returnCode"] == 0

    sorry_warnings = [
        m for m in result["messages"]
        if m.get("severity") == "warning" and "sorry" in m.get("message", "").lower()
    ]
    assert len(sorry_warnings) >= 1, (
        "Expected at least one warning mentioning 'sorry', got: " + str(result["messages"])
    )


# ---------------------------------------------------------------------------
# TC-17-03 — Type mismatch returns verified=False with error diagnostics
# ---------------------------------------------------------------------------


def test_tc17_03_type_mismatch():
    """A type mismatch causes verification failure with at least one error diagnostic."""
    result = verify_lean_proof("theorem bad : True := (42 : Nat)")

    assert result["verified"] is False
    assert result["returnCode"] != 0

    error_msgs = [m for m in result["messages"] if m.get("severity") == "error"]
    assert len(error_msgs) >= 1, (
        "Expected at least one error diagnostic, got: " + str(result["messages"])
    )


# ---------------------------------------------------------------------------
# TC-17-04 — Multi-theorem snippet: all declarations are detected
# ---------------------------------------------------------------------------


def test_tc17_04_multi_theorem_detection():
    """parse_theorem_info detects all theorem declarations in a multi-theorem snippet."""
    snippet = (
        "theorem alpha : True := trivial\n"
        "theorem beta : True := trivial\n"
    )
    result = verify_lean_proof(snippet)

    assert result["verified"] is True

    names = [t["name"] for t in result["theorems"]]
    assert len(names) == 2
    assert names[0] == "alpha"
    assert names[1] == "beta"


# ---------------------------------------------------------------------------
# TC-17-05 — Response dict always contains all required keys
# ---------------------------------------------------------------------------


def test_tc17_05_response_shape():
    """verify_lean_proof always returns a dict with all documented keys."""
    result = verify_lean_proof("theorem hello : True := trivial")

    assert isinstance(result, dict)
    assert REQUIRED_KEYS.issubset(result.keys()), (
        "Missing keys: " + str(REQUIRED_KEYS - result.keys())
    )
    assert isinstance(result["feedback"], dict)
    assert REQUIRED_FEEDBACK_KEYS.issubset(result["feedback"].keys()), (
        "Missing feedback keys: " + str(REQUIRED_FEEDBACK_KEYS - result["feedback"].keys())
    )
    assert isinstance(result["processingTimeSeconds"], float)
    assert result["processingTimeSeconds"] >= 0
