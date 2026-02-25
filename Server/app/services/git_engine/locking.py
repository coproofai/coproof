import time
from contextlib import contextmanager
from redis.exceptions import LockError
from app.extensions import socketio # Access redis client via socketio or create new
import redis
from config import Config
from app.exceptions import GitLockError

# Create a dedicated redis client for locks if needed, 
# or reuse the one from the config.
# For robustness, we create a direct client here.
redis_client = redis.from_url(Config.REDIS_URL)

@contextmanager
def acquire_project_lock(project_id: str, timeout: int = 10, expire: int = 60):
    """
    Context manager that acquires a distributed Redis lock for a project.
    
    :param project_id: UUID of the project
    :param timeout: How long to wait to acquire the lock (seconds)
    :param expire: Time-to-live for the lock (seconds) to prevent deadlocks
    """
    lock_name = f"lock:project:{project_id}"
    lock = redis_client.lock(lock_name, timeout=expire, blocking_timeout=timeout)
    
    have_lock = False
    try:
        have_lock = lock.acquire()
        if not have_lock:
            raise GitLockError(f"Could not acquire lock for project {project_id}")
        yield
    except LockError:
        raise GitLockError(f"Lock error for project {project_id}")
    finally:
        if have_lock:
            try:
                lock.release()
            except LockError:
                # Lock might have expired already, which is fine
                pass

@contextmanager
def acquire_branch_lock(project_id: str, branch_name: str, timeout: int = 10, expire: int = 60):
    """
    Branch-Level Lock: Used for Fetch, Commit, Push on a specific branch.
    Allows parallel work on different branches of the same project.
    """
    lock_name = f"lock:project:{project_id}:branch:{branch_name}"
    lock = redis_client.lock(lock_name, timeout=expire, blocking_timeout=timeout)
    
    if not lock.acquire():
        raise GitLockError(f"Could not acquire BRANCH lock for {branch_name} in {project_id}")
    try:
        yield
    finally:
        try:
            lock.release()
        except redis.exceptions.LockError:
            pass