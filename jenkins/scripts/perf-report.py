"""
perf-report.py
Reads perf-summary.json and writes perf-report.txt — a plain-English summary
of every performance section, with a short description of what each test does.
Run from the Jenkins workspace (not inside a container).
"""
import json
import os
import sys

# ── Friendly names + descriptions for benchmark test IDs ─────────────────────
BENCH_DESCRIPTIONS = {
    "test_tc24_01_bench_verify_proof_simple": (
        "TC-24-01  Verify a simple Lean 4 proof (baseline)",
        "Measures how long the Lean worker takes to compile and verify a single "
        "short theorem.  This is the baseline for all other latency comparisons.",
    ),
    "test_tc24_02_bench_verify_proof_multi_theorem": (
        "TC-24-02  Verify a 5-theorem Lean 4 snippet",
        "Same as TC-24-01 but the input contains 5 separate theorem declarations.  "
        "Reveals whether multi-declaration files add measurable overhead.",
    ),
    "test_tc24_03_bench_snippet_response": (
        "TC-24-03  Build a compiler snippet response",
        "Benchmarks the to_compiler_snippet_response helper, which wraps a raw "
        "Lean snippet in the JSON structure the frontend expects.",
    ),
    "test_tc24_04_bench_project_response": (
        "TC-24-04  Build a compiler project response",
        "Like TC-24-03 but for full project files.  Exercises the project-level "
        "compilation path including file I/O.",
    ),
    "test_tc24_05_bench_mathlib_info": (
        "TC-24-05  Look up a Mathlib theorem (Nat.add_comm)",
        "Calls get_mathlib_info for a well-known theorem.  This loads the pre-built "
        "Mathlib .olean cache, so times here reflect real-world Mathlib query cost.",
    ),
    "test_tc24_06_bench_mathlib_lineage_depth1": (
        "TC-24-06  Traverse Mathlib theorem lineage (depth 1)",
        "BFS traversal from Nat.add_comm one level deep.  Shows the overhead of "
        "walking the Mathlib dependency graph.",
    ),
    "test_tc25_01_bench_mathlib_nat_arithmetic": (
        "TC-25-01  Real-world Mathlib snippet: Nat arithmetic (import Mathlib)",
        "Compiles a complete Lean 4 file that starts with 'import Mathlib' and "
        "proves a Nat arithmetic theorem.  This mirrors actual user workloads and "
        "is the most realistic latency figure for Mathlib-heavy proofs.",
    ),
}


def fmt_s(seconds):
    """Format seconds as ms if < 1 s, else as s."""
    ms = seconds * 1000
    if ms < 1000:
        return "{:.0f} ms".format(ms)
    return "{:.2f} s".format(seconds)


def section(title):
    bar = "=" * 72
    return "\n{}\n  {}\n{}\n".format(bar, title, bar)


def subsection(title):
    return "\n  -- {} --\n".format(title)


lines = []

# ── Load summary ──────────────────────────────────────────────────────────────
reports_dir = os.environ.get("PERF_REPORTS", "/tmp")
summary_path = os.path.join(reports_dir, "perf-summary.json")

if not os.path.exists(summary_path):
    print("ERROR: {} not found".format(summary_path))
    sys.exit(1)

with open(summary_path) as f:
    summary = json.load(f)

reports = summary.get("reports", {})
ts = summary.get("build_timestamp", "unknown")

lines.append("CoProof — Performance Test Report")
lines.append("Build timestamp : {}".format(ts))
lines.append("=" * 72)

# ── 1. Web API Response-Time Audit ────────────────────────────────────────────
web = reports.get("web-api-timing", {})
if web:
    lines.append(section("1. Web API Response-Time Audit"))
    lines.append(
        "  What this measures:\n"
        "  Each HTTP endpoint listed below was called 20 times from inside the\n"
        "  CI network.  The table shows the fastest call (min), typical call\n"
        "  (avg), the 95th-percentile call (p95 — 19 out of 20 calls were at\n"
        "  or below this value), and the slowest call (max).\n"
    )
    lines.append(
        "  {:<42}  {:>8}  {:>8}  {:>8}  {:>8}".format(
            "Endpoint", "min", "avg", "p95", "max"
        )
    )
    lines.append("  " + "-" * 70)
    for ep in web.get("endpoints", []):
        if "error" in ep:
            lines.append("  {:<42}  ERROR: {}".format(ep["label"], ep["error"]))
        else:
            lines.append(
                "  {:<42}  {:>5} ms  {:>5} ms  {:>5} ms  {:>5} ms".format(
                    ep["label"],
                    ep["min_ms"],
                    ep["avg_ms"],
                    ep["p95_ms"],
                    ep["max_ms"],
                )
            )

# ── 2. Lean Worker Benchmarks (TCD-24) ────────────────────────────────────────
tcd24 = reports.get("tcd24-benchmark", {})
if tcd24 and "benchmarks" in tcd24:
    lines.append(section("2. Lean Worker Benchmarks (TCD-24)"))
    lines.append(
        "  What this measures:\n"
        "  Each benchmark calls a specific lean_service function repeatedly\n"
        "  (at least 3 rounds) and records how long a single call takes.\n"
        "  Times under ~300 ms use an in-process Lean evaluation path;\n"
        "  times in the 4–5 s range require loading the full Mathlib library.\n"
    )
    for bm in tcd24["benchmarks"]:
        name = bm["name"]
        title, desc = BENCH_DESCRIPTIONS.get(
            name, (name, "No description available.")
        )
        s = bm["stats"]
        lines.append(subsection(title))
        lines.append("  {}".format(desc))
        lines.append(
            "\n  Rounds run : {rounds}\n"
            "  Mean       : {mean}\n"
            "  Median     : {median}\n"
            "  Fastest    : {mn}\n"
            "  Slowest    : {mx}\n"
            "  Std dev    : {sd}".format(
                rounds=s["rounds"],
                mean=fmt_s(s["mean"]),
                median=fmt_s(s["median"]),
                mn=fmt_s(s["min"]),
                mx=fmt_s(s["max"]),
                sd=fmt_s(s["stddev"]),
            )
        )

