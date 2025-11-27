import os
import shutil
import git
import logging
from app.exceptions import GitOperationError
from config import Config

logger = logging.getLogger(__name__)

class RepoPool:
    """
    Manages the pool of Bare Repositories in /tmp.
    Does NOT handle Worktrees (that is for Transaction).
    """
    
    @staticmethod
    def get_storage_path(project_id):
        return os.path.join(Config.REPO_STORAGE_PATH, 'repos', f"{project_id}.git")

    @classmethod
    def ensure_bare_repo(cls, project_id, remote_url):
        """
        Ensures a valid Bare Repo exists for the project.
        If missing -> Clone --bare
        If exists -> Fetch origin
        """
        repo_path = cls.get_storage_path(project_id)
        
        try:
            if os.path.exists(repo_path):
                # Hit: Fetch updates
                logger.info(f"Repo hit for {project_id}. Fetching...")
                repo = git.Repo(repo_path)
                repo.remotes.origin.fetch()
            else:
                # Miss: Clone bare
                logger.info(f"Repo miss for {project_id}. Cloning...")
                os.makedirs(repo_path, exist_ok=True)
                git.Repo.clone_from(remote_url, repo_path, bare=True)
                
            return repo_path
            
        except git.GitCommandError as e:
            logger.error(f"Git error for {project_id}: {e}")
            raise GitOperationError(f"Failed to initialize repo: {str(e)}")

    @classmethod
    def cleanup_cache(cls):
        """
        TODO: Implement LRU eviction logic here.
        For now, this is a placeholder stub.
        """
        pass