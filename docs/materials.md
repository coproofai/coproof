# Materials — CoProof Platform

## 1. Hardware

| Component | Specification | Role |
|---|---|---|
| Raspberry Pi 4 Model B | ARM Cortex-A72, 64-bit, ×4 units | HPC cluster (1 SMS head node + 3 compute nodes) |
| SD Cards (×4) | ≥32 GB | OS installation per node |
| Local network switch | — | Internal cluster LAN (192.168.1.0/24) |
| Development workstation | x86-64, Windows | Local development, Docker host |

---

## 2. Operating Systems

| System | Version | Usage |
|---|---|---|
| Rocky Linux | 10 (aarch64) | HPC cluster nodes |
| Ubuntu | 22.04 LTS | Lean verification Docker container base image |
| Python slim base | Debian Bookworm slim | Backend & computation Docker containers (`python:3.11-slim`) |
| Windows 11 | — | Developer host |

---

## 3. Container & Orchestration

| Tool | Version / Image | Notes |
|---|---|---|
| Docker | Current stable | Container runtime |
| Docker Compose | v2 syntax | Multi-service orchestration (`docker-compose.yml`) |
| PostgreSQL | `postgres:15-alpine` | Relational database |
| Redis | `redis:7-alpine` | Message broker, result backend, distributed cache |
| Nginx | Included in frontend image | Production static file serving |

---

## 4. Backend Python Environment (`server/`)

Runtime: **Python 3.11** (Docker container `python:3.11-slim`); **Python 3.14.3** (local `.venv` for development)

| Library | Version | Purpose |
|---|---|---|
| Flask | 3.1.3 | Web framework / application factory |
| Werkzeug | 3.1.6 | WSGI middleware, routing |
| Flask-JWT-Extended | 4.7.1 | JWT access + refresh token authentication |
| Flask-CORS | 6.0.2 | Cross-origin resource sharing |
| SQLAlchemy | 2.0.47 | ORM / database abstraction |
| Flask-SQLAlchemy | (bundled with Flask-Migrate) | SQLAlchemy integration for Flask |
| Flask-Migrate | 4.1.0 | Alembic-based schema migrations |
| psycopg2-binary | 2.9.11 | PostgreSQL adapter |
| Celery | 5.6.2 | Distributed task queue |
| redis (Python client) | 7.2.1 | Celery broker + cache backend |
| Flask-Caching | 2.3.1 | Response caching (Redis backend) |
| Flask-SocketIO | 5.6.1 | WebSocket / real-time events |
| marshmallow | 4.2.2 | Serialization / deserialization |
| flask-marshmallow | 1.4.0 | Marshmallow integration for Flask |
| marshmallow-sqlalchemy | 1.4.2 | SQLAlchemy schema generation |
| gunicorn | 25.1.0 | WSGI production server |
| gevent | 25.9.1 | Async worker class for gunicorn |
| GitPython | 3.1.46 | Programmatic Git operations (RepoPool, transactions) |
| networkx | 3.6.1 | Theorem dependency graph representation |
| pytest | 9.0.2 | Test framework |
| pytest-flask | 1.3.0 | Flask test fixtures |
| python-dotenv | (pinned in requirements.txt) | Environment variable loading |
| cryptography | (pinned in requirements.txt) | Token signing utilities |

---

## 5. Lean Verification Service (`lean/`)

Runtime: **Ubuntu 22.04** Docker container

| Component | Version / Identifier | Purpose |
|---|---|---|
| Lean 4 | Toolchain pinned via `lean-toolchain` in Mathlib4 | Formal proof verification language |
| elan | Latest (from `elan-init.sh`) | Lean toolchain version manager |
| Mathlib4 | Commit `29dcec074de168ac2bf835a77ef68bbe069194c5` | Standard mathematics library for Lean 4 |
| lake | Bundled with Lean toolchain | Lean build system and package manager |
| Celery | (see `lean/requirements.txt`) | Task worker consuming `lean_queue` |
| redis (Python client) | (see `lean/requirements.txt`) | Broker communication |
| Python 3 | System Python (Ubuntu 22.04) | Lean service wrapper (`lean_service.py`) |

Mathlib4 packages compiled and exposed via `LEAN_PATH`:
`Qq`, `aesop`, `Cli`, `importGraph`, `LeanSearchClient`, `batteries`, `proofwidgets`

---

## 6. Computation Service (`computation/`)

Runtime: **Python 3.11** (`python:3.11-slim`)

| Library | Version | Purpose |
|---|---|---|
| Celery | 5.6.2 | Task worker consuming `computation_queue` |
| redis (Python client) | 7.2.1 | Broker communication |

---

## 7. Frontend (`frontend/`)

Runtime: **Node.js** with **npm 11.8.0**

| Library | Version | Purpose |
|---|---|---|
| Angular (core, common, compiler, forms, platform-browser, router) | ^21.2.0 | SPA framework |
| @angular/cli | ^21.2.0 | Build tooling |
| TypeScript | ~5.9.2 | Static typing |
| RxJS | ~7.8.0 | Reactive programming / HTTP observables |
| tslib | ^2.3.0 | TypeScript helper runtime |
| jsdom | ^28.0.0 | DOM testing environment |
| vitest | ^4.0.8 | Unit test runner |
| prettier | ^3.8.1 | Code formatter |

---

## 8. HPC Cluster Software Stack

| Software | Notes |
|---|---|
| OpenHPC | HPC provisioning and management layer over Rocky Linux 10 |
| SLURM | Workload manager for job scheduling across compute nodes |
| OpenMPI | MPI implementation for distributed computation |
| DNSMASQ + TFTP | PXE/network boot for diskless compute node provisioning |
| NFS | Shared filesystem between SMS and compute nodes |
| Balena Etcher | Image flashing utility for SD card preparation |

---

## 9. External Services & Integrations

| Service | Usage |
|---|---|
| GitHub OAuth 2.0 | User authentication; scopes: `repo`, `read:user`, `user:email` |
| GitHub REST API v3 | Repository creation, file commits, pull request workflow, webhook push events |
| LeanDojo | Source of benchmark theorems (100-theorem evaluation set) |

---

## 10. Datasets

| Dataset | Description |
|---|---|
| LeanDojo benchmark (subset) | 100 theorems sourced from Mathlib4 via LeanDojo; fields: `full_name`, `file_path`, `url`, `commit`, `traced_tactics` |
| GitHub-fetched Lean sources | Raw `.lean` files fetched from the public Mathlib4 GitHub repository at specific commits |
| Benchmark results (`benchmark_results_20251127_124045.{json,csv}`) | Verification outcomes for 100 theorems: 96 verified, 4 timeouts (60 s limit); avg. API latency 8.42 s, avg. processing time 8.31 s |

---

## 11. Development & Testing Tools

| Tool | Version | Purpose |
|---|---|---|
| pytest-mock | (pinned in requirements.txt) | Mock objects for unit tests |
| black | (pinned in requirements.txt) | Python code formatter |
| flake8 | (pinned in requirements.txt) | Python linter |
| Alembic | (via Flask-Migrate 4.1.0) | Database migration engine |
| matplotlib | (benchmark script `benchmark200.py`) | Benchmark latency distribution plots |
| numpy | (benchmark script `benchmark200.py`) | Numerical processing in benchmark |
