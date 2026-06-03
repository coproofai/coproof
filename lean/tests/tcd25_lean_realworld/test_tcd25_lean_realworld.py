"""
TCD-25 — Lean Worker: Real-World Mathlib Scenario Tests
========================================================
Module : lean/lean_service.py (verify_lean_proof, to_compiler_snippet_response)
Data   : Lean 4 + Mathlib snippets derived from real Mathlib theorem patterns
         (mirroring complexity of lean/benchmark/val.json entries)

Covered test cases
──────────────────
TC-25-01  Benchmark: Mathlib snippet — Nat arithmetic (baseline with import Mathlib)
TC-25-02  Sequential: 10 real-world Mathlib snippets — all succeed, print latency table
TC-25-03  Concurrent: 4 workers × 10 calls — speedup vs sequential baseline
TC-25-04  Concurrent: 8 workers × 20 calls — throughput at higher parallelism
TC-25-05  Mixed validity: 8 valid + 2 intentionally-invalid Mathlib snippets

Test design notes
─────────────────
All snippets use `import Mathlib` (real-world usage pattern).  Lean loads the
pre-built .olean files from /tmp/mathlib4, so each call costs ~5–15 s.

Metric visibility:
  pytest captures stdout by default.  To see the full timing tables pass -s:
    pytest -v -s tests/tcd25_lean_realworld/
  Timing is also printed to stderr (visible without -s in most CI pipelines).

Run (inside lean-worker container):
  docker compose cp lean/tests lean-worker:/app/tests
  docker compose exec lean-worker bash -c \\
    "pip3 install pytest pytest-benchmark --quiet && \\
     cd /app && pytest -v -s tests/tcd25_lean_realworld/ --benchmark-sort=mean"

Skips:
  All tests are skipped when LEAN_PATH is not set (Mathlib build not available).
"""

import concurrent.futures
import os
import statistics
import sys
import time

import pytest

from lean_service import find_lean_executable, to_compiler_snippet_response, verify_lean_proof

# ---------------------------------------------------------------------------
# Module-level skip: require both Lean and Mathlib build
# ---------------------------------------------------------------------------

_MATHLIB_AVAILABLE = bool(os.environ.get("LEAN_PATH") and find_lean_executable())

pytestmark = pytest.mark.skipif(
    not _MATHLIB_AVAILABLE,
    reason="LEAN_PATH not set or Lean not found — Mathlib build unavailable",
)

# ---------------------------------------------------------------------------
# Real-world Mathlib snippets
# ---------------------------------------------------------------------------
# Each snippet is a self-contained Lean 4 file that:
#   1. Imports Mathlib (real-world dependency)
#   2. Proves a novel theorem using Mathlib types/tactics
#   3. Mirrors a category of theorem found in lean/benchmark/val.json
#
# Categories covered (matching val.json distribution):
#   NAT  — Nat arithmetic       (mirrors: Nat.bit1_eq_bit1, Nat.add_comm)
#   LIST — List operations      (mirrors: List.findIdx_le_length)
#   INT  — Integer arithmetic   (mirrors: Int-based theorems)
#   POLY — Polynomial algebra   (mirrors: Polynomial.eval₂_ofFinsupp)
#   SET  — Set operations       (mirrors: isPiSystem_Ioc_mem, Set.inter_comm)
#   RING — Ring/field algebra   (mirrors: Algebra.Polynomial.Monic theorems)
#   BOOL — Boolean algebra      (mirrors: Bool-related Nat.bit theorems)
#   FIN  — Finset operations    (mirrors: measure-theory membership theorems)
#   ORD  — Order theory         (mirrors: le/lt theorems)
#   REAL — Real number analysis (mirrors: Real.diam_Ioc, intervalIntegral)

