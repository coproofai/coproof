import os
import shutil
from urllib.parse import urlparse, urlunparse
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
    def _get_auth_url(cls, remote_url, auth_token=None):
        if auth_token:
            try:
                parsed = urlparse(remote_url)
                # Inject oauth2:TOKEN@host or x-access-token:TOKEN@host depending on type
                # For GitHub OAuth/App tokens, generic user 'x-access-token' or 'oauth2' usually works
                # Using 'x-access-token' is safer for GitHub App Installation tokens
                user = "x-access-token" 
                new_netloc = f"{user}:{auth_token}@{parsed.netloc}"
                return urlunparse((parsed.scheme, new_netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))
            except Exception as e:
                logger.error(f"Failed to parse URL for token injection: {e}")
        return remote_url

    @classmethod
    def ensure_repo_exists(cls, project_id, remote_url, auth_token=None):
        """
        Ensures a valid Bare Repo exists and is configured to fetch ALL branches.
        """
        repo_path = cls.get_storage_path(project_id)
        auth_url = cls._get_auth_url(remote_url, auth_token)

        # 1. Clone if missing
        if not os.path.exists(repo_path):
            try:
                logger.info(f"Cloning {project_id}...")
                os.makedirs(repo_path, exist_ok=True)
                git.Repo.clone_from(auth_url, repo_path, bare=True)
            except git.GitCommandError as e:
                if os.path.exists(repo_path): shutil.rmtree(repo_path)
                raise GitOperationError(f"Failed to clone repo: {e}")

        # 2. Configure Refspec & URL (Self-Healing)
        try:
            repo = git.Repo(repo_path)
            with repo.remotes.origin.config_writer as cw:
                cw.set("url", auth_url)
                # Ensure we fetch all heads to local heads for bare repo manipulation
                # This is critical for knowing about feature branches
                #fetch from remotes
                cw.set("fetch", "+refs/heads/*:refs/remotes/origin/*")
                # cw.set("fetch", "+refs/heads/*:refs/heads/*")
            
            return repo_path
        except Exception as e:
            logger.error(f"Repo configuration failed: {e}")
            raise GitOperationError(f"Repo corruption detected: {e}")

    @classmethod
    def update_repo(cls, project_id, remote_url, auth_token=None):
        """
        Fetches updates for ALL branches.
        """
        repo_path = cls.ensure_repo_exists(project_id, remote_url, auth_token)
        try:
            repo = git.Repo(repo_path)
            logger.info(f"Fetching all updates for {project_id}...")
            repo.remotes.origin.fetch()
        except git.GitCommandError as e:
            raise GitOperationError(f"Failed to fetch updates: {e}")

    @classmethod
    def cleanup_cache(cls):
        pass