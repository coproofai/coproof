from celery_service import celery
from computation_service import run_cluster_computation_job


@celery.task(name="tasks.run_cluster_computation")
def run_cluster_computation(payload: dict):
    return run_cluster_computation_job(payload)