MATHLIB_SNIPPETS: list[dict] = [
    {
        "id": "NAT-01",
        "category": "Nat arithmetic",
        "description": "zero_add via Mathlib lemma",
        "code": (
            "import Mathlib\n"
            "theorem custom_nat_zero_add (n : ℕ) : 0 + n = n := Nat.zero_add n"
        ),
        "expect_valid": True,
    },
    {
        "id": "NAT-02",
        "category": "Nat arithmetic",
        "description": "succ_ne_zero — mirrors Nat.bit1_eq_bit1 complexity",
        "code": (
            "import Mathlib\n"
            "theorem custom_nat_succ_ne_zero (n : ℕ) : n.succ ≠ 0 := Nat.succ_ne_zero n"
        ),
        "expect_valid": True,
    },
    {
        "id": "LIST-01",
        "category": "List operations",
        "description": "empty list length — mirrors List.findIdx_le_length style",
        "code": (
            "import Mathlib\n"
            "theorem custom_list_nil_length : ([] : List ℕ).length = 0 := rfl"
        ),
        "expect_valid": True,
    },
    {
        "id": "LIST-02",
        "category": "List operations",
        "description": "singleton reverse — tactic-style proof",
        "code": (
            "import Mathlib\n"
            "theorem custom_list_reverse_reverse (xs : List ℕ) :\n"
            "    xs.reverse.reverse = xs := List.reverse_reverse xs"
        ),
        "expect_valid": True,
    },
    {
        "id": "INT-01",
        "category": "Integer arithmetic",
        "description": "add_neg_cancel — mirrors Int negation pattern",
        "code": (
            "import Mathlib\n"
            "theorem custom_int_add_neg_self (n : ℤ) : n + (-n) = 0 := by ring"
        ),
        "expect_valid": True,
    },
    {
        "id": "RING-01",
        "category": "Ring algebra",
        "description": "zero_mul — mirrors monic polynomial lemma style",
        "code": (
            "import Mathlib\n"
            "theorem custom_ring_zero_mul (R : Type) [Ring R] (a : R) : 0 * a = 0 :=\n"
            "  zero_mul a"
        ),
        "expect_valid": True,
    },
    {
        "id": "SET-01",
        "category": "Set operations",
        "description": "inter_comm — mirrors isPiSystem_Ioc_mem set style",
        "code": (
            "import Mathlib\n"
            "theorem custom_set_inter_comm (s t : Set ℕ) : s ∩ t = t ∩ s :=\n"
            "  Set.inter_comm s t"
        ),
        "expect_valid": True,
    },
    {
        "id": "FIN-01",
        "category": "Finset membership",
        "description": "mem_insert_self — mirrors MeasureTheory membership style",
        "code": (
            "import Mathlib\n"
            "theorem custom_finset_insert_self (a : ℕ) (s : Finset ℕ) :\n"
            "    a ∈ insert a s := Finset.mem_insert_self a s"
        ),
        "expect_valid": True,
    },
    {
        "id": "ORD-01",
        "category": "Order theory",
        "description": "invalid proof — wrong direction of le_antisymm",
        "code": (
            "import Mathlib\n"
            "-- Intentionally invalid: conclusion should be a = b, not a > b\n"
            "theorem custom_invalid_order (a b : ℕ) (h1 : a ≤ b) (h2 : b ≤ a) : a > b :=\n"
            "  Nat.le_antisymm h1 h2"
        ),
        "expect_valid": False,
    },
    {
        "id": "REAL-01",
        "category": "Real analysis — invalid",
        "description": "invalid proof — false equation x + 1 = x, ring cannot close",
        "code": (
            "import Mathlib\n"
            "-- Intentionally invalid: x + 1 = x is false in ℝ\n"
            "theorem custom_real_false (x : ℝ) : x + 1 = x := by ring"
        ),
        "expect_valid": False,
    },
]

# Separate valid/invalid for easy indexing
VALID_SNIPPETS = [s for s in MATHLIB_SNIPPETS if s["expect_valid"]]
INVALID_SNIPPETS = [s for s in MATHLIB_SNIPPETS if not s["expect_valid"]]


def _fmt_table(rows: list[tuple], headers: tuple) -> str:
    """Format a list of tuples as a plain-text table."""
    col_widths = [max(len(str(r[i])) for r in [headers] + rows) for i in range(len(headers))]
    sep = "  ".join("-" * w for w in col_widths)
    header_line = "  ".join(str(h).ljust(col_widths[i]) for i, h in enumerate(headers))
    rows_lines = [
        "  ".join(str(c).ljust(col_widths[i]) for i, c in enumerate(row)) for row in rows
    ]
    return "\n".join(["", header_line, sep] + rows_lines + [""])


# ---------------------------------------------------------------------------
# TC-25-01 — Benchmark: Mathlib snippet — Nat arithmetic
# ---------------------------------------------------------------------------


def test_tc25_01_bench_mathlib_nat_arithmetic(benchmark):
    """Benchmark latency for a single Mathlib-import snippet (import Mathlib overhead).

    Uses pytest-benchmark for statistical measurement (min/max/mean/stddev).
    This is the Mathlib-variant baseline — compare against TC-24-01 (~100 ms)
    to observe the `import Mathlib` load overhead.
    """
    code = MATHLIB_SNIPPETS[0]["code"]  # NAT-01

    result = benchmark.pedantic(
        to_compiler_snippet_response,
        args=(code,),
        iterations=1,
        rounds=3,
    )
    assert result["valid"] is True, f"NAT-01 should verify.\nErrors: {result.get('errors')}"

    benchmark.extra_info["snippet_id"] = "NAT-01"
    benchmark.extra_info["import_mathlib"] = True


