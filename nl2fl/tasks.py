from celery_service import celery
from nl2fl_service import translate_and_verify, fl_to_nl


@celery.task(name='tasks.translate_and_verify')
def translate_and_verify_task(payload: dict) -> dict:
    return translate_and_verify(
        natural_text=payload['natural_text'],
        model_id=payload['model_id'],
        api_key=payload['api_key'],
        max_retries=payload.get('max_retries', 3),
        system_prompt=payload.get('system_prompt'),
    )


@celery.task(name='tasks.fl_to_nl')
def fl_to_nl_task(payload: dict) -> dict:
    return fl_to_nl(
        lean_code=payload['lean_code'],
        model_id=payload['model_id'],
        api_key=payload['api_key'],
        system_prompt=payload.get('system_prompt'),
    )
