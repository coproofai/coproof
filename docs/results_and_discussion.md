# CoProof — Results and Discussion

**Project:** CoProof — Collaborative Formal Theorem Proving Platform  
**Team:** David López 22310432, Daniel Tejeda 22310431, Emiliano Flores 22110044  
**Date:** April 27, 2026

---

## 1. Results

### 1.1 Lean Verification Service — Benchmark

A benchmark of 100 theorems drawn from the Mathlib4 library was executed against the Lean verification service on November 27, 2025.

| Metric | Value |
|---|---|
| Total theorems submitted | 100 |
| Theorems with tactics | 48 |
| Theorems without tactics | 52 |
| Successful verifications | 96 |
| Failed verifications | 4 |
| Verified (Lean return code 0) | 96 |
| Mock proofs used | 0 |
| Total fetch time (s) | 97.90 |
| Total API latency (s) | 808.17 |
| Total API processing time (s) | 797.29 |
| Average fetch time per theorem (s) | 1.02 |
| Average API latency per theorem (s) | 8.42 |
| Average API processing time per theorem (s) | 8.31 |

All 4 failures were caused by request timeouts (`api_latency = 35.0 s`). No failure was due to a Lean compilation error in the benchmark inputs.

---

### 1.2 System Architecture — Implemented Services

The platform was delivered as a Docker Compose stack. The following services were implemented and containerised:

| Service | Technology | Role |
|---|---|---|
| `web` | Flask + SocketIO | Backend API + real-time notifications |
| `celery_worker` | Celery + Redis | Git engine and general async tasks |
| `lean-worker` | Celery + Lean 4 (elan) | Formal verification |
| `nl2fl-worker` | Celery + OpenRouter API | Natural language → Lean translation |
| `agents-worker` | Celery + OpenRouter API | LLM suggestion primitive |
| `computation-worker` | Celery + Python subprocess | Sandboxed numeric computation |
| `frontend` | Angular 21 + Nginx | Single-page application |
| `db` | PostgreSQL | Relational index and metadata |
| `redis` | Redis | Task queue broker + Redlock |

The entire stack is started with a single command (`docker compose up --build`).

---

### 1.3 Backend — Implementation Phases Completed

The backend was built across six sequential phases:

| Phase | Scope |
|---|---|
| 1 | Application factory, configuration, Docker stack, error handling |
| 2 | PostgreSQL schema and SQLAlchemy models (`User`, `NewProject`, `NewNode`) |
| 3 | Stateless Git engine with LRU `RepoPool` and Redis Redlock concurrency control |
| 4 | Domain service layer (`ProjectService`, `AuthService`, `CompilerClient`, graph engine) |
| 5 | RESTful API blueprints (auth, projects, nodes, agents, webhooks) |
| 6 | Asynchronous Celery tasks and GitHub webhook reindexation |

---

### 1.4 Features Delivered

| Feature | Status |
|---|---|
| GitHub OAuth 2.0 authentication (JWT pair) | Delivered |
| Project creation with pre-compilation gate | Delivered |
| DAG-based proof graph (root node, split, solve) | Delivered |
| Lean verification worker (Ubuntu 22.04, Mathlib4 pinned) | Delivered |
| Collaborative PR workflow via GitHub REST API | Delivered |
| Webhook-triggered asynchronous reindexation | Delivered |
| NL2FL translation pipeline (LLM + retry loop with Lean feedback) | Delivered |
| AI suggestion microservice (one-shot LLM prompt) | Delivered |
| Computation nodes (Python sandbox + evidence embedding in Lean) | Delivered |
| LaTeX inline viewer in the frontend | Delivered |
| Angular workspace view with DAG rendering | Delivered |
| CI pipeline (GitHub Actions — backend pytest + frontend Vitest + production build) | Delivered |
| Per-user encrypted API key storage for LLM providers | Delivered |

---

### 1.5 Continuous Integration Pipeline

The CI pipeline executes two parallel jobs on every push to `main` or `develop` and on every pull request:

| Job | Steps |
|---|---|
| `build` (backend) | `docker compose build` → `pytest tests/ -v` against live PostgreSQL → `docker compose down -v` |
| `frontend` | `npm ci` → `ng test --configuration=ci` (Vitest) → `ng build --configuration=production` |

Average CI run time observed: under 5 minutes from push to result.

---

### 1.6 Development Process Metrics

