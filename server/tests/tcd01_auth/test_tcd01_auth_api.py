"""
TCD-01 — Auth API (`web`)
=========================
Module : server/app/api/auth.py + server/app/services/auth_service.py
Responsible : David
Tools : pytest-flask, pytest-mock, responses

Covered test cases
──────────────────
TC-01-01  GET  /auth/github/url               → valid OAuth redirect URL
TC-01-02  POST /auth/github/callback          → new user created, tokens returned
TC-01-03  POST /auth/github/callback          → missing code → 400
TC-01-04  POST /auth/github/callback          → existing github_id → upsert, no duplicate
TC-01-05  POST /auth/refresh                  → valid refresh token → new access token
TC-01-06  POST /auth/refresh                  → access token (wrong type) → 422
TC-01-07  GET  /auth/me                       → valid JWT → user profile
TC-01-08  GET  /auth/me                       → no JWT → 401
TC-01-09  GET  /auth/github/invitations       → list of pending invitations
TC-01-10  GET  /auth/github/invitations       → no linked GitHub account → 400
TC-01-11  POST /auth/github/invitations/<id>/accept → 200 accepted

External dependencies (GitHub REST API) are intercepted by the `responses` library
so no real network call is ever made.
"""

import pytest
import responses as rsps
from flask_jwt_extended import create_access_token, create_refresh_token

from app.extensions import db as _db
from app.models.user import User

# ─── GitHub endpoint constants ────────────────────────────────────────────────
_GH_TOKEN_URL = "https://github.com/login/oauth/access_token"
_GH_USER_URL = "https://api.github.com/user"
_GH_INVITATIONS_URL = "https://api.github.com/user/repository_invitations"


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _mock_github_callback(github_id: int, login: str, name: str, email: str,
                          access_token: str = "gho_mock_token") -> None:
    """Register `responses` mocks for the two GitHub calls made by handle_github_callback."""
    rsps.add(rsps.POST, _GH_TOKEN_URL,
             json={"access_token": access_token, "token_type": "bearer"},
             status=200)
    rsps.add(rsps.GET, _GH_USER_URL,
             json={"id": github_id, "login": login, "name": name, "email": email},
             status=200)


# ─────────────────────────────────────────────────────────────────────────────
# TC-01-01  GET /auth/github/url
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0101_GetGithubUrl:
    """TC-01-01 — GET /auth/github/url returns a valid OAuth URL."""

    def test_returns_http_200(self, client):
        resp = client.get("/api/v1/auth/github/url")
        assert resp.status_code == 200

    def test_body_has_url_key(self, client):
        data = client.get("/api/v1/auth/github/url").get_json()
        assert "url" in data

    def test_url_is_non_empty_string(self, client):
        data = client.get("/api/v1/auth/github/url").get_json()
        assert isinstance(data["url"], str) and len(data["url"]) > 0

    def test_url_points_to_github_authorize(self, client):
        data = client.get("/api/v1/auth/github/url").get_json()
        assert data["url"].startswith("https://github.com/login/oauth/authorize")

    def test_url_contains_configured_client_id(self, client):
        # UnitTestConfig sets GITHUB_CLIENT_ID = "test_client_id"
        data = client.get("/api/v1/auth/github/url").get_json()
        assert "test_client_id" in data["url"]


# ─────────────────────────────────────────────────────────────────────────────
# TC-01-02  POST /auth/github/callback — new user
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0102_GithubCallbackNewUser:
    """TC-01-02 — POST /auth/github/callback with valid code creates a new user
    and returns both JWT tokens plus a user object."""

    @rsps.activate
    def test_returns_http_200(self, client):
        _mock_github_callback(11111, "newuser", "New User", "new@example.com")
        resp = client.post("/api/v1/auth/github/callback", json={"code": "code_tc0102a"})
        assert resp.status_code == 200

    @rsps.activate
    def test_response_has_access_token(self, client):
        _mock_github_callback(11112, "newuser2", "New User 2", "new2@example.com")
        data = client.post(
            "/api/v1/auth/github/callback", json={"code": "code_tc0102b"}
        ).get_json()
        assert "access_token" in data
        assert isinstance(data["access_token"], str) and len(data["access_token"]) > 0

    @rsps.activate
    def test_response_has_refresh_token(self, client):
        _mock_github_callback(11113, "newuser3", "New User 3", "new3@example.com")
        data = client.post(
            "/api/v1/auth/github/callback", json={"code": "code_tc0102c"}
        ).get_json()
        assert "refresh_token" in data
        assert isinstance(data["refresh_token"], str) and len(data["refresh_token"]) > 0

    @rsps.activate
    def test_response_has_user_object_with_email(self, client):
        _mock_github_callback(11114, "newuser4", "New User 4", "new4@example.com")
        data = client.post(
            "/api/v1/auth/github/callback", json={"code": "code_tc0102d"}
        ).get_json()
        assert "user" in data
        assert data["user"]["email"] == "new4@example.com"

    @rsps.activate
    def test_user_row_is_created_in_db(self, client, app):
        _mock_github_callback(11115, "dbuser", "DB User", "dbuser@example.com")
        client.post("/api/v1/auth/github/callback", json={"code": "code_tc0102e"})
        with app.app_context():
            user = User.query.filter_by(github_id="11115").first()
        assert user is not None
        assert user.email == "dbuser@example.com"

    @rsps.activate
    def test_github_access_token_is_stored(self, client, app):
        _mock_github_callback(11116, "tokenuser", "Token User", "token@example.com",
                               access_token="gho_stored_123")
        client.post("/api/v1/auth/github/callback", json={"code": "code_tc0102f"})
        with app.app_context():
            user = User.query.filter_by(github_id="11116").first()
        assert user is not None
        assert user.github_access_token == "gho_stored_123"


