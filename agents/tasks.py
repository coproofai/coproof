from celery_service import celery
from agents_service import suggest, DEFAULT_SYSTEM_PROMPT


@celery.task(name='tasks.suggest')
def suggest_task(payload: dict) -> dict:
    return suggest(
        prompt=payload['prompt'],
        model_id=payload['model_id'],
        api_key=payload['api_key'],
        system_prompt=payload.get('system_prompt', DEFAULT_SYSTEM_PROMPT),
        context=payload.get('context'),
    )
