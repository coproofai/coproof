from celery_service import celery
from nl2fl_service import translate_and_verify


@celery.task(name='tasks.translate_and_verify')
def translate_and_verify_task(payload: dict) -> dict:
    return translate_and_verify(
        natural_text=payload['natural_text'],
        model_id=payload['model_id'],
        api_key=payload['api_key'],
        max_retries=payload.get('max_retries', 3),
        system_prompt=payload.get('system_prompt'),
    )
