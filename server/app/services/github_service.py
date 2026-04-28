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
    def close_pull_request(remote_repo_url, token, pr_number):
        """Close (discard) a pull request without merging, then delete its head branch."""
        full_name = GitHubService.extract_github_full_name(remote_repo_url)
        # 1. Close the PR
        try:
            response = requests.patch(
                f"https://api.github.com/repos/{full_name}/pulls/{pr_number}",
                headers=GitHubService.github_headers(token),
                json={"state": "closed"},
                timeout=20,
            )
        except (RequestsConnectionError, Timeout) as exc:
            raise CoProofError("Could not reach GitHub API (network error).", code=502) from exc

        if response.status_code not in (200,):
            if response.status_code in (401, 403):
                raise CoProofError("GitHub authentication failed while closing PR.", code=401)
            raise CoProofError(f"GitHub PR close failed: {response.text}", code=502)

        pr_data = response.json()
        head_branch = pr_data.get("head", {}).get("ref")

        # 2. Delete the head branch (best-effort — ignore 422/404 if already gone)
        if head_branch:
            try:
                requests.delete(
                    f"https://api.github.com/repos/{full_name}/git/refs/heads/{head_branch}",
                    headers=GitHubService.github_headers(token),
                    timeout=20,
                )
            except Exception:
                pass

        return {"closed": True, "pr_number": pr_number, "branch": head_branch}

    @staticmethod
    def get_pull_request_files(remote_repo_url, token, pr_number):
        """Return the list of files changed in a pull request with their contents."""
        import logging
        _log = logging.getLogger(__name__)

        full_name = GitHubService.extract_github_full_name(remote_repo_url)
        try:
            response = requests.get(
                f"https://api.github.com/repos/{full_name}/pulls/{pr_number}/files",
                headers=GitHubService.github_headers(token),
                params={"per_page": 100},
                timeout=20,
            )
        except (RequestsConnectionError, Timeout) as exc:
            raise CoProofError("Could not reach GitHub API (network error).", code=502) from exc

        if response.status_code != 200:
            if response.status_code in (401, 403):
                raise CoProofError("GitHub authentication failed while listing PR files.", code=401)
            raise CoProofError(f"GitHub PR files failed: {response.text}", code=502)

        _log.debug("[pr_files] PR #%s files API returned %d entries", pr_number, len(response.json()))

        files = []
        for f in response.json():
            filename = f.get("filename", "")
            raw_url = f.get("raw_url") or f.get("blob_url")
            content = None

            # GitHub PR files API sometimes returns github.com/.../raw/... instead of
            # raw.githubusercontent.com/... — the former requires a browser session and
            # returns an HTML 404 when fetched programmatically.  Normalise it.
            if raw_url:
                import re as _re
                from urllib.parse import unquote as _unquote
                m = _re.match(r'^https://github\.com/(.+?)/raw/(.+)$', raw_url)
                if m:
                    raw_url = _unquote(f"https://raw.githubusercontent.com/{m.group(1)}/{m.group(2)}")

            print(f"[pr_files] file={filename!r}  raw_url={raw_url!r}", flush=True)
            if raw_url:
                try:
                    raw_resp = requests.get(
                        raw_url,
                        headers={"Authorization": f"token {token}"},
                        timeout=20,
                    )
                    print(f"[pr_files]   raw fetch status={raw_resp.status_code}  len={len(raw_resp.text)}", flush=True)
                    if raw_resp.status_code == 200:
                        content = raw_resp.text
                    else:
                        print(f"[pr_files]   raw fetch FAILED for {filename!r}: {raw_resp.status_code} {raw_resp.text[:300]}", flush=True)
                except Exception as exc:
                    print(f"[pr_files]   raw fetch EXCEPTION for {filename!r}: {exc}", flush=True)
            files.append({
                "filename": filename,
                "status": f.get("status"),
                "additions": f.get("additions", 0),
                "deletions": f.get("deletions", 0),
                "content": content,
            })
        return files

    @staticmethod
    def delete_repo(remote_repo_url, token):
        """Delete the GitHub repository. Requires the owner's token with delete_repo scope."""
        full_name = GitHubService.extract_github_full_name(remote_repo_url)
        try:
            response = requests.delete(
                f"https://api.github.com/repos/{full_name}",
                headers=GitHubService.github_headers(token),
                timeout=20,
            )
        except (RequestsConnectionError, Timeout) as exc:
            raise CoProofError("Could not reach GitHub API (network error).", code=502) from exc

        if response.status_code == 204:
            return {"deleted": True, "repo": full_name}
        if response.status_code in (401, 403):
            raise CoProofError("GitHub authentication failed or missing delete_repo permission.", code=401)
        if response.status_code == 404:
            raise CoProofError("Repository not found on GitHub.", code=404)
        raise CoProofError(
            f"GitHub repo deletion failed ({response.status_code}): {response.text}", code=502
        )

    @staticmethod
    def delete_fork(fork_full_name, token):
        """Delete a forked repository by its full_name (owner/repo). Best-effort, caller should catch."""
        try:
            response = requests.delete(
                f"https://api.github.com/repos/{fork_full_name}",
                headers=GitHubService.github_headers(token),
                timeout=20,
            )
        except Exception:
            return {"deleted": False, "reason": "network_error"}

        if response.status_code == 204:
            return {"deleted": True, "repo": fork_full_name}
        return {"deleted": False, "reason": f"http_{response.status_code}"}

    @staticmethod
    def get_repo_invitations(token):
        """List pending repository invitations for the authenticated user."""
        try:
            response = requests.get(
                "https://api.github.com/user/repository_invitations",
                headers=GitHubService.github_headers(token),
                timeout=20,
            )
        except (RequestsConnectionError, Timeout) as exc:
            raise CoProofError("Could not reach GitHub API (network error).", code=502) from exc

        if response.status_code == 200:
            return response.json()
        if response.status_code in (401, 403):
            raise CoProofError("GitHub authentication failed while fetching invitations.", code=401)
        raise CoProofError(
            f"GitHub invitations fetch failed ({response.status_code}): {response.text}", code=502
        )

    @staticmethod
    def accept_repo_invitation(token, invitation_id):
        """Accept a pending repository invitation."""
        try:
            response = requests.patch(
                f"https://api.github.com/user/repository_invitations/{invitation_id}",
                headers=GitHubService.github_headers(token),
                timeout=20,
            )
        except (RequestsConnectionError, Timeout) as exc:
            raise CoProofError("Could not reach GitHub API (network error).", code=502) from exc

        if response.status_code == 204:
            return {"accepted": True}
        if response.status_code in (401, 403):
            raise CoProofError("GitHub authentication failed while accepting invitation.", code=401)
        if response.status_code == 404:
            raise CoProofError("Invitation not found or already handled.", code=404)
        raise CoProofError(
            f"GitHub invitation accept failed ({response.status_code}): {response.text}", code=502
        )

    @staticmethod
    def decline_repo_invitation(token, invitation_id):
        """Decline a pending repository invitation."""
        try:
            response = requests.delete(
                f"https://api.github.com/user/repository_invitations/{invitation_id}",
                headers=GitHubService.github_headers(token),
                timeout=20,
            )
        except (RequestsConnectionError, Timeout) as exc:
            raise CoProofError("Could not reach GitHub API (network error).", code=502) from exc

        if response.status_code == 204:
            return {"declined": True}
        if response.status_code in (401, 403):
            raise CoProofError("GitHub authentication failed while declining invitation.", code=401)
        if response.status_code == 404:
            raise CoProofError("Invitation not found or already handled.", code=404)
        raise CoProofError(
            f"GitHub invitation decline failed ({response.status_code}): {response.text}", code=502
        )

    @staticmethod
    def add_repo_collaborator(remote_repo_url, token, github_username):
        """Invite a GitHub user as a collaborator on the repository (push permission)."""
        full_name = GitHubService.extract_github_full_name(remote_repo_url)
        try:
            response = requests.put(
                f"https://api.github.com/repos/{full_name}/collaborators/{github_username}",
                headers=GitHubService.github_headers(token),
                json={"permission": "push"},
                timeout=20,
            )
        except (RequestsConnectionError, Timeout) as exc:
            raise CoProofError("Could not reach GitHub API (network error).", code=502) from exc

        # 201 = invited, 204 = already a collaborator
        if response.status_code in (201, 204):
            return {"invited": True, "username": github_username}
        if response.status_code in (401, 403):
            raise CoProofError("GitHub authentication failed while inviting collaborator.", code=401)
        raise CoProofError(
            f"GitHub collaborator invite failed ({response.status_code}): {response.text}", code=502
        )

    @staticmethod
    def remove_repo_collaborator(remote_repo_url, token, github_username):
        """Remove a GitHub user from repository collaborators."""
        full_name = GitHubService.extract_github_full_name(remote_repo_url)
        try:
            response = requests.delete(
                f"https://api.github.com/repos/{full_name}/collaborators/{github_username}",
                headers=GitHubService.github_headers(token),
                timeout=20,
            )
        except (RequestsConnectionError, Timeout) as exc:
            raise CoProofError("Could not reach GitHub API (network error).", code=502) from exc

        if response.status_code in (204,):
            return {"removed": True, "username": github_username}
        if response.status_code in (401, 403):
            raise CoProofError("GitHub authentication failed while removing collaborator.", code=401)
        raise CoProofError(
            f"GitHub collaborator removal failed ({response.status_code}): {response.text}", code=502
        )

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
    def fork_or_get_fork(remote_repo_url, token):
        """
        Fork the upstream repo into the token owner's account (if not already forked).
        Returns the full_name of the fork (e.g. "accountB/repo-name").
        GitHub returns the fork immediately but actual readiness may take a few seconds;
        we poll until the default branch ref is available.
        """
        import time
        upstream_full_name = GitHubService.extract_github_full_name(remote_repo_url)

        # Attempt to create fork (idempotent — returns existing fork if already forked)
        try:
            resp = requests.post(
                f"https://api.github.com/repos/{upstream_full_name}/forks",
                headers=GitHubService.github_headers(token),
                json={},
                timeout=30,
            )
        except (RequestsConnectionError, Timeout) as exc:
            raise CoProofError("Could not reach GitHub API (network error).", code=502) from exc

        if resp.status_code not in (200, 202):
            if resp.status_code in (401, 403):
                raise CoProofError("GitHub authentication failed while forking repository.", code=401)
            raise CoProofError(f"GitHub fork failed ({resp.status_code}): {resp.text}", code=502)

        fork_data = resp.json()
        fork_full_name = fork_data.get('full_name')
        fork_clone_url = fork_data.get('clone_url') or f"https://github.com/{fork_full_name}"

        # Poll until the fork's default branch is ready (up to ~15 s)
        default_branch = fork_data.get('default_branch', 'main')
        for _ in range(6):
            check = requests.get(
                f"https://api.github.com/repos/{fork_full_name}/git/ref/heads/{default_branch}",
                headers=GitHubService.github_headers(token),
                timeout=10,
            )
            if check.status_code == 200:
                break
            time.sleep(3)

        return fork_clone_url, fork_full_name

    @staticmethod
    def sync_fork_branch(fork_full_name, token, branch):
        """
        Sync a fork's branch with the upstream via GitHub's merge-upstream API.
        Best-effort — silently ignores errors (e.g. if already in sync).
        """
        try:
            requests.post(
                f"https://api.github.com/repos/{fork_full_name}/merge-upstream",
                headers=GitHubService.github_headers(token),
                json={"branch": branch},
                timeout=20,
            )
        except Exception:
            pass

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