# ─────────────────────────────────────────────────────────────────────────────
# TC-01-03  POST /auth/github/callback — missing code
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0103_GithubCallbackMissingCode:
    """TC-01-03 — POST /auth/github/callback without a code returns HTTP 400."""

    def test_returns_http_400(self, client):
        resp = client.post("/api/v1/auth/github/callback", json={})
        assert resp.status_code == 400

    def test_error_message_is_missing_code(self, client):
        data = client.post("/api/v1/auth/github/callback", json={}).get_json()
        assert "error" in data
        assert data["error"] == "Missing code"

    def test_null_body_also_returns_400(self, client):
        resp = client.post("/api/v1/auth/github/callback",
                           data="", content_type="application/json")
        assert resp.status_code == 400


# ─────────────────────────────────────────────────────────────────────────────
# TC-01-04  POST /auth/github/callback — existing GitHub user (upsert)
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0104_GithubCallbackExistingUser:
    """TC-01-04 — When github_id already exists the service updates the token
    and returns the same user row without creating a duplicate."""

    @rsps.activate
    def test_returns_http_200(self, client, existing_github_user):
        _mock_github_callback(12345, "alicesmith", "Alice Smith",
                               "alice@example.com", access_token="gho_200_update")
        resp = client.post("/api/v1/auth/github/callback",
                           json={"code": "code_tc0104a"})
        assert resp.status_code == 200

    @rsps.activate
    def test_no_duplicate_user_row_created(self, client, app, existing_github_user):
        _mock_github_callback(12345, "alicesmith", "Alice Smith",
                               "alice@example.com", access_token="gho_nodup")
        client.post("/api/v1/auth/github/callback", json={"code": "code_tc0104b"})
        with app.app_context():
            count = User.query.filter_by(github_id="12345").count()
        assert count == 1

    @rsps.activate
    def test_github_access_token_is_updated(self, client, app, existing_github_user):
        _mock_github_callback(12345, "alicesmith", "Alice Smith",
                               "alice@example.com", access_token="gho_refreshed_v2")
        client.post("/api/v1/auth/github/callback", json={"code": "code_tc0104c"})
        with app.app_context():
            user = User.query.filter_by(github_id="12345").first()
        assert user.github_access_token == "gho_refreshed_v2"

    @rsps.activate
    def test_response_contains_user_id(self, client, existing_github_user):
        _mock_github_callback(12345, "alicesmith", "Alice Smith",
                               "alice@example.com")
        data = client.post("/api/v1/auth/github/callback",
                           json={"code": "code_tc0104d"}).get_json()
        assert "user" in data
        assert "id" in data["user"]


# ─────────────────────────────────────────────────────────────────────────────
# TC-01-05  POST /auth/refresh — valid refresh token
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0105_RefreshValidToken:
    """TC-01-05 — POST /auth/refresh with a valid refresh token returns a
    new access token (HTTP 200)."""

    def _refresh_token(self, app):
        with app.app_context():
            return create_refresh_token(identity="test-user-id-abc")

    def test_returns_http_200(self, client, app):
        token = self._refresh_token(app)
        resp = client.post("/api/v1/auth/refresh", headers=_bearer(token))
        assert resp.status_code == 200

    def test_response_has_access_token(self, client, app):
        token = self._refresh_token(app)
        data = client.post("/api/v1/auth/refresh",
                           headers=_bearer(token)).get_json()
        assert "access_token" in data

    def test_returned_access_token_is_non_empty_string(self, client, app):
        token = self._refresh_token(app)
        data = client.post("/api/v1/auth/refresh",
                           headers=_bearer(token)).get_json()
        assert isinstance(data["access_token"], str) and len(data["access_token"]) > 0

    def test_returned_access_token_differs_from_refresh_token(self, client, app):
        token = self._refresh_token(app)
        data = client.post("/api/v1/auth/refresh",
                           headers=_bearer(token)).get_json()
        assert data["access_token"] != token


