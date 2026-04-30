"""
TCD-07 — Lean Worker
=====================
Module : lean/lean_service.py
Responsible : Daniel
Tools : pytest, pytest-mock

Covered test cases
──────────────────
TC-07-01  parse_theorem_info detects `theorem` declaration
TC-07-02  parse_theorem_info detects `lemma` declaration
TC-07-03  parse_theorem_info detects `def` declaration
TC-07-04  parse_theorem_info returns [] for code with no declarations
TC-07-05  parse_theorem_info detects multiple declarations
TC-07-06  parse_lean_messages extracts an error from compiler output
TC-07-07  parse_lean_messages extracts a warning
TC-07-08  parse_lean_messages returns [] when output has no diagnostics
TC-07-09  verify_lean_proof returns error when Lean executable not found
TC-07-10  verify_lean_proof returns verified=True for valid code (mocked subprocess)
TC-07-11  verify_lean_proof returns verified=False with messages for invalid code
TC-07-12  verify_lean_proof handles subprocess.TimeoutExpired
TC-07-13  find_lean_executable returns path when Lean is installed
TC-07-14  find_lean_executable returns None when no Lean binary exists

Test design notes
─────────────────
lean_service.py is pure Python — no Flask app context and no database.
All tests import directly from `lean_service`.

subprocess.run is patched at `lean_service.subprocess.run` because
lean_service imports the `subprocess` module and calls `subprocess.run`.

For TC-07-10/11/12: `find_lean_executable` is also patched to return `"lean"`
so that `verify_lean_proof` does not attempt a real `subprocess.run` call for
`--version` before reaching the code we want to exercise.

For TC-07-12: `subprocess.TimeoutExpired` requires a `cmd` and `timeout`
argument; the test supplies `cmd=[]` and `timeout=60`.

For TC-07-14: both `subprocess.run` (raising `FileNotFoundError`) and
`os.path.exists` (returning `False`) must be patched so that neither the
command-lookup branch nor the filesystem-path branch can return a result.

Run with:
  cd lean
  pytest -v tests/tcd07_lean_worker/test_tcd07_lean_service.py
"""

import subprocess
import unittest.mock as mock

import pytest

from lean_service import (
    find_lean_executable,
    parse_lean_messages,
    parse_theorem_info,
    verify_lean_proof,
)


# ─────────────────────────────────────────────────────────────────────────────
# TC-07-01  parse_theorem_info — detects `theorem` declaration
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0701_ParseTheoremInfoTheorem:
    """TC-07-01 — A single `theorem` declaration is detected correctly."""

    def test_detects_theorem(self):
        result = parse_theorem_info("theorem myTheorem : 1 + 1 = 2 := by norm_num")
        assert len(result) == 1
        entry = result[0]
        assert entry["name"] == "myTheorem"
        assert entry["type"] == "theorem"
        assert entry["line"] == 1


# ─────────────────────────────────────────────────────────────────────────────
# TC-07-02  parse_theorem_info — detects `lemma` declaration
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0702_ParseTheoremInfoLemma:
    """TC-07-02 — A `lemma` declaration is detected and typed correctly."""

    def test_detects_lemma(self):
        result = parse_theorem_info("lemma myLemma : True := trivial")
        assert len(result) == 1
        assert result[0]["type"] == "lemma"
        assert result[0]["name"] == "myLemma"


# ─────────────────────────────────────────────────────────────────────────────
# TC-07-03  parse_theorem_info — detects `def` declaration
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0703_ParseTheoremInfoDef:
    """TC-07-03 — A `def` declaration is detected and typed correctly."""

    def test_detects_def(self):
        result = parse_theorem_info("def myDef : Nat := 42")
        assert len(result) == 1
        assert result[0]["type"] == "def"
        assert result[0]["name"] == "myDef"


# ─────────────────────────────────────────────────────────────────────────────
# TC-07-04  parse_theorem_info — returns [] for code with no declarations
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0704_ParseTheoremInfoNoDeclarations:
    """TC-07-04 — Pure comments / check commands produce an empty list."""

    def test_returns_empty_list(self):
        result = parse_theorem_info("-- just a comment\n#check Nat")
        assert result == []


