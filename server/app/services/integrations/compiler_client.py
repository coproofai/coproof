import logging
import os
import time
from celery import Celery
from celery.exceptions import CeleryError, TimeoutError
from app.exceptions import CoProofError

logger = logging.getLogger(__name__)

class CompilerClient:
    """
    Interface for the external Lean worker via Celery.
    """
    REDIS_URL = os.environ.get('REDIS_URL', 'redis://redis:6379/0')
    LEAN_QUEUE_NAME = os.environ.get('CELERY_LEAN_QUEUE', 'lean_queue')
    _celery = None

    @classmethod
    def _get_celery(cls):
        if cls._celery is None:
            cls._celery = Celery(
                'compiler_client',
                broker=cls.REDIS_URL,
                backend=cls.REDIS_URL,
            )
        return cls._celery

    @classmethod
    def _dispatch_task(
        cls,
        task_name: str,
        args: list,
        timeout: int,
        queue_name: str | None = None,
    ):
        try:
            task = cls._get_celery().send_task(
                task_name,
                args=args,
                queue=queue_name or cls.LEAN_QUEUE_NAME,
            )
            return task.get(timeout=timeout)
        except TimeoutError as e:
            logger.error(f'Lean worker task timeout ({task_name}): {e}')
            raise CoProofError('Lean Worker Timeout', code=504)
        except CeleryError as e:
            logger.error(f'Lean worker task failure ({task_name}): {e}')
            raise CoProofError(f'Lean Worker Unavailable: {str(e)}', code=503)
        except Exception as e:
            logger.error(f'Lean worker dispatch error ({task_name}): {e}')
            raise CoProofError(f'Lean Worker Unavailable: {str(e)}', code=503)


    @staticmethod
    def verify_snippet(lean_code: str, dependencies: list = None):
        """
        Ephemeral Check: Sends raw code to check for syntax/type errors.
        Does NOT require a full Git repo sync.
        """
        try:
            started = time.perf_counter()
            data = CompilerClient._dispatch_task(
                'tasks.verify_snippet',
                [lean_code, 'snippet.lean'],
                timeout=45,
                queue_name=CompilerClient.LEAN_QUEUE_NAME,
            )
            elapsed = time.perf_counter() - started

            if 'processing_time_seconds' not in data:
                data['processing_time_seconds'] = round(elapsed, 6)
                data['timing_source'] = 'backend_fallback'
            else:
                data['timing_source'] = 'lean_worker'

            data['roundtrip_time_seconds'] = round(elapsed, 6)
            return data
        except CoProofError:
            raise
        except Exception as e:
            logger.error(f'Verification failed: {e}')
            raise CoProofError(f'Compiler Service Unavailable: {str(e)}', code=503)

    @staticmethod
    def verify_project_files(file_map: dict, entry_file: str):
        """
        Project-aware verification: compiles one entry file with all provided Lean files available,
        so imports are resolved consistently.
        """
        if not isinstance(file_map, dict) or not file_map:
            raise CoProofError('file_map must be a non-empty dictionary', code=400)
        if not entry_file:
            raise CoProofError('entry_file is required', code=400)

        try:
            started = time.perf_counter()
            data = CompilerClient._dispatch_task(
                'tasks.verify_project_files',
                [file_map, entry_file],
                timeout=45,
                queue_name=CompilerClient.LEAN_QUEUE_NAME,
            )
            elapsed = time.perf_counter() - started

            if 'processing_time_seconds' not in data:
                data['processing_time_seconds'] = round(elapsed, 6)
                data['timing_source'] = 'backend_fallback'
            else:
                data['timing_source'] = 'lean_worker'

            data['roundtrip_time_seconds'] = round(elapsed, 6)
            return data
        except CoProofError:
            raise
        except Exception as e:
            logger.error(f'Project verification failed: {e}')
            raise CoProofError(f'Compiler Service Unavailable: {str(e)}', code=503)

    # ------------------------------------------------------------------
    # Mathlib Declaration Lookup  (non-blocking, same pattern as AgentsClient)
    # ------------------------------------------------------------------

    @classmethod
    def submit_mathlib_lookup(cls, declaration_name: str) -> str:
        """
        Dispatch a Mathlib declaration lookup job to the lean worker.

        Returns the Celery task ID immediately (non-blocking).
        Poll the result with get_mathlib_lookup_result().
        """
        if not declaration_name or not declaration_name.strip():
            raise CoProofError('declaration_name is required', code=400)

        try:
            task = cls._get_celery().send_task(
                'tasks.get_mathlib_info',
                args=[declaration_name.strip()],
                queue=cls.LEAN_QUEUE_NAME,
            )
            logger.info('CompilerClient: dispatched mathlib lookup task %s for %s',
                        task.id, declaration_name)
            return task.id
        except Exception as e:
            logger.error('CompilerClient: mathlib lookup dispatch error: %s', e)
            raise CoProofError(f'Lean Worker Unavailable: {str(e)}', code=503)

    @classmethod
    def get_mathlib_lookup_result(cls, task_id: str) -> dict | None:
        """
        Check whether a Mathlib lookup task has completed.

        Returns the result dict when done, or None if still pending.
        Raises CoProofError if the task failed.
        """
        try:
            async_result = cls._get_celery().AsyncResult(task_id)

            if not async_result.ready():
                return None

            if async_result.successful():
                return async_result.result

            err = async_result.result
            logger.error('CompilerClient: mathlib lookup task %s failed: %s', task_id, err)
            raise CoProofError(f'Mathlib lookup task failed: {str(err)}', code=500)
        except CoProofError:
            raise
        except Exception as e:
            logger.error('CompilerClient: get_mathlib_lookup_result error for %s: %s', task_id, e)
            raise CoProofError(f'Lean Worker Unavailable: {str(e)}', code=503)

    # ------------------------------------------------------------------
    # Mathlib Lineage (dependency graph)  — same non-blocking pattern
    # ------------------------------------------------------------------

    @classmethod
    def submit_mathlib_lineage(cls, declaration_name: str, depth: int) -> str:
        """
        Dispatch a Mathlib lineage (dependency graph) job to the lean worker.

        Returns the Celery task ID immediately (non-blocking).
        Poll the result with get_mathlib_lineage_result().
        """
        if not declaration_name or not declaration_name.strip():
            raise CoProofError('declaration_name is required', code=400)

        depth = max(1, min(4, int(depth)))

        try:
            task = cls._get_celery().send_task(
                'tasks.get_mathlib_lineage',
                args=[declaration_name.strip(), depth],
                queue=cls.LEAN_QUEUE_NAME,
            )
            logger.info(
                'CompilerClient: dispatched mathlib lineage task %s for %s (depth=%d)',
                task.id, declaration_name, depth,
            )
            return task.id
        except Exception as e:
            logger.error('CompilerClient: mathlib lineage dispatch error: %s', e)
            raise CoProofError(f'Lean Worker Unavailable: {str(e)}', code=503)

    @classmethod
    def get_mathlib_lineage_result(cls, task_id: str) -> dict | None:
        """
        Check whether a Mathlib lineage task has completed.

        Returns the result dict when done, or None if still pending.
        Raises CoProofError if the task failed.
        """
        try:
            async_result = cls._get_celery().AsyncResult(task_id)

            if not async_result.ready():
                return None

            if async_result.successful():
                return async_result.result

            err = async_result.result
            logger.error('CompilerClient: mathlib lineage task %s failed: %s', task_id, err)
            raise CoProofError(f'Mathlib lineage task failed: {str(err)}', code=500)
        except CoProofError:
            raise
        except Exception as e:
            logger.error('CompilerClient: get_mathlib_lineage_result error for %s: %s', task_id, e)
            raise CoProofError(f'Lean Worker Unavailable: {str(e)}', code=503)