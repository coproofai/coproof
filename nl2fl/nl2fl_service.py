"""
nl2fl_service.py
~~~~~~~~~~~~~~~~
Translates a natural-language mathematical statement into a verified Lean 4
proof by calling an LLM directly (OpenAI / Anthropic / Google / DeepSeek),
then validates the result against the Lean compiler via the lean_queue Celery
worker.

Retry loop:
  1. Ask the LLM to produce Lean 4 code.
  2. Send the code to the Lean verifier.
  3. If valid  → return success.
  4. If invalid and attempts remain → feed compiler errors back to the LLM
     as a follow-up user message and try again.
  5. If max_retries exhausted → return failure with full attempt history.

Model ID format: "<provider>/<model-name>"
  openai/gpt-4o               → OpenAI Chat Completions API
  anthropic/claude-3-5-sonnet → Anthropic Messages API
  google/gemini-2.0-flash     → Google Generative Language API
  deepseek/deepseek-chat      → DeepSeek (OpenAI-compatible) API
"""

import os
import re
import time
import logging

import requests
from celery import Celery

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

LLM_TIMEOUT = 300  # seconds per HTTP request (5 minutes)

# Base URL of the local Copilot FastAPI proxy (used by the 'mock' provider).
# Inside Docker on Windows/macOS use host.docker.internal; override via env var.
COPILOT_BASE_URL = os.environ.get('COPILOT_BASE_URL', 'http://host.docker.internal:8000')
COPILOT_MODEL = 'claude-sonnet-4-6'  # model sent to the /copilot endpoint

DEFAULT_SYSTEM_PROMPT = (
    'You are an expert Lean 4 theorem prover. '
    'Given a mathematical statement in natural language, produce ONLY valid Lean 4 code '
    'that formally states and proves the theorem. '
    'Wrap the code in a single ```lean ... ``` fenced block. '
    'Do not include any explanatory text outside the fenced block. '
    'Use Mathlib4 imports where appropriate.'
)

ERROR_FEEDBACK_TEMPLATE = (
    'The Lean 4 code you produced has the following compiler errors. '
    'Please fix every error and return an updated ```lean ... ``` block:\n\n{errors}'
)

# ---------------------------------------------------------------------------
# Provider-specific callers
# ---------------------------------------------------------------------------

def _call_openai_compat(messages: list[dict], model_name: str,
                         api_key: str, base_url: str) -> str:
    """Call any OpenAI-compatible chat completions endpoint."""
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }
    payload = {
        'model': model_name,
        'messages': messages,
        'stream': False,
    }
    print(f'[nl2fl DEBUG] POST {base_url} model={model_name} '
          f'api_key_len={len(api_key)} api_key_prefix={api_key[:8] if api_key else "EMPTY"}',
          flush=True)
    resp = requests.post(base_url, json=payload, headers=headers, timeout=LLM_TIMEOUT)
    print(f'[nl2fl DEBUG] response status={resp.status_code}', flush=True)
    if not resp.ok:
        raise RuntimeError(f'API error {resp.status_code}: {resp.text[:400]}')
    data = resp.json()
    choices = data.get('choices') or []
    if not choices:
        raise RuntimeError(f'No choices in response: {data}')
    return choices[0]['message']['content']


def _call_anthropic(messages: list[dict], model_name: str, api_key: str) -> str:
    """Call the Anthropic Messages API."""
    system = next((m['content'] for m in messages if m['role'] == 'system'), None)
    user_messages = [m for m in messages if m['role'] != 'system']
    headers = {
        'x-api-key': api_key,
        'anthropic-version': '2023-06-01',
        'Content-Type': 'application/json',
    }
    payload: dict = {
        'model': model_name,
        'max_tokens': 4096,
        'messages': user_messages,
    }
    if system:
        payload['system'] = system
    print(f'[nl2fl DEBUG] POST anthropic/v1/messages model={model_name} '
          f'api_key_len={len(api_key)} api_key_prefix={api_key[:8] if api_key else "EMPTY"}',
          flush=True)
    resp = requests.post(
        'https://api.anthropic.com/v1/messages',
        json=payload, headers=headers, timeout=LLM_TIMEOUT,
    )
    print(f'[nl2fl DEBUG] response status={resp.status_code}', flush=True)
    if not resp.ok:
        raise RuntimeError(f'Anthropic error {resp.status_code}: {resp.text[:400]}')
    data = resp.json()
    content = data.get('content') or []
    if not content:
        raise RuntimeError(f'No content in Anthropic response: {data}')
    return content[0]['text']


