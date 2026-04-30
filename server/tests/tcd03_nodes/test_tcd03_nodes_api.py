"""
TCD-03 — Nodes API (`web`)
===========================
Module : server/app/api/nodes.py
Responsible : David
Tools : pytest-flask, responses, pytest-mock

Covered test cases
──────────────────
TC-03-01  Owner → _prepare_pr_context returns pr_head_prefix=None, no fork call
TC-03-02  Public-repo contributor → fork flow: pr_head_prefix=fork_owner, _build_pr_head="owner:branch"
TC-03-03  Private-repo contributor → no fork flow: pr_head_prefix=None
TC-03-04  No linked GitHub account → HTTP 400 from /solve endpoint

Test design notes
─────────────────
TC-03-01/02/03 exercise _prepare_pr_context (and _build_pr_head) directly.
These are module-level helpers in nodes.py; importing them avoids the need to
mock the entire /solve endpoint chain (CompilerClient, LeanService, TranslateClient,
GitHubService.get_repository_files_map, etc.).

TC-03-04 goes through the HTTP /solve endpoint to validate the 400 response.
It relies on the `project_and_node` DB fixture and mocks CompilerClient so that
execution reaches the GitHub-token guard without hitting Lean workers.

Run with:
  cd server
  pytest -v tests/tcd03_nodes/test_tcd03_nodes_api.py
"""

import types
import unittest.mock as mock
import uuid

import pytest
import responses as rsps

from app.api.nodes import _prepare_pr_context, _build_pr_head
from app.exceptions import CoProofError


# ─── GitHub mock constants ────────────────────────────────────────────────────

_UPSTREAM_URL  = "https://github.com/owner/myrepo.git"
_UPSTREAM_FULL = "owner/myrepo"
_FORK_FULL     = "forkowner/myrepo"
_FORK_URL      = "https://github.com/forkowner/myrepo.git"

_GH_FORKS_URL     = f"https://api.github.com/repos/{_UPSTREAM_FULL}/forks"
_GH_FORK_REF_URL  = f"https://api.github.com/repos/{_FORK_FULL}/git/ref/heads/main"
_GH_SYNC_URL      = f"https://api.github.com/repos/{_FORK_FULL}/merge-upstream"


# ─── Tiny mock-object helpers ─────────────────────────────────────────────────

def _make_user(user_id=None, token="gho_test"):
    """Return a simple namespace that satisfies _prepare_pr_context's user interface."""
    ns = types.SimpleNamespace()
    ns.id = user_id or uuid.uuid4()
    ns.github_access_token = token
    ns.github_refresh_token = None
    ns.token_expires_at = None
    return ns


