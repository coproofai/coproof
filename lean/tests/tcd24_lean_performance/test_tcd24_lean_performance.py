"""
TCD-24 — Lean Worker: Performance Benchmarks & Load
=====================================================
Module : lean/lean_service.py (all entry points)
Tools  : pytest-benchmark (latency), ThreadPoolExecutor (concurrency), Celery (E2E)

Covered test cases
──────────────────
TC-24-01  Benchmark: verify_lean_proof — simple snippet (baseline latency)
TC-24-02  Benchmark: verify_lean_proof — 5-theorem snippet (multi-decl overhead)
TC-24-03  Benchmark: to_compiler_snippet_response — simple snippet
TC-24-04  Benchmark: to_compiler_project_response — single-file project
TC-24-05  Benchmark: get_mathlib_info — Nat.add_comm (Mathlib load cost)
TC-24-06  Benchmark: get_mathlib_lineage — Nat.add_comm depth=1 (BFS overhead)
TC-24-07  Concurrent load: 1 worker × 4 calls — all succeed
TC-24-08  Concurrent load: 4 workers × 8 calls — all succeed
TC-24-09  Concurrent load: 8 workers × 12 calls — all succeed
TC-24-10  Concurrent load: 16 workers × 16 calls — all succeed
TC-24-11  Celery E2E: verify_snippet task round-trip (requires full stack)

Test design notes
─────────────────
Benchmark tests (TC-24-01 through TC-24-06):
  Use the `benchmark` fixture from pytest-benchmark.  When the library is not
  installed, conftest.py provides a no-op fallback that calls the function once.
  TC-24-05/06 require LEAN_PATH (Mathlib build) and are skipped otherwise.
  Use `benchmark.pedantic(rounds=N)` to limit Mathlib invocations to N runs.

Concurrency tests (TC-24-07 through TC-24-10):
  ThreadPoolExecutor submits `n_calls` invocations of `verify_lean_proof` across
  `n_workers` threads.  Each call spawns its own `lean` subprocess in a unique
  tempdir — no shared state, no file conflicts.
  Correctness assertion: all results must have `verified=True`.
  Timing is printed (not asserted) because thresholds are environment-dependent.

Celery E2E (TC-24-11):
  Sends `tasks.verify_snippet` to the broker and awaits the result.
  Skipped when REDIS_URL is not set or when the full stack is not running.
  Run only via `docker compose exec lean-worker` while the full compose stack
  (including Redis and the lean-worker Celery consumer) is up.

Run with (no pytest-benchmark):
  docker compose cp lean/tests lean-worker:/app/tests
  docker compose exec lean-worker bash -c "pip3 install pytest --quiet && cd /app && pytest -v tests/tcd24_lean_performance/"

Run with statistics (pytest-benchmark installed):
  docker compose exec lean-worker bash -c "pip3 install pytest pytest-benchmark --quiet && cd /app && pytest -v tests/tcd24_lean_performance/ --benchmark-sort=mean"
"""

import concurrent.futures
import os
import sys
import time

import pytest

from lean_service import (
    find_lean_executable,
    get_mathlib_info,
    get_mathlib_lineage,
    to_compiler_project_response,
    to_compiler_snippet_response,
    verify_lean_proof,
)

# ---------------------------------------------------------------------------
# Module-level skip when Lean is not installed
# ---------------------------------------------------------------------------

pytestmark = pytest.mark.skipif(
    find_lean_executable() is None,
    reason="Lean 4 executable not found — skipping performance tests",
)

_MATHLIB_AVAILABLE = bool(os.environ.get("LEAN_PATH") and find_lean_executable())
_MATHLIB_SKIP = pytest.mark.skipif(
    not _MATHLIB_AVAILABLE,
    reason="LEAN_PATH not set — Mathlib build not available in this environment",
)

_REDIS_URL = os.environ.get("REDIS_URL", "")

# ---------------------------------------------------------------------------
# Snippets used across tests
# ---------------------------------------------------------------------------

SIMPLE_SNIPPET = "theorem hello : True := trivial"
MULTI_THEOREM_SNIPPET = "\n".join(f"theorem t{i} : True := trivial" for i in range(5))

# ---------------------------------------------------------------------------
# TC-24-01 — Benchmark: verify_lean_proof — simple snippet
# ---------------------------------------------------------------------------


def test_tc24_01_bench_verify_proof_simple(benchmark):
    """Baseline latency for verify_lean_proof with a trivial theorem."""
    result = benchmark(verify_lean_proof, SIMPLE_SNIPPET)
    assert result["verified"] is True


# ---------------------------------------------------------------------------
# TC-24-02 — Benchmark: verify_lean_proof — 5-theorem snippet
# ---------------------------------------------------------------------------


