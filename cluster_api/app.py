import os
import subprocess
import time
from functools import wraps

from flask import Flask, jsonify, request

from job_manager import get_job, submit_job

app = Flask(__name__)

# Shared secret injected via environment variable (see setup.sh / systemd unit).
# If unset the API is open — only acceptable on a fully isolated LAN.
_API_KEY = os.environ.get("CLUSTER_API_KEY", "")

TERMINAL_STATES = {
    "COMPLETED", "FAILED", "CANCELLED", "TIMEOUT", "OUT_OF_MEMORY", "NODE_FAIL"
}


def require_api_key(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if _API_KEY and request.headers.get("X-API-Key") != _API_KEY:
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated


@app.get("/health")
def health():
    return jsonify({"status": "ok", "timestamp": time.time()})


@app.post("/jobs")
@require_api_key
def post_job():
    payload = request.get_json(force=True, silent=True)
    if not payload:
        return jsonify({"error": "JSON body required"}), 400
    if not payload.get("entrypoint"):
        return jsonify({"error": "Missing required field: entrypoint"}), 400
    try:
        job_id = submit_job(payload)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    return jsonify({"job_id": job_id}), 202


@app.get("/jobs/<job_id>")
@require_api_key
def get_job_status(job_id):
    entry = get_job(job_id)
    if entry is None:
        return jsonify({"error": "Job not found"}), 404

    response = {
        "job_id": job_id,
        "status": entry["status"],
        "slurm_job_id": entry["slurm_job_id"],
        "submitted_at": entry["submitted_at"],
    }

    if entry["status"] in TERMINAL_STATES and entry["result"] is not None:
        response["result"] = entry["result"]

    return jsonify(response)


@app.get("/nodes")
@require_api_key
def get_nodes():
    """Return Slurm node states via `sinfo`."""
    try:
        out = subprocess.check_output(
            ["sinfo", "--noheader", "--format=%n|%T|%c|%m|%e|%O"],
            text=True, timeout=10,
        )
    except FileNotFoundError:
        return jsonify({"error": "sinfo not found — is Slurm installed?"}), 503
    except subprocess.CalledProcessError as exc:
        return jsonify({"error": exc.stderr or str(exc)}), 503
    except subprocess.TimeoutExpired:
        return jsonify({"error": "sinfo timed out"}), 503

    nodes = []
    for line in out.strip().splitlines():
        parts = line.split("|")
        if len(parts) >= 6:
            nodes.append({
                "node": parts[0].strip(),
                "state": parts[1].strip(),
                "cpus": parts[2].strip(),
                "memory_mb": parts[3].strip(),
                "free_memory_mb": parts[4].strip(),
                "cpu_load": parts[5].strip(),
            })
    return jsonify({"nodes": nodes, "timestamp": time.time()})


@app.get("/queue")
@require_api_key
def get_queue():
    """Return Slurm job queue via `squeue`."""
    try:
        out = subprocess.check_output(
            ["squeue", "--noheader", "--format=%i|%j|%T|%M|%l|%C|%R|%u"],
            text=True, timeout=10,
        )
    except FileNotFoundError:
        return jsonify({"error": "squeue not found — is Slurm installed?"}), 503
    except subprocess.CalledProcessError as exc:
        return jsonify({"error": exc.stderr or str(exc)}), 503
    except subprocess.TimeoutExpired:
        return jsonify({"error": "squeue timed out"}), 503

    jobs = []
    for line in out.strip().splitlines():
        if not line.strip():
            continue
        parts = line.split("|")
        if len(parts) >= 8:
            jobs.append({
                "job_id": parts[0].strip(),
                "name": parts[1].strip(),
                "state": parts[2].strip(),
                "time": parts[3].strip(),
                "time_limit": parts[4].strip(),
                "cpus": parts[5].strip(),
                "reason": parts[6].strip(),
                "user": parts[7].strip(),
            })
    return jsonify({"jobs": jobs, "timestamp": time.time()})


if __name__ == "__main__":
    port = int(os.environ.get("CLUSTER_API_PORT", "8765"))
    app.run(host="0.0.0.0", port=port)