# ---------------------------------------------------------------------------
# TC-25-02 — Sequential: 10 real-world Mathlib snippets with latency table
# ---------------------------------------------------------------------------


def test_tc25_02_sequential_all_snippets():
    """Run all 10 snippets sequentially; assert expected outcomes; print latency table.

    Each snippet uses `import Mathlib`. Timings are printed to stderr so they
    appear in CI logs without requiring the -s flag.

    Expected outcomes per snippet:
        NAT-01  valid   NAT-02  valid   LIST-01 valid   LIST-02 valid
        INT-01  valid   RING-01 valid   SET-01  valid   FIN-01  valid
        ORD-01  invalid (wrong conclusion type)
        REAL-01 invalid (false equation: x + 1 = x, ring fails)
    """
    rows = []
    latencies: list[float] = []

    for snippet in MATHLIB_SNIPPETS:
        t0 = time.perf_counter()
        result = to_compiler_snippet_response(snippet["code"])
        elapsed = time.perf_counter() - t0

        actual_valid = result.get("valid", False)
        expected_valid = snippet["expect_valid"]
        status = "PASS" if actual_valid == expected_valid else "FAIL"

        rows.append((
            snippet["id"],
            snippet["category"][:28],
            f"{elapsed:.2f}s",
            "valid" if actual_valid else "invalid",
            "valid" if expected_valid else "invalid",
            status,
        ))

        if expected_valid:
            latencies.append(elapsed)

        assert actual_valid == expected_valid, (
            f"Snippet {snippet['id']}: expected valid={expected_valid}, "
            f"got valid={actual_valid}.\nErrors: {result.get('errors')}"
        )

    # Stats for valid snippets only
    headers = ("ID", "Category", "Time", "Got", "Expect", "Status")
    table = _fmt_table(rows, headers)

    if latencies:
        mean_t = statistics.mean(latencies)
        median_t = statistics.median(latencies)
        p95_t = sorted(latencies)[int(0.95 * len(latencies)) - 1]
        stats_line = (
            f"Valid-snippet stats: n={len(latencies)}, "
            f"mean={mean_t:.2f}s, median={median_t:.2f}s, p95={p95_t:.2f}s, "
            f"total={sum(latencies):.2f}s"
        )
    else:
        stats_line = "No valid snippets timed."

    summary = (
        f"\n{'='*72}\n"
        f"TC-25-02 Sequential Results\n"
        f"{table}"
        f"{stats_line}\n"
        f"{'='*72}"
    )
    print(summary, file=sys.stderr)


# ---------------------------------------------------------------------------
# TC-25-03 — Concurrent: 4 workers × 10 valid snippets vs sequential baseline
# ---------------------------------------------------------------------------


def test_tc25_03_concurrent_4workers_10calls():
    """4 ThreadPoolExecutor workers, 10 concurrent Mathlib snippet verifications.

    Submits all 10 valid snippets at once (cycling through them) across 4 workers.
    Asserts all return valid=True.  Prints wall-clock and effective throughput to
    stderr for comparison with TC-25-02 sequential baseline.

    Expected behaviour:
      - Speedup ≥ 1.5× vs sequential wall-clock (environment-dependent)
      - All 10 results valid=True
    """
    n_workers = 4
    calls = [s["code"] for s in (VALID_SNIPPETS * 2)[:10]]  # cycle up to 10 calls

    # Sequential baseline (1 call to estimate per-call time without startup)
    t_seq_start = time.perf_counter()
    _baseline = to_compiler_snippet_response(calls[0])
    t_per_call = time.perf_counter() - t_seq_start
    estimated_sequential_total = t_per_call * len(calls)

    # Concurrent run
    with concurrent.futures.ThreadPoolExecutor(max_workers=n_workers) as executor:
        t_conc_start = time.perf_counter()
        futures = [executor.submit(to_compiler_snippet_response, code) for code in calls]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]
        t_conc_total = time.perf_counter() - t_conc_start

    failures = [r for r in results if not r.get("valid")]
    speedup = estimated_sequential_total / t_conc_total if t_conc_total > 0 else 0.0
    throughput = len(calls) / t_conc_total

    summary = (
        f"\n{'='*72}\n"
        f"TC-25-03 Concurrent 4-workers × 10 calls\n"
        f"  wall-clock:          {t_conc_total:.2f}s\n"
        f"  est. sequential:     {estimated_sequential_total:.2f}s\n"
        f"  speedup ratio:       {speedup:.2f}×\n"
        f"  throughput:          {throughput:.2f} verifications/s\n"
        f"  workers:             {n_workers}\n"
        f"  calls:               {len(calls)}\n"
        f"  failures:            {len(failures)}\n"
        f"{'='*72}"
    )
    print(summary, file=sys.stderr)

    assert not failures, (
        f"{len(failures)}/{len(calls)} snippets failed to verify.\n"
        f"First failure errors: {failures[0].get('errors') if failures else 'N/A'}"
    )