# ─────────────────────────────────────────────────────────────────────────────
# TC-07-05  parse_theorem_info — detects multiple declarations
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0705_ParseTheoremInfoMultiple:
    """TC-07-05 — Two declarations are detected at the correct line numbers."""

    def test_detects_two_declarations(self):
        code = (
            "theorem t1 : True := trivial\n"
            "\n"
            "\n"
            "\n"
            "lemma l1 : True := trivial"
        )
        result = parse_theorem_info(code)
        assert len(result) == 2

    def test_line_numbers_are_correct(self):
        code = (
            "theorem t1 : True := trivial\n"
            "\n"
            "\n"
            "\n"
            "lemma l1 : True := trivial"
        )
        result = parse_theorem_info(code)
        lines = {e["name"]: e["line"] for e in result}
        assert lines["t1"] == 1
        assert lines["l1"] == 5


# ─────────────────────────────────────────────────────────────────────────────
# TC-07-06  parse_lean_messages — extracts an error from compiler output
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0706_ParseLeanMessagesError:
    """TC-07-06 — A compiler error line is parsed into a structured message."""

    def test_extracts_error(self):
        result = parse_lean_messages(
            stdout="",
            stderr="proof.lean:3:5: error: unknown identifier 'x'",
            filename="proof.lean",
        )
        assert len(result) == 1
        msg = result[0]
        assert msg["line"] == 3
        assert msg["column"] == 5
        assert msg["severity"] == "error"
        assert "unknown identifier" in msg["message"]


# ─────────────────────────────────────────────────────────────────────────────
# TC-07-07  parse_lean_messages — extracts a warning
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0707_ParseLeanMessagesWarning:
    """TC-07-07 — A compiler warning line is parsed with severity=warning."""

    def test_extracts_warning(self):
        result = parse_lean_messages(
            stdout="",
            stderr="proof.lean:2:1: warning: declaration uses 'sorry'",
            filename="proof.lean",
        )
        assert len(result) == 1
        assert result[0]["severity"] == "warning"


# ─────────────────────────────────────────────────────────────────────────────
# TC-07-08  parse_lean_messages — returns [] when output has no diagnostics
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0708_ParseLeanMessagesEmpty:
    """TC-07-08 — Empty stdout and stderr produce an empty messages list."""

    def test_returns_empty_list(self):
        assert parse_lean_messages(stdout="", stderr="", filename="proof.lean") == []


# ─────────────────────────────────────────────────────────────────────────────
# TC-07-09  verify_lean_proof — Lean executable not found
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0709_VerifyLeanProofNoExecutable:
    """TC-07-09 — When find_lean_executable returns None, verified=False is returned."""

    @mock.patch("lean_service.find_lean_executable", return_value=None)
    def test_returns_verified_false(self, _mock):
        result = verify_lean_proof("theorem t : True := trivial")
        assert result["verified"] is False

    @mock.patch("lean_service.find_lean_executable", return_value=None)
    def test_return_code_is_minus_one(self, _mock):
        result = verify_lean_proof("theorem t : True := trivial")
        assert result["returnCode"] == -1

    @mock.patch("lean_service.find_lean_executable", return_value=None)
    def test_messages_mention_not_found(self, _mock):
        result = verify_lean_proof("theorem t : True := trivial")
        assert any("Lean" in m.get("message", "") for m in result["messages"])


# ─────────────────────────────────────────────────────────────────────────────
# TC-07-10  verify_lean_proof — verified=True for valid code (subprocess mocked)
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0710_VerifyLeanProofValid:
    """TC-07-10 — returncode=0 from subprocess → verified=True, messages=[]."""

    @mock.patch("lean_service.find_lean_executable", return_value="lean")
    @mock.patch(
        "lean_service.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=["lean"], returncode=0, stdout="", stderr=""
        ),
    )
    def test_verified_true(self, _mock_run, _mock_find):
        result = verify_lean_proof("theorem t : True := trivial")
        assert result["verified"] is True

    @mock.patch("lean_service.find_lean_executable", return_value="lean")
    @mock.patch(
        "lean_service.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=["lean"], returncode=0, stdout="", stderr=""
        ),
    )
    def test_return_code_zero(self, _mock_run, _mock_find):
        result = verify_lean_proof("theorem t : True := trivial")
        assert result["returnCode"] == 0

    @mock.patch("lean_service.find_lean_executable", return_value="lean")
    @mock.patch(
        "lean_service.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=["lean"], returncode=0, stdout="", stderr=""
        ),
    )
    def test_messages_empty(self, _mock_run, _mock_find):
        result = verify_lean_proof("theorem t : True := trivial")
        assert result["messages"] == []