def _make_project(author_id, visibility="public",
                  repo_url=_UPSTREAM_URL, default_branch="main"):
    """Return a simple namespace that satisfies _prepare_pr_context's project interface."""
    ns = types.SimpleNamespace()
    ns.author_id = author_id
    ns.visibility = visibility
    ns.remote_repo_url = repo_url
    ns.default_branch = default_branch
    return ns


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ─────────────────────────────────────────────────────────────────────────────
# TC-03-01  Owner → direct push, no fork
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0301_OwnerDirectPush:
    """TC-03-01 — Project owner: _prepare_pr_context returns pr_head_prefix=None."""

    def test_pr_head_prefix_is_none(self, app):
        owner_id = uuid.uuid4()
        user    = _make_user(user_id=owner_id)
        project = _make_project(author_id=owner_id, visibility="public")

        with app.app_context():
            ctx = _prepare_pr_context(project, user)

        assert ctx["pr_head_prefix"] is None

    def test_token_is_user_token(self, app):
        owner_id = uuid.uuid4()
        user    = _make_user(user_id=owner_id, token="gho_owner_token")
        project = _make_project(author_id=owner_id)

        with app.app_context():
            ctx = _prepare_pr_context(project, user)

        assert ctx["token"] == "gho_owner_token"

    def test_repo_url_is_upstream(self, app):
        owner_id = uuid.uuid4()
        user    = _make_user(user_id=owner_id)
        project = _make_project(author_id=owner_id)

        with app.app_context():
            ctx = _prepare_pr_context(project, user)

        assert ctx["repo_url"] == _UPSTREAM_URL

    def test_pr_repo_url_is_upstream(self, app):
        owner_id = uuid.uuid4()
        user    = _make_user(user_id=owner_id)
        project = _make_project(author_id=owner_id)

        with app.app_context():
            ctx = _prepare_pr_context(project, user)

        assert ctx["pr_repo_url"] == _UPSTREAM_URL

    @rsps.activate
    def test_fork_endpoint_is_not_called(self, app):
        """No fork HTTP call should be made for the owner."""
        rsps.add(rsps.POST, _GH_FORKS_URL, status=500)  # would fail if called

        owner_id = uuid.uuid4()
        user    = _make_user(user_id=owner_id)
        project = _make_project(author_id=owner_id)

        with app.app_context():
            ctx = _prepare_pr_context(project, user)  # must not raise

        assert ctx["pr_head_prefix"] is None

    def test_build_pr_head_returns_bare_branch(self, app):
        """_build_pr_head with pr_head_prefix=None returns the branch name as-is."""
        ctx = {"pr_head_prefix": None}
        assert _build_pr_head(ctx, "my-branch") == "my-branch"


# ─────────────────────────────────────────────────────────────────────────────
# TC-03-02  Public-repo contributor → fork-based flow
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0302_PublicContributorForkFlow:
    """TC-03-02 — Public-repo contributor: fork flow invoked, pr_head_prefix set."""

    def _register_fork_mocks(self):
        """Register responses mocks for fork + poll + sync."""
        rsps.add(
            rsps.POST, _GH_FORKS_URL,
            json={
                "full_name": _FORK_FULL,
                "clone_url": _FORK_URL,
                "default_branch": "main",
            },
            status=202,
        )
        # Fork-readiness poll (first attempt succeeds)
        rsps.add(rsps.GET, _GH_FORK_REF_URL, json={"ref": "refs/heads/main"}, status=200)
        # sync_fork_branch — best-effort, silently ignored
        rsps.add(rsps.POST, _GH_SYNC_URL, json={}, status=200)

    @rsps.activate
    def test_pr_head_prefix_equals_fork_owner(self, app):
        self._register_fork_mocks()

        contributor_id = uuid.uuid4()
        owner_id       = uuid.uuid4()   # different from contributor
        user    = _make_user(user_id=contributor_id)
        project = _make_project(author_id=owner_id, visibility="public")

        with app.app_context():
            ctx = _prepare_pr_context(project, user)

        assert ctx["pr_head_prefix"] == "forkowner"

    @rsps.activate
    def test_repo_url_is_fork(self, app):
        self._register_fork_mocks()

        contributor_id = uuid.uuid4()
        user    = _make_user(user_id=contributor_id)
        project = _make_project(author_id=uuid.uuid4(), visibility="public")

        with app.app_context():
            ctx = _prepare_pr_context(project, user)

        assert ctx["repo_url"] == _FORK_URL

    @rsps.activate
    def test_pr_repo_url_is_upstream(self, app):
        """PR must still target the upstream repo, not the fork."""
        self._register_fork_mocks()

        user    = _make_user(user_id=uuid.uuid4())
        project = _make_project(author_id=uuid.uuid4(), visibility="public")

        with app.app_context():
            ctx = _prepare_pr_context(project, user)

        assert ctx["pr_repo_url"] == _UPSTREAM_URL

    @rsps.activate
    def test_build_pr_head_returns_owner_colon_branch(self, app):
        """_build_pr_head with a prefix returns 'owner:branch'."""
        self._register_fork_mocks()

        user    = _make_user(user_id=uuid.uuid4())
        project = _make_project(author_id=uuid.uuid4(), visibility="public")

        with app.app_context():
            ctx = _prepare_pr_context(project, user)

        assert _build_pr_head(ctx, "feature-branch") == "forkowner:feature-branch"

    @rsps.activate
    def test_fork_endpoint_is_called(self, app):
        """The forks endpoint must be called exactly once."""
        self._register_fork_mocks()

        user    = _make_user(user_id=uuid.uuid4())
        project = _make_project(author_id=uuid.uuid4(), visibility="public")

        with app.app_context():
            _prepare_pr_context(project, user)

        fork_calls = [c for c in rsps.calls if "forks" in c.request.url]
        assert len(fork_calls) == 1