| Metric | Value |
|---|---|
| Team size | 3 members |
| Total sprints | 3 (one-week each) + 1 feature-freeze/testing week |
| Backend implementation phases | 6 |
| Branching model | `feature/<desc>` / `fix/<desc>` → PR → `main` |
| Branch protection | Direct push to `main` blocked; CI green + 1 approved review required |
| Bug tracking | GitHub Issues with priority labels (`priority:high`, `priority:low`) |
| Build reproducibility | One command on a clean machine |

---

### 1.7 Joel Test Self-Assessment

Each of the 12 Joel Test criteria was evaluated and documented in `docs/spolsky-plan.md`. The following table records the binary outcome per criterion at the time of evaluation (April 2026):

| # | Criterion | Status |
|---|---|---|
| 1 | Source control | ✅ |
| 2 | One-step build | ✅ |
| 3 | Daily builds (CI) | ✅ |
| 4 | Bug database | ✅ |
| 5 | Fix bugs before new code | ✅ |
| 6 | Up-to-date schedule | ✅ |
| 7 | Spec before code | ✅ |
| 8 | Quiet working conditions | ✅ |
| 9 | Best tools money can buy | ✅ |
| 10 | Testers | ✅ |
| 11 | Interviews include coding exercises | ✅ |
| 12 | Hallway usability testing | ✅ |

---

## 2. Discussion

### 2.1 Lean Verification Performance

The 96 % success rate on the Mathlib4 benchmark confirms that the Lean worker is operationally sound for the expected workload. All four failures shared the same root cause: API latency exceeding the 35-second timeout threshold, not a correctness defect in the verification logic. The average processing time of 8.3 seconds per theorem is consistent with Lean 4 compilation times for medium-complexity theorems against a pre-compiled Mathlib4 environment. The absence of any mock proofs in the benchmark ensures that the numbers reflect real verification against actual Lean source.

The timeout failures highlight a structural tension: theorems with long tactic chains can exceed the wall-clock budget that is acceptable for a synchronous API response. The current architecture mitigates this by placing Lean tasks in a Celery queue and polling from the frontend, but the 45-second backend client timeout still acts as a hard ceiling. For the project's current scope — user-submitted leaf-node proofs that are expected to be short and targeted — this ceiling is adequate. It becomes a limitation for goals drawn from deeper layers of Mathlib.

### 2.2 Architecture: Git as Source of Truth

Using GitHub as the authoritative content store and PostgreSQL as a fast relational index is the most consequential architectural decision in the system. It enables the platform to provide a collaborative PR-based workflow without building a custom version control system, and it ensures that the Lean source remains auditable, fork-able, and independent of the platform's database. The tradeoff is operational complexity: every write operation that touches file content must execute a multi-step Git transaction (clone → worktree → reset → write → commit → push → clean), protected by a Redis Redlock to prevent concurrent corruption.

In practice, the transaction latency is acceptable for the expected concurrency of an academic collaboration tool. The LRU `RepoPool` cache of bare clones in `/tmp` reduces redundant GitHub API calls significantly. However, at higher concurrency levels the Redlock becomes a serialisation bottleneck per project. A future optimisation would be to allow read operations (node listing, state queries) to bypass the Git layer entirely — which is already partially achieved by the PostgreSQL index — while reserving Git transactions exclusively for write paths.

### 2.3 NL2FL Pipeline and LLM Integration

The natural language to formal language pipeline introduces a non-deterministic element into an otherwise deterministic verification chain. The retry loop that feeds Lean error messages back to the LLM as context improves translation quality but does not guarantee convergence. Empirically, the quality of the Lean output depends heavily on the LLM's prior exposure to Lean 4 syntax and Mathlib idioms. Models with stronger Lean coverage (e.g., those exposed to Lean corpora during training) produce far fewer syntactic errors in the first pass, reducing the number of retries needed.

The decision to store per-user API keys encrypted (AES-256-GCM) rather than using a shared platform key gives users full control over their LLM provider and model selection, and eliminates the platform's liability for API usage costs. The tradeoff is that the user must obtain and manage their own keys, which adds friction for first-time users.

### 2.4 Computation Nodes

The computation node feature introduces a hybrid formal/empirical proof model: a Python program produces numerical evidence, and that evidence is embedded as a concrete Lean definition replacing an axiom placeholder. This is a non-standard use of Lean's type system — the "proof" of the axiom is not a derivation but a datum — and its soundness depends entirely on the correctness of the Python computation. The platform does not currently verify that the embedded evidence value is consistent with the axiomatic claim it replaces; that responsibility rests with the user.

This feature is most appropriate for theorems that have a computational witness (e.g., a specific counterexample does not exist up to a given bound, or a numerical bound has been verified empirically). It is not a substitute for formal proof and is architecturally separated from the verification path to make this distinction explicit.