# ── 3. Lean Worker — Real-World Mathlib Scenarios (TCD-25) ───────────────────
tcd25 = reports.get("tcd25-benchmark", {})
if tcd25 and "benchmarks" in tcd25:
    lines.append(section("3. Lean Worker: Real-World Mathlib Scenarios (TCD-25)"))
    lines.append(
        "  What this measures:\n"
        "  These benchmarks use files that begin with 'import Mathlib', which\n"
        "  forces Lean to load the full Mathlib library from its pre-built .olean\n"
        "  cache.  This mirrors what real users submit to the platform.\n"
    )
    for bm in tcd25["benchmarks"]:
        name = bm["name"]
        title, desc = BENCH_DESCRIPTIONS.get(
            name, (name, "No description available.")
        )
        s = bm["stats"]
        lines.append(subsection(title))
        lines.append("  {}".format(desc))
        lines.append(
            "\n  Rounds run : {rounds}\n"
            "  Mean       : {mean}\n"
            "  Median     : {median}\n"
            "  Fastest    : {mn}\n"
            "  Slowest    : {mx}\n"
            "  Std dev    : {sd}".format(
                rounds=s["rounds"],
                mean=fmt_s(s["mean"]),
                median=fmt_s(s["median"]),
                mn=fmt_s(s["min"]),
                mx=fmt_s(s["max"]),
                sd=fmt_s(s["stddev"]),
            )
        )

# ── 4. Lean Worker — Concurrent Load Test ────────────────────────────────────
load = reports.get("lean-concurrent-load", {})
if load:
    lines.append(section("4. Lean Worker: Concurrent Load Test"))
    lines.append(
        "  What this measures:\n"
        "  The same simple proof is submitted multiple times simultaneously\n"
        "  using a thread pool.  Three concurrency levels are tested to see\n"
        "  how throughput scales when requests arrive in parallel.\n"
        "  'passed' counts how many calls returned verified=True; a low count\n"
        "  usually means the Lean executable is not available in this environment.\n"
    )
    lines.append(
        "  {:<10}  {:<8}  {:<8}  {:>12}  {:>12}  {:>14}".format(
            "Workers", "Calls", "Passed", "Avg latency", "Wall time", "Throughput"
        )
    )
    lines.append("  " + "-" * 70)
    for b in load.get("batches", []):
        lines.append(
            "  {:<10}  {:<8}  {:<8}  {:>9} ms  {:>9} ms  {:>11} /s".format(
                b["workers"],
                b["calls"],
                "{}/{}".format(b["passed"], b["calls"]),
                b["avg_latency_ms"],
                b["wall_ms"],
                b["throughput_per_s"],
            )
        )

# ── 5. Celery / Redis Throughput Snapshot ─────────────────────────────────────
celery = reports.get("celery-throughput", {})
if celery:
    lines.append(section("5. Celery / Redis Throughput Snapshot"))
    lines.append(
        "  What this measures:\n"
        "  Redis is the message broker that carries tasks between the web API\n"
        "  and the background workers (Lean, Computation, NL2FL, Agents).\n"
        "  This section reports: (a) how many tasks are currently queued,\n"
        "  (b) how quickly a Redis PING round-trips from the web container,\n"
        "  and (c) how many workers are registered and their task counts.\n"
    )

    rl = celery.get("redis_latency", {})
    if rl:
        lines.append(subsection("Redis broker round-trip latency  (50 pings)"))
        lines.append(
            "  Average : {} ms\n"
            "  p95     : {} ms   (95 % of pings were at or below this)\n"
            "  Fastest : {} ms\n"
            "  Slowest : {} ms".format(
                rl.get("avg_ms"), rl.get("p95_ms"),
                rl.get("min_ms"), rl.get("max_ms"),
            )
        )

    qd = celery.get("queue_depths", {})
    if qd:
        lines.append(subsection("Task queue depths at snapshot time"))
        lines.append(
            "  A depth of 0 means all previously submitted tasks have been\n"
            "  consumed.  A non-zero depth indicates a backlog.\n"
        )
        for name, info in qd.items():
            lines.append(
                "  {:<18}  depth = {}".format(info.get("queue", name), info.get("depth", "?"))
            )

    workers = celery.get("workers", [])
    if workers:
        lines.append(subsection("Active Celery workers  ({} online)".format(len(workers))))
        total_tasks = sum(w.get("registered_tasks", 0) for w in workers)
        lines.append(
            "  {} worker process(es) responded to the inspect probe.\n"
            "  Total registered task types across all workers: {}\n".format(
                len(workers), total_tasks
            )
        )
        for w in workers:
            lines.append(
                "  Worker {:40s}  concurrency={:>3}  registered tasks={:>2}".format(
                    w.get("name", "?"),
                    w.get("max_concurrency", "?"),
                    w.get("registered_tasks", "?"),
                )
            )

# ── Footer ────────────────────────────────────────────────────────────────────
lines.append("\n" + "=" * 72)
lines.append("End of report")
lines.append("=" * 72 + "\n")

out_path = os.path.join(reports_dir, "perf-report.txt")
with open(out_path, "w") as f:
    f.write("\n".join(lines))
print("Plain-English report written: {}".format(out_path))