# ─────────────────────────────────────────────────────────────────────────────
# TC-03-03  Private-repo contributor → direct push (no fork)
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0303_PrivateContributorDirectPush:
    """TC-03-03 — Private-repo contributor: fork flow skipped, pr_head_prefix=None."""

    def test_pr_head_prefix_is_none(self, app):
        contributor_id = uuid.uuid4()
        user    = _make_user(user_id=contributor_id)
        project = _make_project(
            author_id=uuid.uuid4(),   # different owner
            visibility="private",
        )

        with app.app_context():
            ctx = _prepare_pr_context(project, user)

        assert ctx["pr_head_prefix"] is None

    def test_repo_url_is_upstream(self, app):
        user    = _make_user(user_id=uuid.uuid4())
        project = _make_project(author_id=uuid.uuid4(), visibility="private")

        with app.app_context():
            ctx = _prepare_pr_context(project, user)

        assert ctx["repo_url"] == _UPSTREAM_URL

    @rsps.activate
    def test_fork_endpoint_is_not_called(self, app):
        """Private-repo contributors must NOT trigger a fork."""
        rsps.add(rsps.POST, _GH_FORKS_URL, status=500)  # would fail if called

        user    = _make_user(user_id=uuid.uuid4())
        project = _make_project(author_id=uuid.uuid4(), visibility="private")

        with app.app_context():
            ctx = _prepare_pr_context(project, user)  # must not raise

        assert ctx["pr_head_prefix"] is None

    def test_build_pr_head_returns_bare_branch(self, app):
        ctx = {"pr_head_prefix": None}
        assert _build_pr_head(ctx, "collab-fix") == "collab-fix"


# ─────────────────────────────────────────────────────────────────────────────
# TC-03-04  No linked GitHub account → HTTP 400 from /solve endpoint
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0304_NoGitHubAccount:
    """TC-03-04 — User without a GitHub token gets HTTP 400 from the /solve endpoint."""

    @mock.patch(
        "app.services.integrations.compiler_client.CompilerClient.verify_snippet",
        return_value={"valid": True, "errors": []},
    )
    def test_returns_http_400(self, _mock_verify, client, user_no_github, project_and_node):
        pid = project_and_node["project_id"]
        nid = project_and_node["node_id"]
        resp = client.post(
            f"/api/v1/nodes/{pid}/{nid}/solve",
            json={"lean_code": "theorem t : True := trivial", "model_id": "mock/test"},
            headers=_bearer(user_no_github["token"]),
        )
        assert resp.status_code == 400

    @mock.patch(
        "app.services.integrations.compiler_client.CompilerClient.verify_snippet",
        return_value={"valid": True, "errors": []},
    )
    def test_error_mentions_github(self, _mock_verify, client, user_no_github, project_and_node):
        pid = project_and_node["project_id"]
        nid = project_and_node["node_id"]
        data = client.post(
            f"/api/v1/nodes/{pid}/{nid}/solve",
            json={"lean_code": "theorem t : True := trivial", "model_id": "mock/test"},
            headers=_bearer(user_no_github["token"]),
        ).get_json()
        msg = (data.get("message") or data.get("error") or "").lower()
        assert "github" in msg

