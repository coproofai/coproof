"""
TCD-02 — Projects API (`web`)
==============================
Module : server/app/api/projects.py + server/app/services/project_service.py
Responsible : David
Tools : pytest-flask, responses, pytest-mock

Covered test cases
──────────────────
TC-02-01  POST /projects  valid payload            → 201 + project created
TC-02-02  POST /projects  missing name             → 400
TC-02-03  POST /projects  missing goal             → 400
TC-02-04  POST /projects  invalid visibility       → 400
TC-02-05  POST /projects  non-list tags            → 400
TC-02-06  POST /projects  no linked GitHub account → 400
TC-02-07  GET  /projects/public                    → paginated list (public only)
TC-02-08  GET  /projects/public?q=gold             → filtered by name
TC-02-09  GET  /projects/public with JWT           → is_following flag populated

External GitHub REST API calls are intercepted by the `responses` library.
CompilerClient.verify_snippet is patched wherever the request reaches that
point in the service (before GitHub token validation).

Run with:
  cd server
  pytest -v tests/tcd02_projects/test_tcd02_projects_api.py
"""

import unittest.mock as mock
import uuid

import pytest
import responses as rsps

from app.extensions import db as _db


# ─── GitHub mock constants ────────────────────────────────────────────────────

_GH_REPOS_URL = "https://api.github.com/user/repos"
_FULL_NAME = "testuser/coproof-myproof"
_HTML_URL = "https://github.com/testuser/coproof-myproof"
_CLONE_URL = "https://github.com/testuser/coproof-myproof.git"


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _mock_github_create_project() -> None:
    """
    Register all `responses` mocks for a successful project creation.

    GitHub API sequence
    ───────────────────
    1. POST /user/repos               → 201  (repo created)
    2. GET  .../contents/Definitions.lean → 404 (doesn't exist yet)
    3. PUT  .../contents/Definitions.lean → 201
    4. GET  .../contents/root/main.lean   → 404
    5. PUT  .../contents/root/main.lean   → 201
    6. GET  .../contents/root/main.tex    → 404
    7. PUT  .../contents/root/main.tex    → 201
    """
    rsps.add(
        rsps.POST, _GH_REPOS_URL,
        json={
            "full_name": _FULL_NAME,
            "clone_url": _CLONE_URL,
            "html_url": _HTML_URL,
            "default_branch": "main",
        },
        status=201,
    )
    for path in ("Definitions.lean", "root/main.lean", "root/main.tex"):
        url = f"https://api.github.com/repos/{_FULL_NAME}/contents/{path}"
        rsps.add(rsps.GET, url, status=404)
        rsps.add(rsps.PUT, url, json={"content": {"name": path}}, status=201)


# ─────────────────────────────────────────────────────────────────────────────
# TC-02-01  POST /projects — valid payload
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0201_CreateProjectValid:
    """TC-02-01 — POST /projects with a valid payload creates the project and returns 201."""

    PAYLOAD = {
        "name": "MyProof",
        "goal": "theorem myproof_root : True := trivial",
        "visibility": "private",
    }

    @rsps.activate
    @mock.patch(
        "app.services.project_service.CompilerClient.verify_snippet",
        return_value={"valid": True, "errors": []},
    )
    def test_returns_http_201(self, _mock_verify, client, user_with_github):
        _mock_github_create_project()
        resp = client.post(
            "/api/v1/projects",
            json=self.PAYLOAD,
            headers=_bearer(user_with_github["token"]),
        )
        assert resp.status_code == 201

    @rsps.activate
    @mock.patch(
        "app.services.project_service.CompilerClient.verify_snippet",
        return_value={"valid": True, "errors": []},
    )
    def test_response_has_project_id(self, _mock_verify, client, user_with_github):
        _mock_github_create_project()
        data = client.post(
            "/api/v1/projects",
            json=self.PAYLOAD,
            headers=_bearer(user_with_github["token"]),
        ).get_json()
        assert "id" in data
        assert data["id"] is not None

    @rsps.activate
    @mock.patch(
        "app.services.project_service.CompilerClient.verify_snippet",
        return_value={"valid": True, "errors": []},
    )
    def test_response_has_correct_name(self, _mock_verify, client, user_with_github):
        _mock_github_create_project()
        data = client.post(
            "/api/v1/projects",
            json=self.PAYLOAD,
            headers=_bearer(user_with_github["token"]),
        ).get_json()
        assert data["name"] == "MyProof"

    @rsps.activate
    @mock.patch(
        "app.services.project_service.CompilerClient.verify_snippet",
        return_value={"valid": True, "errors": []},
    )
    def test_response_has_remote_repo_url(self, _mock_verify, client, user_with_github):
        _mock_github_create_project()
        data = client.post(
            "/api/v1/projects",
            json=self.PAYLOAD,
            headers=_bearer(user_with_github["token"]),
        ).get_json()
        assert "remote_repo_url" in data
        assert data["remote_repo_url"] == _CLONE_URL

    @rsps.activate
    @mock.patch(
        "app.services.project_service.CompilerClient.verify_snippet",
        return_value={"valid": True, "errors": []},
    )
    def test_project_row_is_created_in_db(
        self, _mock_verify, client, app, user_with_github
    ):
        _mock_github_create_project()
        client.post(
            "/api/v1/projects",
            json=self.PAYLOAD,
            headers=_bearer(user_with_github["token"]),
        )
        from app.models.project import Project

        with app.app_context():
            project = Project.query.filter_by(name="MyProof").first()
        assert project is not None

    @rsps.activate
    @mock.patch(
        "app.services.project_service.CompilerClient.verify_snippet",
        return_value={"valid": True, "errors": []},
    )
    def test_root_node_is_created_in_db(
        self, _mock_verify, client, app, user_with_github
    ):
        _mock_github_create_project()
        client.post(
            "/api/v1/projects",
            json=self.PAYLOAD,
            headers=_bearer(user_with_github["token"]),
        )
        from app.models.project import Project
        from app.models.node import Node

        with app.app_context():
            project = Project.query.filter_by(name="MyProof").first()
            assert project is not None
            node = Node.query.filter_by(
                project_id=project.id, name="root"
            ).first()
        assert node is not None


