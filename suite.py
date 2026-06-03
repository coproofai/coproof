#!/usr/bin/env python3
"""
CoProof Test Suite Runner
=========================
Trigger any Test Case Description (TCD) by number, list all available TCDs,
or read a full description of what each TCD tests.

Usage
-----
  python suite.py --list                    # table of all TCDs
  python suite.py --describe 17             # full description of TCD-17
  python suite.py --run 17                  # run a single TCD
  python suite.py --run 17 18 24 25         # run multiple TCDs
  python suite.py --implemented             # run all implemented TCDs
  python suite.py --tag lean                # run all lean-tagged TCDs
  python suite.py --tag web                 # run all web/server TCDs
  python suite.py --list-tags               # show available tags

Notes
-----
- Container-based tests (lean-worker, computation-worker, etc.) automatically sync
  the local test directory into the container before running.
- Server tests (TCD-01 to TCD-06) run on the host from the server/ directory.
- Frontend unit tests (TCD-12 to TCD-14) require Node.js in frontend/.
- E2E tests (TCD-15, TCD-16) require `docker compose up` and Cypress.
- Spec-only TCDs (TCD-19 to TCD-22) have no test file yet; --run will skip them.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import textwrap
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).parent.resolve()

# ─────────────────────────────────────────────────────────────────────────────
# ANSI colours (disabled on Windows without VT100 or when not a tty)
# ─────────────────────────────────────────────────────────────────────────────

_USE_COLOR = sys.stdout.isatty() and sys.platform != "win32" or (
    sys.platform == "win32" and shutil.which("ansicon") is not None
)

def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _USE_COLOR else text

def green(t): return _c("32", t)
def red(t):   return _c("31", t)
def yellow(t): return _c("33", t)
def cyan(t):  return _c("36", t)
def bold(t):  return _c("1",  t)
def dim(t):   return _c("2",  t)


# ─────────────────────────────────────────────────────────────────────────────
# Runner configuration dataclass
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Runner:
    """Describes how to execute a TCD."""

    kind: str
    """
    "pytest_host"      – pytest on the host, cwd=<some subdirectory>
    "pytest_container" – pytest inside a docker compose service
    "vitest"           – npm/vitest in frontend/
    "cypress"          – Cypress E2E in frontend/
    "not_implemented"  – spec-only, no test file
    """

    # ── pytest_host ──
    cwd: str = ""                  # relative to project root
    pytest_args: str = ""          # extra pytest flags / paths

    # ── pytest_container ──
    service: str = ""              # docker compose service name
    sync_local: str = ""           # local path to sync (relative to ROOT)
    sync_remote: str = ""          # destination path inside container
    container_cmd: str = ""        # command to run via docker compose exec

    # ── vitest / cypress ──
    npm_script: str = ""           # e.g. "test", "run", "e2e"


# ─────────────────────────────────────────────────────────────────────────────
# TCD Registry
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class TCD:
    id: int
    title: str
    module: str
    description: str          # full multi-line description
    status: str               # "✅" or "⬜"
    tc_count: int
    tags: list[str]
    runner: Runner


REGISTRY: dict[int, TCD] = {}

def _reg(*args, **kwargs):
    t = TCD(*args, **kwargs)
    REGISTRY[t.id] = t


# ── TCD-01: Auth API ─────────────────────────────────────────────────────────
_reg(
    id=1,
    title="Auth API (web)",
    module="server/app/api/auth.py, server/app/services/auth_service.py",
    description=textwrap.dedent("""\
        Validates all endpoints at /api/v1/auth:
          • GitHub OAuth URL generation
          • OAuth code exchange (code → JWT)
          • JWT token refresh
          • Authenticated profile retrieval (/me)
          • GitHub repository invitation management
        External GitHub REST calls are mocked via the `responses` library.
        Requires: PostgreSQL container (coproof_test_db), server .env.
    """),
    status="✅", tc_count=45, tags=["web", "auth", "server"],
    runner=Runner(
        kind="pytest_host",
        cwd="server",
        pytest_args="pytest -v tests/tcd01_auth/",
    ),
)

# ── TCD-02: Projects API ──────────────────────────────────────────────────────
_reg(
    id=2,
    title="Projects API (web)",
    module="server/app/api/projects.py, server/app/services/project_service.py",
    description=textwrap.dedent("""\
        CRUD operations for Lean proof projects:
          • Create, read, update, delete projects
          • Owner/collaborator access control
          • JWT authentication gate
        GitHub API calls mocked via `responses`.
        Requires: PostgreSQL container (coproof_test_db).
    """),
    status="✅", tc_count=29, tags=["web", "projects", "server"],
    runner=Runner(
        kind="pytest_host",
        cwd="server",
        pytest_args="pytest -v tests/tcd02_projects/",
    ),
)

# ── TCD-03: Nodes API ────────────────────────────────────────────────────────
_reg(
    id=3,
    title="Nodes API (web)",
    module="server/app/api/nodes.py",
    description=textwrap.dedent("""\
        Graph node operations inside a project:
          • Create, read, update, delete proof nodes
          • Node ownership and project membership checks
          • Response shape validation
        Requires: PostgreSQL container (coproof_test_db).
    """),
    status="✅", tc_count=17, tags=["web", "nodes", "server"],
    runner=Runner(
        kind="pytest_host",
        cwd="server",
        pytest_args="pytest -v tests/tcd03_nodes/",
    ),
)

# ── TCD-04: Translation API ───────────────────────────────────────────────────
_reg(
    id=4,
    title="Translation API (web)",
    module="server/app/api/translate.py",
    description=textwrap.dedent("""\
        Natural-language-to-formal-language translation endpoints:
          • /translate dispatches to nl2fl Celery worker
          • Task status polling
          • Error propagation from worker
        Celery task calls mocked via pytest-mock.
    """),
    status="✅", tc_count=25, tags=["web", "translation", "server"],
    runner=Runner(
        kind="pytest_host",
        cwd="server",
        pytest_args="pytest -v tests/tcd04_translate/",
    ),
)

# ── TCD-05: Agents API ────────────────────────────────────────────────────────
_reg(
    id=5,
    title="Agents API (web)",
    module="server/app/api/agents.py",
    description=textwrap.dedent("""\
        AI suggestion agent endpoints:
          • Trigger agent on a proof node
          • Retrieve suggestion results
          • Rate limiting / error cases
        Celery task calls mocked via pytest-mock.
    """),
    status="✅", tc_count=19, tags=["web", "agents", "server"],
    runner=Runner(
        kind="pytest_host",
        cwd="server",
        pytest_args="pytest -v tests/tcd05_agents/",
    ),
)

# ── TCD-06: GitHub Service / Git Engine ──────────────────────────────────────
_reg(
    id=6,
    title="GitHub Service / Git Engine (celery_worker)",
    module="server/app/services/github_service.py",
    description=textwrap.dedent("""\
        Git engine Celery tasks:
          • Clone, pull, push operations on user repos
          • Commit authoring with CoProof metadata
          • GitHub API interactions (branches, PRs)
          • Error handling for rate limits and auth failures
        All network calls mocked via `responses`.
    """),
    status="✅", tc_count=18, tags=["web", "git", "celery", "server"],
    runner=Runner(
        kind="pytest_host",
        cwd="server",
        pytest_args="pytest -v tests/tcd06_github_service/",
    ),
)

# ── TCD-07: Lean Worker ───────────────────────────────────────────────────────
_reg(
    id=7,
    title="Lean Worker (unit + mocked)",
    module="lean/lean_service.py (mocked), lean/tasks.py",
    description=textwrap.dedent("""\
        Unit tests for the lean-worker microservice with mocked Lean subprocess:
          • lean_service.py helpers and error handling
          • tasks.py Celery task wrappers (verify_snippet, verify_project,
            get_info, get_lineage)
          • Edge cases: empty input, subprocess timeout, malformed output
        Does NOT invoke the real Lean compiler; uses pytest-mock.
        Runs inside the lean-worker Docker container.
    """),
    status="✅", tc_count=23, tags=["lean", "unit"],
    runner=Runner(
        kind="pytest_container",
        service="lean-worker",
        sync_local="lean/tests/tcd07_lean_worker",
        sync_remote="/app/tests/tcd07_lean_worker",
        container_cmd="cd /app && pytest -v tests/tcd07_lean_worker/",
    ),
)

# ── TCD-08: Computation Worker ────────────────────────────────────────────────
_reg(
    id=8,
    title="Computation Worker (unit + mocked)",
    module="computation/computation_service.py (mocked), computation/tasks.py",
    description=textwrap.dedent("""\
        Unit tests for the computation-worker microservice:
          • Python code execution service (mocked subprocess)
          • Celery task wrappers: run_computation, run_script
          • Safety checks: blocked builtins, import restrictions
          • Timeout and memory error propagation
        Runs inside the computation-worker Docker container.
    """),
    status="✅", tc_count=24, tags=["computation", "unit"],
    runner=Runner(
        kind="pytest_container",
        service="computation-worker",
        sync_local="computation/tests/tcd08_computation",
        sync_remote="/app/tests/tcd08_computation",
        container_cmd="cd /app && pytest -v tests/tcd08_computation/",
    ),
)

# ── TCD-09: Cluster Computation Worker ───────────────────────────────────────
_reg(
    id=9,
    title="Cluster Computation Worker (unit + mocked)",
    module="cluster_computation/computation_service.py",
    description=textwrap.dedent("""\
        Unit tests for the cluster-computation-worker microservice:
          • MPI job submission via Cluster API
          • Poll-loop logic for job status
          • API error and timeout handling
          • Response normalisation
        External Cluster API mocked via `responses`.
        Runs inside the cluster-computation-worker Docker container.
    """),
    status="✅", tc_count=19, tags=["cluster", "computation", "unit"],
    runner=Runner(
        kind="pytest_container",
        service="cluster-computation-worker",
        sync_local="cluster_computation/tests/tcd09_cluster",
        sync_remote="/app/tests/tcd09_cluster",
        container_cmd="cd /app && pytest -v tests/tcd09_cluster/",
    ),
)

# ── TCD-10: NL2FL Worker ─────────────────────────────────────────────────────
_reg(
    id=10,
    title="NL2FL Worker (unit + mocked)",
    module="nl2fl/nl2fl_service.py",
    description=textwrap.dedent("""\
        Unit tests for the nl2fl-worker (natural language → formal language):
          • LLM API call mocking (GitHub Copilot / OpenAI endpoint)
          • Retry logic on rate limits
          • Output parsing and error propagation
          • Celery task wrapper: translate_to_lean
        Runs inside the nl2fl-worker Docker container.
    """),
    status="✅", tc_count=20, tags=["nl2fl", "unit"],
    runner=Runner(
        kind="pytest_container",
        service="nl2fl-worker",
        sync_local="nl2fl/tests/tcd10_nl2fl",
        sync_remote="/app/tests/tcd10_nl2fl",
        container_cmd="cd /app && pytest -v tests/tcd10_nl2fl/",
    ),
)

# ── TCD-11: Agents Worker ─────────────────────────────────────────────────────
_reg(
    id=11,
    title="Agents Worker (unit + mocked)",
    module="agents/agents_service.py",
    description=textwrap.dedent("""\
        Unit tests for the agents-worker microservice:
          • Agent routing: selects correct suggestion strategy
          • LLM call mocking
          • Suggestion formatting and Celery task wrapper
        Runs inside the agents-worker Docker container.
    """),
    status="✅", tc_count=13, tags=["agents", "unit"],
    runner=Runner(
        kind="pytest_container",
        service="agents-worker",
        sync_local="agents/tests/tcd11_agents",
        sync_remote="/app/tests/tcd11_agents",
        container_cmd="cd /app && pytest -v tests/tcd11_agents/",
    ),
)

# ── TCD-12: Angular AuthService ──────────────────────────────────────────────
_reg(
    id=12,
    title="Angular AuthService (frontend)",
    module="frontend/src/app/services/auth.service.ts",
    description=textwrap.dedent("""\
        Angular unit tests for AuthService:
          • login(), logout(), refreshToken()
          • JWT storage in localStorage
          • HTTP interceptor token attachment
          • Redirect on 401
        Tool: Vitest with provideHttpClientTesting.
    """),
    status="✅", tc_count=13, tags=["frontend", "auth", "angular"],
    runner=Runner(
        kind="vitest",
        cwd="frontend",
        npm_script="npx vitest run src/app/services/auth.service.spec.ts",
    ),
)

# ── TCD-13: Angular TaskService ──────────────────────────────────────────────
_reg(
    id=13,
    title="Angular TaskService (frontend)",
    module="frontend/src/app/services/task.service.ts",
    description=textwrap.dedent("""\
        Angular unit tests for TaskService:
          • submitVerification(), pollStatus(), cancelTask()
          • HTTP calls to /api/v1/translate and /api/v1/verify
          • Observable pipe and error mapping
        Tool: Vitest with provideHttpClientTesting.
    """),
    status="✅", tc_count=10, tags=["frontend", "tasks", "angular"],
    runner=Runner(
        kind="vitest",
        cwd="frontend",
        npm_script="npx vitest run src/app/services/task.service.spec.ts",
    ),
)

# ── TCD-14: Angular authGuard ────────────────────────────────────────────────
_reg(
    id=14,
    title="Angular authGuard (frontend)",
    module="frontend/src/app/guards/auth.guard.ts",
    description=textwrap.dedent("""\
        Angular unit tests for the route guard:
          • Allows navigation when JWT is valid
          • Redirects to /login when unauthenticated
          • Redirects after token refresh succeeds
        Tool: Vitest, TestBed.runInInjectionContext, provideRouter.
    """),
    status="✅", tc_count=3, tags=["frontend", "auth", "angular"],
    runner=Runner(
        kind="vitest",
        cwd="frontend",
        npm_script="npx vitest run src/app/guards/auth.guard.spec.ts",
    ),
)

# ── TCD-15: E2E Authentication Flow ──────────────────────────────────────────
_reg(
    id=15,
    title="E2E Authentication Flow",
    module="Full stack (web + frontend + db)",
    description=textwrap.dedent("""\
        End-to-end Cypress tests for the authentication flow:
          • GitHub OAuth login button → redirect → callback
          • Token storage and /me profile fetch
          • Logout clears session and redirects
          • Protected routes redirect unauthenticated users
        Requires: docker compose up (full stack).
        Tool: Cypress 15, cy.intercept to mock GitHub OAuth.
    """),
    status="✅", tc_count=7, tags=["e2e", "auth", "cypress", "frontend"],
    runner=Runner(
        kind="cypress",
        cwd="frontend",
        npm_script="npx cypress run --spec 'cypress/e2e/tcd15_auth/**'",
    ),
)

# ── TCD-16: E2E Project & Node Flow ──────────────────────────────────────────
_reg(
    id=16,
    title="E2E Project & Node Flow",
    module="Full stack (web + frontend + db)",
    description=textwrap.dedent("""\
        End-to-end Cypress tests for the main application workflow:
          • Create a new proof project
          • Add nodes (propositions) to the project graph
          • Edit and delete nodes
          • Navigate between project views
        Requires: docker compose up (full stack).
        Tool: Cypress 15, cy.intercept.
    """),
    status="✅", tc_count=6, tags=["e2e", "projects", "cypress", "frontend"],
    runner=Runner(
        kind="cypress",
        cwd="frontend",
        npm_script="npx cypress run --spec 'cypress/e2e/tcd16_project/**'",
    ),
)

# ── TCD-17: Lean Worker Functional ───────────────────────────────────────────
_reg(
    id=17,
    title="Lean Worker — Functional Verification",
    module="lean/lean_service.py — verify_lean_proof()",
    description=textwrap.dedent("""\
        Functional tests that invoke the real Lean 4 compiler (no mocks):
          • TC-17-01: trivial theorem verifies (True := trivial)
          • TC-17-02: stdlib Nat.add_comm proof verifies
          • TC-17-03: intentionally false theorem → verified=False
          • TC-17-04: syntax error → returnCode != 0, errors non-empty
          • TC-17-05: multi-theorem snippet → all theorems in results
        Each test spawns a real `lean` process.
        Runs inside the lean-worker Docker container.
    """),
    status="✅", tc_count=5, tags=["lean", "functional"],
    runner=Runner(
        kind="pytest_container",
        service="lean-worker",
        sync_local="lean/tests/tcd17_lean_functional",
        sync_remote="/app/tests/tcd17_lean_functional",
        container_cmd="cd /app && pytest -v tests/tcd17_lean_functional/",
    ),
)

# ── TCD-18: Computation Worker Functional ────────────────────────────────────
_reg(
    id=18,
    title="Computation Worker — Functional Execution",
    module="computation/computation_service.py — run_computation()",
    description=textwrap.dedent("""\
        Functional tests that execute real Python code in a subprocess (no mocks):
          • TC-18-01: simple expression evaluates correctly (2 + 2 → 4)
          • TC-18-02: NumPy/SciPy computation returns expected result
          • TC-18-03: runtime exception captured in error field
          • TC-18-04: timeout enforcement (infinite loop → killed)
          • TC-18-05: multi-step stateful computation
        Runs inside the computation-worker Docker container.
    """),
    status="✅", tc_count=5, tags=["computation", "functional"],
    runner=Runner(
        kind="pytest_container",
        service="computation-worker",
        sync_local="computation/tests/tcd18_computation_functional",
        sync_remote="/app/tests/tcd18_computation_functional",
        container_cmd="cd /app && pytest -v tests/tcd18_computation_functional/",
    ),
)

# ── TCD-19: NL2FL Worker Functional (spec-only) ──────────────────────────────
_reg(
    id=19,
    title="NL2FL Worker — Functional Pipeline (SPEC ONLY)",
    module="nl2fl/nl2fl_service.py",
    description=textwrap.dedent("""\
        [Spec only — no test file yet]
        Planned functional tests against the real LLM endpoint:
          • Valid NL input → Lean 4 theorem skeleton returned
          • Retry on transient HTTP 429 (rate limit)
          • Hard fail on 4xx client error
          • Output contains valid Lean syntax
          • Empty/gibberish input → graceful error
    """),
    status="⬜", tc_count=5, tags=["nl2fl", "functional"],
    runner=Runner(kind="not_implemented"),
)

# ── TCD-20: Agents Worker Functional (spec-only) ─────────────────────────────
_reg(
    id=20,
    title="Agents Worker — Functional Suggestion Flow (SPEC ONLY)",
    module="agents/agents_service.py",
    description=textwrap.dedent("""\
        [Spec only — no test file yet]
        Planned functional tests for the agents microservice:
          • Agent routes to correct strategy (tactic / term-mode / hybrid)
          • LLM response parsed into suggestion object
          • Suggestion validated for non-empty Lean tactics
          • Agent re-tries on empty LLM output
    """),
    status="⬜", tc_count=4, tags=["agents", "functional"],
    runner=Runner(kind="not_implemented"),
)

# ── TCD-21: Cluster Computation Functional (spec-only) ───────────────────────
_reg(
    id=21,
    title="Cluster Computation — Functional Polling Flow (SPEC ONLY)",
    module="cluster_computation/computation_service.py",
    description=textwrap.dedent("""\
        [Spec only — no test file yet]
        Planned functional tests against a real or stubbed Cluster API:
          • Job submission returns job_id
          • Poll loop transitions PENDING → RUNNING → DONE
          • Result retrieved after job completes
          • Timeout after N poll cycles
          • Cluster API unreachable → graceful error
    """),
    status="⬜", tc_count=5, tags=["cluster", "functional"],
    runner=Runner(kind="not_implemented"),
)

# ── TCD-22: Web API + PostgreSQL Functional (spec-only) ──────────────────────
_reg(
    id=22,
    title="Web API + PostgreSQL — Functional Integration (SPEC ONLY)",
    module="server/ (Flask app + PostgreSQL)",
    description=textwrap.dedent("""\
        [Spec only — no test file yet]
        Planned integration tests against a real PostgreSQL instance:
          • User creation persists to DB
          • Project CRUD round-trips through DB
          • Node graph stored and retrieved correctly
          • Concurrent requests don't corrupt DB state
          • Migration forward/backward idempotency
    """),
    status="⬜", tc_count=6, tags=["web", "db", "integration"],
    runner=Runner(kind="not_implemented"),
)

# ── TCD-23: Lean Worker — All Entry Points Correctness ───────────────────────
_reg(
    id=23,
    title="Lean Worker — All Entry Points: Correctness",
    module="lean/lean_service.py — all 6 public functions",
    description=textwrap.dedent("""\
        Correctness tests for every public entry point in lean_service.py:
          • verify_lean_proof: valid/invalid/error cases
          • to_compiler_snippet_response: wrapper shape validation
          • verify_lean_project: multi-file project
          • to_compiler_project_response: wrapper shape validation
          • get_mathlib_info: known + unknown declaration (skipped if no LEAN_PATH)
          • get_mathlib_lineage: BFS depth=1 (skipped if no LEAN_PATH)
        Uses real Lean 4 compiler; Mathlib tests auto-skip without LEAN_PATH.
        Runs inside the lean-worker Docker container.
    """),
    status="⬜", tc_count=10, tags=["lean", "correctness"],
    runner=Runner(
        kind="pytest_container",
        service="lean-worker",
        sync_local="lean/tests/tcd23_lean_correctness",
        sync_remote="/app/tests/tcd23_lean_correctness",
        container_cmd="cd /app && pytest -v tests/tcd23_lean_correctness/",
    ),
)

# ── TCD-24: Lean Worker — Performance Benchmarks & Load ──────────────────────
_reg(
    id=24,
    title="Lean Worker — Performance Benchmarks & Load",
    module="lean/lean_service.py — all entry points",
    description=textwrap.dedent("""\
        Performance benchmarks and concurrent load tests (stdlib-only snippets):
          • TC-24-01..04: pytest-benchmark for verify_lean_proof, wrappers,
                          project response (~100–175 ms/call baseline)
          • TC-24-05..06: Mathlib entry points benchmark (skipped if no LEAN_PATH)
          • TC-24-07..10: concurrent load — 1/4/8/16 workers × 4/8/12/16 calls;
                          all must return verified=True; metrics to stderr
          • TC-24-11: Celery E2E round-trip via tasks.verify_snippet (skipped
                      if REDIS_URL not set)
        Benchmark stats printed via pytest-benchmark; concurrent metrics to stderr.
        Runs inside the lean-worker Docker container.
    """),
    status="✅", tc_count=11, tags=["lean", "performance", "benchmark"],
    runner=Runner(
        kind="pytest_container",
        service="lean-worker",
        sync_local="lean/tests/tcd24_lean_performance",
        sync_remote="/app/tests/tcd24_lean_performance",
        container_cmd=(
            "pip3 install pytest-benchmark --quiet && "
            "cd /app && pytest -v -s tests/tcd24_lean_performance/ --benchmark-sort=mean"
        ),
    ),
)

# ── TCD-25: Lean Worker — Real-World Mathlib Scenarios ───────────────────────
_reg(
    id=25,
    title="Lean Worker — Real-World Mathlib Scenario Tests",
    module="lean/lean_service.py — to_compiler_snippet_response()",
    description=textwrap.dedent("""\
        Exhaustive tests using real Lean 4 + Mathlib snippets (import Mathlib):
          • TC-25-01: benchmark NAT-01 snippet (3 rounds) — ~4 s/call with Mathlib
          • TC-25-02: 10 snippets sequentially — latency table on stderr
                      (8 valid: NAT, LIST, INT, RING, SET, FINSET;
                       2 invalid: wrong type, ring-closed false equation)
          • TC-25-03: 4 workers × 10 calls — ~2× speedup vs sequential
          • TC-25-04: 8 workers × 20 calls — throughput ~0.7 verif/s
          • TC-25-05: mixed validity — 8/8 valid, 2/2 invalid correctly classified
        Snippets are inline (no network calls). Requires LEAN_PATH in container.
        Runs inside the lean-worker Docker container.
    """),
    status="✅", tc_count=5, tags=["lean", "performance", "functional", "mathlib"],
    runner=Runner(
        kind="pytest_container",
        service="lean-worker",
        sync_local="lean/tests/tcd25_lean_realworld",
        sync_remote="/app/tests/tcd25_lean_realworld",
        container_cmd=(
            "pip3 install pytest-benchmark --quiet && "
            "cd /app && pytest -v -s tests/tcd25_lean_realworld/ --benchmark-sort=mean"
        ),
    ),
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _all_tags() -> list[str]:
    tags: set[str] = set()
    for t in REGISTRY.values():
        tags.update(t.tags)
    return sorted(tags)


def _status_badge(t: TCD) -> str:
    return green("✅") if t.status == "✅" else yellow("⬜")


def _docker_available() -> bool:
    return shutil.which("docker") is not None


# ─────────────────────────────────────────────────────────────────────────────
# Commands
# ─────────────────────────────────────────────────────────────────────────────

def cmd_list(args) -> None:
    """Print a table of all TCDs."""
    tag_filter: Optional[str] = getattr(args, "tag", None)
    entries = list(REGISTRY.values())
    if tag_filter:
        entries = [t for t in entries if tag_filter in t.tags]

    col_id    = 6
    col_title = 46
    col_tcs   = 4
    col_tags  = 28
    col_st    = 6

    header = (
        bold(f"{'TCD':<{col_id}}")
        + bold(f"{'Title':<{col_title}}")
        + bold(f"{'TCs':>{col_tcs}}")
        + bold(f"  {'Tags':<{col_tags}}")
        + bold(f"  {'Status'}")
    )
    sep = dim("─" * (col_id + col_title + col_tcs + 2 + col_tags + 2 + col_st))

    print()
    print(header)
    print(sep)
    for t in entries:
        badge = _status_badge(t)
        tag_str = ", ".join(t.tags)
        print(
            f"{cyan(f'TCD-{t.id:02d}'):<{col_id + 9}}"
            f"{t.title:<{col_title}}"
            f"{t.tc_count:>{col_tcs}}"
            f"  {dim(tag_str):<{col_tags + 8}}"
            f"  {badge}"
        )
    print(sep)
    total   = sum(t.tc_count for t in entries)
    passing = sum(t.tc_count for t in entries if t.status == "✅")
    print(
        f"\n  {len(entries)} TCDs  |  "
        f"{sum(1 for t in entries if t.status == '✅')} implemented  |  "
        f"{sum(1 for t in entries if t.status == '⬜')} spec-only  |  "
        f"{passing}/{total} TCs passing\n"
    )


def cmd_list_tags(args) -> None:
    print("\nAvailable tags:\n")
    for tag in _all_tags():
        count = sum(1 for t in REGISTRY.values() if tag in t.tags)
        print(f"  {cyan(tag):<20} ({count} TCDs)")
    print()


def cmd_describe(args) -> None:
    """Print a full description of one TCD."""
    tcd_id: int = args.describe
    if tcd_id not in REGISTRY:
        print(red(f"Unknown TCD: {tcd_id}. Run --list to see all TCDs."))
        sys.exit(1)

    t = REGISTRY[tcd_id]
    width = 72
    border = "═" * width
    print()
    print(bold(f"╔{border}╗"))
    print(bold(f"║  TCD-{t.id:02d} — {t.title:<{width - 10}}║"))
    print(bold(f"╚{border}╝"))
    print(f"  {bold('Status:')}     {_status_badge(t)}  {t.tc_count} test cases")
    print(f"  {bold('Module:')}     {t.module}")
    print(f"  {bold('Tags:')}       {', '.join(t.tags)}")

    r = t.runner
    if r.kind == "pytest_host":
        print(f"  {bold('Runner:')}     pytest (host), cwd='{r.cwd}'")
        print(f"  {bold('Command:')}    {r.pytest_args}")
    elif r.kind == "pytest_container":
        print(f"  {bold('Runner:')}     pytest (container: {r.service})")
        print(f"  {bold('Sync:')}       {r.sync_local} → {r.service}:{r.sync_remote}")
        print(f"  {bold('Command:')}    {r.container_cmd}")
    elif r.kind == "vitest":
        print(f"  {bold('Runner:')}     Vitest (host), cwd='{r.cwd}'")
        print(f"  {bold('Command:')}    {r.npm_script}")
    elif r.kind == "cypress":
        print(f"  {bold('Runner:')}     Cypress (host), cwd='{r.cwd}'")
        print(f"  {bold('Command:')}    {r.npm_script}")
    else:
        print(f"  {bold('Runner:')}     {yellow('Not yet implemented')}")

    print(f"\n  {bold('Description:')}")
    for line in t.description.strip().splitlines():
        print(f"    {line}")
    print()


# ─────────────────────────────────────────────────────────────────────────────
# Execution engine
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class RunResult:
    tcd_id: int
    title: str
    returncode: int
    elapsed: float
    skipped: bool = False
    skip_reason: str = ""


def _sync_to_container(service: str, local: str, remote: str) -> bool:
    """Copy local path into docker compose service. Returns True on success."""
    local_path = ROOT / local
    if not local_path.exists():
        print(yellow(f"  [warn] sync source not found: {local_path}"))
        return False
    cmd = ["docker", "compose", "cp", str(local_path), f"{service}:{remote}"]
    print(dim(f"  [sync] {local} → {service}:{remote}"))
    result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        print(red(f"  [sync error] {result.stderr.strip()}"))
        return False
    return True


def _run_tcd(tcd: TCD, force_sync: bool = False) -> RunResult:
    """Execute a single TCD and return the result."""
    r = tcd.runner
    print()
    print(bold(f"┌── TCD-{tcd.id:02d}: {tcd.title} ──"))
    print(dim(f"│   Module:  {tcd.module}"))
    print(dim(f"│   Status:  {tcd.status}  │  Tags: {', '.join(tcd.tags)}"))

    if r.kind == "not_implemented":
        print(yellow(f"│   [skip] Spec-only TCD — no test file yet"))
        print(bold(f"└── SKIPPED\n"))
        return RunResult(tcd.id, tcd.title, 0, 0.0, skipped=True, skip_reason="spec-only")

    print(bold(f"│"))
    start = time.perf_counter()

    if r.kind == "pytest_host":
        cwd = ROOT / r.cwd
        print(dim(f"│   cwd: {cwd}"))
        print(dim(f"│   cmd: {r.pytest_args}"))
        print(bold("│"))
        proc = subprocess.run(
            r.pytest_args,
            shell=True,
            cwd=cwd,
        )
        rc = proc.returncode

    elif r.kind == "pytest_container":
        if not _docker_available():
            print(red("│   [error] docker not found in PATH"))
            print(bold(f"└── FAILED\n"))
            return RunResult(tcd.id, tcd.title, 1, 0.0)

        if r.sync_local:
            ok = _sync_to_container(r.service, r.sync_local, r.sync_remote)
            if not ok:
                print(red("│   [error] sync failed — aborting run"))
                print(bold(f"└── FAILED\n"))
                return RunResult(tcd.id, tcd.title, 1, 0.0)

        print(dim(f"│   service: {r.service}"))
        print(dim(f"│   exec:    {r.container_cmd}"))
        print(bold("│"))
        proc = subprocess.run(
            ["docker", "compose", "exec", r.service, "bash", "-c", r.container_cmd],
            cwd=ROOT,
        )
        rc = proc.returncode

    elif r.kind in ("vitest", "cypress"):
        cwd = ROOT / r.cwd
        print(dim(f"│   cwd: {cwd}"))
        print(dim(f"│   cmd: {r.npm_script}"))
        print(bold("│"))
        proc = subprocess.run(r.npm_script, shell=True, cwd=cwd)
        rc = proc.returncode

    else:
        print(red(f"│   [error] unknown runner kind: {r.kind}"))
        rc = 1

    elapsed = time.perf_counter() - start
    status_str = green("PASSED") if rc == 0 else red("FAILED")
    print(bold(f"└── {status_str}  [{elapsed:.1f}s]\n"))
    return RunResult(tcd.id, tcd.title, rc, elapsed)


def cmd_run(tcd_ids: list[int], force_sync: bool = False) -> None:
    """Run a list of TCDs and print a summary."""
    results: list[RunResult] = []

    for tcd_id in tcd_ids:
        if tcd_id not in REGISTRY:
            print(red(f"\nUnknown TCD-{tcd_id} — skipping"))
            results.append(RunResult(tcd_id, "?", 1, 0.0, skipped=True,
                                     skip_reason="not in registry"))
            continue
        result = _run_tcd(REGISTRY[tcd_id], force_sync=force_sync)
        results.append(result)

    # ── Summary ──────────────────────────────────────────────────────────────
    width = 68
    print(bold(f"\n{'═' * width}"))
    print(bold(f"  Test Suite Run Summary"))
    print(bold(f"{'═' * width}"))

    passed = skipped = failed = 0
    total_elapsed = 0.0

    for res in results:
        if res.skipped:
            badge = yellow("SKIPPED")
            skipped += 1
            time_str = f"({res.skip_reason})"
        elif res.returncode == 0:
            badge = green("PASSED ")
            passed += 1
            time_str = f"{res.elapsed:.1f}s"
            total_elapsed += res.elapsed
        else:
            badge = red("FAILED ")
            failed += 1
            time_str = f"{res.elapsed:.1f}s"
            total_elapsed += res.elapsed

        title_trunc = res.title[:46] if len(res.title) > 46 else res.title
        print(f"  TCD-{res.tcd_id:02d}  {title_trunc:<46}  {badge}  {dim(time_str)}")

    print(bold(f"{'─' * width}"))
    parts = []
    if passed:  parts.append(green(f"{passed} passed"))
    if failed:  parts.append(red(f"{failed} failed"))
    if skipped: parts.append(yellow(f"{skipped} skipped"))
    print(f"  {'  |  '.join(parts)}  |  total time: {total_elapsed:.1f}s")
    print(bold(f"{'═' * width}\n"))

    if failed:
        sys.exit(1)


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="suite.py",
        description="CoProof Test Suite Runner — trigger any TCD and describe what it tests",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
              python suite.py --list
              python suite.py --describe 17
              python suite.py --run 17
              python suite.py --run 17 18 24 25
              python suite.py --implemented
              python suite.py --tag lean
        """),
    )

    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--list", action="store_true",
        help="Show a table of all TCDs with status and tags",
    )
    mode.add_argument(
        "--list-tags", action="store_true", dest="list_tags",
        help="Show available tags for --tag filtering",
    )
    mode.add_argument(
        "--describe", metavar="N", type=int,
        help="Print full description of TCD-N",
    )
    mode.add_argument(
        "--run", metavar="N", nargs="+", type=int,
        help="Run one or more TCDs by number (e.g. --run 17 18 25)",
    )
    mode.add_argument(
        "--implemented", action="store_true",
        help="Run all implemented TCDs (status ✅)",
    )
    mode.add_argument(
        "--tag", metavar="TAG",
        help="Run all TCDs matching a tag (use --list-tags to see tags)",
    )

    parser.add_argument(
        "--sync", action="store_true",
        help="(container tests) always re-sync test files before running",
    )

    args = parser.parse_args()

    if args.list:
        cmd_list(args)
    elif args.list_tags:
        cmd_list_tags(args)
    elif args.describe is not None:
        cmd_describe(args)
    elif args.run:
        cmd_run(args.run, force_sync=args.sync)
    elif args.implemented:
        ids = [t.id for t in REGISTRY.values() if t.status == "✅"]
        cmd_run(ids, force_sync=args.sync)
    elif args.tag:
        ids = [t.id for t in REGISTRY.values() if args.tag in t.tags]
        if not ids:
            print(red(f"No TCDs found with tag '{args.tag}'. Run --list-tags."))
            sys.exit(1)
        cmd_run(ids, force_sync=args.sync)


if __name__ == "__main__":
    main()
