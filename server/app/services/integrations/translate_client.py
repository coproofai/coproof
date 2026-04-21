import logging
import os
from celery import Celery
from celery.exceptions import CeleryError, TimeoutError
from app.exceptions import CoProofError

logger = logging.getLogger(__name__)


class TranslateClient:
    """
    Interface for the external NL2FL worker via Celery.

    Uses the same non-blocking dispatch pattern as CompilerClient:
      - submit()     → sends task, returns task_id immediately (no blocking)
      - get_result() → checks AsyncResult.ready(), returns result or None
    """

    REDIS_URL = os.environ.get('REDIS_URL', 'redis://redis:6379/0')
    NL2FL_QUEUE_NAME = os.environ.get('CELERY_NL2FL_QUEUE', 'nl2fl_queue')
    _celery = None

    @classmethod
    def _get_celery(cls) -> Celery:
        if cls._celery is None:
            cls._celery = Celery(
                'translate_client',
                broker=cls.REDIS_URL,
                backend=cls.REDIS_URL,
            )
        return cls._celery

    @classmethod
    def submit(cls, payload: dict) -> str:
        """
        Dispatch a translation+verification job to the nl2fl worker.

        Parameters
        ----------
        payload : dict
            Must contain:
                natural_text  str   - NL statement to translate
                model_id      str   - OpenRouter model id
                api_key       str   - decrypted API key (plain text, in-memory only)
            Optional:
                max_retries   int   - override retry limit (default 3)
                system_prompt str   - override default system prompt

        Returns
        -------
        str
            Celery task ID; poll with get_result().
        """
        if not isinstance(payload, dict):
            raise CoProofError('Translation payload must be a dict.', code=400)

        required = ('natural_text', 'model_id', 'api_key')
        missing = [k for k in required if not payload.get(k)]
        if missing:
            raise CoProofError(
                f'Missing required fields: {", ".join(missing)}', code=400
            )

        try:
            task = cls._get_celery().send_task(
                'tasks.translate_and_verify',
                args=[payload],
                queue=cls.NL2FL_QUEUE_NAME,
            )
            logger.info('TranslateClient: dispatched task %s', task.id)
            return task.id
        except CeleryError as e:
            logger.error('TranslateClient: dispatch failed: %s', e)
            raise CoProofError(f'NL2FL Worker Unavailable: {str(e)}', code=503)
        except Exception as e:
            logger.error('TranslateClient: unexpected dispatch error: %s', e)
            raise CoProofError(f'NL2FL Worker Unavailable: {str(e)}', code=503)

    @classmethod
    def get_result(cls, task_id: str) -> dict | None:
        """
        Check whether the task has completed.

        Returns
        -------
        dict
            The TranslationResult payload if the task succeeded.
        None
            If the task is still pending/running.

        Raises
        ------
        CoProofError
            If the task failed with an exception.
        """
        try:
            async_result = cls._get_celery().AsyncResult(task_id)

            if not async_result.ready():
                return None

            if async_result.successful():
                return async_result.result

            # Task raised an exception in the worker
            err = async_result.result  # holds the exception instance
            logger.error('TranslateClient: task %s failed: %s', task_id, err)
            raise CoProofError(
                f'NL2FL task failed: {str(err)}', code=500
            )
        except CoProofError:
            raise
        except Exception as e:
            logger.error('TranslateClient: get_result error for %s: %s', task_id, e)
            raise CoProofError(f'NL2FL Worker Unavailable: {str(e)}', code=503)
