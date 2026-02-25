import git
import logging
from app.services.git_engine import repo_pool, locking
from app.exceptions import GitOperationError

logger = logging.getLogger(__name__)

class GitReader:
    """
    Synchronous service to read content from the Bare Repo.
    Uses the same locking/caching mechanisms as the Async Tasks.
    """

    @staticmethod
    def read_node_files(project_id, remote_url, token, file_path, latex_path=None, commit_hash=None):
        """
        Reads the content of the Lean file (and optional Latex file) 
        from the Git repository at a specific commit.
        """
        lean_content = ""
        latex_content = ""

        # 1. Acquire Repo Lock (Read operations still need to ensure no one deletes the repo mid-read)
        with locking.acquire_project_lock(project_id):
            
            # 2. Ensure Repo Exists (Clone if missing)
            bare_path = repo_pool.RepoPool.ensure_repo_exists(
                project_id, remote_url, auth_token=token
            )
            repo = git.Repo(bare_path)
            
            # 3. Strategy: Try read -> If fail (missing commit) -> Fetch -> Retry
            # We don't fetch by default to save time (Speed optimization for reads)
            try:
                return _perform_read(repo, file_path, latex_path, commit_hash)
            except (ValueError, git.BadName, git.BadObject) as e:
                logger.info(f"Commit {commit_hash} not found locally. Fetching updates...")
                
                # 4. Fetch Updates (Only if needed)
                repo_pool.RepoPool.update_repo(
                    project_id, remote_url, auth_token=token
                )
                
                # 5. Retry Read
                repo = git.Repo(bare_path) #reinitilize for saftey
                return _perform_read(repo, file_path, latex_path, commit_hash)

def _perform_read(repo, file_path, latex_path, commit_hash):
    """
    Helper to read blobs from a specific commit.
    """
    # Resolve commit (DB stores hash, or default to HEAD)
    target_commit = commit_hash or 'HEAD'
    commit = repo.commit(target_commit)
    
    lean_content = ""
    latex_content = ""

    # Read Lean
    try:
        # Use simple path traversal
        if file_path in commit.tree:
            lean_content = commit.tree[file_path].data_stream.read().decode('utf-8')
    except KeyError:
        logger.warning(f"File {file_path} not found in commit {target_commit}")

    # Read Latex
    if latex_path:
        try:
            if latex_path in commit.tree:
                latex_content = commit.tree[latex_path].data_stream.read().decode('utf-8')
        except KeyError:
            pass

    return {
        "lean": lean_content,
        "latex": latex_content
    }