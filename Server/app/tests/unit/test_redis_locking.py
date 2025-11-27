import pytest
import time
from threading import Thread
from app.services.git_engine.locking import acquire_project_lock
from app.exceptions import GitLockError

def test_lock_acquisition():
    """Test that we can acquire and release a lock."""
    project_id = "test-proj-123"
    with acquire_project_lock(project_id):
        # We have the lock
        pass

def test_lock_contention():
    """Test that a second attempt fails while locked."""
    project_id = "test-proj-456"
    
    def hold_lock():
        with acquire_project_lock(project_id, expire=5):
            time.sleep(2)

    t = Thread(target=hold_lock)
    t.start()
    
    # Give the thread a moment to acquire lock
    time.sleep(0.5)
    
    # Try to acquire same lock with short timeout
    with pytest.raises(GitLockError):
        with acquire_project_lock(project_id, timeout=0.1):
            pass
            
    t.join()