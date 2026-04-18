# NL2FL — Natural Language to Formal Language (Lean 4) Plan

## Overview

The Translation page receives a natural-language mathematical statement, sends it to an LLM via OpenRouter, then feeds the result into the Lean verification service. If verification fails, the errors are fed back to the LLM as context for a new attempt. This cycle repeats up to a user-configurable retry limit.

---

## Architecture

```
Frontend (Angular)
  TranslationPageComponent
    │
    ▼
TaskService  ─────────────────────────────────────────────────────────────────┐
  │  POST /api/v1/translate/submit                                            │
  │  GET  /api/v1/translate/<task_id>/result  (polling)                       │
  │  GET  /api/v1/translate/models            (model catalogue)               │
  │  POST /api/v1/translate/api-key           (save key for model)            │
  │  GET  /api/v1/translate/api-key/<model>   (retrieve masked key)           │
  └──────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
Flask server  (server/app/api/translate.py)
  TranslateClient  (server/app/services/integrations/translate_client.py)
                              │
                              ▼
              Redis / Celery  ─────────  nl2fl-worker service
                                           (nl2fl/*)
                                           ├── celery_service.py
                                           ├── tasks.py
                                           └── nl2fl_service.py
                                               ├── call_openrouter()
                                               └── retry loop with lean feedback
```

---

## Steps

### Step 1 — DB: `UserApiKey` model and migration

**File:** `server/app/models/user_api_key.py`

```python
class UserApiKey(db.Model):
    __tablename__ = 'user_api_keys'
    id            UUID  PK
    user_id       UUID  FK → users.id  (nullable — anonymous/session key also allowed)
    model_id      Text  NOT NULL        # e.g. "openai/gpt-4o"
    api_key_hash  Text  NOT NULL        # SHA-256 hex of the raw key (never stored plain)
    api_key_enc   Text  NOT NULL        # AES-256-GCM encrypted raw key (decrypt on use)
    created_at    DateTime
    updated_at    DateTime
    UNIQUE(user_id, model_id)
```

**Migration:** create `user_api_keys` table via Alembic (`flask db migrate`, `flask db upgrade`).

> Security note: raw key is **never** persisted. Store AES-256-GCM ciphertext; decrypt in memory at request time using `SECRET_KEY` as KEK.

---

### Step 2 — New Celery worker microservice: `nl2fl/`

Mirror the structure of `lean/` and `computation/`:

```
nl2fl/
├── Dockerfile
├── requirements.txt        # celery, redis, requests, cryptography
├── celery_service.py       # Celery app wired to nl2fl_queue
├── tasks.py                # @celery.task translate_and_verify
└── nl2fl_service.py        # core logic (see below)
```

**`nl2fl_service.py` — `translate_and_verify` function:**

```python
def translate_and_verify(
    natural_text: str,
    model_id: str,
    api_key: str,               # decrypted at server, passed in as plaintext
    lean_backend_url: str,      # internal URL to call Lean via Celery
    max_retries: int = 3,
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
) -> dict:
```

Internal loop:
1. Build messages: `[{role:"system", content: system_prompt}, {role:"user", content: natural_text}]`
2. `POST https://openrouter.ai/api/v1/chat/completions` with `model`, `messages`, `stream: false`
3. Extract Lean code block from response (regex ```` ```lean ... ``` ````)
4. Call Lean verification (Celery task `tasks.verify_snippet` on `lean_queue`) — **blocking** inside the worker is fine because we're already in a Celery task
5. If `valid == True` → return success result
6. If `valid == False` and `attempt < max_retries`:
   - Append `{role:"assistant", content: lean_proposal}` and `{role:"user", content: format_errors(errors)}` to messages
   - Increment attempt, go to step 2
7. If exhausted → return final result with `valid: false`, all attempt history

**Return shape:**
```json
{
  "valid": false,
  "attempts": 3,
  "final_lean": "...",
  "history": [
    { "attempt": 1, "lean_code": "...", "errors": [...] },
    { "attempt": 2, "lean_code": "...", "errors": [...] },
    { "attempt": 3, "lean_code": "...", "errors": [...] }
  ],
  "processing_time_seconds": 12.4
}
```

**`DEFAULT_SYSTEM_PROMPT`** — a module-level constant string, easy to edit.

---

### Step 3 — Flask integration client: `server/app/services/integrations/translate_client.py`

Mirror `compiler_client.py`:

```python
class TranslateClient:
    NL2FL_QUEUE_NAME = os.environ.get('CELERY_NL2FL_QUEUE', 'nl2fl_queue')

    # Non-blocking dispatch (same pattern as verify-snippet):
    @staticmethod
    def submit_translation(payload: dict) -> str:
        """Dispatch task, return task_id immediately."""

    @staticmethod
    def get_result(task_id: str) -> dict | None:
        """Check AsyncResult.ready(), return result or None."""
```

---

### Step 4 — Flask blueprint: `server/app/api/translate.py`

Endpoints:

| Method | Route | Auth | Description |
|--------|-------|------|-------------|
| `POST` | `/api/v1/translate/submit` | optional JWT | Submit NL text + model_id → `{ task_id }` |
| `GET`  | `/api/v1/translate/<task_id>/result` | — | Poll result |
| `GET`  | `/api/v1/translate/models` | — | Return list of available OpenRouter models |
| `POST` | `/api/v1/translate/api-key` | JWT required | Save encrypted API key for a model |
| `GET`  | `/api/v1/translate/api-key/<model_id>` | JWT required | Return masked key (`sk-***...***`) |