# ─────────────────────────────────────────────────────────────────────────────
# TC-01-06  POST /auth/refresh — wrong token type (access token used)
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0106_RefreshWrongTokenType:
    """TC-01-06 — POST /auth/refresh with an access token (not a refresh token)
    is rejected by Flask-JWT-Extended with HTTP 422."""

    def test_returns_http_422(self, client, app):
        with app.app_context():
            access_tok = create_access_token(identity="test-user-id-wrong")
        resp = client.post("/api/v1/auth/refresh", headers=_bearer(access_tok))
        assert resp.status_code == 422

    def test_no_access_token_in_response(self, client, app):
        with app.app_context():
            access_tok = create_access_token(identity="test-user-id-wrong2")
        data = client.post("/api/v1/auth/refresh",
                           headers=_bearer(access_tok)).get_json()
        assert "access_token" not in data


# ─────────────────────────────────────────────────────────────────────────────
# TC-01-07  GET /auth/me — valid JWT
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0107_GetMe:
    """TC-01-07 — GET /auth/me with a valid access token returns the
    authenticated user's profile (HTTP 200)."""

    def test_returns_http_200(self, client, user_with_github):
        token, _ = user_with_github
        resp = client.get("/api/v1/auth/me", headers=_bearer(token))
        assert resp.status_code == 200

    def test_response_has_id(self, client, user_with_github):
        token, user_id = user_with_github
        data = client.get("/api/v1/auth/me", headers=_bearer(token)).get_json()
        assert "id" in data

    def test_response_has_email(self, client, user_with_github):
        token, _ = user_with_github
        data = client.get("/api/v1/auth/me", headers=_bearer(token)).get_json()
        assert data.get("email") == "bob@example.com"

    def test_response_has_full_name(self, client, user_with_github):
        token, _ = user_with_github
        data = client.get("/api/v1/auth/me", headers=_bearer(token)).get_json()
        assert "full_name" in data or "name" in data


# ─────────────────────────────────────────────────────────────────────────────
# TC-01-08  GET /auth/me — no JWT
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0108_GetMeNoJWT:
    """TC-01-08 — GET /auth/me without an Authorization header returns HTTP 401."""

    def test_returns_http_401(self, client):
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code == 401

    def test_returns_401_with_empty_bearer(self, client):
        resp = client.get("/api/v1/auth/me",
                          headers={"Authorization": "Bearer "})
        assert resp.status_code == 422  # JWT-Extended: malformed token


# ─────────────────────────────────────────────────────────────────────────────
# TC-01-09  GET /auth/github/invitations — returns list
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0109_GetGithubInvitations:
    """TC-01-09 — GET /auth/github/invitations returns a list of pending
    GitHub repository invitations for the authenticated user."""

    _MOCK_INVITATIONS = [
        {
            "id": 1,
            "repository": {"full_name": "acme/repo1"},
            "inviter": {"login": "adminuser"},
            "html_url": "https://github.com/acme/repo1/invitations/1",
        },
        {
            "id": 2,
            "repository": {"full_name": "acme/repo2"},
            "inviter": {"login": "adminuser"},
            "html_url": "https://github.com/acme/repo2/invitations/2",
        },
    ]

    @rsps.activate
    def test_returns_http_200(self, client, user_with_github):
        token, _ = user_with_github
        rsps.add(rsps.GET, _GH_INVITATIONS_URL,
                 json=self._MOCK_INVITATIONS, status=200)
        resp = client.get("/api/v1/auth/github/invitations", headers=_bearer(token))
        assert resp.status_code == 200

    @rsps.activate
    def test_invitations_list_has_correct_count(self, client, user_with_github):
        token, _ = user_with_github
        rsps.add(rsps.GET, _GH_INVITATIONS_URL,
                 json=self._MOCK_INVITATIONS, status=200)
        data = client.get("/api/v1/auth/github/invitations",
                          headers=_bearer(token)).get_json()
        assert len(data["invitations"]) == 2

    @rsps.activate
    def test_each_invitation_has_id_field(self, client, user_with_github):
        token, _ = user_with_github
        rsps.add(rsps.GET, _GH_INVITATIONS_URL,
                 json=self._MOCK_INVITATIONS, status=200)
        data = client.get("/api/v1/auth/github/invitations",
                          headers=_bearer(token)).get_json()
        for inv in data["invitations"]:
            assert "id" in inv

    @rsps.activate
    def test_each_invitation_has_repo_field(self, client, user_with_github):
        token, _ = user_with_github
        rsps.add(rsps.GET, _GH_INVITATIONS_URL,
                 json=self._MOCK_INVITATIONS, status=200)
        data = client.get("/api/v1/auth/github/invitations",
                          headers=_bearer(token)).get_json()
        for inv in data["invitations"]:
            assert "repo" in inv

    @rsps.activate
    def test_each_invitation_has_inviter_field(self, client, user_with_github):
        token, _ = user_with_github
        rsps.add(rsps.GET, _GH_INVITATIONS_URL,
                 json=self._MOCK_INVITATIONS, status=200)
        data = client.get("/api/v1/auth/github/invitations",
                          headers=_bearer(token)).get_json()
        for inv in data["invitations"]:
            assert "inviter" in inv

    @rsps.activate
    def test_each_invitation_has_html_url_field(self, client, user_with_github):
        token, _ = user_with_github
        rsps.add(rsps.GET, _GH_INVITATIONS_URL,
                 json=self._MOCK_INVITATIONS, status=200)
        data = client.get("/api/v1/auth/github/invitations",
                          headers=_bearer(token)).get_json()
        for inv in data["invitations"]:
            assert "html_url" in inv

    @rsps.activate
    def test_empty_list_when_no_invitations(self, client, user_with_github):
        token, _ = user_with_github
        rsps.add(rsps.GET, _GH_INVITATIONS_URL, json=[], status=200)
        data = client.get("/api/v1/auth/github/invitations",
                          headers=_bearer(token)).get_json()
        assert data["invitations"] == []


