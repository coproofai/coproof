"""
TCD-06 — GitHub Service / Git Engine (`celery_worker`)
=======================================================
Module : server/app/services/github_service.py
Responsible : David
Tools : pytest, responses

Covered test cases
──────────────────
TC-06-01  extract_github_full_name — HTTPS clone URL (with .git suffix)
TC-06-02  extract_github_full_name — HTTPS URL without .git suffix
TC-06-03  get_branch_head_sha — returns SHA for existing branch
TC-06-04  get_branch_head_sha — raises CoProofError(code=404) for 404
TC-06-05  get_branch_head_sha — raises CoProofError(code=401) for 401/403
TC-06-06  get_blob_content — decodes base64 content correctly
TC-06-07  get_commit_tree_sha — returns tree SHA
TC-06-08  fork_or_get_fork — calls GitHub fork endpoint and returns (clone_url, full_name)
TC-06-09  sync_fork_branch — calls GitHub merge-upstream endpoint exactly once
TC-06-10  open_pull_request — creates PR and returns PR data
TC-06-11  merge_pull_request — calls merge endpoint and returns merged=True
TC-06-12  delete_fork — calls delete repo endpoint and returns deleted=True

Test design notes
─────────────────
GitHubService contains only static methods.  No Flask app context or database is
needed — the module imports only standard library, requests, and app.exceptions
(plain Python exception classes).

All HTTP calls are intercepted by the `responses` library via the @responses.activate
decorator.  Each test class is self-contained; no conftest.py is required.

TC-06-02: SSH URL format (git@github.com:owner/repo.git) is NOT supported by the
current implementation — urlparse does not decompose it into owner/repo correctly.
TC-06-02 tests the functionally equivalent case: HTTPS URL without the .git suffix.

TC-06-09: sync_fork_branch swallows all exceptions via a bare try/except.
The test registers the merge-upstream URL so that the real HTTP call can be captured
in responses.calls and verified.

TC-06-08: fork_or_get_fork polls the fork's default-branch ref after creation.
Mocking the readiness check to return 200 immediately avoids the time.sleep(3)
delay in the poll loop (the sleep is only reached when the check fails).

Run with:
  cd server
  pytest -v tests/tcd06_github_service/test_tcd06_github_service.py
"""

import base64

import pytest
import responses as rsps

from app.services.github_service import GitHubService
from app.exceptions import CoProofError


_REPO_URL  = "https://github.com/acme/repo.git"
_FULL_NAME = "acme/repo"
_TOKEN     = "gho_test_token"
_BASE_API  = f"https://api.github.com/repos/{_FULL_NAME}"


# ─────────────────────────────────────────────────────────────────────────────
# TC-06-01  extract_github_full_name — HTTPS clone URL with .git suffix
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0601_ExtractFullNameHttps:
    """TC-06-01 — Standard HTTPS clone URL → owner/repo (no .git suffix)."""

    def test_strips_dot_git_and_leading_slash(self):
        assert (
            GitHubService.extract_github_full_name("https://github.com/acme/my-repo.git")
            == "acme/my-repo"
        )


# ─────────────────────────────────────────────────────────────────────────────
# TC-06-02  extract_github_full_name — HTTPS URL without .git suffix
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0602_ExtractFullNameNoGitSuffix:
    """TC-06-02 — HTTPS URL without .git extension also works correctly.

    Note: SSH URLs (git@github.com:owner/repo.git) are not decomposed correctly
    by the current implementation (urlparse returns the full host:path string).
    All remote_repo_url values in production are HTTPS clone URLs.
    """

    def test_no_git_suffix(self):
        assert (
            GitHubService.extract_github_full_name("https://github.com/acme/my-repo")
            == "acme/my-repo"
        )


# ─────────────────────────────────────────────────────────────────────────────
# TC-06-03  get_branch_head_sha — returns SHA for existing branch
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0603_GetBranchHeadSha:
    """TC-06-03 — 200 response returns the commit SHA string."""

    @rsps.activate
    def test_returns_sha(self):
        rsps.add(
            rsps.GET,
            f"{_BASE_API}/git/ref/heads/main",
            json={"object": {"sha": "abc123"}},
            status=200,
        )
        sha = GitHubService.get_branch_head_sha(_REPO_URL, _TOKEN, "main")
        assert sha == "abc123"