# ─────────────────────────────────────────────────────────────────────────────
# TC-02-02  POST /projects — missing name
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0202_MissingName:
    """TC-02-02 — POST /projects without a name returns 400."""

    def test_returns_http_400(self, client, user_with_github):
        resp = client.post(
            "/api/v1/projects",
            json={"goal": "theorem r : True := trivial"},
            headers=_bearer(user_with_github["token"]),
        )
        assert resp.status_code == 400

    def test_error_message_mentions_name(self, client, user_with_github):
        data = client.post(
            "/api/v1/projects",
            json={"goal": "theorem r : True := trivial"},
            headers=_bearer(user_with_github["token"]),
        ).get_json()
        assert "message" in data
        assert "name" in data["message"].lower()


# ─────────────────────────────────────────────────────────────────────────────
# TC-02-03  POST /projects — missing goal
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0203_MissingGoal:
    """TC-02-03 — POST /projects without a goal returns 400."""

    def test_returns_http_400(self, client, user_with_github):
        resp = client.post(
            "/api/v1/projects",
            json={"name": "NoGoal"},
            headers=_bearer(user_with_github["token"]),
        )
        assert resp.status_code == 400

    def test_error_message_mentions_goal(self, client, user_with_github):
        data = client.post(
            "/api/v1/projects",
            json={"name": "NoGoal"},
            headers=_bearer(user_with_github["token"]),
        ).get_json()
        assert "message" in data
        assert "goal" in data["message"].lower()


# ─────────────────────────────────────────────────────────────────────────────
# TC-02-04  POST /projects — invalid visibility
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0204_InvalidVisibility:
    """TC-02-04 — POST /projects with an invalid visibility value returns 400."""

    def test_returns_http_400(self, client, user_with_github):
        resp = client.post(
            "/api/v1/projects",
            json={
                "name": "Test",
                "goal": "theorem r : True := trivial",
                "visibility": "secret",
            },
            headers=_bearer(user_with_github["token"]),
        )
        assert resp.status_code == 400

    def test_error_message_mentions_visibility(self, client, user_with_github):
        data = client.post(
            "/api/v1/projects",
            json={
                "name": "Test",
                "goal": "theorem r : True := trivial",
                "visibility": "secret",
            },
            headers=_bearer(user_with_github["token"]),
        ).get_json()
        assert "message" in data
        assert "visibility" in data["message"].lower()


# ─────────────────────────────────────────────────────────────────────────────
# TC-02-05  POST /projects — non-list tags
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0205_NonListTags:
    """TC-02-05 — POST /projects with tags as a string (not a list) returns 400."""

    def test_returns_http_400(self, client, user_with_github):
        resp = client.post(
            "/api/v1/projects",
            json={
                "name": "Test",
                "goal": "theorem r : True := trivial",
                "tags": "algebra",
            },
            headers=_bearer(user_with_github["token"]),
        )
        assert resp.status_code == 400

    def test_error_message_mentions_tags(self, client, user_with_github):
        data = client.post(
            "/api/v1/projects",
            json={
                "name": "Test",
                "goal": "theorem r : True := trivial",
                "tags": "algebra",
            },
            headers=_bearer(user_with_github["token"]),
        ).get_json()
        assert "message" in data
        assert "tags" in data["message"].lower()