# ─────────────────────────────────────────────────────────────────────────────
# TC-07-11  verify_lean_proof — verified=False with messages for invalid code
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0711_VerifyLeanProofInvalid:
    """TC-07-11 — returncode=1 with stderr → verified=False, non-empty messages."""

    @mock.patch("lean_service.find_lean_executable", return_value="lean")
    @mock.patch(
        "lean_service.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=["lean"],
            returncode=1,
            stdout="",
            stderr="proof.lean:1:0: error: type mismatch",
        ),
    )
    def test_verified_false(self, _mock_run, _mock_find):
        result = verify_lean_proof("theorem bad : 1 = 2 := rfl")
        assert result["verified"] is False

    @mock.patch("lean_service.find_lean_executable", return_value="lean")
    @mock.patch(
        "lean_service.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=["lean"],
            returncode=1,
            stdout="",
            stderr="proof.lean:1:0: error: type mismatch",
        ),
    )
    def test_messages_non_empty(self, _mock_run, _mock_find):
        result = verify_lean_proof("theorem bad : 1 = 2 := rfl")
        assert len(result["messages"]) > 0

    @mock.patch("lean_service.find_lean_executable", return_value="lean")
    @mock.patch(
        "lean_service.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=["lean"],
            returncode=1,
            stdout="",
            stderr="proof.lean:1:0: error: type mismatch",
        ),
    )
    def test_message_has_required_fields(self, _mock_run, _mock_find):
        result = verify_lean_proof("theorem bad : 1 = 2 := rfl")
        msg = result["messages"][0]
        assert "severity" in msg
        assert "line" in msg
        assert "column" in msg


# ─────────────────────────────────────────────────────────────────────────────
# TC-07-12  verify_lean_proof — handles subprocess.TimeoutExpired
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0712_VerifyLeanProofTimeout:
    """TC-07-12 — TimeoutExpired → verified=False, timeout message in messages."""

    @mock.patch("lean_service.find_lean_executable", return_value="lean")
    @mock.patch(
        "lean_service.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd=[], timeout=60),
    )
    def test_verified_false(self, _mock_run, _mock_find):
        result = verify_lean_proof("theorem t : True := trivial")
        assert result["verified"] is False

    @mock.patch("lean_service.find_lean_executable", return_value="lean")
    @mock.patch(
        "lean_service.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd=[], timeout=60),
    )
    def test_return_code_minus_one(self, _mock_run, _mock_find):
        result = verify_lean_proof("theorem t : True := trivial")
        assert result["returnCode"] == -1

    @mock.patch("lean_service.find_lean_executable", return_value="lean")
    @mock.patch(
        "lean_service.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd=[], timeout=60),
    )
    def test_message_mentions_timeout(self, _mock_run, _mock_find):
        result = verify_lean_proof("theorem t : True := trivial")
        messages_text = " ".join(m.get("message", "") for m in result["messages"])
        assert "timeout" in messages_text.lower() or "60" in messages_text


# ─────────────────────────────────────────────────────────────────────────────
# TC-07-13  find_lean_executable — returns path when Lean is installed
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0713_FindLeanExecutableFound:
    """TC-07-13 — subprocess returns returncode=0 for `lean --version` → returns `"lean"`."""

    @mock.patch(
        "lean_service.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=["lean", "--version"], returncode=0, stdout="Lean 4.x", stderr=""
        ),
    )
    def test_returns_lean_command(self, _mock_run):
        result = find_lean_executable()
        assert result == "lean"


# ─────────────────────────────────────────────────────────────────────────────
# TC-07-14  find_lean_executable — returns None when no Lean binary exists
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0714_FindLeanExecutableNotFound:
    """TC-07-14 — FileNotFoundError for all commands + os.path.exists=False → None."""

    @mock.patch("lean_service.os.path.exists", return_value=False)
    @mock.patch(
        "lean_service.subprocess.run",
        side_effect=FileNotFoundError,
    )
    def test_returns_none(self, _mock_run, _mock_exists):
        result = find_lean_executable()
        assert result is None