# ─────────────────────────────────────────────────────────────────────────────
# TC-06-04  get_branch_head_sha — raises CoProofError for 404
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0604_GetBranchHeadSha404:
    """TC-06-04 — 404 response raises CoProofError with code=404."""

    @rsps.activate
    def test_raises_coproof_error(self):
        rsps.add(
            rsps.GET,
            f"{_BASE_API}/git/ref/heads/missing-branch",
            json={"message": "Not Found"},
            status=404,
        )
        with pytest.raises(CoProofError):
            GitHubService.get_branch_head_sha(_REPO_URL, _TOKEN, "missing-branch")

    @rsps.activate
    def test_error_code_is_404(self):
        rsps.add(
            rsps.GET,
            f"{_BASE_API}/git/ref/heads/missing-branch",
            json={"message": "Not Found"},
            status=404,
        )
        with pytest.raises(CoProofError) as exc_info:
            GitHubService.get_branch_head_sha(_REPO_URL, _TOKEN, "missing-branch")
        assert exc_info.value.code == 404


# ─────────────────────────────────────────────────────────────────────────────
# TC-06-05  get_branch_head_sha — raises CoProofError for 401/403
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0605_GetBranchHeadShaAuth:
    """TC-06-05 — 401 and 403 responses both raise CoProofError(code=401)."""

    @rsps.activate
    def test_401_raises_with_code_401(self):
        rsps.add(
            rsps.GET,
            f"{_BASE_API}/git/ref/heads/main",
            json={"message": "Bad credentials"},
            status=401,
        )
        with pytest.raises(CoProofError) as exc_info:
            GitHubService.get_branch_head_sha(_REPO_URL, _TOKEN, "main")
        assert exc_info.value.code == 401

    @rsps.activate
    def test_403_raises_with_code_401(self):
        rsps.add(
            rsps.GET,
            f"{_BASE_API}/git/ref/heads/main",
            json={"message": "Forbidden"},
            status=403,
        )
        with pytest.raises(CoProofError) as exc_info:
            GitHubService.get_branch_head_sha(_REPO_URL, _TOKEN, "main")
        assert exc_info.value.code == 401


# ─────────────────────────────────────────────────────────────────────────────
# TC-06-06  get_blob_content — decodes base64 content correctly
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0606_GetBlobContent:
    """TC-06-06 — Base64-encoded blob content is decoded and returned as a string."""

    @rsps.activate
    def test_decodes_base64(self):
        encoded = base64.b64encode(b"hello lean").decode("utf-8")
        rsps.add(
            rsps.GET,
            f"{_BASE_API}/git/blobs/blobsha1",
            json={"content": encoded, "encoding": "base64"},
            status=200,
        )
        content = GitHubService.get_blob_content(_REPO_URL, _TOKEN, "blobsha1")
        assert content == "hello lean"


# ─────────────────────────────────────────────────────────────────────────────
# TC-06-07  get_commit_tree_sha — returns tree SHA
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0607_GetCommitTreeSha:
    """TC-06-07 — Commit object contains tree SHA; method returns it."""

    @rsps.activate
    def test_returns_tree_sha(self):
        rsps.add(
            rsps.GET,
            f"{_BASE_API}/git/commits/commitsha1",
            json={"tree": {"sha": "tree-sha-abc"}},
            status=200,
        )
        tree_sha = GitHubService.get_commit_tree_sha(_REPO_URL, _TOKEN, "commitsha1")
        assert tree_sha == "tree-sha-abc"


# ─────────────────────────────────────────────────────────────────────────────
# TC-06-08  fork_or_get_fork — returns (clone_url, full_name)
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0608_ForkOrGetFork:
    """TC-06-08 — POST /forks followed by a readiness poll; returns clone URL and full_name."""

    @rsps.activate
    def test_returns_clone_url(self):
        rsps.add(
            rsps.POST,
            f"{_BASE_API}/forks",
            json={
                "clone_url":      "https://github.com/user/fork.git",
                "full_name":      "user/fork",
                "default_branch": "main",
            },
            status=202,
        )
        rsps.add(
            rsps.GET,
            "https://api.github.com/repos/user/fork/git/ref/heads/main",
            json={"object": {"sha": "deadbeef"}},
            status=200,
        )
        clone_url, _full_name = GitHubService.fork_or_get_fork(_REPO_URL, _TOKEN)
        assert clone_url == "https://github.com/user/fork.git"

    @rsps.activate
    def test_returns_full_name(self):
        rsps.add(
            rsps.POST,
            f"{_BASE_API}/forks",
            json={
                "clone_url":      "https://github.com/user/fork.git",
                "full_name":      "user/fork",
                "default_branch": "main",
            },
            status=202,
        )
        rsps.add(
            rsps.GET,
            "https://api.github.com/repos/user/fork/git/ref/heads/main",
            json={"object": {"sha": "deadbeef"}},
            status=200,
        )
        _clone_url, full_name = GitHubService.fork_or_get_fork(_REPO_URL, _TOKEN)
        assert full_name == "user/fork"


