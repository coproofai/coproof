"""
smoke_test.py — Quick live smoke test for the cluster REST API.

Usage (from cluster_computation/):
    python smoke_test.py [CLUSTER_API_URL] [CLUSTER_API_KEY]

    Examples:
        python smoke_test.py http://10.86.211.170:8765
        python smoke_test.py http://10.86.211.170:8765 mysecretkey

URL and key can also be set via environment variables.
The root ../.env file is loaded automatically as a fallback.
"""

import json
import os
import sys
from pathlib import Path


def _load_env_file(path: Path) -> None:
    """Parse a simple KEY=VALUE .env file and populate os.environ for missing keys."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if key and key not in os.environ:
            os.environ[key] = value


# Load root .env so CLUSTER_API_KEY is available before the module import
_load_env_file(Path(__file__).parent.parent / ".env")

# CLI overrides (must come before the module import because the module reads
# CLUSTER_API_URL / CLUSTER_API_KEY at import time)
if len(sys.argv) > 1:
    os.environ["CLUSTER_API_URL"] = sys.argv[1]
if len(sys.argv) > 2:
    os.environ["CLUSTER_API_KEY"] = sys.argv[2]

import computation_service  # noqa: E402
from computation_service import run_cluster_computation_job  # noqa: E402

# Patch module-level constants that were already captured at import time
computation_service.CLUSTER_API_URL = os.environ.get(
    "CLUSTER_API_URL", computation_service.CLUSTER_API_URL
)
computation_service.CLUSTER_API_KEY = os.environ.get(
    "CLUSTER_API_KEY", computation_service.CLUSTER_API_KEY
)

# Distributed primality check: each MPI rank processes its slice of the input list.
# register_record() captures per-number results; evidence is the list of primes found.
SOURCE = """\
def compute(data, target):
    def is_prime(n):
        if n < 2:
            return False
        for i in range(2, int(n**0.5) + 1):
            if n % i == 0:
                return False
        return True

    results = []
    for n in (data or []):
        prime = is_prime(n)
        register_record(n=n, is_prime=prime)
        if prime:
            results.append(n)

    return {
        "evidence": results,
        "sufficient": len(results) > 0,
        "summary": f"Found {len(results)} prime(s) in {len(data or [])} numbers",
    }
"""

# 12 numbers spread across 3 ranks (4 per rank)
INPUT = list(range(2, 14))  # [2, 3, 4, ..., 13]
EXPECTED_PRIMES = [n for n in INPUT if all(n % i != 0 for i in range(2, n))]

PAYLOAD = {
    "language": "python",
    "source_code": SOURCE,
    "entrypoint": "compute",
    "input_data": INPUT,
    "target": None,
    "timeout_seconds": 60,
}

print(f"Submitting job to {os.environ.get('CLUSTER_API_URL', '(default)')} ...")
print(f"Input: {INPUT}  |  Expected primes: {EXPECTED_PRIMES}")
result = run_cluster_computation_job(PAYLOAD)
print(json.dumps(result, indent=2))

# --- assertions ---
assert result["completed"] is True, f"Expected completed=True, got: {result.get('error')}"
assert result["sufficient"] is True, "Expected sufficient=True (at least one prime found)"

# Evidence is a list of per-rank prime lists; flatten and sort for comparison
raw_evidence = result["evidence"]
if isinstance(raw_evidence, list) and raw_evidence and isinstance(raw_evidence[0], list):
    found_primes = sorted(p for sublist in raw_evidence for p in sublist)
else:
    found_primes = sorted(raw_evidence or [])

assert found_primes == EXPECTED_PRIMES, (
    f"Prime mismatch — expected {EXPECTED_PRIMES}, got {found_primes}"
)

records = result.get("records", [])
assert len(records) == len(INPUT), (
    f"Expected {len(INPUT)} records (one per input number), got {len(records)}"
)

rank_hosts = result.get("rank_hosts", {})
assert len(rank_hosts) > 1, (
    f"Expected multiple ranks to contribute, got rank_hosts={rank_hosts}"
)

print(f"\nRanks that worked: {rank_hosts}")
print(f"Primes found: {found_primes}")
print(f"Records collected: {len(records)}")
print("\nAll assertions passed.")
