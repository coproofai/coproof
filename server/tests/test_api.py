"""
Integration tests for the CoProof API.

These tests exercise the live Flask application with a real PostgreSQL database
(started by docker compose as a dependency of the web service).  They focus on
HTTP-level contracts that can be verified without GitHub credentials.
"""

import json
import pytest


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------

class TestGithubAuthUrl:
    def test_returns_200(self, client):
        response = client.get("/api/v1/auth/github/url")
        assert response.status_code == 200

    def test_response_contains_url_field(self, client):
        data = client.get("/api/v1/auth/github/url").get_json()
        assert "url" in data

    def test_url_points_to_github(self, client):
        data = client.get("/api/v1/auth/github/url").get_json()
        assert "github.com" in data["url"]


class TestGithubCallback:
    def test_missing_code_returns_400(self, client):
        response = client.post(
            "/api/v1/auth/github/callback",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_missing_body_returns_4xx(self, client):
        # No Content-Type header — Werkzeug returns 415 (Unsupported Media Type),
        # which is a valid rejection. Both 400 and 415 are acceptable here.
        response = client.post("/api/v1/auth/github/callback")
        assert response.status_code in (400, 415)


class TestTokenRefresh:
    def test_refresh_without_token_returns_401(self, client):
        response = client.post("/api/v1/auth/refresh")
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# Global error handlers
# ---------------------------------------------------------------------------

class TestErrorHandlers:
    def test_unknown_route_returns_404(self, client):
        response = client.get("/api/v1/this-route-does-not-exist")
        assert response.status_code == 404

    def test_404_response_has_error_code_field(self, client):
        data = client.get("/api/v1/this-route-does-not-exist").get_json()
        assert data["error_code"] == 404


# ---------------------------------------------------------------------------
# Unit tests — no HTTP needed
# ---------------------------------------------------------------------------

class TestCoProofError:
    def test_to_dict_includes_message(self):
        from app.exceptions import CoProofError
        err = CoProofError("something broke", code=422)
        assert err.to_dict()["message"] == "something broke"

    def test_to_dict_includes_error_code(self):
        from app.exceptions import CoProofError
        err = CoProofError("bad input", code=400)
        assert err.to_dict()["error_code"] == 400

    def test_to_dict_merges_payload(self):
        from app.exceptions import CoProofError
        err = CoProofError("invalid", code=422, payload={"field": "email"})
        result = err.to_dict()
        assert result["field"] == "email"
        assert result["message"] == "invalid"

    def test_git_resource_error_has_404_code(self):
        from app.exceptions import GitResourceError
        err = GitResourceError()
        assert err.code == 404

    def test_git_lock_error_has_409_code(self):
        from app.exceptions import GitLockError
        err = GitLockError()
        assert err.code == 409