Register `translate_bp` in `server/app/__init__.py`.

Add `CELERY_NL2FL_QUEUE` to `server/config.py` and `docker-compose.yml` env blocks for `web` and `celery_worker`.

---

### Step 5 — `docker-compose.yml` — new service `nl2fl-worker`

```yaml
nl2fl-worker:
  build:
    context: ./nl2fl
    dockerfile: Dockerfile
  environment:
    - REDIS_URL=redis://redis:6379/0
    - CELERY_NL2FL_QUEUE=nl2fl_queue
    - CELERY_LEAN_QUEUE=lean_queue      # needed to call lean from inside the worker
  depends_on:
    - redis
    - lean-worker
```

Add `nl2fl-worker: condition: service_started` to the `web` and `celery_worker` depends_on blocks.

---

### Step 6 — TypeScript models: `frontend/src/app/task.models.ts`

Add:

```typescript
export interface TranslationAttempt {
  attempt: number;
  lean_code: string;
  errors: VerificationErrorItem[];
}

export interface TranslationResult {
  valid: boolean;
  attempts: number;
  final_lean: string;
  history: TranslationAttempt[];
  processing_time_seconds: number;
}

export interface AvailableModel {
  id: string;           // "openai/gpt-4o"
  name: string;         // "GPT-4o"
  provider: string;     // "OpenAI"
}

export interface ApiKeyStatus {
  model_id: string;
  masked_key: string;   // "sk-***...abc"
  has_key: boolean;
}
```

---

### Step 7 — `task.service.ts` — new methods

```typescript
// Translation
submitTranslation(payload: TranslatePayload): Observable<{ task_id: string }>
getTranslationResult(taskId: string): Observable<TranslationResult | { status: 'pending' }>
getAvailableModels(): Observable<AvailableModel[]>
saveApiKey(modelId: string, apiKey: string): Observable<void>
getApiKeyStatus(modelId: string): Observable<ApiKeyStatus>
```

---

### Step 8 — Translation page rewrite

**Component state (all driven by `vm$` Observable + `async` pipe):**

```typescript
interface TranslationVm {
  state: 'idle' | 'translating' | 'verifying' | 'valid' | 'invalid' | 'error';
  result: TranslationResult | null;
  currentAttempt: number;
  maxRetries: number;
  serverError: string;
}
```

**UI layout — three columns:**

```
┌──────────────────┬──────────────────┬──────────────────────┐
│  Input           │  Current Lean    │  Attempt History     │
│  (NL textarea)   │  (latest output) │  (collapsible list)  │
└──────────────────┴──────────────────┴──────────────────────┘
```

**Settings panel (collapsible, above columns):**
- Model selector — `<select>` populated from `GET /translate/models`
- API key field — password input + Save button (calls `POST /translate/api-key`), shows masked key if one exists
- System prompt textarea — editable, pre-populated with default
- Max retries — number input (1–10, default 3)

**Status badge** — mirrors validation page: idle / translating / verifying / valid / invalid / error

**Attempt history panel:**
- `@for` list of `TranslationAttempt` objects
- Each row: attempt number, Lean code (collapsed), error count badge, expand toggle

**All structural directives:** `@if`, `@for`, `@switch` (new block syntax).  
**Subscriptions:** single `vm$ | async` binding, `Subject<TranslateRequest | null>` trigger, `switchMap` cancels previous.

---

### Step 9 — Wire up and register

- `translate_bp` registered in `server/app/__init__.py`
- `nl2fl-worker` added to `docker-compose.yml`
- `CELERY_NL2FL_QUEUE` added to `server/config.py` `Config` base class
- Route `/translation` already in `frontend/src/app/app.routes.ts` — no change needed

---

## File Checklist

### New files
- `nl2fl/Dockerfile`
- `nl2fl/requirements.txt`
- `nl2fl/celery_service.py`
- `nl2fl/tasks.py`
- `nl2fl/nl2fl_service.py`
- `server/app/api/translate.py`
- `server/app/models/user_api_key.py`
- `server/app/services/integrations/translate_client.py`
- `server/migrations/versions/<hash>_add_user_api_keys.py`

### Modified files
- `server/app/__init__.py` — register `translate_bp`
- `server/config.py` — add `CELERY_NL2FL_QUEUE`
- `docker-compose.yml` — add `nl2fl-worker` service + env vars
- `frontend/src/app/task.models.ts` — new interfaces
- `frontend/src/app/task.service.ts` — new methods
- `frontend/src/app/pages/translation-page/translation-page.ts` — full rewrite
- `frontend/src/app/pages/translation-page/translation-page.html` — full rewrite
- `frontend/src/app/pages/translation-page/translation-page.css` — full rewrite

---

## Implementation Order (suggested)

1. Step 1 — DB model + migration
2. Step 2 — `nl2fl/` worker (pure Python, testable standalone)
3. Step 3 — `translate_client.py`
4. Step 4 — `translate.py` blueprint + register
5. Step 5 — `docker-compose.yml`
6. Step 6-7 — TypeScript models + service methods
7. Step 8 — Translation page UI
8. Step 9 — Final wiring + smoke test
