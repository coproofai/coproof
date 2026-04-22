"""
agents_service.py
~~~~~~~~~~~~~~~~~
Forwards a natural-language prompt to a configurable LLM and returns the
model's natural-language suggestion.  Unlike the NL2FL pipeline there is no
Lean compilation step and no retry loop — one prompt, one response.

Model ID format: "<provider>/<model-name>"
  openai/gpt-4o               → OpenAI Chat Completions API
  anthropic/claude-3-5-sonnet → Anthropic Messages API
  google/gemini-2.0-flash     → Google Generative Language API
  deepseek/deepseek-chat      → DeepSeek (OpenAI-compatible) API
  github/openai/gpt-4o        → GitHub Models (OpenAI-compatible)
  mock/...                    → Local Copilot FastAPI proxy
"""

import os
import time
import logging

import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

LLM_TIMEOUT = 120  # seconds per HTTP request

# Base URL of the local Copilot FastAPI proxy (used by the 'mock' provider).
COPILOT_BASE_URL = os.environ.get('COPILOT_BASE_URL', 'http://host.docker.internal:8000')
COPILOT_MODEL = 'claude-sonnet-4-6'

DEFAULT_SYSTEM_PROMPT = (
    'You are a helpful mathematical assistant working within the CoProof formal '
    'verification platform. '
    'Given a prompt, produce a clear, concise natural-language suggestion. '
    'Do not produce Lean 4 code unless explicitly asked.'
)

# ---------------------------------------------------------------------------
# Provider-specific callers  (mirrored from nl2fl_service.py)
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
    print(f'[agents DEBUG] POST {base_url} model={model_name} '
          f'api_key_len={len(api_key)} api_key_prefix={api_key[:8] if api_key else "EMPTY"}',
          flush=True)
    resp = requests.post(base_url, json=payload, headers=headers, timeout=LLM_TIMEOUT)
    print(f'[agents DEBUG] response status={resp.status_code}', flush=True)
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
    print(f'[agents DEBUG] POST anthropic/v1/messages model={model_name} '
          f'api_key_len={len(api_key)} api_key_prefix={api_key[:8] if api_key else "EMPTY"}',
          flush=True)
    resp = requests.post(
        'https://api.anthropic.com/v1/messages',
        json=payload, headers=headers, timeout=LLM_TIMEOUT,
    )
    print(f'[agents DEBUG] response status={resp.status_code}', flush=True)
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
    print(f'[agents DEBUG] POST google model={model_name} '
          f'api_key_len={len(api_key)} api_key_prefix={api_key[:8] if api_key else "EMPTY"}',
          flush=True)
    resp = requests.post(
        url, json=payload,
        headers={'Content-Type': 'application/json'},
        timeout=LLM_TIMEOUT,
    )
    print(f'[agents DEBUG] response status={resp.status_code}', flush=True)
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
    logger.info('[agents] _call_llm provider=%s model=%s api_key_len=%d api_key_prefix=%s',
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
        return _call_openai_compat(
            messages, model_name, api_key,
            'https://models.github.ai/inference/chat/completions',
        )
    elif provider == 'mock':
        # Forwards the conversation to a local FastAPI /copilot endpoint.
        # The api_key is ignored — the local service handles auth itself.
        system_prompt_text = next(
            (m['content'] for m in messages if m['role'] == 'system'), ''
        )
        # Build the conversation body from all non-system messages
        conversation_parts = []
        for m in messages:
            if m['role'] == 'system':
                continue
            role_label = 'Assistant' if m['role'] == 'assistant' else 'User'
            conversation_parts.append(f'[{role_label}]\n{m["content"]}')
        prompt = '\n\n'.join(conversation_parts)
        base_url = COPILOT_BASE_URL.rstrip('/')
        print(f'[agents DEBUG] mock provider POST {base_url}/copilot '
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
        print(f'[agents DEBUG] mock provider answer_len={len(answer)}', flush=True)
        return answer
    else:
        raise RuntimeError(
            f'Unknown provider "{provider}". '
            f'Supported: openai, anthropic, google, deepseek, github, mock'
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def suggest(
    prompt: str,
    model_id: str,
    api_key: str,
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    context: str | None = None,
) -> dict:
    """
    Send *prompt* (with optional *context*) to the specified LLM and return
    the natural-language suggestion.

    Args:
        prompt:        The user's question or instruction.
        model_id:      Provider-qualified model identifier, e.g. "openai/gpt-4o".
        api_key:       Plaintext API key for the provider (decrypted before dispatch).
        system_prompt: Override the default assistant persona if needed.
        context:       Optional extra context (e.g. a Lean snippet or project
                       description) prepended to the user message.

    Returns:
        {
            "suggestion":               str,
            "model_id":                 str,
            "processing_time_seconds":  float,
        }
    """
    user_content = f'{context}\n\n{prompt}' if context else prompt
    messages = [
        {'role': 'system', 'content': system_prompt},
        {'role': 'user',   'content': user_content},
    ]

    start = time.time()
    suggestion = _call_llm(messages, model_id, api_key)
    elapsed = round(time.time() - start, 2)

    return {
        'suggestion': suggestion,
        'model_id': model_id,
        'processing_time_seconds': elapsed,
    }
