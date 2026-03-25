from celery_service import celery
from computation_service import run_computation_job


@celery.task(name='tasks.run_computation')
def run_computation(payload: dict):
    return run_computation_job(payload)