# ─────────────────────────────────────────────────────────────────────────────
# TC-06-09  sync_fork_branch — calls merge-upstream endpoint exactly once
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0609_SyncForkBranch:
    """TC-06-09 — sync_fork_branch POSTs to merge-upstream; swallows all errors silently."""

    @rsps.activate
    def test_calls_merge_upstream_once(self):
        rsps.add(
            rsps.POST,
            "https://api.github.com/repos/user/fork/merge-upstream",
            json={"message": "Successfully synced"},
            status=200,
        )
        GitHubService.sync_fork_branch("user/fork", _TOKEN, "main")
        assert len(rsps.calls) == 1
        assert "merge-upstream" in rsps.calls[0].request.url


# ─────────────────────────────────────────────────────────────────────────────
# TC-06-10  open_pull_request — creates PR and returns PR data
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0610_OpenPullRequest:
    """TC-06-10 — POST /pulls returns PR JSON; method forwards it to caller."""

    @rsps.activate
    def test_returns_pr_number(self):
        rsps.add(
            rsps.POST,
            f"{_BASE_API}/pulls",
            json={
                "number":   7,
                "html_url": "https://github.com/acme/repo/pull/7",
                "head":     {"ref": "user:branch"},
                "base":     {"ref": "main"},
            },
            status=201,
        )
        pr = GitHubService.open_pull_request(
            _REPO_URL, _TOKEN, "Fix proof", "", "user:branch", "main"
        )
        assert pr["number"] == 7

    @rsps.activate
    def test_returns_html_url(self):
        rsps.add(
            rsps.POST,
            f"{_BASE_API}/pulls",
            json={
                "number":   7,
                "html_url": "https://github.com/acme/repo/pull/7",
                "head":     {"ref": "user:branch"},
                "base":     {"ref": "main"},
            },
            status=201,
        )
        pr = GitHubService.open_pull_request(
            _REPO_URL, _TOKEN, "Fix proof", "", "user:branch", "main"
        )
        assert "html_url" in pr
        assert pr["html_url"] == "https://github.com/acme/repo/pull/7"


# ─────────────────────────────────────────────────────────────────────────────
# TC-06-11  merge_pull_request — calls merge endpoint and returns result
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0611_MergePullRequest:
    """TC-06-11 — PUT /pulls/{n}/merge returns merged=True."""

    @rsps.activate
    def test_returns_merged_true(self):
        rsps.add(
            rsps.PUT,
            f"{_BASE_API}/pulls/7/merge",
            json={"merged": True, "message": "Pull Request successfully merged"},
            status=200,
        )
        result = GitHubService.merge_pull_request(_REPO_URL, _TOKEN, pr_number=7)
        assert result.get("merged") is True

    @rsps.activate
    def test_merge_endpoint_called_once(self):
        rsps.add(
            rsps.PUT,
            f"{_BASE_API}/pulls/7/merge",
            json={"merged": True, "message": "Pull Request successfully merged"},
            status=200,
        )
        GitHubService.merge_pull_request(_REPO_URL, _TOKEN, pr_number=7)
        assert len(rsps.calls) == 1
        assert "/pulls/7/merge" in rsps.calls[0].request.url


# ─────────────────────────────────────────────────────────────────────────────
# TC-06-12  delete_fork — calls delete repo endpoint
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0612_DeleteFork:
    """TC-06-12 — DELETE /repos/{fork} returns 204; method returns deleted=True."""

    @rsps.activate
    def test_returns_deleted_true(self):
        rsps.add(
            rsps.DELETE,
            "https://api.github.com/repos/user/fork",
            status=204,
        )
        result = GitHubService.delete_fork("user/fork", _TOKEN)
        assert result.get("deleted") is True

    @rsps.activate
    def test_delete_endpoint_called_once(self):
        rsps.add(
            rsps.DELETE,
            "https://api.github.com/repos/user/fork",
            status=204,
        )
        GitHubService.delete_fork("user/fork", _TOKEN)
        assert len(rsps.calls) == 1
        assert "repos/user/fork" in rsps.calls[0].request.url
