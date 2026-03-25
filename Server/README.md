# Local Development Setup & GitHub Authentication

This guide shows how to run the app locally with Docker, handle migrations, authenticate with GitHub, and test project & node creation.

---

## 1. Prerequisites

- Docker & Docker Compose installed
- Python 3.11+ (optional for local scripts)
- GitHub OAuth credentials
- PowerShell (or any shell capable of running `irm` / `Invoke-RestMethod`)

---

## 2. Clone the repository

```bash
git clone https://github.com/your-org/your-repo.git
cd your-repo
````

---

## 3. Configure environment variables

Create `.env` or set in Docker Compose:

```env
FLASK_ENV=development
DATABASE_URL=postgresql://coproof:coproofpass@db:5432/coproof_db
REDIS_URL=redis://redis:6379/0
CELERY_LEAN_QUEUE=lean_queue
CELERY_COMPUTATION_QUEUE=computation_queue
CELERY_GIT_ENGINE_QUEUE=git_engine_queue
GITHUB_CLIENT_ID=<your-client-id>
GITHUB_CLIENT_SECRET=<your-client-secret>
GITHUB_REDIRECT_URI=<optional-callback-url>
JWT_SECRET_KEY=<some-secret>
SECRET_KEY=<some-secret>
```

`GITHUB_REDIRECT_URI` is optional. If omitted, GitHub uses the callback URL configured in your OAuth App settings.

---

## 4. Start Docker containers

```bash
docker-compose up -d --build
```

* `web` → Flask API
* `celery_worker` → Async tasks
* `db` → PostgreSQL
* `redis` → Redis broker
* `lean-worker` → Lean verification Celery worker (`lean_queue`)
* `computation-worker` → Generic computation Celery worker (`computation_queue`)

The backend talks to Lean and computation workers through Redis/Celery (`REDIS_URL`) by dispatching tasks to `lean_queue` and `computation_queue`.

---

## 5. Initialize the database

```bash
docker-compose exec web flask db upgrade
```

* Creates all tables.
* Migration scripts (`migrations/versions/`) are tracked in Git.

---

## 6. Start Celery worker

```bash
docker-compose exec celery_worker celery -A celery_worker.celery worker -Q git_engine_queue --loglevel=info
```

* Needed for async Git tasks like commits or cloning.

---

## 7. GitHub Authentication (Local / Headless)

Since local callback URLs are not reachable by GitHub, follow these steps manually:

### 7.1 Get the GitHub OAuth URL

Hit the endpoint:

```powershell
irm -Method GET -Uri "http://localhost:5001/api/v1/auth/github/url" | ConvertTo-Json
```

* Copy the returned URL and open it in your browser.
* Authorize your app.
* GitHub will redirect to a **callback URL that is currently unreachable locally**, but the URL will contain a `code` query parameter.

### 7.2 Exchange `code` for JWT tokens

Copy the `code` from the URL, then run:

```powershell
irm -Method POST -Uri "http://localhost:5001/api/v1/auth/github/callback" `
  -Headers @{ "Content-Type" = "application/json" } `
  -Body '{ "code": "GITHUB_CODE_FROM_BROWSER" }' | ConvertTo-Json | Out-File -Encoding utf8 respuesta.json
```

* This returns a JSON file with:

  * `access_token` → for API requests
  * `refresh_token` → to refresh expired tokens

### 7.3 Refresh the access token if expired

```powershell
$refresh_token = (Get-Content .\respuesta.json | ConvertFrom-Json).refresh_token
irm -Method POST -Uri "http://localhost:5001/api/v1/auth/refresh" `
  -Headers @{ "Authorization" = "Bearer $refresh_token" } `
  | ConvertTo-Json -Depth 10 | Out-File -Encoding utf8 refreshed.json
```

* Use `refreshed.json.access_token` for future requests.

---

## 8. Create a new project

```powershell
access_token = (Get-Content .\respuesta.json | ConvertFrom-Json).access_token
irm -Method POST -Uri "http://localhost:5001/api/v1/projects" `
  -Headers @{
      "Authorization" = "Bearer $access_token"
      "Content-Type"  = "application/json"
  } `
  -Body '{ "name":"Algebraic Topology", "description":"A study on simplicial complexes", "visibility":"private" }'$
```

* Returns the `project_id` for subsequent operations.

---

## 9. Add / Commit a file (node) to a branch

```powershell
irm -Method POST -Uri "http://localhost:5001/api/v1/projects/PROJECT_ID/nodes" `
  -Headers @{
      "Authorization" = "Bearer $access_token"
      "Content-Type"  = "application/json"
  } `
  -Body '{ 
      "file_path": "src/first_theorem.lean", 
      "content": "theorem hello_world (a b : Nat) : a + b = b + a := by apply Nat.add_comm", 
      "branch": "main" 
  }'
```

* The backend handles the Git commit + push via Celery tasks.
* No knowledge of Git is needed on the frontend.

---

## Notes / Recommendations

* **Migrations**: Commit scripts in `migrations/versions/`. Never commit DB data.
* **Celery**: Must be running for async Git operations.
* **GitHub OAuth**: Local dev requires manual code copy due to callback URL restrictions.
* **Access / Refresh Tokens**: Always refresh access token if expired.
* **Branches**: Consider using per-user branch locks for collaborative `.latex` editing.
* **Feature workflow**: Each developer works in their own branch. Project owner merges `.latex` branches into main.

## Computation node contract

Computation nodes are backed by a Lean file in the project tree, but their truth value is produced by the computation worker.

`POST /api/v1/nodes/<project_id>/<node_id>/compute`

Expected JSON payload:

```json
{
  "language": "python",
  "code": "def run(input_data, target):\n    return {\"evidence\": {...}, \"sufficient\": True}\n",
  "entrypoint": "run",
  "input_data": {},
  "target": {"kind": "range_check", "description": "..."},
  "lean_statement": "GoalDef"
}
```

The worker currently supports Python entrypoints with the signature `run(input_data, target)`. The return value must be either:

```python
{"evidence": <json-serializable>, "sufficient": <bool>}
```

or a two-item tuple/list `(evidence, sufficient)`.

On a sufficient result, the backend writes artifacts in the node folder and opens a PR:

* `main.lean` → Lean-consumable theorem wrapper for the computation result
* `computation.py` → computation program submitted by the client
* `evidence.json` → summary evidence, hashes and artifact pointers
* `evidence_full.json.gz.b64` → full computation payload compressed with gzip and encoded in base64
* `evidence_records.csv.gz.b64` → full per-record dataset in CSV format, compressed with gzip and encoded in base64 (if `records` are provided)

To inspect compressed artifacts locally:

```python
import base64, gzip, pathlib

text = pathlib.Path("evidence_full.json.gz.b64").read_text(encoding="utf-8").strip()
raw = base64.b64decode(text)
decoded = gzip.decompress(raw).decode("utf-8")
print(decoded[:1000])
```

---

## Lean roundtrip smoke test (terminal)

This checks the full path:

`Client script -> Backend API -> Lean worker (Celery) -> Backend API -> Client script`

It uses a development-only endpoint: `POST /api/v1/projects/tools/verify-snippet/public`.
No user registration/login is required for this smoke test.

From `server/` run:

```powershell
./scripts/lean_roundtrip_demo.ps1
```

Optional custom backend URL:

```powershell
./scripts/lean_roundtrip_demo.ps1 -BackendUrl http://localhost:5001
```

---