# ─────────────────────────────────────────────────────────────────────────────
# TC-02-06  POST /projects — no linked GitHub account
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0206_NoGitHubAccount:
    """TC-02-06 — POST /projects for a user without a linked GitHub account returns 400.

    Note: _validate_goal_context (→ CompilerClient.verify_snippet) is called
    before the GitHub token check, so it must be mocked here too.
    """

    @mock.patch(
        "app.services.project_service.CompilerClient.verify_snippet",
        return_value={"valid": True, "errors": []},
    )
    def test_returns_http_400(self, _mock_verify, client, user_without_github):
        resp = client.post(
            "/api/v1/projects",
            json={"name": "Test", "goal": "theorem r : True := trivial"},
            headers=_bearer(user_without_github["token"]),
        )
        assert resp.status_code == 400

    @mock.patch(
        "app.services.project_service.CompilerClient.verify_snippet",
        return_value={"valid": True, "errors": []},
    )
    def test_error_message_mentions_github(self, _mock_verify, client, user_without_github):
        data = client.post(
            "/api/v1/projects",
            json={"name": "Test", "goal": "theorem r : True := trivial"},
            headers=_bearer(user_without_github["token"]),
        ).get_json()
        assert "message" in data
        assert "github" in data["message"].lower()


# ─────────────────────────────────────────────────────────────────────────────
# TC-02-07  GET /projects/public — paginated list
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0207_ListPublicProjects:
    """TC-02-07 — GET /projects/public returns only public projects with pagination metadata."""

    def test_returns_http_200(self, client, seed_public_projects):
        resp = client.get("/api/v1/projects/public")
        assert resp.status_code == 200

    def test_returns_exactly_three_public_projects(self, client, seed_public_projects):
        data = client.get("/api/v1/projects/public").get_json()
        assert len(data["projects"]) == 3

    def test_total_matches_public_count(self, client, seed_public_projects):
        data = client.get("/api/v1/projects/public").get_json()
        assert data["total"] == 3

    def test_response_includes_pages_field(self, client, seed_public_projects):
        data = client.get("/api/v1/projects/public").get_json()
        assert "pages" in data
        assert data["pages"] >= 1

    def test_current_page_is_one_by_default(self, client, seed_public_projects):
        data = client.get("/api/v1/projects/public").get_json()
        assert data["current_page"] == 1

    def test_private_projects_are_excluded(self, client, seed_public_projects):
        data = client.get("/api/v1/projects/public").get_json()
        for p in data["projects"]:
            assert p["visibility"] == "public"


# ─────────────────────────────────────────────────────────────────────────────
# TC-02-08  GET /projects/public?q= — filter by name
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0208_FilterPublicProjectsByName:
    """TC-02-08 — GET /projects/public?q=gold returns only matching projects."""

    def test_returns_http_200(self, client, seed_public_projects):
        resp = client.get("/api/v1/projects/public?q=gold")
        assert resp.status_code == 200

    def test_returns_only_the_matching_project(self, client, seed_public_projects):
        data = client.get("/api/v1/projects/public?q=gold").get_json()
        assert len(data["projects"]) == 1
        assert data["projects"][0]["name"] == "Goldbach"

    def test_filter_is_case_insensitive(self, client, seed_public_projects):
        data = client.get("/api/v1/projects/public?q=GOLD").get_json()
        assert len(data["projects"]) == 1
        assert data["projects"][0]["name"] == "Goldbach"

    def test_no_match_returns_empty_list(self, client, seed_public_projects):
        data = client.get("/api/v1/projects/public?q=zzznomatch").get_json()
        assert data["projects"] == []
        assert data["total"] == 0


# ─────────────────────────────────────────────────────────────────────────────
# TC-02-09  GET /projects/public with JWT — is_following flag
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0209_IsFollowingFlag:
    """TC-02-09 — When the caller is authenticated, each project carries is_following."""

    @pytest.fixture
    def followed_project(self, app, seed_public_projects, user_with_github):
        """Follow the first public project (Fermat) as user_with_github."""
        from app.models.user_followed_project import UserFollowedProject

        project_id = uuid.UUID(seed_public_projects[0])
        user_id = uuid.UUID(user_with_github["id"])

        with app.app_context():
            follow = UserFollowedProject(user_id=user_id, project_id=project_id)
            _db.session.add(follow)
            _db.session.commit()

        return seed_public_projects[0]  # the followed project's id (str)

    def test_followed_project_has_is_following_true(
        self, client, followed_project, seed_public_projects, user_with_github
    ):
        data = client.get(
            "/api/v1/projects/public",
            headers=_bearer(user_with_github["token"]),
        ).get_json()
        projects_by_id = {p["id"]: p for p in data["projects"]}
        assert projects_by_id[followed_project]["is_following"] is True

    def test_not_followed_projects_have_is_following_false(
        self, client, followed_project, seed_public_projects, user_with_github
    ):
        data = client.get(
            "/api/v1/projects/public",
            headers=_bearer(user_with_github["token"]),
        ).get_json()
        projects_by_id = {p["id"]: p for p in data["projects"]}
        for pid in seed_public_projects[1:]:
            assert projects_by_id[pid]["is_following"] is False

    def test_unauthenticated_request_is_following_is_false(
        self, client, seed_public_projects
    ):
        data = client.get("/api/v1/projects/public").get_json()
        for p in data["projects"]:
            assert p["is_following"] is False