def test_tc24_02_bench_verify_proof_multi_theorem(benchmark):
    """Latency for verify_lean_proof when the snippet contains 5 theorem declarations."""
    result = benchmark(verify_lean_proof, MULTI_THEOREM_SNIPPET)
    assert result["verified"] is True
    assert len(result["theorems"]) == 5


# ---------------------------------------------------------------------------
# TC-24-03 — Benchmark: to_compiler_snippet_response — simple snippet
# ---------------------------------------------------------------------------


def test_tc24_03_bench_snippet_response(benchmark):
    """Latency for the Celery-task-facing wrapper to_compiler_snippet_response."""
    result = benchmark(to_compiler_snippet_response, SIMPLE_SNIPPET)
    assert result["valid"] is True


# ---------------------------------------------------------------------------
# TC-24-04 — Benchmark: to_compiler_project_response — single-file project
# ---------------------------------------------------------------------------


def test_tc24_04_bench_project_response(benchmark):
    """Latency for to_compiler_project_response with a minimal single-file project."""
    result = benchmark.pedantic(
        to_compiler_project_response,
        args=({"main.lean": SIMPLE_SNIPPET}, "main.lean"),
        iterations=1,
        rounds=5,
    )
    assert result["valid"] is True


# ---------------------------------------------------------------------------
# TC-24-05 — Benchmark: get_mathlib_info — Nat.add_comm
# ---------------------------------------------------------------------------


@_MATHLIB_SKIP
def test_tc24_05_bench_mathlib_info(benchmark):
    """Latency for get_mathlib_info (includes Mathlib .olean load time)."""
    result = benchmark.pedantic(
        get_mathlib_info,
        args=("Nat.add_comm",),
        iterations=1,
        rounds=3,
    )
    assert result["found"] is True


# ---------------------------------------------------------------------------
# TC-24-06 — Benchmark: get_mathlib_lineage — Nat.add_comm depth=1
# ---------------------------------------------------------------------------


@_MATHLIB_SKIP
def test_tc24_06_bench_mathlib_lineage_depth1(benchmark):
    """Latency for get_mathlib_lineage at depth=1 (one BFS level / one Lean batch call)."""
    result = benchmark.pedantic(
        get_mathlib_lineage,
        args=("Nat.add_comm", 1),
        iterations=1,
        rounds=2,
    )
    assert result["total_nodes"] >= 1
    assert result["root"] == "Nat.add_comm"


# ---------------------------------------------------------------------------
# TC-24-07 through TC-24-10 — Concurrent load tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("n_workers,n_calls", [
    (1,  4),   # TC-24-07
    (4,  8),   # TC-24-08
    (8,  12),  # TC-24-09
    (16, 16),  # TC-24-10
])
def test_tc24_concurrent_snippet_load(n_workers, n_calls):
    """Submit n_calls verify_lean_proof calls concurrently across n_workers threads.

    Asserts correctness (all verified=True).  Timing is printed for manual review
    but not asserted, since thresholds vary across environments.
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=n_workers) as executor:
        start = time.perf_counter()
        futures = [
            executor.submit(verify_lean_proof, SIMPLE_SNIPPET)
            for _ in range(n_calls)
        ]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]
        total_time = time.perf_counter() - start

    failures = [r for r in results if not r.get("verified")]
    assert failures == [], f"Some concurrent calls returned verified=False: {failures}"

    throughput = n_calls / total_time
    avg_per_call = total_time / n_calls
    print(
        f"\n[TC-24 workers={n_workers:2d}, calls={n_calls:2d}]  "
        f"total={total_time:.3f}s  "
        f"throughput={throughput:.2f} calls/s  "
        f"avg/call={avg_per_call:.3f}s",
        file=sys.stderr,
    )


# ---------------------------------------------------------------------------
# TC-24-11 — Celery E2E round-trip via tasks.verify_snippet
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not _REDIS_URL,
    reason="REDIS_URL not set — Celery broker not available (run via docker compose exec with full stack up)",
)
def test_tc24_11_celery_verify_snippet_roundtrip():
    """Submit verify_snippet via Celery and measure full broker + worker round-trip time."""
    from celery import Celery as _Celery

    app = _Celery(broker=_REDIS_URL, backend=_REDIS_URL)

    start = time.perf_counter()
    async_result = app.send_task(
        "tasks.verify_snippet",
        args=["theorem hello : True := trivial"],
        queue="lean_queue",
    )
    response = async_result.get(timeout=30)
    elapsed = time.perf_counter() - start

    assert response["valid"] is True
    assert response["processing_time_seconds"] >= 0
    print(f"\nCelery broker round-trip: {elapsed:.3f}s")
