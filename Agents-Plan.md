# Agents — LLM Suggestion Microservice Plan

## Overview

The Agents microservice receives a natural-language prompt (and optional contextual data such as a
Lean theorem or project description), forwards it to a configurable LLM, and returns the model's
natural-language suggestion.  Unlike the NL2FL pipeline there is **no Lean compilation step** and
**no retry loop** — one prompt, one response.  The service is designed to be a general-purpose
"suggest" primitive that other parts of the UI (workspace, project creation, etc.) can call
whenever they need an AI-generated text suggestion.

---

## Architecture

```
Frontend (Angular)
  Any page component
    │
    ▼
TaskService  ─────────────────────────────────────────────────────────────────┐
  │  POST /api/v1/agents/suggest/submit                                       │
  │  GET  /api/v1/agents/suggest/<task_id>/result  (polling)                  │
  │  GET  /api/v1/agents/models                    (model catalogue — shared  │
  │                                                 with translate blueprint) │
  └──────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
Flask server  (server/app/api/agents.py)
  AgentsClient  (server/app/services/integrations/agents_client.py)
                              │
                              ▼
              Redis / Celery  ─────────  agents-worker service
                                           (agents/)
                                           ├── celery_service.py
                                           ├── tasks.py
                                           └── agents_service.py
                                               └── suggest()
```

---

## Steps

### Step 1 — New Celery worker microservice: `agents/`

Mirror the structure of `nl2fl/`:

```
agents/
├── Dockerfile
├── requirements.txt        # celery, redis, requests
├── celery_service.py       # Celery app wired to agents_queue
├── tasks.py                # @celery.task suggest
└── agents_service.py       # core logic (see below)
```

**`agents_service.py` — `suggest` function:**

```python
def suggest(
    prompt: str,
    model_id: str,
    api_key: str,               # decrypted at server, passed in as plaintext
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    context: str | None = None, # optional extra context prepended to the user message
) -> dict:
```

Logic (single shot, no retry):
1. Build messages:
   ```
   [
     { role: "system",    content: system_prompt },
     { role: "user",      content: f"{context}\n\n{prompt}" if context else prompt }
   ]
   ```
2. Route to the appropriate provider based on `model_id` prefix (same provider dispatch
   table as `nl2fl_service.py`: `openai/`, `anthropic/`, `google/`, `deepseek/`, `github/`, `mock`).
3. Call the provider API once (no loop).
4. Extract the text reply from the response.
5. Return:
   ```json
   {
     "suggestion": "...",
     "model_id": "openai/gpt-4o",
     "processing_time_seconds": 2.1
   }
   ```

**`DEFAULT_SYSTEM_PROMPT`** (module-level constant):
```
You are a helpful mathematical assistant working within the CoProof formal verification platform.
Given a prompt, produce a clear, concise natural-language suggestion.
Do not produce Lean 4 code unless explicitly asked.
```

**`celery_service.py`:**
```python
queue_name = os.environ.get('CELERY_AGENTS_QUEUE', 'agents_queue')
celery = Celery('agents_worker', broker=REDIS_URL, backend=REDIS_URL)
celery.conf.update(
    task_default_queue=queue_name,
    task_routes={'tasks.*': {'queue': queue_name}},
)
import tasks  # noqa
```

**`tasks.py`:**
```python
@celery.task(name='tasks.suggest')
def suggest_task(payload: dict) -> dict:
    return suggest(
        prompt=payload['prompt'],
        model_id=payload['model_id'],
        api_key=payload['api_key'],
        system_prompt=payload.get('system_prompt', DEFAULT_SYSTEM_PROMPT),
        context=payload.get('context'),
    )
```

**`requirements.txt`:** `celery`, `redis`, `requests`

**`Dockerfile`:** identical pattern to `nl2fl/Dockerfile` — Python 3.12-slim, install requirements,
`CMD ["python", "celery_service.py"]`.

---

### Step 2 — Flask integration client: `server/app/services/integrations/agents_client.py`

Mirror `translate_client.py`, but without the FL2NL variant:

```python
class AgentsClient:
    REDIS_URL = os.environ.get('REDIS_URL', 'redis://redis:6379/0')
    AGENTS_QUEUE_NAME = os.environ.get('CELERY_AGENTS_QUEUE', 'agents_queue')
    _celery = None

    @classmethod
    def submit(cls, payload: dict) -> str:
        """Dispatch suggest task, return task_id immediately (non-blocking)."""
        # payload keys: prompt, model_id, api_key, system_prompt?, context?
        task = cls._get_celery().send_task(
            'tasks.suggest',
            args=[payload],
            queue=cls.AGENTS_QUEUE_NAME,
        )
        return task.id

    @classmethod
    def get_result(cls, task_id: str) -> dict | None:
        """Return suggestion dict or None if still pending. Raises CoProofError on failure."""
        async_result = cls._get_celery().AsyncResult(task_id)
        if not async_result.ready():
            return None
        if async_result.successful():
            return async_result.result
        raise CoProofError(f'Agents task failed: {async_result.result}', code=500)
```

