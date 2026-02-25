# app/services/integrations/github_service.py

import requests
import logging
from app.exceptions import CoProofError

logger = logging.getLogger(__name__)

class GitHubService:
    """
    Handles GitHub API interactions for the Native Workflow.
    """
    
    @staticmethod
    def ensure_fork_exists(user_token, upstream_owner, upstream_repo):
        """
        Checks if the user has a fork of the upstream repo. If not, creates it.
        Returns the fork's full name (e.g., 'user/repo-fork').
        """
        headers = {
            "Authorization": f"token {user_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        # 1. Check existing forks (or list user repos and filter)
        # Optimization: Just try to create. If it exists, GitHub returns the existing one.
        url = f"https://api.github.com/repos/{upstream_owner}/{upstream_repo}/forks"
        
        try:
            resp = requests.post(url, headers=headers)
            if resp.status_code in (200, 202):
                data = resp.json()
                return data['full_name'], data['clone_url']
            else:
                logger.error(f"Fork creation failed: {resp.text}")
                raise CoProofError(f"Failed to create/find fork: {resp.status_code}")
        except Exception as e:
            raise CoProofError(f"GitHub connection failed: {e}")

    @staticmethod
    def create_or_update_pr(user_token, upstream_full_name, head_branch, base_branch, title, body):
        """
        Creates a PR from head_branch (fork) to base_branch (upstream).
        If a PR already exists for this branch pair, returns the existing number.
        """
        headers = {
            "Authorization": f"token {user_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        # 1. Check if PR exists
        # Format for head is "user:branch_name" for cross-repo PRs
        # We assume head_branch passed here is formatted correctly or we query generic
        # Easier: Query pulls?head=user:branch
        
        api_base = f"https://api.github.com/repos/{upstream_full_name}"
        
        # We need the user login to construct "user:branch"
        user_resp = requests.get("https://api.github.com/user", headers=headers)
        username = user_resp.json()['login']
        head_ref = f"{username}:{head_branch}"
        
        query_url = f"{api_base}/pulls?head={head_ref}&base={base_branch}&state=open"
        resp = requests.get(query_url, headers=headers)
        
        if resp.status_code == 200 and len(resp.json()) > 0:
            # PR Exists
            pr_number = resp.json()[0]['number']
            logger.info(f"PR already exists: #{pr_number}")
            return pr_number

        # 2. Create PR
        payload = {
            "title": title,
            "body": body,
            "head": head_ref,
            "base": base_branch
        }
        
        resp = requests.post(f"{api_base}/pulls", json=payload, headers=headers)
        
        if resp.status_code == 201:
            pr_number = resp.json()['number']
            logger.info(f"Created new PR: #{pr_number}")
            return pr_number
        else:
            logger.error(f"PR creation failed: {resp.text}")
            raise CoProofError(f"Failed to create PR: {resp.status_code}")
        
    @staticmethod
    def sync_fork_with_upstream(user_token, fork_full_name, upstream_default_branch='main'):
        """
        Ensures the fork's main branch is up-to-date with upstream.
        Uses GitHub API 'merge-upstream'.
        """
        owner, repo = fork_full_name.split('/')
        url = f"https://api.github.com/repos/{owner}/{repo}/merge-upstream"
        
        headers = {
            "Authorization": f"token {user_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        payload = {
            "branch": upstream_default_branch
        }
        
        try:
            resp = requests.post(url, json=payload, headers=headers)
            if resp.status_code == 200:
                logger.info(f"Fork {fork_full_name} merged with upstream.")
            elif resp.status_code == 409:
                # Merge conflict - requires manual intervention, or we assume
                # the user will fix it on their branch. For automated drafts, this blocks.
                raise CoProofError("Fork is in conflict with upstream. Please sync manually via GitHub.")
            elif resp.status_code == 422:
                # "Upstream is not a fork of..." or branch mismatch.
                logger.warning(f"Sync skipped (already even or unrelated): {resp.text}")
            else:
                logger.warning(f"Fork sync warning: {resp.status_code} {resp.text}")
                
        except Exception as e:
            logger.error(f"Failed to sync fork: {e}")
            # We might allow proceeding, but warn.