# ---------------------------------------------------------------------------
# TC-25-04 — Concurrent: 8 workers × 20 calls — throughput measurement
# ---------------------------------------------------------------------------


def test_tc25_04_concurrent_8workers_20calls():
    """8 ThreadPoolExecutor workers, 20 concurrent Mathlib snippet verifications.

    Cycles through the 8 valid snippets to produce 20 calls.  Asserts all valid.
    Reports throughput and per-worker efficiency to stderr.
    """
    n_workers = 8
    calls = [s["code"] for s in (VALID_SNIPPETS * 3)[:20]]  # 20 calls

    with concurrent.futures.ThreadPoolExecutor(max_workers=n_workers) as executor:
        t_start = time.perf_counter()
        futures = [executor.submit(to_compiler_snippet_response, code) for code in calls]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]
        t_total = time.perf_counter() - t_start

    failures = [r for r in results if not r.get("valid")]
    throughput = len(calls) / t_total
    proc_times = [r.get("processing_time_seconds", 0.0) for r in results]
    mean_proc = statistics.mean(proc_times) if proc_times else 0.0

    summary = (
        f"\n{'='*72}\n"
        f"TC-25-04 Concurrent 8-workers × 20 calls\n"
        f"  wall-clock:          {t_total:.2f}s\n"
        f"  throughput:          {throughput:.2f} verifications/s\n"
        f"  mean Lean proc time: {mean_proc:.2f}s\n"
        f"  workers:             {n_workers}\n"
        f"  calls:               {len(calls)}\n"
        f"  failures:            {len(failures)}\n"
        f"{'='*72}"
    )
    print(summary, file=sys.stderr)

    assert not failures, (
        f"{len(failures)}/{len(calls)} snippets failed.\n"
        f"First failure: {failures[0].get('errors') if failures else 'N/A'}"
    )


# ---------------------------------------------------------------------------
# TC-25-05 — Mixed validity: 8 valid + 2 invalid Mathlib snippets
# ---------------------------------------------------------------------------


def test_tc25_05_mixed_valid_invalid_snippets():
    """Verify that the Lean verifier correctly classifies valid vs invalid Mathlib code.

    Runs all 10 snippets (8 valid, 2 intentionally invalid) sequentially.
    Asserts each snippet's validity matches its expected outcome.
    Invalid snippets (ORD-01, REAL-01) must NOT return valid=True — this guards
    against false positives when Mathlib is imported.
    """
    rows = []

    for snippet in MATHLIB_SNIPPETS:
        result = to_compiler_snippet_response(snippet["code"])
        actual_valid = result.get("valid", False)
        expected_valid = snippet["expect_valid"]
        correct = actual_valid == expected_valid

        rows.append((
            snippet["id"],
            "VALID" if actual_valid else "INVALID",
            "VALID" if expected_valid else "INVALID",
            "✓" if correct else "✗",
        ))

        assert correct, (
            f"Snippet {snippet['id']} ({snippet['description']}): "
            f"expected valid={expected_valid}, got valid={actual_valid}.\n"
            f"Return code: {result.get('return_code')}\n"
            f"Errors: {result.get('errors')}"
        )

    table = _fmt_table(rows, ("ID", "Actual", "Expected", "OK"))
    summary = (
        f"\n{'='*72}\n"
        f"TC-25-05 Mixed Validity Results\n"
        f"{table}"
        f"Valid snippets correct: {sum(1 for s in MATHLIB_SNIPPETS if s['expect_valid'])}/8\n"
        f"Invalid snippets correct: {sum(1 for s in MATHLIB_SNIPPETS if not s['expect_valid'])}/2\n"
        f"{'='*72}"
    )
    print(summary, file=sys.stderr)
