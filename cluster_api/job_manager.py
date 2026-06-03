"""
job_manager.py — Slurm job lifecycle for the cluster REST API.

Flow:
  submit_job(payload) -> job_id
    1. Write user_code.py + payload.json to /tmp/cluster_jobs/<job_id>/
    2. Render mpi_runner.py.j2 -> runner.py
    3. Write job.sh (sbatch script)
    4. Submit via `sbatch`; record Slurm job ID
    5. Spawn background polling thread

  get_job(job_id) -> entry dict (status + result once terminal)
"""

import json
import logging
import os
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Optional

from jinja2 import Environment, FileSystemLoader

log = logging.getLogger(__name__)

JOBS_ROOT = Path(os.environ.get("CLUSTER_JOBS_DIR", "/home/mpiuser/cluster_jobs"))
SLURM_PARTITION = os.environ.get("SLURM_PARTITION", "all")
MPI_NP = int(os.environ.get("MPI_NP", "3"))
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL_SECONDS", "3"))

TERMINAL_STATES = {
    "COMPLETED", "FAILED", "CANCELLED", "TIMEOUT", "OUT_OF_MEMORY", "NODE_FAIL"
}

# In-memory store: job_id -> {status, slurm_job_id, workdir, submitted_at, result}
_jobs: dict = {}
_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def submit_job(payload: dict) -> str:
    """Write files, submit to Slurm, start polling thread, return job_id."""
    job_id = str(uuid.uuid4())
    workdir = JOBS_ROOT / job_id
    workdir.mkdir(parents=True, exist_ok=True)

    # Write user-supplied source code (may be absent for pure-MPI payloads)
    source_code = payload.get("source_code") or payload.get("code") or ""
    (workdir / "user_code.py").write_text(source_code, encoding="utf-8")

    # Write payload metadata (everything except source_code/code)
    meta = {k: v for k, v in payload.items() if k not in ("source_code", "code")}
    (workdir / "payload.json").write_text(
        json.dumps(meta, ensure_ascii=True), encoding="utf-8"
    )

    # Render MPI runner template
    _write_runner(workdir)

    # Write sbatch script
    timeout_seconds = int(payload.get("timeout_seconds") or 120)
    timeout_minutes = max(1, (timeout_seconds + 59) // 60 + 1)
    (workdir / "job.sh").write_text(
        _render_sbatch(job_id, workdir, timeout_minutes), encoding="utf-8"
    )

    # Submit
    proc = subprocess.run(
        ["sbatch", str(workdir / "job.sh")],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"sbatch failed (rc={proc.returncode}): "
            f"stdout={proc.stdout.strip()!r} stderr={proc.stderr.strip()!r}"
        )

    # "Submitted batch job 12345"
    slurm_job_id = proc.stdout.strip().split()[-1]
    log.info("Submitted Slurm job %s for api job %s", slurm_job_id, job_id)

    with _lock:
        _jobs[job_id] = {
            "status": "PENDING",
            "slurm_job_id": slurm_job_id,
            "workdir": str(workdir),
            "submitted_at": time.time(),
            "result": None,
        }

    threading.Thread(target=_poll_job, args=(job_id,), daemon=True).start()
    return job_id


def get_job(job_id: str) -> Optional[dict]:
    with _lock:
        entry = _jobs.get(job_id)
        return dict(entry) if entry else None


# ---------------------------------------------------------------------------
# Template helpers
# ---------------------------------------------------------------------------

def _write_runner(workdir: Path) -> None:
    template_dir = Path(__file__).parent
    env = Environment(loader=FileSystemLoader(str(template_dir)), autoescape=False)
    rendered = env.get_template("mpi_runner.py.j2").render(workdir=str(workdir))
    (workdir / "runner.py").write_text(rendered, encoding="utf-8")


OPENMPI_BIN = os.environ.get("OPENMPI_BIN", "/usr/lib64/openmpi/bin")
# Directory on shared NFS where mpi4py (and other packages) are installed
# so compute nodes without internet access can import them.
SHARED_PYLIB = os.environ.get("SHARED_PYLIB", "/srv/nfs/shared/pylib")


def _render_sbatch(job_id: str, workdir: Path, timeout_minutes: int) -> str:
    return (
        "#!/bin/bash\n"
        f"#SBATCH --job-name=coproof_{job_id[:8]}\n"
        f"#SBATCH --output={workdir}/slurm_stdout.txt\n"
        f"#SBATCH --error={workdir}/slurm_stderr.txt\n"
        f"#SBATCH --chdir={workdir}\n"
        f"#SBATCH --partition={SLURM_PARTITION}\n"
        f"#SBATCH --nodes={MPI_NP}\n"
        f"#SBATCH --ntasks={MPI_NP}\n"
        f"#SBATCH --ntasks-per-node=1\n"
        f"#SBATCH --time=00:{timeout_minutes:02d}:00\n"
        "\n"
        # Ensure OpenMPI binaries are on PATH on compute nodes
        f"export PATH={OPENMPI_BIN}:/usr/local/bin:/usr/bin:/bin:$PATH\n"
        # libmpi.so lives alongside the OpenMPI binaries
        f"export LD_LIBRARY_PATH={OPENMPI_BIN}/../lib:$LD_LIBRARY_PATH\n"
        # Shared NFS pylib makes mpi4py visible on nodes without internet
        f"export PYTHONPATH={SHARED_PYLIB}:$PYTHONPATH\n"
        f"export PMIX_MCA_gds=hash\n"
        f"cd {workdir}\n"
        f"mpirun --mca gds hash -n {MPI_NP} python3 runner.py\n"
    )


# ---------------------------------------------------------------------------
# Background polling
# ---------------------------------------------------------------------------

def _poll_job(job_id: str) -> None:
    with _lock:
        entry = _jobs.get(job_id)
    if not entry:
        return

    slurm_job_id = entry["slurm_job_id"]
    workdir = Path(entry["workdir"])

    while True:
        state = _query_slurm_state(slurm_job_id)

        with _lock:
            if job_id in _jobs:
                _jobs[job_id]["status"] = state

        if state in TERMINAL_STATES:
            result = _collect_result(slurm_job_id, workdir, state)
            with _lock:
                if job_id in _jobs:
                    _jobs[job_id]["result"] = result
                    _jobs[job_id]["status"] = state
            log.info("Job %s (Slurm %s) finished: %s", job_id, slurm_job_id, state)
            break

        time.sleep(POLL_INTERVAL)


def _query_slurm_state(slurm_job_id: str) -> str:
    """Return the current Slurm state string, upper-cased."""
    proc = subprocess.run(
        ["squeue", "-j", slurm_job_id, "-h", "-o", "%T"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    state = proc.stdout.strip().upper()

    if not state:
        # Job left the queue — confirm via sacct
        sacct = subprocess.run(
            ["sacct", "-j", slurm_job_id, "--format=State", "--noheader", "-P"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        lines = [ln.strip() for ln in sacct.stdout.splitlines() if ln.strip()]
        # sacct may return "COMPLETED" or "COMPLETED|..." per step
        state = lines[0].split("|")[0].strip().upper() if lines else "COMPLETED"

    return state


def _collect_result(slurm_job_id: str, workdir: Path, slurm_state: str) -> dict:
    """Read result.json written by the MPI runner, or build an error result."""
    stdout_text = _safe_read(workdir / "slurm_stdout.txt")
    stderr_text = _safe_read(workdir / "slurm_stderr.txt")

    result_file = workdir / "result.json"

    if slurm_state != "COMPLETED" or not result_file.exists():
        return {
            "completed": False,
            "sufficient": False,
            "evidence": None,
            "summary": None,
            "records": [],
            "stdout": stdout_text,
            "stderr": stderr_text,
            "error": f"Slurm job ended with state: {slurm_state}",
            "slurm_job_id": slurm_job_id,
            "slurm_state": slurm_state,
            "exit_code": None,
        }

    try:
        data = json.loads(result_file.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "completed": False,
            "sufficient": False,
            "evidence": None,
            "summary": None,
            "records": [],
            "stdout": stdout_text,
            "stderr": stderr_text,
            "error": f"Failed to parse result.json: {exc}",
            "slurm_job_id": slurm_job_id,
            "slurm_state": slurm_state,
            "exit_code": None,
        }

    data.setdefault("slurm_job_id", slurm_job_id)
    data.setdefault("slurm_state", slurm_state)
    return data


def _safe_read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return ""
