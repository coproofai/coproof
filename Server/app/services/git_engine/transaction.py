import os
import uuid
import shutil
import git
from contextlib import contextmanager
from app.services.git_engine.repo_pool import RepoPool
from app.services.git_engine.locking import acquire_project_lock
from app.exceptions import GitOperationError
from config import Config

@contextmanager
def git_transaction(project_id, remote_url, author_name, author_email, branch='main'):
    """
    High-level Context Manager for Git Operations.
    1. Acquires Lock
    2. Ensures Bare Repo (Clone/Fetch)
    3. Creates Ephemeral Worktree
    4. Yields worktree path for editing
    5. Commits & Pushes changes
    6. Cleans up
    """
    worktree_path = None
    
    with acquire_project_lock(project_id):
        # 1. Prepare Bare Repo
        bare_repo_path = RepoPool.ensure_bare_repo(project_id, remote_url)
        bare_repo = git.Repo(bare_repo_path)
        
        # 2. Create Ephemeral Worktree Path
        request_id = str(uuid.uuid4())
        worktree_path = os.path.join(Config.REPO_STORAGE_PATH, 'worktrees', project_id, request_id)
        os.makedirs(worktree_path, exist_ok=True)
        
        try:
            # 3. Create Worktree
            # git worktree add -f <path> <branch>
            bare_repo.git.worktree('add', '-f', worktree_path, branch)
            
            # 4. Yield control to caller (to write files)
            yield worktree_path
            
            # 5. Commit & Push
            wt_repo = git.Repo(worktree_path)
            
            # Check for changes
            if wt_repo.is_dirty(untracked_files=True):
                wt_repo.git.add(A=True) # Add all
                wt_repo.index.commit(
                    "Update via CoProof", 
                    author=git.Actor(author_name, author_email),
                    committer=git.Actor("CoProof Bot", "bot@coproof.com")
                )
                
                # Push from the worktree? No, push from bare repo usually, 
                # but pushing from worktree is valid if remote is set.
                # However, the worktree shares config with bare.
                # Safest is to push the branch we are on.
                wt_repo.remotes.origin.push()
            
        except Exception as e:
            raise GitOperationError(f"Transaction failed: {str(e)}")
            
        finally:
            # 6. Cleanup Worktree
            if worktree_path and os.path.exists(worktree_path):
                # Prune worktree metadata from bare repo
                try:
                    bare_repo.git.worktree('prune')
                except:
                    pass
                # Delete files
                shutil.rmtree(worktree_path)