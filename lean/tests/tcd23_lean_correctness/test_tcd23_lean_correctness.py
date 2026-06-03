"""
TCD-23 — Lean Worker: All Entry Points — Correctness
======================================================
Module : lean/lean_service.py
Tool   : pytest (real Lean 4 compiler — no subprocess mocking)

Covered test cases
──────────────────
TC-23-01  to_compiler_snippet_response: valid snippet → valid=True, no errors, theorem_count=1
TC-23-02  to_compiler_snippet_response: invalid snippet → valid=False, errors with line info
TC-23-03  to_compiler_snippet_response: sorry proof → valid=True, message_count >= 1
TC-23-04  to_compiler_snippet_response: multi-theorem snippet → theorem_count=2
TC-23-05  to_compiler_project_response: single-file project → valid=True, no errors
TC-23-06  to_compiler_project_response: missing entry file → valid=False, error message
TC-23-07  get_mathlib_info: known Mathlib declaration → found=True, lean_source non-empty
TC-23-08  get_mathlib_info: unknown declaration → found=False, error_message non-empty
TC-23-09  get_mathlib_lineage: known declaration depth=1 → root found=True, nodes/edges present
TC-23-10  get_mathlib_lineage: unknown declaration → root found=False, no edges

Test design notes
─────────────────
TC-23-01 through TC-23-06 require only the Lean 4 executable (no Mathlib).
TC-23-07 through TC-23-10 additionally require the Mathlib build to be accessible
via the LEAN_PATH environment variable, which is set inside the lean-worker container.

The `pytestmark` skipif fires when no Lean executable is found (host without elan).
Individual Mathlib tests carry a second skipif for LEAN_PATH.

`to_compiler_snippet_response` and `to_compiler_project_response` are the
functions exposed directly to Celery tasks (`verify_snippet` and
`verify_project_files`).  They wrap `verify_lean_proof` / `verify_lean_project`
and produce the contract shape consumed by the rest of the platform.

Run with:
  docker compose cp lean/tests lean-worker:/app/tests
  docker compose exec lean-worker bash -c "pip3 install pytest --quiet && cd /app && pytest -v tests/tcd23_lean_correctness/"
"""

import os

import pytest

from lean_service import (
    find_lean_executable,
    get_mathlib_info,
    get_mathlib_lineage,
    to_compiler_project_response,
    to_compiler_snippet_response,
)

# ---------------------------------------------------------------------------
# Module-level skip when Lean is not installed
# ---------------------------------------------------------------------------

pytestmark = pytest.mark.skipif(
    find_lean_executable() is None,
    reason="Lean 4 executable not found — skipping correctness tests",
)

# Mathlib-specific tests additionally require LEAN_PATH to point to the
# pre-built Mathlib .olean files (set in the lean-worker Dockerfile).
_MATHLIB_AVAILABLE = bool(os.environ.get("LEAN_PATH") and find_lean_executable())
_MATHLIB_SKIP = pytest.mark.skipif(
    not _MATHLIB_AVAILABLE,
    reason="LEAN_PATH not set — Mathlib build not available in this environment",
)

# ---------------------------------------------------------------------------
# Fixtures / constants
# ---------------------------------------------------------------------------

SIMPLE_SNIPPET = "theorem hello : True := trivial"
INVALID_SNIPPET = "theorem bad : True := (42 : Nat)"
SORRY_SNIPPET = "theorem sorry_ex : 1 = 2 := by sorry"
MULTI_SNIPPET = "theorem alpha : True := trivial\ntheorem beta : True := trivial"

# ---------------------------------------------------------------------------
# TC-23-01 — to_compiler_snippet_response: valid snippet
# ---------------------------------------------------------------------------


def test_tc23_01_snippet_response_valid():
    """Valid snippet produces valid=True, no errors, theorem_count=1."""
    result = to_compiler_snippet_response(SIMPLE_SNIPPET)

    assert result["valid"] is True
    assert result["errors"] == []
    assert result["theorem_count"] == 1
    assert result["return_code"] == 0
    assert result["processing_time_seconds"] >= 0


# ---------------------------------------------------------------------------
# TC-23-02 — to_compiler_snippet_response: invalid snippet
# ---------------------------------------------------------------------------


def test_tc23_02_snippet_response_invalid():
    """Type mismatch produces valid=False with at least one error including line info."""
    result = to_compiler_snippet_response(INVALID_SNIPPET)

    assert result["valid"] is False
    assert len(result["errors"]) >= 1
    first_error = result["errors"][0]
    assert first_error["line"] > 0
    assert first_error["message"] != ""