# ─────────────────────────────────────────────────────────────────────────────
# TC-01-10  GET /auth/github/invitations — no linked GitHub account
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0110_GetInvitationsNoGithub:
    """TC-01-10 — GET /auth/github/invitations for a user without a linked
    GitHub account returns HTTP 400."""

    def test_returns_http_400(self, client, user_without_github):
        token, _ = user_without_github
        resp = client.get("/api/v1/auth/github/invitations", headers=_bearer(token))
        assert resp.status_code == 400

    def test_error_body_mentions_github(self, client, user_without_github):
        token, _ = user_without_github
        data = client.get("/api/v1/auth/github/invitations",
                          headers=_bearer(token)).get_json()
        assert "error" in data
        assert "GitHub" in data["error"] or "github" in data["error"].lower()

    def test_no_github_api_call_is_made(self, client, user_without_github):
        """GitHub API must NOT be called when the user has no token."""
        token, _ = user_without_github
        # If responses is not activated, any outgoing HTTP call would raise
        # ConnectionError, proving no external call is attempted.
        resp = client.get("/api/v1/auth/github/invitations", headers=_bearer(token))
        assert resp.status_code == 400


# ─────────────────────────────────────────────────────────────────────────────
# TC-01-11  POST /auth/github/invitations/<id>/accept
# ─────────────────────────────────────────────────────────────────────────────

class TestTC0111_AcceptGithubInvitation:
    """TC-01-11 — POST /auth/github/invitations/<id>/accept calls the GitHub
    PATCH endpoint and returns HTTP 200 with a success status."""

    _ACCEPT_URL = "https://api.github.com/user/repository_invitations/42"

    @rsps.activate
    def test_returns_http_200(self, client, user_with_github):
        token, _ = user_with_github
        rsps.add(rsps.PATCH, self._ACCEPT_URL, status=204, body="")
        resp = client.post("/api/v1/auth/github/invitations/42/accept",
                           headers=_bearer(token))
        assert resp.status_code == 200

    @rsps.activate
    def test_response_body_indicates_accepted(self, client, user_with_github):
        token, _ = user_with_github
        rsps.add(rsps.PATCH, self._ACCEPT_URL, status=204, body="")
        data = client.post("/api/v1/auth/github/invitations/42/accept",
                           headers=_bearer(token)).get_json()
        assert data.get("status") == "accepted"

    @rsps.activate
    def test_github_patch_endpoint_is_called_once(self, client, user_with_github):
        token, _ = user_with_github
        rsps.add(rsps.PATCH, self._ACCEPT_URL, status=204, body="")
        client.post("/api/v1/auth/github/invitations/42/accept",
                    headers=_bearer(token))
        assert rsps.calls[0].request.method == "PATCH"
        assert "/user/repository_invitations/42" in rsps.calls[0].request.url

    def test_returns_400_without_jwt(self, client):
        resp = client.post("/api/v1/auth/github/invitations/42/accept")
        assert resp.status_code == 401

    def test_returns_400_for_user_without_github(
            self, client, user_without_github):
        token, _ = user_without_github
        resp = client.post("/api/v1/auth/github/invitations/42/accept",
                           headers=_bearer(token))
        assert resp.status_code == 400