### 2.5 Development Process

The spec-first, phase-gated approach produced a backend that was internally consistent and largely defect-free before frontend integration began. Committing architecture documents before implementation forced early resolution of interface contracts (API shapes, model schemas, service boundaries) and reduced the number of late-stage integration surprises. The Joel Test served as a process audit tool rather than a goal in itself: every criterion that passed had a concrete artefact to point to, rather than being a nominal checkbox.

The three-sprint frontend integration cadence was tight relative to the scope. Several features (LaTeX viewer, computation node UI, AI suggestion UX) required non-trivial Angular component work that compressed the available testing time. The feature freeze at April 30 provides a buffer, but future projects of similar scope would benefit from a longer frontend integration phase or earlier parallelisation of backend and frontend work.

### 2.6 Known Limitations

- **Lean timeout ceiling (45 s):** Complex theorems drawing heavily on Mathlib tactics may consistently hit the timeout. There is no mechanism to automatically increase the budget per-node based on historical verification times.
- **Single-branch collaboration model:** Each contributor works on independent feature branches but there is no built-in conflict resolution for simultaneous edits to the same node. The Redlock prevents corruption but does not mediate concurrent intent — last write wins at the Git level.
- **Computation sandbox isolation:** The Python subprocess for computation nodes runs in the container's process space. There is no network isolation, resource cap enforcement, or time limit beyond the Celery task timeout. A malicious or poorly written computation payload could exhaust container resources.
- **LLM non-determinism in NL2FL:** Identical natural-language inputs may produce different Lean outputs across calls. There is no caching layer for translation results, so two users translating the same statement may trigger duplicate LLM calls.
- **No offline mode:** The platform requires live GitHub API access for all write operations. A GitHub API outage prevents any proof editing, even for projects whose content is already locally cached.

### 2.7 Future Work

The following extensions are identified as high-value next steps, ordered by estimated impact:

1. **Adaptive Lean timeout per node.** Instrument the verification worker to record per-theorem compile times and expose a node-level timeout configuration. Nodes that historically require long compilations could be given a higher budget, while simple leaf nodes retain the fast timeout.

2. **Proof suggestion with tactic-level LLM integration.** The current agents microservice provides a one-shot natural-language suggestion. Integrating a tactic-aware model (e.g., one fine-tuned on Lean 4 proof states) and wiring it to the node's current Lean goal state would transform the suggestion service into a step-by-step proof assistant rather than a general text generator.

3. **Conflict resolution for concurrent node edits.** Introduce an optimistic lock on nodes (version counter in PostgreSQL) so that a solve or split operation that arrives after a concurrent modification receives a conflict error rather than silently overwriting work. Expose a merge-conflict resolution UI in the frontend.

4. **Computation node sandboxing.** Replace the bare subprocess execution with a container-in-container or `nsjail`/`gVisor` sandbox that enforces CPU, memory, and network limits. This is required before the platform can be opened to untrusted users.

5. **Persistent NL2FL translation cache.** Hash the (model, input statement, retry count) tuple and cache successful translations in Redis or PostgreSQL. This eliminates redundant LLM calls for shared theorems and reduces per-user API key consumption.

6. **Export and reproducibility bundle.** Provide a one-click export of any fully validated project as a self-contained Lean 4 package (`lakefile.lean` + all `.lean` sources + `Definitions.lean`) that can be compiled independently of the platform. This ensures long-term reproducibility of results.

7. **HPC / Slurm computation backend.** The `computation` worker currently executes Python locally in the container. The planned MPI + Slurm integration (`docs/CoProof_LeanEnabling.md`, `docs/ClusterEnabling.md`) would allow large-scale numerical computations to be dispatched to an external HPC cluster, extending the types of computational evidence the platform can produce.

8. **Public project discovery and forking.** Currently, project search is limited to projects the authenticated user belongs to. A public project index with read-only access and a fork operation (creating a new GitHub repository from the source project's content) would enable community-driven theorem development.

9. **Multi-language formal verification backends.** The verification layer is tightly coupled to Lean 4. Abstracting the `CompilerClient` to support alternative backends (Coq, Isabelle/HOL, Agda) would broaden the platform's applicability without requiring a full architectural rewrite.

10. **Real-time collaborative editing.** SocketIO infrastructure is already present in the backend. Extending it to broadcast node-state changes and lock-acquisition events to all connected collaborators in real time would eliminate the need for manual refresh and improve the collaborative experience significantly.
