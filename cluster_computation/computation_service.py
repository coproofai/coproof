"""
cluster_computation_service.py — HTTP client for the RPI cluster REST API.

Mirrors the interface of computation/computation_service.py so the rest of
the platform needs no changes to consume results.
"""

import os
import time

import requests

CLUSTER_API_URL = os.environ.get("CLUSTER_API_URL", "http://192.168.0.17:8765").rstrip("/")
CLUSTER_API_KEY = os.environ.get("CLUSTER_API_KEY", "")

# How long to wait between polls (seconds)
POLL_INTERVAL = float(os.environ.get("CLUSTER_POLL_INTERVAL", "4"))

# States returned by the RPI API that mean the job is still running
_PENDING_STATES = {"PENDING", "CONFIGURING", "RUNNING"}

_TERMINAL_STATES = {
    "COMPLETED", "FAILED", "CANCELLED", "TIMEOUT", "OUT_OF_MEMORY", "NODE_FAIL"
}


def _headers() -> dict:
    h = {"Content-Type": "application/json"}
    if CLUSTER_API_KEY:
        h["X-API-Key"] = CLUSTER_API_KEY
    return h


def run_cluster_job(payload: dict) -> dict:
    """
    Submit a job to the cluster REST API, poll until done, return a result
    dict with the same schema as computation/computation_service.py:

        completed, sufficient, evidence, summary, records,
        stdout, stderr, error, processing_time_seconds,
        + slurm_job_id, slurm_state, exit_code
    """
    start = time.perf_counter()
    timeout_seconds = int(payload.get("timeout_seconds") or 120)

    # --- submit ----------------------------------------------------------
    try:
        resp = requests.post(
            f"{CLUSTER_API_URL}/jobs",
            json=payload,
            headers=_headers(),
            timeout=15,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        return _error_result(
            f"Failed to submit job to cluster API: {exc}", start
        )

    job_id = resp.json().get("job_id")
    if not job_id:
        return _error_result("Cluster API returned no job_id", start)

    # --- poll ------------------------------------------------------------
    deadline = time.perf_counter() + timeout_seconds

    while True:
        if time.perf_counter() > deadline:
            return _error_result(
                f"Cluster job {job_id} timed out after {timeout_seconds}s",
                start,
                slurm_job_id=job_id,
            )

        try:
            status_resp = requests.get(
                f"{CLUSTER_API_URL}/jobs/{job_id}",
                headers=_headers(),
                timeout=15,
            )
            status_resp.raise_for_status()
        except requests.RequestException as exc:
            return _error_result(
                f"Failed to poll cluster API for job {job_id}: {exc}",
                start,
                slurm_job_id=job_id,
            )

        body = status_resp.json()
        status = body.get("status", "UNKNOWN").upper()

        if status in _TERMINAL_STATES:
            result = body.get("result")
            if result is None:
                return _error_result(
                    f"Cluster job {job_id} ended ({status}) but returned no result",
                    start,
                    slurm_job_id=body.get("slurm_job_id", job_id),
                    slurm_state=status,
                )
            # Normalize and augment with timing
            result.setdefault("slurm_job_id", body.get("slurm_job_id", job_id))
            result.setdefault("slurm_state", status)
            result["processing_time_seconds"] = round(time.perf_counter() - start, 6)
            return result

        time.sleep(POLL_INTERVAL)


def run_cluster_computation_job(payload: dict) -> dict:
    """Entry-point called by the Celery task."""
    start = time.perf_counter()
    language = (payload.get("language") or "mpi").strip().lower()

    if language not in ("mpi", "python"):
        return {
            "completed": False,
            "sufficient": False,
            "evidence": None,
            "summary": None,
            "records": [],
            "stdout": "",
            "stderr": "",
            "error": f"cluster_computation worker does not handle language: {language}",
            "processing_time_seconds": round(time.perf_counter() - start, 6),
            "slurm_job_id": None,
            "slurm_state": None,
            "exit_code": None,
        }

    return run_cluster_job(payload)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _error_result(
    message: str,
    start: float,
    slurm_job_id: str | None = None,
    slurm_state: str | None = None,
) -> dict:
    return {
        "completed": False,
        "sufficient": False,
        "evidence": None,
        "summary": None,
        "records": [],
        "stdout": "",
        "stderr": "",
        "error": message,
        "processing_time_seconds": round(time.perf_counter() - start, 6),
        "slurm_job_id": slurm_job_id,
        "slurm_state": slurm_state,
        "exit_code": None,
    }