def _call_google(messages: list[dict], model_name: str, api_key: str) -> str:
    """Call the Google Generative Language (Gemini) API."""
    system = next((m['content'] for m in messages if m['role'] == 'system'), None)
    gemini_contents = []
    for m in messages:
        if m['role'] == 'system':
            continue
        role = 'model' if m['role'] == 'assistant' else 'user'
        gemini_contents.append({'role': role, 'parts': [{'text': m['content']}]})
    payload: dict = {'contents': gemini_contents}
    if system:
        payload['system_instruction'] = {'parts': [{'text': system}]}
    url = (
        f'https://generativelanguage.googleapis.com/v1beta'
        f'/models/{model_name}:generateContent?key={api_key}'
    )
    print(f'[nl2fl DEBUG] POST google model={model_name} '
          f'api_key_len={len(api_key)} api_key_prefix={api_key[:8] if api_key else "EMPTY"}',
          flush=True)
    resp = requests.post(url, json=payload,
                         headers={'Content-Type': 'application/json'},
                         timeout=LLM_TIMEOUT)
    print(f'[nl2fl DEBUG] response status={resp.status_code}', flush=True)
    if not resp.ok:
        raise RuntimeError(f'Google error {resp.status_code}: {resp.text[:400]}')
    data = resp.json()
    candidates = data.get('candidates') or []
    if not candidates:
        raise RuntimeError(f'No candidates in Google response: {data}')
    parts = candidates[0].get('content', {}).get('parts', [])
    if not parts:
        raise RuntimeError(f'No parts in Google response: {data}')
    return parts[0]['text']


def _call_llm(messages: list[dict], model_id: str, api_key: str) -> str:
    """
    Route a chat-completion request to the correct provider.
    model_id format: "<provider>/<model-name>"
    """
    provider, _, model_name = model_id.partition('/')
    logger.info('[nl2fl] _call_llm provider=%s model=%s api_key_len=%d api_key_prefix=%s',
                provider, model_name, len(api_key), api_key[:8] if api_key else 'EMPTY')

    if provider == 'openai':
        return _call_openai_compat(
            messages, model_name, api_key,
            'https://api.openai.com/v1/chat/completions',
        )
    elif provider == 'anthropic':
        return _call_anthropic(messages, model_name, api_key)
    elif provider == 'google':
        return _call_google(messages, model_name, api_key)
    elif provider == 'deepseek':
        return _call_openai_compat(
            messages, model_name, api_key,
            'https://api.deepseek.com/v1/chat/completions',
        )
    elif provider == 'github':
        # GitHub Models API is OpenAI-compatible.
        # model_name here is everything after the first '/', e.g. "openai/gpt-4o"
        return _call_openai_compat(
            messages, model_name, api_key,
            'https://models.github.ai/inference/chat/completions',
        )
    elif provider == 'mock':
        # Forwards the conversation to a local FastAPI /copilot endpoint.
        # - system_prompt is sent as a top-level field.
        # - All prior turns (natural text, previous Lean proposals, error feedback)
        #   are concatenated into a single `prompt` so the proxy has full context.
        # The api_key is ignored — the local service handles auth itself.
        system_prompt_text = next(
            (m['content'] for m in messages if m['role'] == 'system'), ''
        )
        # Build the conversation body from all non-system messages
        conversation_parts = []
        for m in messages:
            if m['role'] == 'system':
                continue
            role_label = 'Assistant (previous Lean proposal)' if m['role'] == 'assistant' else 'User'
            conversation_parts.append(f'[{role_label}]\n{m["content"]}')
        prompt = '\n\n'.join(conversation_parts)

        base_url = COPILOT_BASE_URL.rstrip('/')
        print(f'[nl2fl DEBUG] mock provider POST {base_url}/copilot '
              f'prompt_len={len(prompt)} system_prompt_len={len(system_prompt_text)}',
              flush=True)
        resp = requests.post(
            f'{base_url}/copilot',
            json={
                'prompt': prompt,
                'model': COPILOT_MODEL,
                'system_prompt': system_prompt_text,
            },
            timeout=LLM_TIMEOUT,
        )
        if not resp.ok:
            raise RuntimeError(f'Copilot proxy error {resp.status_code}: {resp.text[:400]}')
        data = resp.json()
        answer = data.get('answer') or ''
        if not answer:
            raise RuntimeError(f'Copilot proxy returned no answer: {data}')
        print(f'[nl2fl DEBUG] mock provider answer_len={len(answer)}', flush=True)
        return answer
    else:
        raise RuntimeError(
            f'Unknown provider "{provider}". '
            f'Supported: openai, anthropic, google, deepseek, github, mock'
        )


