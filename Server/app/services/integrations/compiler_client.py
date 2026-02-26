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
    def verify_project_content(full_source_code: str):
        """
        Sends the fully concatenated Lean project code for verification.
        
        Lean service must:
         - Wrap content in a temporary Lean project
         - Provide correct imports / lakefile context
        
        Make sure your compiler service:
         - Creates ephemeral project
         - Places main.lean inside
         - Runs lake build

        Returns:
        {
            "compile_success": bool,
            "contains_sorry": bool,
            "errors": str
        }
        """
        data = CompilerClient._dispatch_task(
            'tasks.verify_content',
            [full_source_code, 'Main.lean'],
            timeout=120,
            queue_name=CompilerClient.LEAN_QUEUE_NAME,
        )
        return {
            'compile_success': data.get('compile_success', False),
            'contains_sorry': data.get('contains_sorry', False),
            'errors': data.get('errors', ''),
        }

    @staticmethod
    def translate_nl_to_lean(nl_text: str, context: str = ""):
        """
        Sends Natural Language -> Returns Lean Code.
        """
        return CompilerClient._dispatch_task(
            'tasks.translate',
            [nl_text, context],
            timeout=30,
            queue_name=CompilerClient.LEAN_QUEUE_NAME,
        )

    @staticmethod
    def verify_code_snippet(lean_code: str, dependencies: list = None):
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
    def compile_project_repo(remote_url: str, commit_hash: str):
        """
        Full Project Check: Tells the compiler to pull the repo and build.
        """
        return CompilerClient._dispatch_task(
            'tasks.verify_project',
            [remote_url, commit_hash],
            timeout=10,
            queue_name=CompilerClient.LEAN_QUEUE_NAME,
        )