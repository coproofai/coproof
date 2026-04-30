"""
Fixtures for TCD-03 (Nodes API — PR context logic) unit tests.

Infrastructure follows TCD-01/02 conventions:
  - coproof_test_db + NullPool + pg_terminate_backend + os.environ patch

TC-03-01 / TC-03-02 / TC-03-03 exercise _prepare_pr_context directly,
so they need no HTTP client — only the `app` fixture (for import health)
and `responses` mocks for GitHub HTTP calls.

TC-03-04 exercises the /solve endpoint over HTTP, so it needs the full
DB fixture stack: user (no GitHub token) + project + proof node.
"""

import os
import uuid
import unittest.mock as mock

import pytest
from flask_jwt_extended import create_access_token
from sqlalchemy.pool import NullPool

from app import create_app
from app.extensions import db as _db


# ─────────────────────────────────────────────────────────────────────────────
# Minimal testing configuration (identical to TCD-01/02)
# ─────────────────────────────────────────────────────────────────────────────

class UnitTestConfig:
    TESTING = True
    DEBUG = True
    SECRET_KEY = "unit-test-secret"
    SQLALCHEMY_DATABASE_URI = (
        "postgresql://coproof:coproofpass@localhost:5432/coproof_test_db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = "unit-test-jwt-secret-key-32-bytes!"
    JWT_ACCESS_TOKEN_EXPIRES = False
    JWT_REFRESH_TOKEN_EXPIRES = False
    CACHE_TYPE = "NullCache"
    REDIS_URL = "redis://localhost:6379/0"
    CELERY_BROKER_URL = "memory://"
    CELERY_RESULT_BACKEND = "cache+memory://"
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_LEAN_QUEUE = "lean_queue"
    CELERY_COMPUTATION_QUEUE = "computation_queue"
    CELERY_CLUSTER_COMPUTATION_QUEUE = "cluster_computation_queue"
    CELERY_GIT_ENGINE_QUEUE = "git_engine_queue"
    CELERY_NL2FL_QUEUE = "nl2fl_queue"
    CELERY_AGENTS_QUEUE = "agents_queue"
    REPO_STORAGE_PATH = "/tmp/coproof-test"
    GITHUB_CLIENT_ID = "test_client_id"
    GITHUB_CLIENT_SECRET = "test_client_secret"
    GITHUB_OAUTH_SCOPES = "repo,read:user,user:email"
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_ENGINE_OPTIONS = {"poolclass": NullPool}


# ─────────────────────────────────────────────────────────────────────────────
# Core fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def app():
    from app import extensions
    from sqlalchemy import text as sa_text

    env_patch = mock.patch.dict(os.environ, {
        "GITHUB_CLIENT_ID": "test_client_id",
        "GITHUB_CLIENT_SECRET": "test_client_secret",
    })
    env_patch.start()

    patcher = mock.patch.object(extensions.socketio, "init_app")
    patcher.start()

    application = create_app(UnitTestConfig)

    with application.app_context():
        _db.create_all()

    yield application

    with application.app_context():
        with _db.engine.begin() as conn:
            conn.execute(sa_text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))

    patcher.stop()
    env_patch.stop()


@pytest.fixture
def client(app):
    return app.test_client()


# ─────────────────────────────────────────────────────────────────────────────
# Test-isolation fixture
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def clean_tables(app):
    from sqlalchemy import text as sa_text

    with app.app_context():
        with _db.engine.connect().execution_options(
            isolation_level="AUTOCOMMIT"
        ) as conn:
            conn.execute(sa_text(
                "SELECT pg_terminate_backend(pid) "
                "FROM pg_stat_activity "
                "WHERE datname = current_database() "
                "  AND pid <> pg_backend_pid()"
            ))
            conn.execute(sa_text("TRUNCATE TABLE users CASCADE"))

    yield


# ─────────────────────────────────────────────────────────────────────────────
# DB fixtures used by TC-03-04 (endpoint test)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def user_no_github(app):
    """User with no linked GitHub account (github_access_token = None)."""
    from app.models.user import User

    with app.app_context():
        u = User(
            id=uuid.uuid4(),
            full_name="No GitHub",
            email="nogithub@tcd03.com",
            password_hash="$2b$12$placeholder",
        )
        _db.session.add(u)
        _db.session.commit()
        user_id = str(u.id)

    with app.app_context():
        token = create_access_token(identity=user_id)

    return {"id": user_id, "token": token}


@pytest.fixture
def project_and_node(app, user_no_github):
    """
    A public project + root proof node owned by user_no_github.
    Used by TC-03-04 to exercise the /solve endpoint's GitHub-token guard.
    """
    from app.models.project import Project
    from app.models.node import Node

    owner_id = uuid.UUID(user_no_github["id"])

    with app.app_context():
        p = Project(
            name="TestProject",
            goal="theorem test_root : True := trivial",
            visibility="public",
            url="https://github.com/testuser/coproof-test",
            remote_repo_url="https://github.com/testuser/coproof-test.git",
            default_branch="main",
            author_id=owner_id,
        )
        _db.session.add(p)
        _db.session.flush()

        n = Node(
            name="root",
            url=(
                "https://github.com/testuser/coproof-test"
                "/blob/main/root/main.lean"
            ),
            project_id=p.id,
            state="sorry",
            node_kind="proof",
        )
        _db.session.add(n)
        _db.session.commit()

        return {"project_id": str(p.id), "node_id": str(n.id)}