# ---------------------------------------------------------------------------
# Lean Celery helper
# ---------------------------------------------------------------------------

def _lean_celery() -> Celery:
    """Return a Celery client connected to the lean_queue broker."""
    redis_url = os.environ.get('REDIS_URL', 'redis://redis:6379/0')
    return Celery('nl2fl_lean_client', broker=redis_url, backend=redis_url)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _extract_lean_code(text: str) -> str:
    """
    Extract the first ```lean ... ``` fenced block from *text*.
    Falls back to the full text if no fence is found (tolerates non-conforming
    models).
    """
    match = re.search(r'```lean\s*(.*?)```', text, re.DOTALL)
    if match:
        return match.group(1).strip()
    # Fallback: strip any outer ``` fences (language-agnostic)
    match = re.search(r'```\s*(.*?)```', text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text.strip()


def _verify_with_lean(lean_code: str) -> dict:
    """
    Dispatch *lean_code* to the Lean Celery worker (lean_queue) and wait for
    the result synchronously (we are already inside a Celery task so blocking
    is acceptable here).

    Returns the VerifyCompilerResult dict:
        { valid, errors, processing_time_seconds, return_code,
          message_count, theorem_count }
    """
    lean_queue = os.environ.get('CELERY_LEAN_QUEUE', 'lean_queue')
    client = _lean_celery()
    task = client.send_task(
        'tasks.verify_snippet',
        args=[lean_code, 'nl2fl_output.lean'],
        queue=lean_queue,
    )
    # Lean verification can take up to 60 s; allow a generous timeout.
    # disable_sync_subtasks=False is required when calling .get() from inside
    # another Celery task (the nl2fl worker is itself a task).
    return task.get(timeout=90, disable_sync_subtasks=False)


def _format_errors(errors: list[dict]) -> str:
    """Format a list of VerificationErrorItem dicts into a readable string."""
    if not errors:
        return 'No specific error messages were returned. The code may have timed out or encountered a runtime error.'
    lines = []
    for err in errors:
        lines.append(f'  Line {err.get("line", "?")}, Col {err.get("column", "?")}: {err.get("message", "")}')
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def translate_and_verify(
    natural_text: str,
    model_id: str,
    api_key: str,
    max_retries: int = 3,
    system_prompt: str | None = None,
) -> dict:
    """
    Full NL→Lean translation + verification pipeline.

    Parameters
    ----------
    natural_text : str
        The mathematical statement in natural language.
    model_id : str
        OpenRouter model identifier, e.g. ``"openai/gpt-4o"``.
    api_key : str
        Decrypted OpenRouter API key for *model_id*.
    max_retries : int
        Maximum number of LLM → verify cycles (default 3).
    system_prompt : str | None
        Override the default system prompt (``None`` uses DEFAULT_SYSTEM_PROMPT).

    Returns
    -------
    dict  matching ``TranslationResult`` on the frontend::

        {
            "valid": bool,
            "attempts": int,
            "final_lean": str,
            "history": [
                {
                    "attempt": int,
                    "lean_code": str,
                    "errors": [ {"line": int, "column": int, "message": str} ]
                },
                ...
            ],
            "processing_time_seconds": float
        }
    """
    if not natural_text or not natural_text.strip():
        raise ValueError('natural_text must not be empty.')
    if not model_id:
        raise ValueError('model_id must not be empty.')
    if not api_key:
        raise ValueError('api_key must not be empty.')

    effective_prompt = system_prompt if system_prompt else DEFAULT_SYSTEM_PROMPT
    max_retries = max(1, min(int(max_retries), 10))

    start_time = time.perf_counter()
    history: list[dict] = []

    # Initial conversation context
    messages: list[dict] = [
        {'role': 'system', 'content': effective_prompt},
        {'role': 'user',   'content': natural_text},
    ]

    final_lean = ''
    valid = False

    for attempt in range(1, max_retries + 1):
        logger.info('[nl2fl] attempt %d/%d, model=%s api_key_len=%d api_key_prefix=%s',
                    attempt, max_retries, model_id, len(api_key), api_key[:8] if api_key else 'EMPTY')
        print(f'[nl2fl DEBUG] attempt={attempt} model={model_id} '
              f'api_key_len={len(api_key)} api_key_prefix={api_key[:8] if api_key else "EMPTY"}',
              flush=True)

        # --- Step 1: Ask LLM ---
        try:
            llm_reply = _call_llm(messages, model_id, api_key)
        except Exception as exc:
            logger.error('[nl2fl] OpenRouter error on attempt %d: %s', attempt, exc)
            history.append({
                'attempt': attempt,
                'lean_code': '',
                'errors': [{'line': 0, 'column': 0, 'message': f'LLM error: {exc}'}],
            })
            break  # fatal — stop retrying on LLM errors

        lean_code = _extract_lean_code(llm_reply)
        final_lean = lean_code

        # --- Step 2: Verify ---
        try:
            verification = _verify_with_lean(lean_code)
        except Exception as exc:
            logger.error('[nl2fl] Lean verification error on attempt %d: %s', attempt, exc)
            verification = {
                'valid': False,
                'errors': [{'line': 0, 'column': 0, 'message': f'Lean worker error: {exc}'}],
            }

        errors: list[dict] = verification.get('errors', [])
        valid = bool(verification.get('valid', False))

        history.append({
            'attempt': attempt,
            'lean_code': lean_code,
            'errors': errors,
        })

        if valid:
            logger.info('[nl2fl] verified successfully on attempt %d', attempt)
            break

        # --- Step 3: Feed errors back if retries remain ---
        if attempt < max_retries:
            # Append the assistant's proposal and user's error feedback
            messages.append({'role': 'assistant', 'content': llm_reply})
            messages.append({
                'role': 'user',
                'content': ERROR_FEEDBACK_TEMPLATE.format(errors=_format_errors(errors)),
            })

    return {
        'valid': valid,
        'attempts': len(history),
        'final_lean': final_lean,
        'history': history,
        'processing_time_seconds': round(time.perf_counter() - start_time, 3),
    }


# ---------------------------------------------------------------------------
# FL → NL  (converse translation)
# ---------------------------------------------------------------------------

FL2NL_SYSTEM_PROMPT = (
    'You are a mathematician and Lean 4 expert. '
    'Given a Lean 4 formal mathematical statement (theorem, lemma, or definition), '
    'produce a clear and precise natural-language description suitable for a math paper. '
    'Requirements:\n'
    '- Write in LaTeX-compatible prose (use $...$ for inline math and $$...$$ for display math).\n'
    '- State the mathematical meaning directly; do NOT describe the Lean syntax.\n'
    '- Include all relevant hypotheses and conclusions.\n'
    '- Be concise but complete: one to three paragraphs maximum.\n'
    '- Do NOT include any Lean code in the output.'
)


def fl_to_nl(
    lean_code: str,
    model_id: str,
    api_key: str,
    system_prompt: str | None = None,
) -> dict:
    """
    Translate a Lean 4 formal statement into natural-language prose (with LaTeX).

    Parameters
    ----------
    lean_code : str
        The Lean 4 source to describe.
    model_id : str
        Provider/model identifier (e.g. ``"openai/gpt-4o"``).
    api_key : str
        Decrypted API key for the provider.
    system_prompt : str | None
        Override the default FL2NL system prompt.

    Returns
    -------
    dict::

        {
            "natural_text": str,          # LaTeX-ready prose
            "processing_time_seconds": float
        }
    """
    if not lean_code or not lean_code.strip():
        raise ValueError('lean_code must not be empty.')
    if not model_id:
        raise ValueError('model_id must not be empty.')
    if not api_key:
        raise ValueError('api_key must not be empty.')

    effective_system = system_prompt if system_prompt else FL2NL_SYSTEM_PROMPT

    start_time = time.perf_counter()

    messages: list[dict] = [
        {'role': 'system', 'content': effective_system},
        {'role': 'user',   'content': lean_code.strip()},
    ]

    try:
        reply = _call_llm(messages, model_id, api_key)
    except Exception as exc:
        logger.error('[fl2nl] LLM error: %s', exc)
        raise

    return {
        'natural_text': reply.strip(),
        'processing_time_seconds': round(time.perf_counter() - start_time, 3),
    }
