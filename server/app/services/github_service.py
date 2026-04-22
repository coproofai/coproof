import re
import base64
from urllib.parse import urlparse
from urllib.parse import quote

import requests
from requests.exceptions import ConnectionError as RequestsConnectionError, Timeout

from app.exceptions import CoProofError


class GitHubService:
    """Static helper methods for GitHub URL parsing and Pull Request operations."""

    @staticmethod
    def get_branch_head_sha(remote_repo_url, token, branch):
        """Get the latest commit SHA for a branch."""
        full_name = GitHubService.extract_github_full_name(remote_repo_url)
        response = requests.get(
            f"https://api.github.com/repos/{full_name}/git/ref/heads/{branch}",
            headers=GitHubService.github_headers(token),
            timeout=20,
        )

        if response.status_code == 200:
            payload = response.json()
            return (payload.get('object') or {}).get('sha')
        if response.status_code == 404:
            raise CoProofError(f"Branch '{branch}' not found in repository.", code=404)
        if response.status_code in (401, 403):
            raise CoProofError("GitHub authentication failed while reading branch head.", code=401)

        raise CoProofError(f"GitHub branch read failed: {response.text}", code=502)

    @staticmethod
    def get_commit_tree_sha(remote_repo_url, token, commit_sha):
        """Get the tree SHA for a commit SHA."""
        full_name = GitHubService.extract_github_full_name(remote_repo_url)
        response = requests.get(
            f"https://api.github.com/repos/{full_name}/git/commits/{commit_sha}",
            headers=GitHubService.github_headers(token),
            timeout=20,
        )

        if response.status_code == 200:
            payload = response.json()
            return (payload.get('tree') or {}).get('sha')
        if response.status_code == 404:
            raise CoProofError("Commit not found while reading tree SHA.", code=404)
        if response.status_code in (401, 403):
            raise CoProofError("GitHub authentication failed while reading commit tree.", code=401)

        raise CoProofError(f"GitHub commit read failed: {response.text}", code=502)

    @staticmethod
    def get_blob_content(remote_repo_url, token, blob_sha):
        """Read text content for a Git blob SHA."""
        full_name = GitHubService.extract_github_full_name(remote_repo_url)
        response = requests.get(
            f"https://api.github.com/repos/{full_name}/git/blobs/{blob_sha}",
            headers=GitHubService.github_headers(token),
            timeout=20,
        )

        if response.status_code == 200:
            payload = response.json()
            encoded = payload.get('content', '').replace('\n', '')
            return base64.b64decode(encoded).decode('utf-8', errors='replace')
        if response.status_code == 404:
            raise CoProofError("Blob not found while reading repository file.", code=404)
        if response.status_code in (401, 403):
            raise CoProofError("GitHub authentication failed while reading blob.", code=401)

        raise CoProofError(f"GitHub blob read failed: {response.text}", code=502)

    @staticmethod
    def get_repository_files_map(remote_repo_url, token, branch, extensions=None):
        """Return a path-to-content map of repository files for a branch."""
        full_name = GitHubService.extract_github_full_name(remote_repo_url)
        branch_head_sha = GitHubService.get_branch_head_sha(remote_repo_url, token, branch)
        response = requests.get(
            f"https://api.github.com/repos/{full_name}/git/trees/{branch_head_sha}",
            headers=GitHubService.github_headers(token),
            params={"recursive": "1"},
            timeout=30,
        )

        if response.status_code == 404:
            raise CoProofError(f"Repository tree not found for branch '{branch}'.", code=404)
        if response.status_code in (401, 403):
            raise CoProofError("GitHub authentication failed while reading repository tree.", code=401)
        if response.status_code != 200:
            raise CoProofError(f"GitHub repository tree read failed: {response.text}", code=502)

        payload = response.json()
        tree = payload.get('tree') or []
        selected_files = []

        for item in tree:
            if item.get('type') != 'blob':
                continue
            path = item.get('path')
            if not path:
                continue
            if extensions and not any(path.endswith(extension) for extension in extensions):
                continue
            selected_files.append((path, item.get('sha')))

        result = {}
        for path, blob_sha in selected_files:
            if not blob_sha:
                continue
            result[path] = GitHubService.get_blob_content(remote_repo_url, token, blob_sha)

        return result

    @staticmethod
    def get_file_content(remote_repo_url, token, path, branch):
        """Read one repository file from the contents API."""
        full_name = GitHubService.extract_github_full_name(remote_repo_url)
        quoted_path = quote(path, safe='/')
        response = requests.get(
            f"https://api.github.com/repos/{full_name}/contents/{quoted_path}",
            headers=GitHubService.github_headers(token),
            params={"ref": branch},
            timeout=20,
        )

        if response.status_code == 200:
            payload = response.json()
            encoded = payload.get('content', '').replace('\n', '')
            return base64.b64decode(encoded).decode('utf-8', errors='replace')
        if response.status_code == 404:
            raise CoProofError(f"File '{path}' not found in branch '{branch}'.", code=404)
        if response.status_code in (401, 403):
            raise CoProofError("GitHub authentication failed while reading file content.", code=401)

        raise CoProofError(f"GitHub file read failed: {response.text}", code=502)

    @staticmethod
    def create_branch(remote_repo_url, token, new_branch, from_branch):
        """Create a new branch from an existing branch head."""
        full_name = GitHubService.extract_github_full_name(remote_repo_url)
        base_sha = GitHubService.get_branch_head_sha(remote_repo_url, token, from_branch)
        response = requests.post(
            f"https://api.github.com/repos/{full_name}/git/refs",
            headers=GitHubService.github_headers(token),
            json={"ref": f"refs/heads/{new_branch}", "sha": base_sha},
            timeout=20,
        )

        if response.status_code in (200, 201):
            return response.json()
        if response.status_code == 422:
            raise CoProofError(f"Branch '{new_branch}' already exists or cannot be created.", code=409)
        if response.status_code in (401, 403):
            raise CoProofError("GitHub authentication failed while creating branch.", code=401)

        raise CoProofError(f"GitHub branch creation failed: {response.text}", code=502)

    @staticmethod
    def commit_files(remote_repo_url, token, branch, files, commit_message):
        """Commit multiple file contents directly to a branch using GitHub Git Data API."""
        if not files:
            raise CoProofError("No files provided for commit operation.", code=400)

        full_name = GitHubService.extract_github_full_name(remote_repo_url)
        head_sha = GitHubService.get_branch_head_sha(remote_repo_url, token, branch)
        base_tree_sha = GitHubService.get_commit_tree_sha(remote_repo_url, token, head_sha)

        tree_entries = []
        for path, content in files.items():
            blob_response = requests.post(
                f"https://api.github.com/repos/{full_name}/git/blobs",
                headers=GitHubService.github_headers(token),
                json={"content": content, "encoding": "utf-8"},
                timeout=20,
            )

            if blob_response.status_code not in (200, 201):
                if blob_response.status_code in (401, 403):
                    raise CoProofError("GitHub authentication failed while creating file blob.", code=401)
                raise CoProofError(f"GitHub blob creation failed: {blob_response.text}", code=502)

            blob_sha = (blob_response.json() or {}).get('sha')
            tree_entries.append({
                "path": path,
                "mode": "100644",
                "type": "blob",
                "sha": blob_sha,
            })

        tree_response = requests.post(
            f"https://api.github.com/repos/{full_name}/git/trees",
            headers=GitHubService.github_headers(token),
            json={"base_tree": base_tree_sha, "tree": tree_entries},
            timeout=20,
        )

        if tree_response.status_code not in (200, 201):
            if tree_response.status_code in (401, 403):
                raise CoProofError("GitHub authentication failed while creating commit tree.", code=401)
            raise CoProofError(f"GitHub tree creation failed: {tree_response.text}", code=502)

        new_tree_sha = (tree_response.json() or {}).get('sha')
        commit_response = requests.post(
            f"https://api.github.com/repos/{full_name}/git/commits",
            headers=GitHubService.github_headers(token),
            json={"message": commit_message, "tree": new_tree_sha, "parents": [head_sha]},
            timeout=20,
        )

        if commit_response.status_code not in (200, 201):
            if commit_response.status_code in (401, 403):
                raise CoProofError("GitHub authentication failed while creating commit.", code=401)
            raise CoProofError(f"GitHub commit creation failed: {commit_response.text}", code=502)

        commit_sha = (commit_response.json() or {}).get('sha')
        ref_response = requests.patch(
            f"https://api.github.com/repos/{full_name}/git/refs/heads/{branch}",
            headers=GitHubService.github_headers(token),
            json={"sha": commit_sha, "force": False},
            timeout=20,
        )

        if ref_response.status_code == 200:
            return {"commit_sha": commit_sha}
        if ref_response.status_code in (401, 403):
            raise CoProofError("GitHub authentication failed while updating branch ref.", code=401)
        if ref_response.status_code == 422:
            raise CoProofError("GitHub rejected branch update due to non-fast-forward.", code=409)

        raise CoProofError(f"GitHub ref update failed: {ref_response.text}", code=502)

    @staticmethod
    def extract_repo_path_from_node_url(node_url):
        """Extract the repository-relative path from a GitHub blob URL."""
        parsed = urlparse(node_url)
        marker = '/blob/'
        if marker not in parsed.path:
            return None
        _, blob_part = parsed.path.split(marker, 1)
        split_idx = blob_part.find('/')
        if split_idx == -1:
            return None
        return blob_part[split_idx + 1:]

    @staticmethod
    def extract_github_full_name(remote_repo_url):
        """Extract owner/repository from a GitHub remote URL."""
        parsed = urlparse(remote_repo_url)
        repo_path = parsed.path.strip('/')
        if repo_path.endswith('.git'):
            repo_path = repo_path[:-4]
        if '/' not in repo_path:
            raise CoProofError("Invalid GitHub remote URL format.", code=400)
        return repo_path

    @staticmethod
    def github_headers(token):
        """Build default GitHub API headers using a personal access token."""
        return {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        }

    @staticmethod
    def get_pull_request(remote_repo_url, token, pr_number):
        """Fetch one pull request from GitHub."""
        full_name = GitHubService.extract_github_full_name(remote_repo_url)
        try:
            response = requests.get(
                f"https://api.github.com/repos/{full_name}/pulls/{pr_number}",
                headers=GitHubService.github_headers(token),
                timeout=20,
            )
        except (RequestsConnectionError, Timeout) as exc:
            raise CoProofError("Could not reach GitHub API (network error).", code=502) from exc

        if response.status_code == 200:
            return response.json()
        if response.status_code == 404:
            raise CoProofError(f"PR #{pr_number} not found in repository.", code=404)
        if response.status_code in (401, 403):
            raise CoProofError("GitHub authentication failed while reading PR.", code=401)

        raise CoProofError(f"GitHub PR read failed: {response.text}", code=502)

    @staticmethod
    def list_open_pull_requests(remote_repo_url, token, base_branch):
        """List open pull requests that target the provided base branch."""
        full_name = GitHubService.extract_github_full_name(remote_repo_url)
        try:
            response = requests.get(
                f"https://api.github.com/repos/{full_name}/pulls",
                headers=GitHubService.github_headers(token),
                params={"state": "open", "base": base_branch, "per_page": 100},
                timeout=20,
            )
        except (RequestsConnectionError, Timeout) as exc:
            raise CoProofError("Could not reach GitHub API (network error).", code=502) from exc

        if response.status_code == 200:
            pulls = response.json()
            return [
                {
                    "number": pr.get("number"),
                    "title": pr.get("title"),
                    "url": pr.get("html_url"),
                    "head": pr.get("head", {}).get("ref"),
                    "base": pr.get("base", {}).get("ref"),
                    "author": (pr.get("user") or {}).get("login"),
                    "created_at": pr.get("created_at"),
                    "updated_at": pr.get("updated_at"),
                }
                for pr in pulls
            ]
        if response.status_code in (401, 403):
            raise CoProofError("GitHub authentication failed while listing PRs.", code=401)

        raise CoProofError(f"GitHub PR list failed: {response.text}", code=502)

    @staticmethod
    def merge_pull_request(remote_repo_url, token, pr_number):
        """Merge a pull request through the GitHub API using merge strategy."""
        full_name = GitHubService.extract_github_full_name(remote_repo_url)
        try:
            response = requests.put(
                f"https://api.github.com/repos/{full_name}/pulls/{pr_number}/merge",
                headers=GitHubService.github_headers(token),
                json={"merge_method": "merge"},
                timeout=20,
            )
        except (RequestsConnectionError, Timeout) as exc:
            raise CoProofError("Could not reach GitHub API (network error).", code=502) from exc

        if response.status_code == 200:
            payload = response.json()
            if not payload.get('merged', False):
                message = payload.get('message') or 'PR merge was not completed by GitHub.'
                raise CoProofError(message, code=409)
            return payload
        if response.status_code == 405:
            raise CoProofError("PR is not mergeable (possibly conflicts or already merged).", code=409)
        if response.status_code in (401, 403):
            raise CoProofError("GitHub authentication failed while merging PR.", code=401)
        if response.status_code == 404:
            raise CoProofError(f"PR #{pr_number} not found in repository.", code=404)

        raise CoProofError(f"GitHub PR merge failed: {response.text}", code=502)

    @staticmethod
    def parse_pr_metadata(pr_body):
        """Parse metadata tags from pull request body generated by backend flows."""
        body = pr_body or ""
        metadata = {
            "action": None,
            "base_node_id": None,
            "affected_nodes": [],
            "affected_node_id": None,
            "child_folder": None,
        }

        action_match = re.search(r"(?im)^Action:\s*(.+)$", body)
        if action_match:
            metadata["action"] = action_match.group(1).strip()

        base_match = re.search(r"(?im)^Base node ID:\s*([0-9a-fA-F\-]{36})$", body)
        if base_match:
            metadata["base_node_id"] = base_match.group(1).strip()

        affected_nodes_match = re.search(r"(?im)^Affected nodes:\s*(.+)$", body)
        if affected_nodes_match:
            metadata["affected_nodes"] = [
                part.strip() for part in affected_nodes_match.group(1).split(',') if part.strip()
            ]

        affected_node_id_match = re.search(r"(?im)^Affected node ID:\s*([0-9a-fA-F\-]{36})$", body)
        if affected_node_id_match:
            metadata["affected_node_id"] = affected_node_id_match.group(1).strip()

        child_folder_match = re.search(r"(?im)^Child folder:\s*([^\n\r]+)$", body)
        if child_folder_match:
            metadata["child_folder"] = child_folder_match.group(1).strip()

        return metadata

    @staticmethod
    def open_pull_request(remote_repo_url, token, title, body, head_branch, base_branch):
        """Create a pull request on GitHub."""
        full_name = GitHubService.extract_github_full_name(remote_repo_url)
        payload = {
            "title": title,
            "body": body,
            "head": head_branch,
            "base": base_branch,
        }

        try:
            response = requests.post(
                f"https://api.github.com/repos/{full_name}/pulls",
                json=payload,
                headers=GitHubService.github_headers(token),
                timeout=20,
            )
        except (RequestsConnectionError, Timeout) as exc:
            raise CoProofError("Could not reach GitHub API (network error).", code=502) from exc

        if response.status_code in (200, 201):
            return response.json()
        if response.status_code == 422:
            raise CoProofError(f"Unable to create PR: {response.text}", code=400)
        if response.status_code in (401, 403):
            raise CoProofError("GitHub authentication failed while creating PR.", code=401)

        raise CoProofError(f"GitHub PR creation failed: {response.text}", code=502)
