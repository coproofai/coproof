# Cluster Computation Worker — Implementation Plan

## Context

The project already has a `computation` Celery worker that runs user-supplied Python code in
isolated subprocesses and returns a normalized result (`completed`, `sufficient`, `evidence`,
`summary`, `records`, `stdout`, `stderr`).

The goal is to add a **second, parallel computation backend** that targets a physical
Raspberry Pi cluster (1 manager + 3 compute nodes) running **Slurm + OpenMPI**, while
producing the exact same result schema so the rest of the platform is unaffected.

---

## High-Level Architecture

```
[Docker stack – main network]
  ├── web (Flask/SocketIO)
  ├── redis
  ├── computation-worker          ← existing, unchanged
  └── cluster-computation-worker  ← NEW Celery worker
          │
          │  HTTP REST (LAN)
          ▼
  [RPI Manager node  192.168.x.x]
  └── cluster_api  (Flask REST service, systemd unit)
          │
          │  sbatch / squeue / scontrol
          ▼
  [Slurm controller (same RPI or dedicated)]
  └── 3× RPI compute nodes  (OpenMPI jobs)
```

The Celery worker on the Docker side **never SSH's directly**; it speaks HTTP to a lightweight
REST API that lives on the manager node. This keeps credentials out of containers and makes the
cluster independently testable.

---

## Result Schema Contract

Both backends must return this dict (identical to current `computation_service.py`):

```python
{
    "completed": bool,
    "sufficient": bool,
    "evidence": any,
    "summary": str | None,
    "records": list,
    "stdout": str,
    "stderr": str,
    "error": str | None,
    "processing_time_seconds": float,
    # cluster-specific extras (ignored by platform, useful for debugging):
    "slurm_job_id": str | None,
    "slurm_state": str | None,
    "exit_code": int | None,
}
```

---

## File Map

### A — On the RPI Manager Node (copy manually)

```
~/cluster_api/
  app.py                  Flask REST API entry-point
  job_manager.py          Slurm submission, polling, result collection
  mpi_runner.py.j2        Jinja2 template: wraps user code for MPI execution
  requirements.txt
  setup.sh                One-shot setup script (venv, systemd unit)
  systemd/
    cluster_api.service   systemd unit file
```

### B — In the Main Repository

```
cluster_computation/
  celery_service.py       Celery app, listens to cluster_computation_queue
  computation_service.py  HTTP client → RPI API; same interface as computation/
  tasks.py                Celery task: run_cluster_computation
  requirements.txt
  Dockerfile
```

### C — Root Changes

```
docker-compose.yml        Add cluster-computation-worker service
server/config.py          Add CLUSTER_API_URL env var (consumed by web if needed)
```

---

## Implementation Steps

### Step 1 — RPI Manager: REST API (`cluster_api/`)

**`app.py`**  
Flask app exposing:

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/jobs` | Submit a new computation job; returns `{"job_id": "..."}` |
| `GET`  | `/jobs/<job_id>` | Poll status; returns full result once finished |
| `GET`  | `/health` | Liveness check |

Authentication: shared secret via `X-API-Key` header (set in env var `CLUSTER_API_KEY`).

**`job_manager.py`**  
- Writes user code + payload to a temp working directory under `/tmp/cluster_jobs/<job_id>/`
- Renders `mpi_runner.py.j2` with the user code embedded → `runner.py`
- Writes an `sbatch` script that calls `mpirun -n <np> python runner.py`
- Submits with `subprocess.run(["sbatch", "job.sh"])` → captures Slurm job ID
- Polls `squeue -j <job_id> -h -o %T` until terminal state
- On completion: reads `result.json` written by the runner, returns normalized dict
- Cleans up temp dir after result is collected (configurable TTL)

**`mpi_runner.py.j2`** (Jinja2 template)  
- Each MPI rank runs the user entrypoint with a slice of `input_data`
- Rank 0 gathers all partial results, normalizes, writes `result.json`
- Captures stdout/stderr per-rank, merges into single strings

**`setup.sh`**  
- Creates venv, installs deps, writes and enables the systemd unit

---

### Step 2 — Main Repo: Celery Worker (`cluster_computation/`)

**`computation_service.py`**  
- `run_cluster_job(payload)` — mirrors `run_python_job()` in `computation/`
- POSTs payload to `CLUSTER_API_URL/jobs` with API key header
- Polls `/jobs/<job_id>` with backoff (max `timeout_seconds`)
- Returns normalized result dict (with `slurm_*` extras)

**`celery_service.py`**  
- Listens on `cluster_computation_queue` (separate from `computation_queue`)

**`tasks.py`**  
- `run_cluster_computation(payload)` — same signature as `run_computation`

---

### Step 3 — docker-compose.yml

Add `cluster-computation-worker` service:
- Built from `./cluster_computation`
- Env: `REDIS_URL`, `CLUSTER_API_URL`, `CLUSTER_API_KEY`
- No dependency on the RPI being reachable at startup (worker will fail individual tasks, not crash)

---

### Step 4 — Server Integration

The `web` service already dispatches to `computation_queue` when `language == "python"`.
To route to the cluster instead, the caller can pass `language: "mpi"` (or a future
`backend: "cluster"` field). Add a dispatch branch in the server's task routing:

```python
if language == "mpi":
    celery.send_task("tasks.run_cluster_computation", args=[payload],
                     queue="cluster_computation_queue")
else:
    celery.send_task("tasks.run_computation", args=[payload],
                     queue="computation_queue")
```

This keeps both workers hot and lets the platform choose per-job.

---

## Security Notes

- The REST API on the manager node is LAN-only; do not expose it to the internet.
- Use `X-API-Key` with a strong random secret stored in `.env` / systemd `EnvironmentFile`.
- User-supplied code runs in a Slurm job under a restricted OS user (`slurm_runner`), not root.
- Working directories are isolated per job ID (UUID4); no cross-job file access.
- Slurm job time-limit (`--time`) acts as a hard kill switch independent of the Python timeout.

---

## Open Decisions (to confirm before coding)

| # | Question | Default assumption |
|---|----------|--------------------|
| 1 | Number of MPI ranks to request per job? | `np = 3` (one per compute node) |
| 2 | Partition name in Slurm? | `all` |
| 3 | Static IP / hostname of manager node? | Set via `CLUSTER_API_URL` env var |
| 4 | Port for the REST API? | `8765` |
| 5 | Should the web server be able to choose the backend per-request, or per-project? | Per-request (`language` field) |
| 6 | MPI framework already installed on RPIs? | OpenMPI 4.x via `apt` |
| 7 | Slurm already configured and `sbatch` working? | Yes (user confirmed) |
