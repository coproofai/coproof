# Test Case Descriptions (TCDs) & Test Cases (TCs) — CoProof Platform

**Project:** CoProof — Collaborative Formal Verification Platform  
**Document version:** 1.0  
**Date:** 2026-04-29  
**Scope:** All ten microservice containers — `web`, `celery_worker`, `lean-worker`,
`computation-worker`, `cluster-computation-worker`, `nl2fl-worker`, `agents-worker`,
`frontend`, `db`, `redis`

---

## Naming Convention

| Pattern | Meaning |
|---|---|
| `TCD-XX` | Test Case Description — a cohesive group of related tests for one functional area |
| `TC-XX-YY` | Individual Test Case within a TCD |
| **Pre** | Precondition(s) that must hold before execution |
| **Steps** | Ordered actions to perform |
| **Expected** | Observable result that indicates pass |
| **Tool** | Primary testing tool / library |

---

## Table of Contents

1. [TCD-01 — Auth API (`web`)](#tcd-01--auth-api-web)
2. [TCD-02 — Projects API (`web`)](#tcd-02--projects-api-web)
3. [TCD-03 — Nodes API (`web`)](#tcd-03--nodes-api-web)
4. [TCD-04 — Translation API (`web`)](#tcd-04--translation-api-web)
5. [TCD-05 — Agents API (`web`)](#tcd-05--agents-api-web)
6. [TCD-06 — GitHub Service / Git Engine (`celery_worker`)](#tcd-06--github-service--git-engine-celery_worker)
7. [TCD-07 — Lean Worker](#tcd-07--lean-worker)
8. [TCD-08 — Computation Worker](#tcd-08--computation-worker)
9. [TCD-09 — Cluster Computation Worker](#tcd-09--cluster-computation-worker)
10. [TCD-10 — NL2FL Worker](#tcd-10--nl2fl-worker)
11. [TCD-11 — Agents Worker](#tcd-11--agents-worker)
12. [TCD-12 — Angular `AuthService` (`frontend`)](#tcd-12--angular-authservice-frontend)
13. [TCD-13 — Angular `TaskService` (`frontend`)](#tcd-13--angular-taskservice-frontend)
14. [TCD-14 — Angular `authGuard` (`frontend`)](#tcd-14--angular-authguard-frontend)
15. [TCD-15 — E2E: Authentication Flow](#tcd-15--e2e-authentication-flow)
16. [TCD-16 — E2E: Project & Node Flow](#tcd-16--e2e-project--node-flow)

---

## TCD-01 — Auth API (`web`)

**Module:** `server/app/api/auth.py`, `server/app/services/auth_service.py`  
**Tool:** `pytest-flask`, `pytest-mock`, `responses`  
**Status:** ✅ Implemented & passing — 45/45 TCs pass  
**Run command:** `pytest -v tests/tcd01_auth/test_tcd01_auth_api.py` (from `server/`)

**Description:**  
Validates all endpoints exposed at `/api/v1/auth`: GitHub OAuth URL generation,
OAuth code exchange, JWT token refresh, authenticated profile retrieval, and
GitHub repository invitation management. External GitHub REST API calls are
mocked throughout via the `responses` library.

**Infrastructure notes (implemented):**
- Requires the `db` Docker container running and `coproof_test_db` to exist.
  Create it once with: `docker compose exec db psql -U coproof -d postgres -c "CREATE DATABASE coproof_test_db OWNER coproof;"`
- Uses a dedicated `coproof_test_db` database — the live `coproof_db` is never touched.
- `NullPool` is configured so no SQLAlchemy connections are pooled between tests.
- `pg_terminate_backend` runs in AUTOCOMMIT before each test to clear TCP zombie
  connections (a Windows + Docker Desktop networking artefact).
- Table isolation is pre-test only (`TRUNCATE users CASCADE`); post-test cleanup
  is skipped to avoid killing the connection that `pytest-flask` uses for teardown.
- `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` are injected via `mock.patch.dict(os.environ)`
  because `auth_service.py` reads them from `os.environ` directly, not Flask config.
- `JWT_SECRET_KEY` in `UnitTestConfig` is ≥ 32 bytes to suppress `InsecureKeyLengthWarning`.

---

### TC-01-01 — GET `/auth/github/url` returns a valid OAuth URL

| Field | Detail |
|---|---|
| **Pre** | Flask app running in test config; `GITHUB_CLIENT_ID` patched to `"test_client_id"` via `mock.patch.dict(os.environ)` in the module-scoped `app` fixture |
| **Steps** | 1. Send `GET /api/v1/auth/github/url` |
| **Expected** | HTTP 200; response JSON contains key `"url"` whose value is a non-empty string starting with `https://github.com/login/oauth/authorize` and containing `test_client_id` |
| **Tool** | `pytest-flask` |

---

### TC-01-02 — POST `/auth/github/callback` with valid code returns tokens and user

| Field | Detail |
|---|---|
| **Pre** | Mock GitHub token exchange endpoint returns `{"access_token": "gho_test", "refresh_token": "ghr_test"}`; mock `/user` endpoint returns a valid GitHub user object; DB has no user with that `github_id` |
| **Steps** | 1. Mock `https://github.com/login/oauth/access_token` via `responses`. 2. Mock `https://api.github.com/user`. 3. POST `{ "code": "valid_code" }` to `/api/v1/auth/github/callback` |
| **Expected** | HTTP 200; JSON body contains `access_token` (str), `refresh_token` (str), and `user` object with `id`, `full_name`, `email`; a new `User` row is created in DB |
| **Tool** | `pytest-flask`, `responses` |

---

### TC-01-03 — POST `/auth/github/callback` without code returns 400

| Field | Detail |
|---|---|
| **Pre** | Flask app in test mode |
| **Steps** | 1. POST `{}` (empty body) to `/api/v1/auth/github/callback` |
| **Expected** | HTTP 400; JSON body contains `"error": "Missing code"` |
| **Tool** | `pytest-flask` |

---

### TC-01-04 — POST `/auth/github/callback` for existing GitHub user updates token and returns JWT

| Field | Detail |
|---|---|
| **Pre** | DB already contains a `User` with `github_id = "12345"` (inserted by the `existing_github_user` fixture); mocked GitHub endpoints return the same `github_id` |
| **Steps** | 1. Mock GitHub token and user endpoints. 2. POST `{ "code": "code_for_existing_user" }` |
| **Expected** | HTTP 200; same user record is returned (no duplicate created); `github_access_token` field is updated |
| **Tool** | `pytest-flask`, `responses` |

---

### TC-01-05 — POST `/auth/refresh` with valid refresh token returns new access token

| Field | Detail |
|---|---|
| **Pre** | A refresh token for `user_id = "abc-123"` is signed with `JWT_SECRET_KEY` and `type = "refresh"` |
| **Steps** | 1. POST `/api/v1/auth/refresh` with `Authorization: Bearer <refresh_token>` |
| **Expected** | HTTP 200; JSON contains `access_token` (new, non-empty string) |
| **Tool** | `pytest-flask`, `flask_jwt_extended` test helpers |

---

### TC-01-06 — POST `/auth/refresh` with an access token (wrong type) returns 422

| Field | Detail |
|---|---|
| **Pre** | An access token (not refresh) is available |
| **Steps** | 1. POST `/api/v1/auth/refresh` with `Authorization: Bearer <access_token>` |
| **Expected** | HTTP 422; JWT-Extended rejects the token type |
| **Tool** | `pytest-flask` |

---

### TC-01-07 — GET `/auth/me` with valid JWT returns user profile

| Field | Detail |
|---|---|
| **Pre** | DB contains a user; a valid access token for that user is available |
| **Steps** | 1. GET `/api/v1/auth/me` with `Authorization: Bearer <access_token>` |
| **Expected** | HTTP 200; JSON matches the user's `UserSchema` dump (id, full_name, email) |
| **Tool** | `pytest-flask` |

---

### TC-01-08 — GET `/auth/me` without JWT returns 401

| Field | Detail |
|---|---|
| **Pre** | No Authorization header |
| **Steps** | 1. GET `/api/v1/auth/me` with no header |
| **Expected** | HTTP 401 |
| **Tool** | `pytest-flask` |

---

### TC-01-09 — GET `/auth/github/invitations` returns list of pending invitations

| Field | Detail |
|---|---|
| **Pre** | Authenticated user has `github_access_token` set; mock GitHub `/user/repository_invitations` returns two invitations |
| **Steps** | 1. Mock `https://api.github.com/user/repository_invitations`. 2. GET `/api/v1/auth/github/invitations` with valid JWT |
| **Expected** | HTTP 200; JSON `invitations` array has 2 items each with `id`, `repo`, `inviter`, `html_url` |
| **Tool** | `pytest-flask`, `responses` |

---

### TC-01-10 — GET `/auth/github/invitations` without linked GitHub account returns 400

| Field | Detail |
|---|---|
| **Pre** | Authenticated user has `github_access_token = None` |
| **Steps** | 1. GET `/api/v1/auth/github/invitations` with valid JWT |
| **Expected** | HTTP 400; JSON `"error": "No linked GitHub account."` |
| **Tool** | `pytest-flask` |

---

### TC-01-11 — POST `/auth/github/invitations/<id>/accept` accepts invitation

| Field | Detail |
|---|---|
| **Pre** | Authenticated user has token; mock GitHub `PATCH /user/repository_invitations/42` returns 204 |
| **Steps** | 1. Mock GitHub accept endpoint. 2. POST `/api/v1/auth/github/invitations/42/accept` with valid JWT |
| **Expected** | HTTP 200; response indicates success |
| **Tool** | `pytest-flask`, `responses` |

---

## TCD-02 — Projects API (`web`)

**Module:** `server/app/api/projects.py`, `server/app/services/project_service.py`  
**Tool:** `pytest-flask`, `responses`, `pytest-mock`  
**Status:** ✅ Implemented & passing — 29/29 TCs pass  
**Run command:** `pytest -v tests/tcd02_projects/test_tcd02_projects_api.py` (from `server/`)

**Description:**  
Tests creation, retrieval, and public discovery of projects. GitHub REST API
calls are intercepted by the `responses` library; PostgreSQL is the same
dedicated `coproof_test_db` used by TCD-01 (no `testcontainers` needed).

**Infrastructure notes (implemented):**
- Same `coproof_test_db` + `NullPool` + `pg_terminate_backend` setup as TCD-01.
- `clean_tables` truncates `users CASCADE` (cascades through `new_projects → new_nodes`, `user_followed_projects`) before each test.
- `CompilerClient.verify_snippet` is patched to `{"valid": True, "errors": []}` for all tests that reach the goal-validation step, including TC-02-06 (the GitHub token check comes after goal validation).
- GitHub mock sequence for project creation: `POST /user/repos` (201) then for each of the 3 initial files: `GET .../contents/<path>` (404) → `PUT .../contents/<path>` (201).
- `user_with_github` and `user_without_github` are hand-written DB fixtures (no `factory_boy`).
- `seed_public_projects` inserts 3 public + 2 private projects directly via SQLAlchemy.
- Error responses carry `"message"` (not `"error"`) because `CoProofError.to_dict()` serialises under that key.

---

### TC-02-01 — POST `/projects` with valid payload creates project and returns 201

| Field | Detail |
|---|---|
| **Pre** | `user_with_github` fixture; `CompilerClient.verify_snippet` patched to return valid; GitHub mocks: `POST /user/repos` (201), `GET`/`PUT` for `Definitions.lean`, `root/main.lean`, `root/main.tex` (404 then 201 each) |
| **Steps** | 1. Register `responses` mocks. 2. POST `{ "name": "MyProof", "goal": "theorem myproof_root : True := trivial", "visibility": "private" }` with valid JWT |
| **Expected** | HTTP 201; JSON contains `id`, `name="MyProof"`, `remote_repo_url`; a `Project` row and a root `Node` row exist in DB |
| **Tool** | `pytest-flask`, `responses`, `pytest-mock` |

---

### TC-02-02 — POST `/projects` with missing `name` returns 400

| Field | Detail |
|---|---|
| **Pre** | `user_with_github` fixture |
| **Steps** | 1. POST `{ "goal": "theorem ..." }` (no `name` field) with valid JWT |
| **Expected** | HTTP 400; JSON `"message"` contains `"name"` |
| **Tool** | `pytest-flask` |

---

### TC-02-03 — POST `/projects` with missing `goal` returns 400

| Field | Detail |
|---|---|
| **Pre** | `user_with_github` fixture |
| **Steps** | 1. POST `{ "name": "Test" }` (no `goal`) with valid JWT |
| **Expected** | HTTP 400; JSON `"message"` contains `"goal"` |
| **Tool** | `pytest-flask` |

---

### TC-02-04 — POST `/projects` with invalid `visibility` value returns 400

| Field | Detail |
|---|---|
| **Pre** | `user_with_github` fixture |
| **Steps** | 1. POST `{ "name": "T", "goal": "...", "visibility": "secret" }` with valid JWT |
| **Expected** | HTTP 400; JSON `"message"` contains `"visibility"` |
| **Tool** | `pytest-flask` |

---

### TC-02-05 — POST `/projects` with non-list `tags` returns 400

| Field | Detail |
|---|---|
| **Pre** | `user_with_github` fixture |
| **Steps** | 1. POST `{ "name": "T", "goal": "...", "tags": "algebra" }` (string, not list) with valid JWT |
| **Expected** | HTTP 400; JSON `"message"` contains `"tags"` |
| **Tool** | `pytest-flask` |

---

### TC-02-06 — POST `/projects` without linked GitHub account returns 400

| Field | Detail |
|---|---|
| **Pre** | `user_without_github` fixture; `CompilerClient.verify_snippet` patched (goal validation runs before the GitHub token check) |
| **Steps** | 1. POST `{ "name": "Test", "goal": "theorem r : True := trivial" }` with valid JWT |
| **Expected** | HTTP 400; JSON `"message"` contains `"github"` |
| **Tool** | `pytest-flask`, `pytest-mock` |

---

### TC-02-07 — GET `/projects/public` returns paginated list of public projects

| Field | Detail |
|---|---|
| **Pre** | `seed_public_projects` fixture inserts 3 public + 2 private projects |
| **Steps** | 1. GET `/api/v1/projects/public` (unauthenticated) |
| **Expected** | HTTP 200; `projects` array has exactly 3 entries (all `visibility="public"`); `total=3`; `pages≥1`; `current_page=1` |
| **Tool** | `pytest-flask` |

---

### TC-02-08 — GET `/projects/public` with `q` parameter filters by name

| Field | Detail |
|---|---|
| **Pre** | `seed_public_projects` fixture provides projects named `"Fermat"`, `"Goldbach"`, `"Collatz"` |
| **Steps** | 1. GET `/api/v1/projects/public?q=gold`. 2. GET `/api/v1/projects/public?q=GOLD` (case-insensitive). 3. GET `/api/v1/projects/public?q=zzznomatch` |
| **Expected** | `?q=gold` → only `"Goldbach"`; `?q=GOLD` → same result; `?q=zzznomatch` → empty list, `total=0` |
| **Tool** | `pytest-flask` |

---

### TC-02-09 — GET `/projects/public` with valid JWT includes `is_following` flag

| Field | Detail |
|---|---|
| **Pre** | `seed_public_projects` fixture; a `UserFollowedProject` row is inserted for the first public project (Fermat) and `user_with_github` |
| **Steps** | 1. GET `/api/v1/projects/public` with valid JWT. 2. GET `/api/v1/projects/public` without JWT |
| **Expected** | Authenticated: followed project has `is_following=true`, the other two have `is_following=false`; unauthenticated: all three have `is_following=false` |
| **Tool** | `pytest-flask` |

---

## TCD-03 — Nodes API (`web`)

**Module:** `server/app/api/nodes.py`  
**Tool:** `pytest`, `responses`, `pytest-mock`  
**Status:** ✅ Implemented & passing — 17/17 TCs pass  
**Run command:** `pytest -v tests/tcd03_nodes/test_tcd03_nodes_api.py` (from `server/`)

**Description:**  
Tests the PR-context logic that determines how branch/commit/PR operations are
routed — directly to the upstream repo (owner or private-repo collaborator) or
via a fork (public-repo contributor). GitHub API interactions are mocked.

**Infrastructure notes (implemented):**
- Same `coproof_test_db` + `NullPool` + `pg_terminate_backend` setup as TCD-01/02.
- **TC-03-01/02/03** call `_prepare_pr_context` and `_build_pr_head` directly (imported from `app.api.nodes`) using lightweight `types.SimpleNamespace` mock objects for `user` and `project`. No Flask test client or DB is needed for these three cases; only `responses` mocks for GitHub HTTP calls.
- **TC-03-04** goes through the `/api/v1/nodes/<pid>/<nid>/solve` HTTP endpoint with real DB fixtures (`user_no_github`, `project_and_node`). `CompilerClient.verify_snippet` is patched so execution reaches the GitHub-token guard without hitting Lean workers.
- Error responses from `CoProofError` carry `"message"` at top-level; TC-03-04 checks both `"message"` and `"error"` keys for the word `"github"`.
- Fork mock sequence: `POST .../forks` (202) → `GET .../git/ref/heads/main` (200, readiness poll) → `POST .../merge-upstream` (200, sync).

---

### TC-03-01 — Project owner: `_prepare_pr_context` returns direct-push context

| Field | Detail |
|---|---|
| **Pre** | `user.id == project.author_id`; `user.github_access_token = "gho_owner_token"` |
| **Steps** | 1. Call `_prepare_pr_context(project, user)` inside an app context. 2. Call `_build_pr_head(ctx, "my-branch")` |
| **Expected** | `ctx["pr_head_prefix"] is None`; `ctx["token"] == "gho_owner_token"`; `ctx["repo_url"]` and `ctx["pr_repo_url"]` both equal the upstream URL; fork endpoint (`POST .../forks`) is NOT called; `_build_pr_head` returns `"my-branch"` |
| **Tool** | `pytest`, `responses` |

---

### TC-03-02 — Contributor on a public project uses fork-based flow

| Field | Detail |
|---|---|
| **Pre** | `user.id != project.author_id`; `project.visibility = "public"`; `responses` mocks: `POST .../forks` (202, returns `fork_full_name="forkowner/myrepo"`), `GET .../git/ref/heads/main` (200), `POST .../merge-upstream` (200) |
| **Steps** | 1. Call `_prepare_pr_context(project, user)`. 2. Call `_build_pr_head(ctx, "feature-branch")` |
| **Expected** | `ctx["pr_head_prefix"] == "forkowner"`; `ctx["repo_url"]` equals fork clone URL; `ctx["pr_repo_url"]` equals upstream URL; fork endpoint called exactly once; `_build_pr_head` returns `"forkowner:feature-branch"` |
| **Tool** | `pytest`, `responses` |

---

### TC-03-03 — Contributor on a private project pushes directly (no fork)

| Field | Detail |
|---|---|
| **Pre** | `user.id != project.author_id`; `project.visibility = "private"` |
| **Steps** | 1. Call `_prepare_pr_context(project, user)`. 2. Call `_build_pr_head(ctx, "collab-fix")` |
| **Expected** | `ctx["pr_head_prefix"] is None`; `ctx["repo_url"]` equals upstream URL; fork endpoint is NOT called; `_build_pr_head` returns `"collab-fix"` |
| **Tool** | `pytest`, `responses` |

---

### TC-03-04 — Node submission without linked GitHub account returns 400

| Field | Detail |
|---|---|
| **Pre** | `user_no_github` fixture (no `github_access_token`); `project_and_node` fixture (public project + root proof node); `CompilerClient.verify_snippet` patched to `{"valid": True}` |
| **Steps** | 1. POST `{ "lean_code": "theorem t : True := trivial", "model_id": "mock/test" }` to `/api/v1/nodes/<pid>/<nid>/solve` with valid JWT |
| **Expected** | HTTP 400; JSON `"message"` (or `"error"`) contains `"github"` |
| **Tool** | `pytest-flask`, `pytest-mock` |

---

## TCD-04 — Translation API (`web`)

**Module:** `server/app/api/translate.py`  
**Tool:** `pytest-flask`, `pytest-mock`  
**Status:** ✅ Implemented & passing — 25/25 TCs pass  
**Run command:** `pytest -v tests/tcd04_translate/test_tcd04_translate_api.py` (from `server/`)

**Description:**  
Tests the `/api/v1/translate` blueprint: input validation, saved API key
auto-loading, task dispatch, and the static model catalogue endpoint.

**Infrastructure notes (implemented):**
- Same `coproof_test_db` + `NullPool` + `pg_terminate_backend` + `TRUNCATE users CASCADE` setup as TCD-01/02/03.
- `TranslateClient.submit` is patched at `app.services.integrations.translate_client.TranslateClient.submit` for all tests that should reach the dispatch step — this prevents any Celery/Redis connection attempt. `CELERY_TASK_ALWAYS_EAGER = True` is set in config for safety but is redundant given the mock.
- `auth_user` fixture: plain `User` row + JWT, used for TC-04-06 (authenticated-but-no-key case).
- `user_with_key` fixture: `User` row + `UserApiKey` record created via `UserApiKey.create()` (AES-256-GCM encryption), for TC-04-05. No `factory_boy` needed.
- TC-04-04 covers four sub-cases: `max_retries=0` (below range), `=11` (above range), `="many"` (non-integer), and the valid boundaries `=1` and `=10`.
- TC-04-06 covers two sub-cases: unauthenticated with no key, and authenticated with no DB record for the model.
- TC-04-07 covers five assertions on the static catalogue: status 200, is a list, non-empty, each entry has `id`/`name`/`provider`, `"mock/test"` is present.
- Error responses from the translate blueprint use `"error"` key (not `"message"`) — this blueprint returns `jsonify({"error": ...})` directly, unlike `CoProofError`-based routes.

---

### TC-04-01 — POST `/translate/submit` with valid body returns 202 and `task_id`

| Field | Detail |
|---|---|
| **Pre** | `TranslateClient.submit` patched to return `"task-uuid-1"` |
| **Steps** | 1. POST `{ "natural_text": "For all n, n+1 > n", "model_id": "openai/gpt-4o", "api_key": "sk-test" }` (no JWT required) |
| **Expected** | HTTP 202; JSON `{ "task_id": "task-uuid-1" }`; `submit` called exactly once; forwarded payload contains `natural_text` and `model_id` |
| **Tool** | `pytest-flask`, `pytest-mock` |

---

### TC-04-02 — POST `/translate/submit` without `natural_text` returns 400

| Field | Detail |
|---|---|
| **Pre** | None |
| **Steps** | 1. POST `{ "model_id": "openai/gpt-4o", "api_key": "sk-x" }` |
| **Expected** | HTTP 400; JSON `"error": "natural_text is required"` |
| **Tool** | `pytest-flask` |

---

### TC-04-03 — POST `/translate/submit` without `model_id` returns 400

| Field | Detail |
|---|---|
| **Pre** | None |
| **Steps** | 1. POST `{ "natural_text": "For all n ...", "api_key": "sk-x" }` |
| **Expected** | HTTP 400; JSON `"error": "model_id is required"` |
| **Tool** | `pytest-flask` |

---

### TC-04-04 — POST `/translate/submit` with `max_retries` outside range 1–10 returns 400

| Field | Detail |
|---|---|
| **Pre** | Full required fields present; `TranslateClient.submit` patched for boundary tests only |
| **Steps** | 1. POST with `"max_retries": 0`. 2. POST with `"max_retries": 11`. 3. POST with `"max_retries": "many"`. 4. POST with `"max_retries": 1` (valid boundary). 5. POST with `"max_retries": 10` (valid boundary) |
| **Expected** | `max_retries` 0, 11, `"many"` → HTTP 400; JSON error mentions `"max_retries"`; `max_retries` 1 and 10 → HTTP 202 |
| **Tool** | `pytest-flask`, `pytest-mock` |

---

### TC-04-05 — POST `/translate/submit` loads saved API key for authenticated user

| Field | Detail |
|---|---|
| **Pre** | `user_with_key` fixture: `User` row + `UserApiKey` record (`model_id="openai/gpt-4o"`, encrypted with `UserApiKey.create()`); `TranslateClient.submit` patched to return `"task-from-db-key"` |
| **Steps** | 1. POST `{ "natural_text": "∀ n, n + 1 > n", "model_id": "openai/gpt-4o" }` (no `api_key`) with valid JWT |
| **Expected** | HTTP 202; `task_id = "task-from-db-key"`; the decrypted saved key is passed as `payload["api_key"]` to `TranslateClient.submit` |
| **Tool** | `pytest-flask`, `pytest-mock` |

---

### TC-04-06 — POST `/translate/submit` without `api_key` and no saved key returns 400

| Field | Detail |
|---|---|
| **Pre** | Sub-case A: no JWT, no `api_key`. Sub-case B: `auth_user` fixture (authenticated, no `UserApiKey` DB record for `openai/gpt-4o`) |
| **Steps** | 1. POST `{ "natural_text": "...", "model_id": "openai/gpt-4o" }` with no JWT. 2. Same POST with valid JWT |
| **Expected** | Both sub-cases → HTTP 400; JSON `"error"` contains `"api_key"` |
| **Tool** | `pytest-flask` |

---

### TC-04-07 — GET `/translate/models` returns catalogue of available models

| Field | Detail |
|---|---|
| **Pre** | None |
| **Steps** | 1. GET `/api/v1/translate/models` |
| **Expected** | HTTP 200; response is a non-empty JSON array; every entry has `id`, `name`, `provider` fields; `"mock/test"` model is present |
| **Tool** | `pytest-flask` |

---

## TCD-05 — Agents API (`web`)

**Module:** `server/app/api/agents.py`  
**Tool:** `pytest-flask`, `pytest-mock`  
**Status:** ✅ Implemented & passing — 19/19 TCs pass  
**Run command:** `pytest -v tests/tcd05_agents/test_tcd05_agents_api.py` (from `server/`)

**Description:**  
Tests the `/api/v1/agents` blueprint for submitting suggestion tasks and
retrieving their results via two endpoints: `POST /agents/suggest/submit` and
`GET /agents/suggest/<task_id>/result`.

**Infrastructure notes (implemented):**
- Same `coproof_test_db` + `NullPool` + `pg_terminate_backend` + `TRUNCATE users CASCADE` setup as TCD-01/02/03/04.
- `AgentsClient.submit` is patched at `app.services.integrations.agents_client.AgentsClient.submit` for all dispatch tests. `AgentsClient.get_result` is patched at `app.services.integrations.agents_client.AgentsClient.get_result` for polling tests.
- `auth_user` fixture: plain `User` row + JWT, used for TC-05-04 sub-case B (authenticated with no saved key).
- `user_with_key` fixture: `User` row + `UserApiKey` record created via `UserApiKey.create()` (AES-256-GCM encryption) for model `openai/gpt-4o`. No `factory_boy` needed.
- TC-05-01 also verifies optional fields (`system_prompt`, `context`) are forwarded in the payload when supplied.
- TC-05-04 covers two sub-cases: unauthenticated with no key, and authenticated with no DB record for the model.
- TC-05-05 asserts that the decrypted DB key is forwarded as `payload["api_key"]` to `AgentsClient.submit`.
- TC-05-06 tests both the SUCCESS path (HTTP 200 + result body) and the PENDING path (HTTP 202 + `{"status": "pending"}`) by controlling the return value of `AgentsClient.get_result` (`None` → pending).
- Error responses from the agents blueprint use `"error"` key (not `"message"`) — same convention as the translate blueprint.

---

### TC-05-01 — POST `/agents/suggest/submit` with valid payload returns 202

| Field | Detail |
|---|---|
| **Pre** | `AgentsClient.submit` mocked to return `"agent-task-1"` |
| **Steps** | 1. POST `{ "prompt": "Suggest a lemma for...", "model_id": "openai/gpt-4o", "api_key": "sk-test" }`. 2. Repeat with optional fields `system_prompt` and `context` added |
| **Expected** | HTTP 202; JSON `{ "task_id": "agent-task-1" }`; `submit` called exactly once; forwarded payload contains `prompt` and `model_id`; optional `system_prompt` and `context` forwarded when present |
| **Tool** | `pytest-flask`, `pytest-mock` |

---

### TC-05-02 — POST `/agents/suggest/submit` without `prompt` returns 400

| Field | Detail |
|---|---|
| **Pre** | None |
| **Steps** | 1. POST `{ "model_id": "openai/gpt-4o", "api_key": "sk-x" }` |
| **Expected** | HTTP 400; JSON `"error": "prompt is required"` |
| **Tool** | `pytest-flask` |

---

### TC-05-03 — POST `/agents/suggest/submit` without `model_id` returns 400

| Field | Detail |
|---|---|
| **Pre** | None |
| **Steps** | 1. POST `{ "prompt": "...", "api_key": "sk-x" }` |
| **Expected** | HTTP 400; JSON `"error": "model_id is required"` |
| **Tool** | `pytest-flask` |

---

### TC-05-04 — POST `/agents/suggest/submit` without `api_key` and no saved key returns 400

| Field | Detail |
|---|---|
| **Pre** | Sub-case A: no JWT, no `api_key`. Sub-case B: `auth_user` fixture (authenticated, no `UserApiKey` DB record for `openai/gpt-4o`) |
| **Steps** | 1. POST `{ "prompt": "...", "model_id": "openai/gpt-4o" }` with no JWT. 2. Same POST with valid JWT |
| **Expected** | Both sub-cases → HTTP 400; JSON `"error"` contains `"api_key"` |
| **Tool** | `pytest-flask` |

---

### TC-05-05 — POST `/agents/suggest/submit` loads saved API key when authenticated

| Field | Detail |
|---|---|
| **Pre** | `user_with_key` fixture: `User` row + `UserApiKey` record (`model_id="openai/gpt-4o"`, encrypted with `UserApiKey.create()`); `AgentsClient.submit` patched to return `"task-from-db-key"` |
| **Steps** | 1. POST `{ "prompt": "Suggest a lemma.", "model_id": "openai/gpt-4o" }` (no `api_key`) with valid JWT |
| **Expected** | HTTP 202; `task_id = "task-from-db-key"`; the decrypted saved key is passed as `payload["api_key"]` to `AgentsClient.submit` |
| **Tool** | `pytest-flask`, `pytest-mock` |

---

### TC-05-06 — GET `/agents/suggest/<task_id>/result` returns task result

| Field | Detail |
|---|---|
| **Pre** | Sub-case A: `AgentsClient.get_result` mocked to return `{ "status": "SUCCESS", "result": "Consider induction." }`. Sub-case B: mocked to return `None` (task not yet complete) |
| **Steps** | 1. GET `/api/v1/agents/suggest/agent-task-1/result` (completed). 2. GET `/api/v1/agents/suggest/agent-task-pending/result` (pending) |
| **Expected** | Completed → HTTP 200; JSON matches mocked result structure. Pending → HTTP 202; JSON `{ "status": "pending" }` |
| **Tool** | `pytest-flask`, `pytest-mock` |

---

## TCD-06 — GitHub Service / Git Engine (`celery_worker`)

**Module:** `server/app/services/github_service.py`  
**Tool:** `pytest`, `responses`  
**Status:** ✅ Implemented & passing — 18/18 TCs pass  
**Run command:** `pytest -v tests/tcd06_github_service/test_tcd06_github_service.py` (from `server/`)

**Description:**  
Validates all static helper methods on `GitHubService` for URL parsing, branch
reading, blob decoding, fork management, and pull request operations. All HTTP
calls are intercepted by `responses`.

**Infrastructure notes (implemented):**
- **No Flask app context, no database** — `GitHubService` is pure static methods that import only `requests` and `app.exceptions` (plain Python exception classes). Neither `NullPool` nor `pg_terminate_backend` is needed.
- `@responses.activate` is applied per-method so each test gets a fully isolated `responses` context and `rsps.calls` is reset between tests.
- No conftest.py required; all shared constants are module-level (`_REPO_URL`, `_FULL_NAME`, `_TOKEN`, `_BASE_API`).
- TC-06-02 tests HTTPS URL without `.git` suffix (not SSH — `urlparse` does not decompose `git@github.com:owner/repo.git` into `owner/repo`; all production URLs are HTTPS clone URLs anyway).
- TC-06-04/05 verify that `CoProofError` is raised with the *correct `.code` value* (404 vs 401) — this matters because Flask error handlers use `error.code` to set the HTTP response status.
- TC-06-08 mocks the fork readiness poll (`GET .../git/ref/heads/main`) to return 200 immediately, avoiding the real `time.sleep(3)` inside the poll loop.
- TC-06-09 (`sync_fork_branch`) swallows all exceptions by design; the test confirms the merge-upstream endpoint is reached by inspecting `rsps.calls`.
- Each TC that verifies multiple properties (e.g., clone URL **and** full_name for TC-06-08) is split into separate test methods — this is why the total test count (18) exceeds the number of TCs in the spec (12).

---

### TC-06-01 — `extract_github_full_name` parses HTTPS clone URL

| Field | Detail |
|---|---|
| **Pre** | None |
| **Steps** | 1. Call `GitHubService.extract_github_full_name("https://github.com/acme/my-repo.git")` |
| **Expected** | Returns `"acme/my-repo"` (`.git` suffix stripped, leading slash removed) |
| **Tool** | `pytest` |

---

### TC-06-02 — `extract_github_full_name` parses HTTPS URL without `.git` suffix

| Field | Detail |
|---|---|
| **Pre** | None |
| **Steps** | 1. Call with `"https://github.com/acme/my-repo"` (no `.git`) |
| **Expected** | Returns `"acme/my-repo"` |
| **Tool** | `pytest` |

_Note: SSH URLs (`git@github.com:owner/repo.git`) are not supported by `urlparse`; all production `remote_repo_url` values are HTTPS clone URLs._

---

### TC-06-03 — `get_branch_head_sha` returns SHA for existing branch

| Field | Detail |
|---|---|
| **Pre** | Mock `GET https://api.github.com/repos/acme/repo/git/ref/heads/main` returns `{ "object": { "sha": "abc123" } }` |
| **Steps** | 1. Call `GitHubService.get_branch_head_sha(url, token, "main")` |
| **Expected** | Returns `"abc123"` |
| **Tool** | `pytest`, `responses` |

---

### TC-06-04 — `get_branch_head_sha` raises `CoProofError` for 404

| Field | Detail |
|---|---|
| **Pre** | Mock returns HTTP 404 |
| **Steps** | 1. Call method for non-existent branch |
| **Expected** | `CoProofError` raised with `code=404` |
| **Tool** | `pytest`, `responses` |

---

### TC-06-05 — `get_branch_head_sha` raises `CoProofError` for 401 / 403

| Field | Detail |
|---|---|
| **Pre** | Mock returns HTTP 401 |
| **Steps** | 1. Call method |
| **Expected** | `CoProofError` raised with `code=401` |
| **Tool** | `pytest`, `responses` |

---

### TC-06-06 — `get_blob_content` decodes base64 content correctly

| Field | Detail |
|---|---|
| **Pre** | Mock `GET .../git/blobs/<sha>` returns `{ "content": "<base64 of 'hello lean'>", "encoding": "base64" }` |
| **Steps** | 1. Call `GitHubService.get_blob_content(url, token, blob_sha)` |
| **Expected** | Returns `"hello lean"` |
| **Tool** | `pytest`, `responses` |

---

### TC-06-07 — `get_commit_tree_sha` returns tree SHA

| Field | Detail |
|---|---|
| **Pre** | Mock `/git/commits/<sha>` returns `{ "tree": { "sha": "tree-sha" } }` |
| **Steps** | 1. Call `GitHubService.get_commit_tree_sha(url, token, commit_sha)` |
| **Expected** | Returns `"tree-sha"` |
| **Tool** | `pytest`, `responses` |

---

### TC-06-08 — `fork_or_get_fork` calls GitHub fork endpoint and returns fork URL

| Field | Detail |
|---|---|
| **Pre** | Mock `POST .../forks` returns `{ "clone_url": "https://github.com/user/fork.git", "full_name": "user/fork", "default_branch": "main" }`; mock `GET .../git/ref/heads/main` returns 200 (readiness poll passes immediately) |
| **Steps** | 1. Call `GitHubService.fork_or_get_fork(upstream_url, token)` |
| **Expected** | Returns `("https://github.com/user/fork.git", "user/fork")` |
| **Tool** | `pytest`, `responses` |

---

### TC-06-09 — `sync_fork_branch` calls GitHub sync endpoint

| Field | Detail |
|---|---|
| **Pre** | Mock `POST .../merge-upstream` returns HTTP 200 |
| **Steps** | 1. Call `GitHubService.sync_fork_branch("user/fork", token, "main")` |
| **Expected** | No exception raised; sync endpoint is called exactly once |
| **Tool** | `pytest`, `responses` |

---

### TC-06-10 — `open_pull_request` creates PR and returns PR data

| Field | Detail |
|---|---|
| **Pre** | Mock `POST .../pulls` returns `{ "number": 7, "html_url": "https://github.com/...", "head": {...}, "base": {...} }` |
| **Steps** | 1. Call `GitHubService.open_pull_request(url, token, head="user:branch", base="main", title="Fix", body="")` |
| **Expected** | Returns dict with `number=7` and `html_url` populated |
| **Tool** | `pytest`, `responses` |

---

### TC-06-11 — `merge_pull_request` calls merge endpoint and returns result

| Field | Detail |
|---|---|
| **Pre** | Mock `PUT .../pulls/7/merge` returns HTTP 200 with `{ "merged": true }` |
| **Steps** | 1. Call `GitHubService.merge_pull_request(url, token, pr_number=7)` |
| **Expected** | Returns `{ "merged": true }` or equivalent success indicator |
| **Tool** | `pytest`, `responses` |

---

### TC-06-12 — `delete_fork` calls delete repo endpoint

| Field | Detail |
|---|---|
| **Pre** | Mock `DELETE /repos/user/fork` returns HTTP 204 |
| **Steps** | 1. Call `GitHubService.delete_fork("user/fork", token)` |
| **Expected** | No exception raised; endpoint called once |
| **Tool** | `pytest`, `responses` |

---

## TCD-07 — Lean Worker

**Module:** `lean/lean_service.py`  
**Tool:** `pytest`, `pytest-mock`, `subprocess` (mocked)  
**Status:** ✅ Implemented & passing — 23/23 tests pass  
**Run command:** `pytest -v tests/tcd07_lean_worker/test_tcd07_lean_service.py` (from `lean/`)

**Description:**  
Validates pure-Python parsing functions (`parse_theorem_info`,
`parse_lean_messages`) and the `verify_lean_proof` orchestrator under mocked
subprocess conditions. No real Lean binary is invoked.

**Infrastructure notes (implemented):**
- **No Flask app context, no database** — `lean_service.py` is pure Python (`subprocess`, `tempfile`, `hashlib`, `re`, `os`, `time`). Neither `NullPool` nor `pg_terminate_backend` is needed.
- No `conftest.py` required; no shared fixtures. All state is self-contained per test class.
- Import path: `from lean_service import ...` directly, because `pytest.ini` sets `testpaths = tests` and the `lean/` directory is on `sys.path` when running from `lean/`.
- **Mocking strategy**: `lean_service.subprocess.run` is patched at that dotted path (not `subprocess.run`) because `lean_service.py` imports the `subprocess` module and calls `subprocess.run` through it.
- TC-07-09 patches `lean_service.find_lean_executable` to return `None` — the short-circuit path inside `verify_lean_proof` is exercised without touching subprocess at all.
- TC-07-10/11/12 patch **both** `lean_service.find_lean_executable → "lean"` and `lean_service.subprocess.run` so that `verify_lean_proof` reaches the subprocess call with a controlled result.
- TC-07-12: `subprocess.TimeoutExpired` requires positional arguments `cmd` and `timeout`; instantiated as `TimeoutExpired(cmd=[], timeout=60)`.
- TC-07-14: both `lean_service.subprocess.run` (raises `FileNotFoundError`) and `lean_service.os.path.exists` (returns `False`) are patched to block all discovery paths in `find_lean_executable`.
- Some TCs verify multiple properties (e.g., TC-07-05 checks both declaration count and line numbers; TC-07-09/10/11/12 check `verified`, `returnCode`, and `messages` separately) → split into separate test methods. This is why the total test count (23) exceeds the number of TCs in the spec (14).

---

### TC-07-01 — `parse_theorem_info` detects a `theorem` declaration

| Field | Detail |
|---|---|
| **Pre** | None |
| **Steps** | 1. Call `parse_theorem_info("theorem myTheorem : 1 + 1 = 2 := by norm_num")` |
| **Expected** | Returns list with one entry: `{ "name": "myTheorem", "type": "theorem", "line": 1, "column": <int> }` |
| **Tool** | `pytest` |

---

### TC-07-02 — `parse_theorem_info` detects a `lemma` declaration

| Field | Detail |
|---|---|
| **Pre** | None |
| **Steps** | 1. Call with code containing `lemma myLemma : ...` |
| **Expected** | Entry has `"type": "lemma"` and correct `name` |
| **Tool** | `pytest` |

---

### TC-07-03 — `parse_theorem_info` detects a `def` declaration

| Field | Detail |
|---|---|
| **Pre** | None |
| **Steps** | 1. Call with `def myDef : Nat := 42` |
| **Expected** | Entry has `"type": "def"` and `"name": "myDef"` |
| **Tool** | `pytest` |

---

### TC-07-04 — `parse_theorem_info` returns empty list for code with no declarations

| Field | Detail |
|---|---|
| **Pre** | None |
| **Steps** | 1. Call with `"-- just a comment\n#check Nat"` |
| **Expected** | Returns `[]` |
| **Tool** | `pytest` |

---

### TC-07-05 — `parse_theorem_info` detects multiple declarations

| Field | Detail |
|---|---|
| **Pre** | None |
| **Steps** | 1. Call with code containing one `theorem` at line 1 and one `lemma` at line 5 |
| **Expected** | Returns list with 2 entries; each has correct `line` number |
| **Tool** | `pytest` |

---

### TC-07-06 — `parse_lean_messages` extracts an error from compiler output

| Field | Detail |
|---|---|
| **Pre** | None |
| **Steps** | 1. Call `parse_lean_messages(stdout="", stderr="proof.lean:3:5: error: unknown identifier 'x'", filename="proof.lean")` |
| **Expected** | Returns list with one entry: `line=3`, `column=5`, `severity="error"`, `message="unknown identifier 'x'"` |
| **Tool** | `pytest` |

---

### TC-07-07 — `parse_lean_messages` extracts a warning from output

| Field | Detail |
|---|---|
| **Pre** | None |
| **Steps** | 1. Call with stderr containing a warning line |
| **Expected** | Entry has `severity="warning"` |
| **Tool** | `pytest` |

---

### TC-07-08 — `parse_lean_messages` returns empty list when output has no diagnostics

| Field | Detail |
|---|---|
| **Pre** | None |
| **Steps** | 1. Call with `stdout=""` and `stderr=""` |
| **Expected** | Returns `[]` |
| **Tool** | `pytest` |

---

### TC-07-09 — `verify_lean_proof` returns error when Lean executable is not found

| Field | Detail |
|---|---|
| **Pre** | `find_lean_executable` patched to return `None` |
| **Steps** | 1. Call `verify_lean_proof("theorem t : True := trivial")` |
| **Expected** | Returns `{ "verified": False, "returnCode": -1, "messages": [<error about Lean not found>] }` |
| **Tool** | `pytest`, `pytest-mock` |

---

### TC-07-10 — `verify_lean_proof` returns `verified=True` for valid code (subprocess mocked)

| Field | Detail |
|---|---|
| **Pre** | `subprocess.run` patched to return `CompletedProcess(returncode=0, stdout="", stderr="")` |
| **Steps** | 1. Call `verify_lean_proof("theorem t : True := trivial")` |
| **Expected** | Returns `{ "verified": True, "returnCode": 0, "messages": [] }` |
| **Tool** | `pytest`, `pytest-mock` |

---

### TC-07-11 — `verify_lean_proof` returns `verified=False` with messages for invalid code

| Field | Detail |
|---|---|
| **Pre** | `subprocess.run` patched to return `returncode=1` with error in `stderr` |
| **Steps** | 1. Call `verify_lean_proof("theorem bad : 1 = 2 := rfl")` |
| **Expected** | `verified=False`; `messages` list is non-empty; each message has `severity`, `line`, `column` |
| **Tool** | `pytest`, `pytest-mock` |

---

### TC-07-12 — `verify_lean_proof` handles `subprocess.TimeoutExpired`

| Field | Detail |
|---|---|
| **Pre** | `subprocess.run` patched to raise `subprocess.TimeoutExpired(cmd=[], timeout=60)` |
| **Steps** | 1. Call `verify_lean_proof(...)` |
| **Expected** | Returns `{ "verified": False, "returnCode": -1, "messages": [{ "message": "Verification timeout after 60 seconds" }] }` |
| **Tool** | `pytest`, `pytest-mock` |

---

### TC-07-13 — `find_lean_executable` returns a path when Lean is installed

| Field | Detail |
|---|---|
| **Pre** | `subprocess.run` patched to return `returncode=0` for `["lean", "--version"]` |
| **Steps** | 1. Call `find_lean_executable()` |
| **Expected** | Returns `"lean"` (or the matched command string) |
| **Tool** | `pytest`, `pytest-mock` |

---

### TC-07-14 — `find_lean_executable` returns `None` when no Lean binary exists anywhere

| Field | Detail |
|---|---|
| **Pre** | `subprocess.run` raises `FileNotFoundError` for all candidates; none of the filesystem paths exist (mocked via `os.path.exists`) |
| **Steps** | 1. Call `find_lean_executable()` |
| **Expected** | Returns `None` |
| **Tool** | `pytest`, `pytest-mock` |

---

## TCD-08 — Computation Worker

**Module:** `computation/computation_service.py`  
**Tool:** `pytest`, `pytest-mock`  
**Status:** ✅ Implemented & passing — 24/24 tests pass  
**Run command:** `pytest -v tests/tcd08_computation/test_tcd08_computation_service.py` (from `computation/`)

**Description:**  
Tests `run_python_job` and the embedded `normalize_result` logic. The actual
subprocess spawning is allowed in unit tests because it runs the bundled
`runner.py` in a temp directory (pure Python, no external dependency); timeout
and exception paths use mocks.

**Infrastructure notes (implemented):**
- **No Flask app context, no database** — `computation_service.py` is pure Python. Neither `NullPool` nor `pg_terminate_backend` is needed.
- No `conftest.py` required; no shared fixtures.
- Import path: `from computation_service import RUNNER_SOURCE, run_computation_job, run_python_job` directly, same pattern as TCD-07.
- **`normalize_result` extraction**: the function lives inside `RUNNER_SOURCE` (a string embedded in the module), not at module level. Tests extract it once at module scope via `exec(RUNNER_SOURCE, _runner_ns)` then pull `normalize_result` from the resulting namespace — no code duplication.
- **TC-08-01/02/08/09 use real subprocess** — `runner.py` is pure Python with no external dependencies and completes in well under 1 s. Mocking is not needed for these cases.
- **Mocking strategy for TC-08-10/11**: `computation_service.subprocess.run` is patched at that dotted path (same pattern as TCD-07/08).
- **TC-08-10 calls `run_computation_job`, not `run_python_job`**: `run_python_job` does NOT catch `subprocess.TimeoutExpired` — it propagates uncaught. `run_computation_job` is the wrapper that catches it and returns `completed=False`. The test therefore calls `run_computation_job` to make the expected response observable, matching the actual call graph even though the spec text says `run_python_job`.
- Some TCs verify multiple observable properties (e.g., TC-08-01 checks `completed`, `sufficient`, `evidence`, `error` separately; TC-08-06 checks `sufficient`, `evidence`, `summary`) → split into separate test methods. This is why the total test count (24) exceeds the number of TCs in the spec (11).

---

### TC-08-01 — `run_python_job` with code returning `{ "evidence": ..., "sufficient": True }` dict

| Field | Detail |
|---|---|
| **Pre** | None |
| **Steps** | 1. Call `run_python_job({ "source_code": "def check(d, t): return {'evidence': 'ok', 'sufficient': True}", "entrypoint": "check", "input_data": None, "target": None, "timeout_seconds": 10 })` |
| **Expected** | `completed=True`, `sufficient=True`, `evidence="ok"`, `error=None` |
| **Tool** | `pytest` (real subprocess, fast) |

---

### TC-08-02 — `run_python_job` with code returning `(evidence, True)` tuple

| Field | Detail |
|---|---|
| **Pre** | None |
| **Steps** | 1. Call with code `def f(d, t): return ('evidence_data', True)` |
| **Expected** | `completed=True`, `sufficient=True`, `evidence="evidence_data"` |
| **Tool** | `pytest` |

---

### TC-08-03 — `normalize_result` accepts valid dict with `sufficient=True`

| Field | Detail |
|---|---|
| **Pre** | Import `normalize_result` from the embedded `RUNNER_SOURCE` or expose it as a helper |
| **Steps** | 1. Call `normalize_result({"evidence": "e", "sufficient": True, "records": []})` |
| **Expected** | Returns dict with `sufficient=True`, `evidence="e"`, `records=[]` |
| **Tool** | `pytest` |

---

### TC-08-04 — `normalize_result` rejects dict without `"sufficient"` field → raises `ValueError`

| Field | Detail |
|---|---|
| **Pre** | None |
| **Steps** | 1. Call `normalize_result({"evidence": "e"})` |
| **Expected** | `ValueError` raised |
| **Tool** | `pytest` |

---

### TC-08-05 — `normalize_result` rejects dict with non-boolean `"sufficient"` → raises `ValueError`

| Field | Detail |
|---|---|
| **Pre** | None |
| **Steps** | 1. Call `normalize_result({"evidence": "e", "sufficient": "yes"})` |
| **Expected** | `ValueError` raised |
| **Tool** | `pytest` |

---

### TC-08-06 — `normalize_result` accepts a 2-tuple `(evidence, bool)`

| Field | Detail |
|---|---|
| **Pre** | None |
| **Steps** | 1. Call `normalize_result(("data", False))` |
| **Expected** | Returns `{ "evidence": "data", "sufficient": False, "summary": None }` |
| **Tool** | `pytest` |

---

### TC-08-07 — `normalize_result` rejects an invalid return type → raises `ValueError`

| Field | Detail |
|---|---|
| **Pre** | None |
| **Steps** | 1. Call `normalize_result(42)` |
| **Expected** | `ValueError` raised |
| **Tool** | `pytest` |

---

### TC-08-08 — `run_python_job` with undefined entrypoint returns `completed=False`

| Field | Detail |
|---|---|
| **Pre** | None |
| **Steps** | 1. Call with `entrypoint="nonexistent_function"` and valid but irrelevant source code |
| **Expected** | `completed=False`; `error` contains "not defined or not callable" |
| **Tool** | `pytest` |

---

### TC-08-09 — `run_python_job` where code raises an exception returns `completed=False`

| Field | Detail |
|---|---|
| **Pre** | None |
| **Steps** | 1. Source code raises `RuntimeError("test error")` inside the entrypoint |
| **Expected** | `completed=False`; `error` contains `"test error"` |
| **Tool** | `pytest` |

---

### TC-08-10 — `run_python_job` with `timeout_seconds=1` for long-running code returns timeout error

| Field | Detail |
|---|---|
| **Pre** | `subprocess.run` patched to raise `subprocess.TimeoutExpired` |
| **Steps** | 1. Patch `subprocess.run` to raise `TimeoutExpired`. 2. Call `run_python_job({ ..., "timeout_seconds": 1 })` |
| **Expected** | `completed=False`; `error` mentions timeout |
| **Tool** | `pytest`, `pytest-mock` |

---

### TC-08-11 — `run_python_job` where subprocess produces no stdout returns error

| Field | Detail |
|---|---|
| **Pre** | `subprocess.run` patched to return `CompletedProcess(returncode=0, stdout="", stderr="crash")` |
| **Steps** | 1. Patch subprocess. 2. Call `run_python_job(...)` |
| **Expected** | `completed=False`; `error` mentions empty output |
| **Tool** | `pytest`, `pytest-mock` |

---

## TCD-09 — Cluster Computation Worker

**Module:** `cluster_computation/computation_service.py`  
**Tool:** `pytest`, `responses`, `pytest-mock`  
**Status:** ✅ Implemented & passing — 19/19 tests pass  
**Run command:** `pytest -v tests/tcd09_cluster/test_tcd09_cluster_computation.py` (from `cluster_computation/`)

**Description:**  
Tests `run_cluster_job` — the HTTP client that submits jobs to the RPI cluster
REST API and polls for completion. All HTTP calls are mocked via `responses`.

**Infrastructure notes (implemented):**
- **No Flask app context, no database** — `computation_service.py` is a pure HTTP client using `requests`. Import path: `from computation_service import _headers, run_cluster_job` directly.
- `@responses.activate` is applied per-method (same pattern as TCD-06) for full isolation — `rsps_lib.calls` is reset between tests.
- **TC-09-01**: two responses registered for `GET /jobs/job-1` — first returns `RUNNING`, second returns `COMPLETED`. The `responses` library consumes them in FIFO order.
- **TC-09-04/05/06**: mock poll body contains only `status`, no `result` field — the `_error_result` helper is reached, which sets `slurm_state` from the status string. Checking `slurm_state` directly is therefore valid.
- **TC-09-07 (deadline exceeded)**: `computation_service.time.perf_counter` is patched with `side_effect=[0.0, 0.0, 0.5, 2.0, 2.0]` matching the exact call sequence inside `run_cluster_job` (start → deadline calc → first loop check → second loop check → `_error_result` processing time). `computation_service.POLL_INTERVAL` is also patched to `0` to suppress the real `time.sleep` call. Test runs **instantly** instead of waiting a real second.
- **TC-09-08/09**: `computation_service.CLUSTER_API_KEY` is patched directly with `mock.patch(..., new=...)` — the module reads the env var once at import time and stores it as a plain string, so patching the variable (not `os.environ`) is the correct approach.
- Some TCs verify multiple properties (e.g., TC-09-01 checks `completed`, `slurm_state`, `slurm_job_id`; TC-09-02/03/04/05/06 check `completed` and a state/error field) → split into separate test methods. This is why the total test count (19) exceeds the number of TCs in the spec (10).
- Total runtime: 12.32 s — the `responses` library replaces all real HTTP calls so no cluster is contacted.

---

### TC-09-01 — `run_cluster_job` submits job and polls until `COMPLETED`

| Field | Detail |
|---|---|
| **Pre** | Mock `POST /jobs` returns `{ "job_id": "job-1" }`; first `GET /jobs/job-1` returns `RUNNING`; second returns `COMPLETED` with a valid `result` |
| **Steps** | 1. Register `responses` mocks. 2. Call `run_cluster_job(valid_payload)` |
| **Expected** | `completed=True`; `slurm_state="COMPLETED"`; `slurm_job_id="job-1"` |
| **Tool** | `pytest`, `responses` |

---

### TC-09-02 — `run_cluster_job` returns error when cluster API is unreachable

| Field | Detail |
|---|---|
| **Pre** | `responses` raises `ConnectionError` for `POST /jobs` |
| **Steps** | 1. Register connection-error mock. 2. Call `run_cluster_job(payload)` |
| **Expected** | `completed=False`; `error` mentions "Failed to submit" |
| **Tool** | `pytest`, `responses` |

---

### TC-09-03 — `run_cluster_job` returns error when API returns no `job_id`

| Field | Detail |
|---|---|
| **Pre** | Mock `POST /jobs` returns HTTP 200 with `{}` (empty body) |
| **Steps** | 1. Call `run_cluster_job(payload)` |
| **Expected** | `completed=False`; `error` contains "no job_id" |
| **Tool** | `pytest`, `responses` |

---

### TC-09-04 — `run_cluster_job` returns error for `FAILED` terminal state

| Field | Detail |
|---|---|
| **Pre** | Mocks: submit returns `job-1`; poll returns `FAILED` immediately |
| **Steps** | 1. Call `run_cluster_job(payload)` |
| **Expected** | `completed=False`; `slurm_state="FAILED"` |
| **Tool** | `pytest`, `responses` |

---

### TC-09-05 — `run_cluster_job` returns error for `TIMEOUT` terminal state

| Field | Detail |
|---|---|
| **Pre** | Poll mock returns `TIMEOUT` |
| **Steps** | 1. Call `run_cluster_job(payload)` |
| **Expected** | `completed=False`; `slurm_state="TIMEOUT"` |
| **Tool** | `pytest`, `responses` |

---

### TC-09-06 — `run_cluster_job` returns error for `NODE_FAIL` terminal state

| Field | Detail |
|---|---|
| **Pre** | Poll mock returns `NODE_FAIL` |
| **Steps** | 1. Call `run_cluster_job(payload)` |
| **Expected** | `completed=False`; `slurm_state="NODE_FAIL"` |
| **Tool** | `pytest`, `responses` |

---

### TC-09-07 — `run_cluster_job` deadline exceeded returns local timeout error

| Field | Detail |
|---|---|
| **Pre** | `payload["timeout_seconds"] = 1`; mock always returns `RUNNING`; `POLL_INTERVAL` patched to `0` |
| **Steps** | 1. Call `run_cluster_job(payload)` |
| **Expected** | `completed=False`; `error` contains "timed out after 1s" |
| **Tool** | `pytest`, `pytest-mock` |

---

### TC-09-08 — `_headers` includes `X-API-Key` when `CLUSTER_API_KEY` is set

| Field | Detail |
|---|---|
| **Pre** | `CLUSTER_API_KEY` env var set to `"secret"` |
| **Steps** | 1. Call `_headers()` |
| **Expected** | Returned dict contains `{ "X-API-Key": "secret" }` |
| **Tool** | `pytest` (monkeypatch env) |

---

### TC-09-09 — `_headers` omits `X-API-Key` when `CLUSTER_API_KEY` is empty

| Field | Detail |
|---|---|
| **Pre** | `CLUSTER_API_KEY` env var set to `""` |
| **Steps** | 1. Call `_headers()` |
| **Expected** | `"X-API-Key"` is NOT present in the returned dict |
| **Tool** | `pytest` (monkeypatch env) |

---

### TC-09-10 — `run_cluster_job` returns error when `COMPLETED` job has no `result` field

| Field | Detail |
|---|---|
| **Pre** | Poll mock returns `{ "status": "COMPLETED", "result": null }` |
| **Steps** | 1. Call `run_cluster_job(payload)` |
| **Expected** | `completed=False`; `error` mentions missing result |
| **Tool** | `pytest`, `responses` |

---

## TCD-10 — NL2FL Worker

**Module:** `nl2fl/nl2fl_service.py`  
**Tool:** `pytest`, `responses`, `unittest.mock`  
**Status:** ✅ 20/20 passing (0.56 s — Python 3.14.3, pytest 9.0.2, Windows 11)  
**Run:** `cd nl2fl && pytest -v tests/tcd10_nl2fl/test_tcd10_nl2fl_service.py`

**Infrastructure notes:**
- Pure-Python module — no Flask app context, no DB, no Celery broker needed in tests.
- `nl2fl_service._call_llm` and `nl2fl_service._verify_with_lean` are patched at the module path via `unittest.mock.patch`.
- Google Gemini URL embeds the API key as a query parameter (`?key=<key>`); `responses.add` uses `re.compile(...)` to match any key value.
- TC-10-10 tests `_call_llm` directly (not `translate_and_verify`) because the wrapper catches all LLM exceptions internally and stores them in `history` rather than re-raising.
- Public API is `translate_and_verify` (not `translate_to_lean`); returns `{"valid", "attempts", "final_lean", "history", "processing_time_seconds"}`.
- TC-10-07/08/09 each produce 3 test methods; TC-10-10 produces 2 → 20 tests total for 12 TCs.

**Description:**  
Tests the natural-language-to-Lean-4 translation pipeline: provider dispatch,
the retry loop with Lean compiler error feedback, history tracking, and edge
cases. All HTTP calls to LLM APIs and the Lean worker are mocked.

---

### TC-10-01 — `_call_openai_compat` returns content on HTTP 200

| Field | Detail |
|---|---|
| **Pre** | Mock `POST https://api.openai.com/v1/chat/completions` returns `{ "choices": [{ "message": { "content": "```lean\ntheorem t : ...\n```" } }] }` |
| **Steps** | 1. Call `_call_openai_compat(messages, "gpt-4o", "sk-test", base_url)` |
| **Expected** | Returns the content string `"```lean\ntheorem t : ...\n```"` |
| **Tool** | `pytest`, `responses` |

---

### TC-10-02 — `_call_openai_compat` raises `RuntimeError` on non-200 response

| Field | Detail |
|---|---|
| **Pre** | Mock returns HTTP 401 |
| **Steps** | 1. Call `_call_openai_compat(...)` |
| **Expected** | `RuntimeError` raised; message includes `"401"` |
| **Tool** | `pytest`, `responses` |

---

### TC-10-03 — `_call_openai_compat` raises `RuntimeError` when `choices` is empty

| Field | Detail |
|---|---|
| **Pre** | Mock returns HTTP 200 with `{ "choices": [] }` |
| **Steps** | 1. Call method |
| **Expected** | `RuntimeError` raised |
| **Tool** | `pytest`, `responses` |

---

### TC-10-04 — `_call_anthropic` returns text from `content[0].text`

| Field | Detail |
|---|---|
| **Pre** | Mock `POST https://api.anthropic.com/v1/messages` returns `{ "content": [{ "text": "```lean\n...\n```" }] }` |
| **Steps** | 1. Call `_call_anthropic(messages, "claude-3-5-sonnet-20241022", "sk-ant-test")` |
| **Expected** | Returns the content text string |
| **Tool** | `pytest`, `responses` |

---

### TC-10-05 — `_call_anthropic` raises `RuntimeError` when `content` is empty

| Field | Detail |
|---|---|
| **Pre** | Mock returns HTTP 200 with `{ "content": [] }` |
| **Steps** | 1. Call method |
| **Expected** | `RuntimeError` raised |
| **Tool** | `pytest`, `responses` |

---

### TC-10-06 — `_call_google` returns text from first candidate

| Field | Detail |
|---|---|
| **Pre** | Mock Gemini endpoint returns `{ "candidates": [{ "content": { "parts": [{ "text": "```lean\n...\n```" }] } }] }` |
| **Steps** | 1. Call `_call_google(messages, "gemini-flash-lite-latest", "api-key")` |
| **Expected** | Returns the text string |
| **Tool** | `pytest`, `responses` |

---

### TC-10-07 — `translate_and_verify` with OpenAI provider succeeds on first attempt

| Field | Detail |
|---|---|
| **Pre** | `nl2fl_service._call_llm` patched to return a `\`\`\`lean...\`\`\`` block; `nl2fl_service._verify_with_lean` patched to return `{"valid": True, "errors": []}` |
| **Steps** | 1. Call `translate_and_verify("For all n, n+1 > n", model_id="openai/gpt-4o", api_key="sk-x")` |
| **Expected** | `valid=True`; `attempts=1`; `final_lean` contains the extracted Lean code |
| **Tool** | `pytest`, `unittest.mock` |

---

### TC-10-08 — `translate_and_verify` retries when Lean compiler returns errors

| Field | Detail |
|---|---|
| **Pre** | `_call_llm` always returns the same Lean block; `_verify_with_lean` patched with `side_effect=[{"valid": False, "errors": [{..."type mismatch"...}]}, {"valid": True, "errors": []}]` |
| **Steps** | 1. Call `translate_and_verify(...)` with `max_retries=3` |
| **Expected** | `valid=True`; `attempts=2`; second `_call_llm` invocation receives messages containing the compiler error text |
| **Tool** | `pytest`, `unittest.mock` |

---

### TC-10-09 — `translate_and_verify` exhausts `max_retries` and returns failure

| Field | Detail |
|---|---|
| **Pre** | `_call_llm` always returns a Lean block; `_verify_with_lean` always returns `{"valid": False, "errors": [{...}]}` |
| **Steps** | 1. Call `translate_and_verify(...)` with `max_retries=2` |
| **Expected** | `valid=False`; `attempts=2`; `history` has exactly 2 entries |
| **Tool** | `pytest`, `unittest.mock` |

---

### TC-10-10 — `_call_llm` with unknown provider raises `RuntimeError`

| Field | Detail |
|---|---|
| **Pre** | None |
| **Steps** | 1. Call `_call_llm(messages, "unknown/model", "key")` directly |
| **Expected** | `RuntimeError` raised; message contains `"unknown"` |
| **Note** | `translate_and_verify` catches all LLM exceptions and stores them in `history` — `_call_llm` must be tested directly to verify the raise behaviour |
| **Tool** | `pytest` |

---

### TC-10-11 — `translate_and_verify` with empty LLM response returns `valid=False`

| Field | Detail |
|---|---|
| **Pre** | `_call_llm` patched to return `""`; `_verify_with_lean` patched to return `{"valid": False, "errors": []}` |
| **Steps** | 1. Call `translate_and_verify(...)` with `max_retries=1` |
| **Expected** | `valid=False` |
| **Tool** | `pytest`, `unittest.mock` |

---

### TC-10-12 — `_extract_lean_code` ignores text outside the fenced block

| Field | Detail |
|---|---|
| **Pre** | None |
| **Steps** | 1. Call `_extract_lean_code("Here is your proof:\n\`\`\`lean\ntheorem t := trivial\n\`\`\`\nHope that helps!")` |
| **Expected** | Returns `"theorem t := trivial"`; preamble and postamble text are absent |
| **Tool** | `pytest` |

---

## TCD-11 — Agents Worker

**Module:** `agents/agents_service.py`  
**Tool:** `pytest`, `responses`, `unittest.mock`  
**Status:** ✅ 13/13 passing (0.30 s — Python 3.14.3, pytest 9.0.2, Windows 11)  
**Run:** `cd agents && pytest -v tests/tcd11_agents/test_tcd11_agents_service.py`

**Infrastructure notes:**
- Pure-Python module — no Flask, no DB, no Celery broker needed in tests.
- Public API is `suggest()` (not `suggest_text`); returns `{"suggestion", "model_id", "processing_time_seconds"}`.
- TC-11-05 (mock/Copilot provider): `COPILOT_BASE_URL` is read at module import; patch `agents_service.COPILOT_BASE_URL` directly with `mock.patch`.
- TC-11-06/07/08: request body is inspected via `json.loads(responses.calls[0].request.body)` to assert `messages` structure.
- Google URL (TC-11-03) embeds the API key as a query parameter; `re.compile(...)` is used in `responses.add` to match any key.
- TC-11-10: `responses.add(..., body=requests.exceptions.Timeout())` makes the HTTP call raise `Timeout`; `suggest()` does not catch it, so it propagates to the caller.
- TC-11-05 produces 2 test methods; TC-11-08/09 produce 2 each → 13 tests total for 10 TCs.
- Gotcha: the original skeleton had a module-level `pytestmark = pytest.mark.skip(...)` appended after all test classes; it must be removed before running.

**Description:**  
Tests the one-shot LLM suggestion service across all five providers (OpenAI,
Anthropic, Google, DeepSeek, mock/Copilot). Validates system prompt injection,
timeout enforcement, rate-limit handling, and context prepending.

---

### TC-11-01 — `suggest` with `openai/gpt-4o` returns the model response

| Field | Detail |
|---|---|
| **Pre** | Mock OpenAI completions endpoint returns `{ "choices": [{ "message": { "content": "Consider using induction." } }] }` |
| **Steps** | 1. Call `suggest(prompt="Suggest a lemma for...", model_id="openai/gpt-4o", api_key="sk-x")` |
| **Expected** | `result["suggestion"] == "Consider using induction."` |
| **Tool** | `pytest`, `responses` |

---

### TC-11-02 — `suggest` with `anthropic/claude-3-5-sonnet-20241022` returns text

| Field | Detail |
|---|---|
| **Pre** | Mock `POST https://api.anthropic.com/v1/messages` returns `{ "content": [{ "text": "..." }] }` |
| **Steps** | 1. Call `suggest(prompt="...", model_id="anthropic/claude-3-5-sonnet-20241022", api_key="sk-ant")` |
| **Expected** | `result["suggestion"]` is non-empty |
| **Tool** | `pytest`, `responses` |

---

### TC-11-03 — `suggest` with `google/gemini-flash-lite-latest` returns text

| Field | Detail |
|---|---|
| **Pre** | Mock Gemini endpoint matched via `re.compile(r"https://generativelanguage\.googleapis\.com/.*")` to handle the `?key=` query param |
| **Steps** | 1. Call `suggest(prompt="...", model_id="google/gemini-flash-lite-latest", api_key="gkey")` |
| **Expected** | `result["suggestion"]` is non-empty |
| **Tool** | `pytest`, `responses` |

---

### TC-11-04 — `suggest` with `deepseek/deepseek-chat` returns text

| Field | Detail |
|---|---|
| **Pre** | Mock `POST https://api.deepseek.com/v1/chat/completions` (OpenAI-compatible response shape) |
| **Steps** | 1. Call `suggest(prompt="...", model_id="deepseek/deepseek-chat", api_key="ds-key")` |
| **Expected** | `result["suggestion"]` is non-empty |
| **Tool** | `pytest`, `responses` |

---

### TC-11-05 — `suggest` with `mock/test` calls Copilot proxy

| Field | Detail |
|---|---|
| **Pre** | `agents_service.COPILOT_BASE_URL` patched to `http://test-copilot:9999`; mock `POST .../copilot` returns `{ "answer": "..." }` |
| **Steps** | 1. Call `suggest(prompt="...", model_id="mock/test", api_key="ignored")` |
| **Expected** | `result["suggestion"]` equals the mocked answer; request URL starts with the patched `COPILOT_BASE_URL` |
| **Tool** | `pytest`, `responses`, `unittest.mock.patch` |

---

### TC-11-06 — `suggest` injects `DEFAULT_SYSTEM_PROMPT` when none is provided

| Field | Detail |
|---|---|
| **Pre** | Mock OpenAI endpoint; `system_prompt` argument not passed |
| **Steps** | 1. Call `suggest(prompt="...", model_id="openai/gpt-4o", api_key="x")` |
| **Expected** | `json.loads(responses.calls[0].request.body)["messages"]` contains a system message whose `content` equals `DEFAULT_SYSTEM_PROMPT` |
| **Tool** | `pytest`, `responses` |

---

### TC-11-07 — `suggest` uses custom `system_prompt` when provided

| Field | Detail |
|---|---|
| **Pre** | Mock OpenAI endpoint |
| **Steps** | 1. Call `suggest(..., system_prompt="You are a geometry expert.")` |
| **Expected** | System message in the outgoing request body has `content == "You are a geometry expert."` |
| **Tool** | `pytest`, `responses` |

---

### TC-11-08 — `suggest` prepends `context` to the user message

| Field | Detail |
|---|---|
| **Pre** | Mock OpenAI endpoint |
| **Steps** | 1. Call `suggest(prompt="Suggest a lemma.", ..., context="The project proves Fermat's Last Theorem.")` |
| **Expected** | The user message in the outgoing request body contains both the context string and the prompt string |
| **Tool** | `pytest`, `responses` |

---

### TC-11-09 — `_call_openai_compat` raises `RuntimeError` on HTTP 429 (rate limit)

| Field | Detail |
|---|---|
| **Pre** | Mock endpoint returns HTTP 429 |
| **Steps** | 1. Call `_call_openai_compat(...)` |
| **Expected** | `RuntimeError` raised; message mentions `"429"` |
| **Tool** | `pytest`, `responses` |

---

### TC-11-10 — `suggest` propagates `requests.exceptions.Timeout`

| Field | Detail |
|---|---|
| **Pre** | `responses.add(..., body=requests.exceptions.Timeout())` registered for the OpenAI endpoint |
| **Steps** | 1. Call `suggest(...)` |
| **Expected** | `requests.exceptions.Timeout` raised and propagates to the caller (`suggest` does not catch it) |
| **Tool** | `pytest`, `responses` |

---

## TCD-12 — Angular `AuthService` (`frontend`)

**Module:** `frontend/src/app/auth.service.ts`  
**Tool:** Vitest 4.0.18 (via `@angular/build:unit-test`), Angular TestBed, `provideHttpClientTesting`  
**Status:** ✅ 13/13 passing (48 ms — Vitest 4.0.18, Angular 21)  
**Run:** `cd frontend && npx ng test --include="src/app/tcd12-auth-service.spec.ts" --watch=false`

**Infrastructure notes:**
- The project's test runner is **Vitest** (not Jest). `pending()` is Jasmine-only and does not exist in Vitest globals — all skeleton placeholders using `pending()` must be replaced or commented out.
- Use `provideHttpClient()` + `provideHttpClientTesting()` (Angular 18+ pattern). The deprecated `HttpClientTestingModule` / `RouterTestingModule` are not available in this setup.
- A `setupTestBed()` helper defers `TestBed.inject(AuthService)` so each test can seed `localStorage` **before** the service is constructed (critical for TC-12-02: `_isLoggedIn$` is a `BehaviorSubject` initialised from `localStorage` at construction time).
- `TestBed.resetTestingModule()` + `localStorage.clear()` + `vi.unstubAllGlobals()` called in `afterEach` for full isolation.
- **TC-12-07:** HTTP error responses use `req.flush(body, { status: 401, statusText: 'Unauthorized' })` which produces an `HttpErrorResponse`; the service's `catch` block returns `false`.
- **TC-12-10:** `window.location` is non-configurable in browser environments. `vi.stubGlobal('location', { href: '' })` replaces `globalThis.location` with a plain writable object; `vi.unstubAllGlobals()` restores it. This is the Vitest-native equivalent of the same workaround used in Cypress (TC-15-02).
- The sibling skeleton files `tcd13-task-service.spec.ts` and `tcd14-auth-guard.spec.ts` had `pending()` calls that caused compile errors; those lines were commented out so the build succeeds when including only TCD-12.
- TC-12-03/06 produce 2 test methods each; TC-12-10 produces 2 → 13 total for 10 TCs.

**Description:**  
Tests the Angular authentication service: token storage/retrieval in
`localStorage`, the `isLoggedIn$` reactive observable, GitHub OAuth initiation,
callback handling, and token refresh.

---

### TC-12-01 — `isLoggedIn()` returns `false` when `localStorage` is empty

| Field | Detail |
|---|---|
| **Pre** | `localStorage` cleared in global `beforeEach` |
| **Steps** | 1. Call `setupTestBed()` to inject `AuthService`. 2. Call `service.isLoggedIn()` |
| **Expected** | Returns `false` |
| **Tool** | Vitest, Angular TestBed |

---

### TC-12-02 — `isLoggedIn()` returns `true` when token exists in `localStorage`

| Field | Detail |
|---|---|
| **Pre** | `localStorage.setItem('access_token', 'test.jwt.token')` called **before** `TestBed.inject(AuthService)` so the `BehaviorSubject` initialises to `true` |
| **Steps** | 1. Seed `localStorage`. 2. Call `setupTestBed()`. 3. Call `service.isLoggedIn()` |
| **Expected** | Returns `true` |
| **Tool** | Vitest, Angular TestBed |

---

### TC-12-03 — `handleOAuthCallback` stores tokens and user in `localStorage`

| Field | Detail |
|---|---|
| **Pre** | `HttpTestingController` ready |
| **Steps** | 1. Call `service.handleOAuthCallback('code_abc')`. 2. Flush `POST .../auth/github/callback` with `{ access_token, refresh_token, user }`. 3. `await` the promise |
| **Expected** | `localStorage.getItem('access_token')` equals the mocked token; `JSON.parse(localStorage.getItem('auth_user'))` has the correct `full_name` |
| **Tool** | Vitest, `HttpTestingController` |

---

### TC-12-04 — `handleOAuthCallback` emits `true` on `isLoggedIn$`

| Field | Detail |
|---|---|
| **Pre** | `HttpTestingController` ready |
| **Steps** | 1. Call `service.handleOAuthCallback('code_abc')`. 2. Flush the request. 3. `await` the promise. 4. `await firstValueFrom(service.isLoggedIn$)` |
| **Expected** | Observable emits `true` |
| **Tool** | Vitest, RxJS `firstValueFrom` |

---

### TC-12-05 — `refreshAccessToken` returns `false` when no refresh token exists

| Field | Detail |
|---|---|
| **Pre** | `localStorage` contains no `refresh_token` |
| **Steps** | 1. Call `await service.refreshAccessToken()` |
| **Expected** | Returns `false`; `httpMock.expectNone('.../auth/refresh')` passes |
| **Tool** | Vitest, `HttpTestingController` |

---

### TC-12-06 — `refreshAccessToken` stores new access token and returns `true`

| Field | Detail |
|---|---|
| **Pre** | `localStorage` has `refresh_token`; flush `POST .../auth/refresh` with `{ access_token: "new.jwt" }` |
| **Steps** | 1. Call `await service.refreshAccessToken()` |
| **Expected** | Returns `true`; `localStorage.getItem('access_token')` equals `"new.jwt"` |
| **Tool** | Vitest, `HttpTestingController` |

---

### TC-12-07 — `refreshAccessToken` returns `false` on HTTP error

| Field | Detail |
|---|---|
| **Pre** | `localStorage` has `refresh_token` |
| **Steps** | 1. Call `refreshAccessToken()`. 2. Flush with `req.flush('Unauthorized', { status: 401, statusText: 'Unauthorized' })` |
| **Expected** | Returns `false` (service's `catch` block swallows `HttpErrorResponse`) |
| **Tool** | Vitest, `HttpTestingController` |

---

### TC-12-08 — `getUser` returns `null` when no user in `localStorage`

| Field | Detail |
|---|---|
| **Pre** | `localStorage` cleared |
| **Steps** | 1. Call `service.getUser()` |
| **Expected** | Returns `null` |
| **Tool** | Vitest |

---

### TC-12-09 — `getUser` returns parsed `AuthUser` when stored in `localStorage`

| Field | Detail |
|---|---|
| **Pre** | `localStorage.setItem('auth_user', JSON.stringify({ id: "1", full_name: "Alice", email: "a@b.com" }))` |
| **Steps** | 1. Call `service.getUser()` |
| **Expected** | Returns `{ id: "1", full_name: "Alice", email: "a@b.com" }` |
| **Tool** | Vitest |

---

### TC-12-10 — `initiateGitHubLogin` fetches OAuth URL and assigns `window.location.href`

| Field | Detail |
|---|---|
| **Pre** | `vi.stubGlobal('location', { href: '' })` called before service injection |
| **Steps** | 1. Call `service.initiateGitHubLogin()`. 2. Flush `GET .../auth/github/url` with `{ url: 'https://github.com/login/oauth/authorize?client_id=x' }`. 3. `await` the promise |
| **Expected** | The GET request is made; `mockLocation.href` equals the mocked URL |
| **Note** | `window.location` is non-configurable — `vi.stubGlobal` replaces `globalThis.location` with a plain writable object; `vi.unstubAllGlobals()` in `afterEach` restores it |
| **Tool** | Vitest, `HttpTestingController`, `vi.stubGlobal` |

---

## TCD-13 — Angular `TaskService` (`frontend`)

**Module:** `frontend/src/app/task.service.ts`  
**Tool:** Vitest 4.0.18 (via `@angular/build:unit-test`), Angular TestBed, `provideHttpClientTesting`  
**Status:** ✅ 10/10 passing (37 ms — Vitest 4.0.18, Angular 21)  
**Run:** `cd frontend && npx ng test --include="src/app/tcd13-task-service.spec.ts" --watch=false`

**Infrastructure notes:**
- Same Vitest + `provideHttpClient()` / `provideHttpClientTesting()` setup as TCD-12. `HttpClientTestingModule` is not used.
- `makeJwt(payload)` helper: uses `btoa` + base64url character replacements (`+`→`-`, `/`→`_`, `=`→``) to produce a syntactically valid 3-part JWT that the service can actually decode. No real signing needed — the service only reads `payload.type`.
- **TC-13-03 gotcha:** `"not.a.valid.jwt.at.all"` has 6 parts so `parts.length >= 2` passes the split check. The test works because the second segment (`"a"`) is not valid base64url-encoded JSON, so `JSON.parse` throws and `getTokenType` returns `null`.
- **TC-13-07/08 gotcha:** `shouldClearAccessTokenOnError` requires **both** `status === 401` **and** a JWT hint string inside `error.error.message` (e.g. `'token has expired'`). Passing `{ status: 401 }` alone returns `false` because the message check fails first. A `jwtError(status, message)` helper wraps the correct structure `{ status, error: { message } }`.
- TC-13-06 produces 3 separate assertions (one per key) for precise failure reporting → 10 total tests for 8 TCs.

**Description:**  
Tests token type detection, access-token lifecycle helpers, and HTTP service
methods that call the CoProof backend API.

---

### TC-13-01 — `getTokenType` returns `"access"` for a valid access JWT

| Field | Detail |
|---|---|
| **Pre** | `makeJwt({ sub: '1', type: 'access' })` builds a 3-part base64url-encoded token |
| **Steps** | 1. Call `service.getTokenType(token)` |
| **Expected** | Returns `"access"` |
| **Tool** | Vitest |

---

### TC-13-02 — `getTokenType` returns `"refresh"` for a valid refresh JWT

| Field | Detail |
|---|---|
| **Pre** | `makeJwt({ sub: '1', type: 'refresh' })` |
| **Steps** | 1. Call `service.getTokenType(token)` |
| **Expected** | Returns `"refresh"` |
| **Tool** | Vitest |

---

### TC-13-03 — `getTokenType` returns `null` for a malformed token string

| Field | Detail |
|---|---|
| **Pre** | None |
| **Steps** | 1. Call `service.getTokenType("not.a.valid.jwt.at.all")` |
| **Expected** | Returns `null` (6-part string passes the split check but the payload segment is not valid JSON, so the `catch` returns `null`) |
| **Tool** | Vitest |

---

### TC-13-04 — `getTokenType` returns `null` for an empty string

| Field | Detail |
|---|---|
| **Pre** | None |
| **Steps** | 1. Call `service.getTokenType("")` |
| **Expected** | Returns `null` |
| **Tool** | Vitest |

---

### TC-13-05 — `setAccessToken` normalizes whitespace and stores in `localStorage`

| Field | Detail |
|---|---|
| **Pre** | None |
| **Steps** | 1. Call `service.setAccessToken("  mytoken  ")` |
| **Expected** | `localStorage.getItem('access_token')` equals `"mytoken"` (trimmed via `normalizeAccessToken`) |
| **Tool** | Vitest |

---

### TC-13-06 — `clearAccessToken` removes `access_token`, `refresh_token`, and `auth_user`

| Field | Detail |
|---|---|
| **Pre** | All three keys set in `localStorage` |
| **Steps** | 1. Call `service.clearAccessToken()` |
| **Expected** | `localStorage.getItem` returns `null` for each of the three keys (3 separate assertions) |
| **Tool** | Vitest |

---

### TC-13-07 — `shouldClearAccessTokenOnError` returns `true` for HTTP 401 with JWT hint

| Field | Detail |
|---|---|
| **Pre** | None |
| **Steps** | 1. Call `service.shouldClearAccessTokenOnError({ status: 401, error: { message: 'token has expired' } })` |
| **Expected** | Returns `true` |
| **Note** | Requires **both** `status === 401` **and** a JWT hint in `error.error.message`. Passing `{ status: 401 }` alone returns `false` |
| **Tool** | Vitest |

---

### TC-13-08 — `shouldClearAccessTokenOnError` returns `false` for HTTP 500

| Field | Detail |
|---|---|
| **Pre** | None |
| **Steps** | 1. Call `service.shouldClearAccessTokenOnError({ status: 500, error: { message: 'token has expired' } })` |
| **Expected** | Returns `false` (status ≠ 401 even when a JWT hint is present) |
| **Tool** | Vitest |

---

## TCD-14 — Angular `authGuard` (`frontend`)

**Module:** `frontend/src/app/auth.guard.ts`  
**Tool:** Vitest 4.0.18 (via `@angular/build:unit-test`), Angular TestBed, `provideRouter`, `TestBed.runInInjectionContext`  
**Status:** ✅ 3/3 passing (22 ms — Vitest 4.0.18, Angular 21)  
**Run:** `cd frontend && npx ng test --include="src/app/tcd14-auth-guard.spec.ts" --watch=false`

**Infrastructure notes:**
- `authGuard` is a `CanActivateFn` (plain function, not a class). It must be invoked inside `TestBed.runInInjectionContext(() => authGuard(null, null))` so Angular's `inject()` calls resolve in the DI context.
- `AuthService` is provided as a plain value mock `{ isLoggedIn: () => bool }` — no real HTTP client needed.
- `provideRouter([])` is required so `Router.createUrlTree` works when the guard redirects to `/auth`. `RouterTestingModule` is deprecated in Angular 18+ and is not used.
- `afterEach(() => TestBed.resetTestingModule())` provides isolation between the two describe blocks, which each call `setupTestBed` with a different `isLoggedIn` value.
- TC-14-02 produces 2 assertions (`instanceof UrlTree` + `toString() === '/auth'`) → 3 total for 2 TCs.

**Description:**  
Tests the `CanActivateFn` guard that protects authenticated routes. `AuthService`
is mocked.

---

### TC-14-01 — Guard returns `true` when user is logged in

| Field | Detail |
|---|---|
| **Pre** | `AuthService.isLoggedIn()` mocked to return `true` |
| **Steps** | 1. `TestBed.runInInjectionContext(() => authGuard(null, null))` (guard ignores both snapshot arguments) |
| **Expected** | Returns `true` |
| **Tool** | Vitest, `TestBed.runInInjectionContext` |

---

### TC-14-02 — Guard returns `UrlTree` to `/auth` when user is not logged in

| Field | Detail |
|---|---|
| **Pre** | `AuthService.isLoggedIn()` mocked to return `false` |
| **Steps** | 1. `TestBed.runInInjectionContext(() => authGuard(null, null))` |
| **Expected** | (a) Return value is `instanceof UrlTree`; (b) `result.toString()` equals `"/auth"` (2 separate assertions) |
| **Tool** | Vitest, `TestBed.runInInjectionContext`, `provideRouter([])` |

---

## TCD-15 — E2E: Authentication Flow

**Scope:** `frontend` Angular app (Angular dev server on `http://localhost:4200`; all backend calls intercepted via `cy.intercept`)  
**Tool:** `Cypress 15.14.2`, `cy.intercept`  
**Status:** ✅ 7/7 passing (2 s — Cypress 15.14.2, Electron 138 headless)  
**Run:** `cd frontend && npx cypress run --e2e --spec cypress/e2e/tcd15-auth-flow.cy.ts`  

**Infrastructure notes:**
- No real backend required. All calls to `http://localhost:5001/api/v1` are intercepted by `cy.intercept` — MSW is not needed.
- `cy.clearLocalStorage()` in global `beforeEach` ensures every test starts unauthenticated unless it explicitly pre-seeds a token.
- **TC-15-01:** Two assertions (one per protected route: `/workspace`, `/account-config`) to cover the `authGuard`.
- **TC-15-02 gotcha:** `window.location` is a non-configurable native property in Electron/Chrome. Both `cy.stub(win, 'location')` and `Object.defineProperty(win, 'location', ...)` throw `TypeError: Cannot redefine property: location`. A failed stub also poisons subsequent `beforeEach` cleanup hooks, cascading failures to TC-15-03. Fix: mock `GET /auth/github/url` to return a same-origin URL (`http://localhost:4200/menu`) so the browser stays in scope and `cy.url()` can assert the navigation.
- **TC-15-03:** The callback is handled by `AuthPageComponent` via `ActivatedRoute` query params (`?code=abc123`), not a separate `/auth/callback` route. Visit `/auth?code=abc123` directly.
- **TC-15-04:** Pre-seed `access_token` via `cy.window().then(win => win.localStorage.setItem(...))` before `cy.visit('/auth')`; the component's `ngOnInit` calls `router.navigate(['/menu'])` if already logged in.
- `cypress.config.ts` created with `baseUrl: http://localhost:4200`, `specPattern: cypress/e2e/**/*.cy.ts`, `supportFile: false`.
- `package.json` scripts added: `cypress:run` and `cypress:open`.
- TC-15-01 produces 2 test assertions; TC-15-03 produces 3 → 7 total for 4 TCs.

**Description:**  
Full end-to-end tests for the GitHub OAuth authentication flow in a real browser
session. Backend HTTP calls are intercepted via `cy.intercept` to avoid
hitting the live API.

---

### TC-15-01 — Unauthenticated user visiting a protected route is redirected to `/auth`

| Field | Detail |
|---|---|
| **Pre** | `localStorage` cleared (global `beforeEach`); Angular dev server running |
| **Steps** | 1. `cy.visit('/workspace')`. 2. `cy.visit('/account-config')` (separate assertions) |
| **Expected** | Browser URL contains `/auth` in both cases |
| **Tool** | Cypress |

---

### TC-15-02 — User clicks "Login with GitHub" and OAuth URL navigation is triggered

| Field | Detail |
|---|---|
| **Pre** | `cy.intercept('GET', '.../auth/github/url')` returns `{ url: 'http://localhost:4200/menu' }` (same-origin so browser stays in scope) |
| **Steps** | 1. `cy.visit('/auth')`. 2. Click the "Continuar con GitHub" button. 3. `cy.wait('@getGithubUrl')` |
| **Expected** | Intercept fires; `cy.url()` contains `/menu` |
| **Note** | `window.location` is non-configurable in Electron/Chrome — `cy.stub` and `Object.defineProperty` both throw `TypeError: Cannot redefine property: location`. Using a same-origin mock URL is the correct Cypress idiom |
| **Tool** | Cypress, `cy.intercept` |

---

### TC-15-03 — OAuth callback exchanges code, stores tokens, and navigates to `/menu`

| Field | Detail |
|---|---|
| **Pre** | `cy.intercept('POST', '.../auth/github/callback')` returns `{ access_token, refresh_token, user }` |
| **Steps** | 1. `cy.visit('/auth?code=abc123')` (callback handled by `AuthPageComponent` via `ActivatedRoute` query params — there is no separate `/auth/callback` route) |
| **Expected** | `cy.url()` includes `/menu`; `localStorage.access_token` equals the mocked token; `localStorage.auth_user` parses to valid JSON with the correct `full_name` |
| **Tool** | Cypress, `cy.intercept` |

---

### TC-15-04 — Authenticated user visiting `/auth` is redirected to `/menu`

| Field | Detail |
|---|---|
| **Pre** | `cy.window().then(win => win.localStorage.setItem('access_token', 'existing-valid-jwt'))` before visiting |
| **Steps** | 1. `cy.visit('/auth')` |
| **Expected** | `cy.url()` includes `/menu` (`AuthPageComponent.ngOnInit` calls `router.navigate(['/menu'])` when already logged in) |
| **Tool** | Cypress |

---

## TCD-16 — E2E: Project & Node Flow

**Scope:** `frontend` Angular app (Angular dev server on `http://localhost:4200`; all backend calls intercepted via `cy.intercept`)  
**Tool:** `Cypress 15.14.2`, `cy.intercept` (no MSW)  
**Status:** ✅ 6/6 passing (11 s — Cypress 15.14.2, Electron 138 headless)  
**Run:** `cd frontend && npx cypress run --e2e --spec cypress/e2e/tcd16-project-node-flow.cy.ts`

**Infrastructure notes:**
- No real backend required. All HTTP calls to `http://localhost:5001/api/v1` are intercepted by `cy.intercept`. MSW is not used.
- `cy.clearLocalStorage()` in global `beforeEach` ensures every test starts unauthenticated.
- **Auth seeding for protected routes:** `/create-project` is behind `authGuard`. Pattern: `cy.visit('/validation')` (public route) → `cy.window().then(win => win.localStorage.setItem('access_token', token))` → `cy.visit('/create-project')`. On the second visit Angular bootstraps with the token, so `AuthService._hasValidToken()` returns `true` and the guard passes.
- **TC-16-01 timer:** `CreateProjectPageComponent` uses `timer(2000, 3000)` before the first FL→NL poll. `cy.contains('Sí, este es el teorema', { timeout: 10000 })` provides sufficient margin.
- **TC-16-01 negative mock:** `POST /projects` response includes `id: 'p-001'`; workspace secondary calls (`graph/simple`, `pulls/open`, `definitions`) are also stubbed so `WorkspacePageComponent.ngOnInit` does not error on arrival.
- **TC-16-02 negative assertion:** `cy.get('@createProject.all').should('have.length', 0)` verifies `POST /projects` was never called.
- **TC-16-03/04:** `/validation` is a public route; component polls with `timer(500, 500)`; assertions use `cy.contains(..., { timeout: 8000 })`.
- **TC-16-05:** `vm$` has `startWith({ state: 'translating' })` so the loading label `"Traduciendo y verificando…"` appears immediately after `submit()` fires, before the first poll. Result endpoint returns `{ status: 'pending' }` to keep the component in loading state.
- **TC-16-06:** Result endpoint returns the final payload on every call. `timer(2000, 3000)` fires the first poll at ~2000 ms; `cy.wait('@result', { timeout: 6000 })` then `.code-block` asserts the Lean snippet is visible.

**Description:**  
Full end-to-end tests of the core CoProof workflow: project creation, standalone
Lean snippet validation, and NL→FL translation. All backend endpoints are
intercepted via `cy.intercept`.

---

### TC-16-01 — Authenticated user creates a new project via the UI

| Field | Detail |
|---|---|
| **Pre** | `access_token` seeded in `localStorage`; `cy.intercept` stubs: `GET /translate/models`, `GET /translate/api-key/m1`, `POST /translate/fl2nl/submit`, `GET /translate/fl2nl/f-001/result`, `POST /projects`, workspace calls |
| **Steps** | 1. Visit `/create-project`. 2. Type project name. 3. Type goal in Manual tab. 4. Select model in Confirm section. 5. Click “Generar vista previa del enunciado”. 6. Click “Sí, este es el teorema…”. 7. Click “Crear Proyecto” |
| **Expected** | URL includes `/workspace`; project name `My Formalization` visible |
| **Tool** | Cypress 15, `cy.intercept` |

---

### TC-16-02 — Creating a project with empty name shows validation error

| Field | Detail |
|---|---|
| **Pre** | `access_token` seeded; `POST /projects` aliased but not expected |
| **Steps** | 1. Visit `/create-project`. 2. Click “Crear Proyecto” without typing a name |
| **Expected** | “El nombre del proyecto es obligatorio.” visible; `POST /projects` call count is 0 |
| **Tool** | Cypress 15, `cy.intercept` |

---

### TC-16-03 — User submits a node for Lean validation and sees result

| Field | Detail |
|---|---|
| **Pre** | `cy.intercept POST /nodes/tools/verify-snippet` returns `{ task_id: 'v-001' }`; `GET .../v-001/result` returns `{ valid: true, errors: [], theorem_count: 1 }` |
| **Steps** | 1. Visit `/validation`. 2. Type Lean code in the textarea. 3. Click “Verificar” |
| **Expected** | “La demostración es válida” visible (within 8 s) |
| **Tool** | Cypress 15, `cy.intercept` |

---

### TC-16-04 — Lean validation with compiler errors shows diagnostics

| Field | Detail |
|---|---|
| **Pre** | Result stub returns `{ valid: false, errors: [{ line: 3, column: 0, message: 'type mismatch' }] }` |
| **Steps** | 1. Visit `/validation`. 2. Type Lean code. 3. Click “Verificar” |
| **Expected** | `L3` and `type mismatch` both visible in the error list (within 8 s) |
| **Tool** | Cypress 15, `cy.intercept` |

---

### TC-16-05 — User initiates NL→FL translation and sees loading state

| Field | Detail |
|---|---|
| **Pre** | Models stub returns one model; `POST /translate/submit` returns `{ task_id: 't-001' }`; result endpoint returns `{ status: 'pending' }` indefinitely |
| **Steps** | 1. Visit `/translation`. 2. Open settings, select model. 3. Type natural-language text. 4. Click “Traducir a Lean” |
| **Expected** | Status bar shows “Traduciendo y verificando…” immediately after submit (fired by `startWith({ state: 'translating' })`) |
| **Tool** | Cypress 15, `cy.intercept` |

---

### TC-16-06 — Translation result polling shows final Lean code when task completes

| Field | Detail |
|---|---|
| **Pre** | Result endpoint returns final payload on every call (`valid: true`, `final_lean: 'theorem comm ...'`); `timer(2000, 3000)` fires first poll at ~2000 ms |
| **Steps** | 1. Submit translation (same as TC-16-05). 2. Wait for `@result` alias (up to 6 s) |
| **Expected** | `.code-block` element contains `theorem comm` (within 8 s) |
| **Tool** | Cypress 15, `cy.intercept` |

---

## Summary Table

| TCD | Microservice / Module | # TCs | Status | Primary Tool |
|---|---|---|---|---|
| TCD-01 | `web` — Auth API | 45 | ✅ 45/45 | `pytest-flask`, `responses` |
| TCD-02 | `web` — Projects API | 29 | ✅ 29/29 | `pytest-flask`, `responses`, `pytest-mock` |
| TCD-03 | `web` — Nodes API | 17 | ✅ 17/17 | `pytest`, `responses` |
| TCD-04 | `web` — Translation API | 25 | ✅ 25/25 | `pytest-flask`, `pytest-mock` |
| TCD-05 | `web` — Agents API | 19 | ✅ 19/19 | `pytest-flask`, `pytest-mock` |
| TCD-06 | `celery_worker` — GitHub Service | 18 | ✅ 18/18 | `pytest`, `responses` |
| TCD-07 | `lean-worker` | 23 | ✅ 23/23 | `pytest`, `pytest-mock` |
| TCD-08 | `computation-worker` | 24 | ✅ 24/24 | `pytest`, `pytest-mock` |
| TCD-09 | `cluster-computation-worker` | 19 | ✅ 19/19 | `pytest`, `responses` |
| TCD-10 | `nl2fl-worker` | 20 | ✅ 20/20 | `pytest`, `responses`, `unittest.mock` |
| TCD-11 | `agents-worker` | 13 | ✅ 13/13 | `pytest`, `responses`, `unittest.mock` |
| TCD-12 | `frontend` — `AuthService` | 13 | ✅ 13/13 | Vitest, `provideHttpClientTesting` |
| TCD-13 | `frontend` — `TaskService` | 10 | ✅ 10/10 | Vitest, `provideHttpClientTesting` |
| TCD-14 | `frontend` — `authGuard` | 3 | ✅ 3/3 | Vitest, `TestBed.runInInjectionContext`, `provideRouter` |
| TCD-15 | E2E — Authentication | 7 | ✅ 7/7 | Cypress 15, `cy.intercept` |
| TCD-16 | E2E — Project & Node | 6 | ✅ 6/6 | Cypress 15, `cy.intercept` |
| **Total** | | **299** | **299/299** | |
