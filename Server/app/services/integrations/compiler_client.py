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
                timeout=15,
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