# ---------------------------------------------------------------------------
# TC-23-03 — to_compiler_snippet_response: sorry proof
# ---------------------------------------------------------------------------


def test_tc23_03_snippet_response_sorry():
    """sorry produces valid=True (warning, not error) with at least one message recorded."""
    result = to_compiler_snippet_response(SORRY_SNIPPET)

    assert result["valid"] is True
    assert result["errors"] == []          # sorry is a warning, not an error
    assert result["message_count"] >= 1    # the sorry warning IS captured


# ---------------------------------------------------------------------------
# TC-23-04 — to_compiler_snippet_response: multi-theorem snippet
# ---------------------------------------------------------------------------


def test_tc23_04_snippet_response_multi_theorem():
    """Multi-theorem snippet is verified and both theorems are counted."""
    result = to_compiler_snippet_response(MULTI_SNIPPET)

    assert result["valid"] is True
    assert result["theorem_count"] == 2


# ---------------------------------------------------------------------------
# TC-23-05 — to_compiler_project_response: single-file project
# ---------------------------------------------------------------------------


def test_tc23_05_project_response_valid():
    """Single-file project with a valid theorem verifies successfully."""
    file_map = {"main.lean": SIMPLE_SNIPPET}
    result = to_compiler_project_response(file_map, "main.lean")

    assert result["valid"] is True
    assert result["errors"] == []
    assert result["return_code"] == 0


# ---------------------------------------------------------------------------
# TC-23-06 — to_compiler_project_response: missing entry file
# ---------------------------------------------------------------------------


def test_tc23_06_project_response_missing_entry_file():
    """When the declared entry file is absent from file_map, valid=False with an error."""
    file_map = {"other.lean": SIMPLE_SNIPPET}
    result = to_compiler_project_response(file_map, "main.lean")

    assert result["valid"] is False
    assert len(result["errors"]) >= 1
    assert "not found" in result["errors"][0]["message"].lower()


# ---------------------------------------------------------------------------
# TC-23-07 — get_mathlib_info: known Mathlib declaration
# ---------------------------------------------------------------------------


@_MATHLIB_SKIP
def test_tc23_07_mathlib_info_known():
    """get_mathlib_info returns found=True and non-empty lean_source for Nat.add_comm."""
    result = get_mathlib_info("Nat.add_comm")

    assert result["found"] is True
    assert result["lean_source"] != ""
    assert result["declaration_name"] == "Nat.add_comm"
    assert result["error_message"] == ""
    assert result["processing_time_seconds"] >= 0


# ---------------------------------------------------------------------------
# TC-23-08 — get_mathlib_info: unknown declaration
# ---------------------------------------------------------------------------


@_MATHLIB_SKIP
def test_tc23_08_mathlib_info_unknown():
    """get_mathlib_info returns found=False with a non-empty error_message for a fictitious name."""
    result = get_mathlib_info("Fake.NonExistent.Declaration99999")

    assert result["found"] is False
    assert result["error_message"] != ""
    assert result["declaration_name"] == "Fake.NonExistent.Declaration99999"


# ---------------------------------------------------------------------------
# TC-23-09 — get_mathlib_lineage: known declaration at depth=1
# ---------------------------------------------------------------------------


@_MATHLIB_SKIP
def test_tc23_09_mathlib_lineage_known():
    """Lineage for Nat.add_comm at depth=1: root is found, edges list is present."""
    result = get_mathlib_lineage("Nat.add_comm", depth=1)

    assert result["root"] == "Nat.add_comm"
    assert result["total_nodes"] >= 1
    assert isinstance(result["edges"], list)
    assert result["processing_time_seconds"] >= 0

    root_node = next(n for n in result["nodes"] if n["name"] == "Nat.add_comm")
    assert root_node["found"] is True
    assert root_node["depth_level"] == 0


# ---------------------------------------------------------------------------
# TC-23-10 — get_mathlib_lineage: unknown declaration
# ---------------------------------------------------------------------------


@_MATHLIB_SKIP
def test_tc23_10_mathlib_lineage_unknown():
    """Lineage for a fictitious name: root node is present but found=False, no outgoing edges."""
    result = get_mathlib_lineage("Fake.NonExistent.Declaration99999", depth=1)

    assert result["root"] == "Fake.NonExistent.Declaration99999"
    assert result["total_nodes"] >= 1

    root_node = next(n for n in result["nodes"] if n["name"] == "Fake.NonExistent.Declaration99999")
    assert root_node["found"] is False
    # An undiscovered root can have no edges
    assert result["edges"] == []
