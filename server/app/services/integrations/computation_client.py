import logging
import os
import time
from celery import Celery
from celery.exceptions import CeleryError, TimeoutError
from app.exceptions import CoProofError

logger = logging.getLogger(__name__)


# Languages routed to the RPI cluster worker instead of the local Python worker.
_CLUSTER_LANGUAGES = {'mpi'}


class ComputationClient:
    """Interface for the external computation worker via Celery."""

    REDIS_URL = os.environ.get('REDIS_URL', 'redis://redis:6379/0')
    COMPUTATION_QUEUE_NAME = os.environ.get('CELERY_COMPUTATION_QUEUE', 'computation_queue')
    CLUSTER_COMPUTATION_QUEUE_NAME = os.environ.get('CELERY_CLUSTER_COMPUTATION_QUEUE', 'cluster_computation_queue')
    _celery = None

    @classmethod
    def _get_celery(cls):
        if cls._celery is None:
            cls._celery = Celery(
                'computation_client',
                broker=cls.REDIS_URL,
                backend=cls.REDIS_URL,
            )
        return cls._celery

    @classmethod
    def _dispatch_task(cls, task_name: str, args: list, timeout: int, queue: str):
        try:
            task = cls._get_celery().send_task(
                task_name,
                args=args,
                queue=queue,
            )
            return task.get(timeout=timeout)
        except TimeoutError as error:
            logger.error(f'Computation worker task timeout ({task_name}): {error}')
            raise CoProofError('Computation Worker Timeout', code=504)
        except CeleryError as error:
            logger.error(f'Computation worker task failure ({task_name}): {error}')
            raise CoProofError(f'Computation Worker Unavailable: {str(error)}', code=503)
        except Exception as error:
            logger.error(f'Computation worker dispatch error ({task_name}): {error}')
            raise CoProofError(f'Computation Worker Unavailable: {str(error)}', code=503)

    @staticmethod
    def run_computation(job: dict):
        if not isinstance(job, dict):
            raise CoProofError('Computation job payload must be an object.', code=400)

        timeout_seconds = int(job.get('timeout_seconds') or 120)
        language = (job.get('language') or 'python').strip().lower()

        if language in _CLUSTER_LANGUAGES:
            task_name = 'tasks.run_cluster_computation'
            queue = ComputationClient.CLUSTER_COMPUTATION_QUEUE_NAME
        else:
            task_name = 'tasks.run_computation'
            queue = ComputationClient.COMPUTATION_QUEUE_NAME

        try:
            started = time.perf_counter()
            data = ComputationClient._dispatch_task(
                task_name,
                [job],
                timeout=timeout_seconds + 10,
                queue=queue,
            )
            elapsed = time.perf_counter() - started

            if 'processing_time_seconds' not in data:
                data['processing_time_seconds'] = round(elapsed, 6)
                data['timing_source'] = 'backend_fallback'
            else:
                data['timing_source'] = 'computation_worker'

            data['roundtrip_time_seconds'] = round(elapsed, 6)
            return data
        except CoProofError:
            raise
        except Exception as error:
            logger.error(f'Computation run failed: {error}')
            raise CoProofError(f'Computation Service Unavailable: {str(error)}', code=503)