---

### Step 3 — Flask blueprint: `server/app/api/agents.py`

Endpoints:

| Method | Route | Auth | Description |
|--------|-------|------|-------------|
| `POST` | `/api/v1/agents/suggest/submit` | optional JWT | Submit prompt + model_id → `{ task_id }` |
| `GET`  | `/api/v1/agents/suggest/<task_id>/result` | — | Poll result |

**`POST /api/v1/agents/suggest/submit` body (JSON):**
```json
{
  "prompt":        "Suggest a name for a lemma about even numbers",
  "model_id":      "openai/gpt-4o",
  "api_key":       "sk-...",          // optional if user has a saved key
  "system_prompt": "...",             // optional override
  "context":       "import Mathlib\n..." // optional extra context
}
```

**`GET /api/v1/agents/suggest/<task_id>/result` response:**
- `202 { "status": "pending" }` while running
- `200 { "suggestion": "...", "model_id": "...", "processing_time_seconds": 1.8 }` when done

**Key/auth resolution** (same pattern as `translate.py`):
1. If `api_key` present in body → use it directly.
2. Else if JWT identity present → look up `UserApiKey` for `(user_id, model_id)` and decrypt.
3. Else → return `400` with message asking for a key.

**Register** `agents_bp` in `server/app/__init__.py` with prefix `/api/v1/agents`.

> **Note:** The model catalogue (`GET /api/v1/translate/models`) and API key management
> (`POST/GET /api/v1/translate/api-key`) are **reused** from the translate blueprint —
> no duplication needed.

---

### Step 4 — `server/config.py` — add queue name

```python
CELERY_AGENTS_QUEUE = os.environ.get('CELERY_AGENTS_QUEUE', 'agents_queue')
```

---

### Step 5 — `docker-compose.yml` — new service `agents-worker`

```yaml
agents-worker:
  build:
    context: ./agents
    dockerfile: Dockerfile
  environment:
    - REDIS_URL=redis://redis:6379/0
    - CELERY_AGENTS_QUEUE=agents_queue
  depends_on:
    - redis
```

Add `CELERY_AGENTS_QUEUE=agents_queue` to the `environment` blocks of both `web` and
`celery_worker`.

Add `agents-worker: condition: service_started` to the `depends_on` blocks of both `web` and
`celery_worker`.

---

### Step 6 — TypeScript models: `frontend/src/app/task.models.ts`

Add:

```typescript
export interface SuggestPayload {
  prompt: string;
  model_id: string;
  api_key?: string;
  system_prompt?: string;
  context?: string;
}

export interface SuggestResult {
  suggestion: string;
  model_id: string;
  processing_time_seconds: number;
}
```

---

### Step 7 — `task.service.ts` — new methods

```typescript
submitSuggest(payload: SuggestPayload): Observable<{ task_id: string }>
getSuggestResult(taskId: string): Observable<SuggestResult | { status: 'pending' }>
```

Both follow the same pattern as `submitFl2nl` / `getFl2nlResult`.

---

### Step 8 — Usage in existing pages

The `suggest` endpoint is a generic primitive.  Any component that already has a model selected
and an API key saved can call it.  Initial planned call sites:

| Page | Trigger | Prompt | Context |
|------|---------|--------|---------|
| Workspace → Node tab | "IA Auto" button (placeholder) | Free-form user input | Current node's `leanCode` |
| Create Project → NL tab | "Sugerir enunciado" helper | User's `nlDescription` partial text | Project definitions |

Call-site integration is handled per-page, not in this microservice plan.

---

### Step 9 — Wire up and register

- `agents_bp` registered in `server/app/__init__.py`
- `agents-worker` added to `docker-compose.yml`
- `CELERY_AGENTS_QUEUE` added to `server/config.py` `Config` base class
- TypeScript interfaces added to `task.models.ts`
- Service methods added to `task.service.ts`

---

## File Checklist

### New files
- `agents/Dockerfile`
- `agents/requirements.txt`
- `agents/celery_service.py`
- `agents/tasks.py`
- `agents/agents_service.py`
- `server/app/api/agents.py`
- `server/app/services/integrations/agents_client.py`

### Modified files
- `server/app/__init__.py` — register `agents_bp`
- `server/config.py` — add `CELERY_AGENTS_QUEUE`
- `docker-compose.yml` — add `agents-worker` service + env vars in `web` / `celery_worker`
- `frontend/src/app/task.models.ts` — `SuggestPayload`, `SuggestResult`
- `frontend/src/app/task.service.ts` — `submitSuggest()`, `getSuggestResult()`

---

## Implementation Order (suggested)

1. Step 1 — `agents/` worker (pure Python, testable standalone with a Redis instance)
2. Step 2 — `agents_client.py`
3. Step 3 — `agents.py` blueprint + register
4. Step 4 — `server/config.py`
5. Step 5 — `docker-compose.yml`
6. Step 6–7 — TypeScript models + service methods
7. Step 8 — Wire first call site (Workspace IA Auto placeholder)
8. Step 9 — Smoke test end-to-end
