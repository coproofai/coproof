import os
from urllib.parse import urlparse, urlunparse
import uuid
import shutil
import git
from contextlib import contextmanager
from app.services.git_engine.repo_pool import RepoPool
from app.services.git_engine.locking import acquire_project_lock
from app.exceptions import GitMergeError, GitOperationError
from config import Config

import logging
logger = logging.getLogger(__name__)


@contextmanager
def read_only_worktree(bare_repo_path, branch='main'):
    """
    Creates a temporary worktree for reading/verifying.
    Does NOT commit or push changes on exit.
    Used for: Validation before merge.
    """
    worktree_name = f"read-{uuid.uuid4()}"
    worktree_path = os.path.join(Config.REPO_STORAGE_PATH, 'worktrees', worktree_name)
    bare_repo = git.Repo(bare_repo_path)
    
    try:
        os.makedirs(worktree_path, exist_ok=True)
        
        # Check if branch exists in bare repo refs
        if branch not in [h.name for h in bare_repo.heads]:
             raise GitOperationError(f"Branch {branch} not found for validation.")

        # Create Worktree
        bare_repo.git.worktree('add', worktree_path, branch)
        
        yield worktree_path
        
    except git.GitCommandError as e:
        raise GitOperationError(f"Read-only worktree failed: {e}")
        
    finally:
        _cleanup_worktree(bare_repo, worktree_path, worktree_name)

@contextmanager
def git_transaction(bare_repo_path, author_name, author_email, branch='main', source_branch='main'):
    """
    Context Manager for Worktrees on a specific branch.
    
    Logic:
    1. If 'branch' exists, checkout.
    2. If 'branch' missing, create it off 'source_branch'.
    3. Yield worktree.
    4. Commit & Push to 'branch'.
    """

    worktree_path = None
    worktree_name = f"wt-{uuid.uuid4()}"
    bare_repo = git.Repo(bare_repo_path)
    
    try:
        # 1. Create Worktree Path and add it
        worktree_path = os.path.join(Config.REPO_STORAGE_PATH, 'worktrees', worktree_name)
        
        os.makedirs(worktree_path, exist_ok=True)
        
        # 1. Determine Checkout Strategy
        # List branches to see if target exists
        heads = [h.name for h in bare_repo.heads]

        if source_branch not in heads:
            logger.info(f"Branch {source_branch} missing locally. Fetching from origin...")
            bare_repo.remotes.origin.fetch(source_branch)

            # Recompute heads after potential fetch
            heads = [h.name for h in bare_repo.heads]
        
        cmd_args = ['add', worktree_path]
        
        if branch in heads:
            # Branch exists, checkout it
            cmd_args.append(branch)
        else:
            # Branch doesn't exist, create new branch (-b) off source
            # cmd_args.extend(['-b', branch, source_branch])
            
            #avoids accidentally branching off stale local refs.
            cmd_args.extend(['-b', branch, f'origin/{source_branch}'])
            
        # 2. Create Worktree
        bare_repo.git.worktree(*cmd_args)
        
        yield worktree_path
        
        # 3. Commit & Push
        wt_repo = git.Repo(worktree_path)
        if wt_repo.is_dirty(untracked_files=True):
            wt_repo.git.add(A=True)
            wt_repo.index.commit(
                f"Update {branch} via CoProof", 
                author=git.Actor(author_name, author_email),
                committer=git.Actor("CoProof Bot", "bot@coproof.com")
            )
            # Push specifically to the target branch
            bare_repo.remotes.origin.push(branch)
            
    except git.GitCommandError as e:
        raise GitOperationError(f"Git transaction failed: {e}")
        
    finally:
        _cleanup_worktree(bare_repo, worktree_path, worktree_name)


def merge_branch_to_main(project_id, remote_url, token, source_branch):
    """
    Merges a feature branch into main.
    
    Flow:
    1. Fetch Latest.
    2. Worktree on Main.
    3. Reset Main to Origin/Main (Canonical Pull).
    4. Merge Source Branch.
    5. Push Main.
    6. Delete Source Branch (Remote & Local).
    """
    #TODO wrap everything in a project-level lock to prevent concurrent merges or operations during merge.
    # 1. Update Repo (Fetch All)
    bare_path = RepoPool.update_repo(project_id, remote_url, token)
    bare_repo = git.Repo(bare_path)
    
    worktree_name = f"merge-{uuid.uuid4()}"
    worktree_path = os.path.join(Config.REPO_STORAGE_PATH, 'worktrees', worktree_name)

    try:
        os.makedirs(worktree_path, exist_ok=True)
        
        # 2. Create Worktree on Main
        # We force checkout 'main'
        if any(wt.branch == 'main' for wt in bare_repo.worktrees):
            logger.info("Worktree on main already exists. Reusing...")
            worktree_path = next(wt.path for wt in bare_repo.worktrees if wt.branch == 'main')

        bare_repo.git.worktree('add', '--force', worktree_path, 'main')
        # bare_repo.git.worktree('add', worktree_path, 'main')
        wt_repo = git.Repo(worktree_path)
        
        # 3. Canonical Pull (Reset hard to origin/main)
        # This ensures we don't merge into a stale local state
        wt_repo.git.fetch('origin', 'main')
        wt_repo.git.reset('--hard', 'origin/main')
        
        remote_ref = f"origin/{source_branch}"
        if remote_ref not in [r.name for r in bare_repo.refs]:
            raise GitOperationError(f"Source branch {source_branch} does not exist on remote.")
        
        
        # 4. Merge
        logger.info(f"Merging {source_branch} into main...")
        try:
            # --no-ff preserves the history of the feature branch
            wt_repo.git.merge(remote_ref, '--no-ff', '-m', f"Merge proposal {source_branch}")
        except git.GitCommandError as e:
            # 4a. CONFLICT HANDLING
            logger.error(f"Merge conflict detected: {e}")
            raise GitMergeError(f"Conflict merging {source_branch} into main. Please resolve manually or re-verify.")
            
        # 5. Push Main
        logger.info("Pushing merged main to remote...")
        try:
            wt_repo.remotes.origin.push('main')
        except git.GitCommandError:
            logger.warning("Push rejected. Refetching and retrying...")
            
            wt_repo.git.fetch('origin', 'main')
            wt_repo.git.reset('--hard', 'origin/main')
            wt_repo.git.merge(remote_ref, '--no-ff', '-m', f"Merge proposal {source_branch}")
            
            wt_repo.remotes.origin.push('main')
        
        # 5.1 Get Merge Commit SHA (Optional, useful for indexing or tracking)
        merge_commit_sha = wt_repo.head.commit.hexsha

        # 6. Delete Feature Branch
        logger.info(f"Deleting branch {source_branch}...")
        try:
            # Delete remote
            wt_repo.remotes.origin.push(f":{source_branch}")
            # Delete local ref in bare repo
            bare_repo.git.update_ref('-d', f'refs/remotes/origin/{source_branch}')
        except Exception as e:
            logger.warning(f"Cleanup of branch {source_branch} failed (non-critical): {e}")

        return merge_commit_sha


    except GitMergeError:
        raise # Re-raise for Task to handle rollback
    except Exception as e:
        raise GitOperationError(f"System error during merge: {e}")
    finally:
        _cleanup_worktree(bare_repo, worktree_path, worktree_name)

def _cleanup_worktree(bare_repo, path, name):
    """Helper to clean up worktrees safely."""
    if os.path.exists(path):
        try:
            bare_repo.git.worktree('remove', name, force=True)
        except: pass
        if os.path.exists(path): shutil.rmtree(path)
        try: bare_repo.git.worktree('prune')
        except: pass