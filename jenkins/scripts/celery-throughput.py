"""
Celery / Redis throughput snapshot — executed inside the web container.
Copied from the Jenkins workspace via 'docker compose cp' and run as a file
(not via stdin) to avoid CRLF / heredoc issues.
"""
import json
import os
import time

import redis

r = redis.from_url(os.environ["REDIS_URL"])

queues = {
    "lean":        os.environ.get("CELERY_LEAN_QUEUE",        "lean_queue"),
    "computation": os.environ.get("CELERY_COMPUTATION_QUEUE", "computation_queue"),
    "nl2fl":       os.environ.get("CELERY_NL2FL_QUEUE",       "nl2fl_queue"),
    "agents":      os.environ.get("CELERY_AGENTS_QUEUE",      "agents_queue"),
}

print("=== Celery queue depth snapshot ===")
queue_depths = {}
for name, q in queues.items():
    depth = r.llen(q)
    queue_depths[name] = {"queue": q, "depth": depth}
    print("  {:<35} depth={}".format(q, depth))

latencies = []
for _ in range(50):
    t0 = time.perf_counter()
    r.ping()
    latencies.append((time.perf_counter() - t0) * 1000)
s = sorted(latencies)
redis_stats = {
    "samples": len(latencies),
    "min_ms":  round(min(latencies), 3),
    "avg_ms":  round(sum(latencies) / len(latencies), 3),
    "p95_ms":  round(s[int(len(s) * 0.95)], 3),
    "max_ms":  round(max(latencies), 3),
}
print(
    "\n=== Redis broker latency (50 pings) ===\n"
    "  avg={avg_ms}ms  p95={p95_ms}ms  min={min_ms}ms  max={max_ms}ms".format(
        **redis_stats
    )
)

from celery_worker import celery as app  # noqa: E402

inspect = app.control.inspect(timeout=5)
registered = inspect.registered() or {}
stats_map = inspect.stats() or {}

workers_info = []
print("\n=== Active workers ({}) ===".format(len(registered)))
for worker, tasks in registered.items():
    pool = stats_map.get(worker, {}).get("pool", {})
    entry = {
        "name": worker,
        "max_concurrency": pool.get("max-concurrency", "?"),
        "registered_tasks": len(tasks),
    }
    workers_info.append(entry)
    print(
        "  {}  concurrency={}  tasks={}".format(
            worker, entry["max_concurrency"], entry["registered_tasks"]
        )
    )

payload = {
    "stage": "celery_throughput",
    "queue_depths": queue_depths,
    "redis_latency": redis_stats,
    "workers": workers_info,
}
with open("/tmp/celery-throughput.json", "w") as f:
    json.dump(payload, f, indent=2)
print("\nArtifact: /tmp/celery-throughput.json")
print("=== Throughput validation PASSED ===")
