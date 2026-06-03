"""
Lean concurrent load test — executed inside the lean-worker container.
Copied from the Jenkins workspace via 'docker compose cp' and run as a file
(not via stdin) to avoid CRLF / heredoc issues.
"""
import concurrent.futures
import json
import sys
import time

sys.path.insert(0, "/app")
from lean_service import verify_lean_proof

NL = chr(10)
SNIPPET = NL.join([
    "theorem add_comm_nat (n m : Nat) : n + m = m + n := by",
    "  induction n with",
    "  | zero => simp",
    "  | succ k ih => simp [Nat.succ_add, ih]",
]) + NL


def run_one(idx):
    t0 = time.perf_counter()
    result = verify_lean_proof(SNIPPET)
    elapsed = (time.perf_counter() - t0) * 1000
    ok = result.get("verified", False)
    if not ok and idx == 0:
        # Print first failure detail so CI logs show the real error
        print("  [debug] verify_lean_proof result: {}".format(result))
    return idx, ok, elapsed


batches = []
print("=== Lean Worker: concurrent load test ===")
for workers, calls in [(1, 4), (4, 16), (8, 16)]:
    t_start = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(run_one, i) for i in range(calls)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]
    wall = (time.perf_counter() - t_start) * 1000
    passed = sum(1 for _, ok, _ in results if ok)
    avg_ms = sum(ms for _, _, ms in results) / len(results)
    tput = round(calls / (wall / 1000), 2)
    print(
        "  workers={}  calls={}  passed={}/{}  "
        "avg_latency={:.0f}ms  wall={:.0f}ms  throughput={}/s".format(
            workers, calls, passed, calls, avg_ms, wall, tput
        )
    )
    batches.append(
        {
            "workers": workers,
            "calls": calls,
            "passed": passed,
            "avg_latency_ms": round(avg_ms, 2),
            "wall_ms": round(wall, 2),
            "throughput_per_s": tput,
        }
    )

with open("/tmp/lean-concurrent-load.json", "w") as f:
    json.dump({"stage": "lean_concurrent_load", "batches": batches}, f, indent=2)
print("Artifact: /tmp/lean-concurrent-load.json")
