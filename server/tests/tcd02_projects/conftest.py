"""
Fixtures for TCD-02 (Projects API) unit tests.

Infrastructure is identical to TCD-01:
  - Dedicated PostgreSQL test database  (coproof_test_db)
  - NullPool to prevent stale connections between tests
  - pg_terminate_backend + TRUNCATE CASCADE before each test
  - GITHUB_CLIENT_ID / SECRET patched via mock.patch.dict(os.environ)

Additional fixtures
  - user_with_github    : User row with github_access_token + JWT
  - user_without_github : User row with no github_access_token + JWT
  - seed_public_projects: 3 public + 2 private projects owned by user_with_github

Cleanup note
  TRUNCATE TABLE users CASCADE cascades through the FK chain:
    users → new_projects → new_nodes
    users → user_followed_projects
    new_projects → user_followed_projects
  so a single TRUNCATE is sufficient for full isolation.
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
# Minimal testing configuration
# ─────────────────────────────────────────────────────────────────────────────

class UnitTestConfig:
    """Test configuration backed by a dedicated PostgreSQL test database."""

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
    # NullPool: every DB call opens/closes its own connection — no stale
    # pooled connections survive between tests on Windows/Docker Desktop.
    SQLALCHEMY_ENGINE_OPTIONS = {"poolclass": NullPool}


# ─────────────────────────────────────────────────────────────────────────────
# Core fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def app():
    """
    Module-scoped Flask application backed by coproof_test_db.

    The app context is opened only briefly for create_all / teardown DROP so
    that per-request contexts pushed by pytest-flask work normally during tests.
    """
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
    """Fresh Flask test client for each test."""
    return app.test_client()


# ─────────────────────────────────────────────────────────────────────────────
# Test-isolation fixture
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def clean_tables(app):
    """
    Truncate all test data BEFORE each test only.

    Post-test cleanup is intentionally omitted — pg_terminate_backend would
    kill the connection that pytest-flask's teardown still holds, causing
    spurious OperationalError.  The next test's pre-cleanup handles leftovers.
    """
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
# User fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def user_with_github(app):
    """
    User with a linked GitHub account (required for project creation).
    Returns a dict with ``id``, ``token`` (JWT), and ``github_login``.
    """
    from app.models.user import User

    with app.app_context():
        u = User(
            id=uuid.uuid4(),
            full_name="Test User",
            email="testuser@example.com",
            password_hash="$2b$12$placeholder",
            github_id="gh-tcd02-001",
            github_login="testuser",
            github_access_token="gho_testtoken",
        )
        _db.session.add(u)
        _db.session.commit()
        user_id = str(u.id)

    with app.app_context():
        token = create_access_token(identity=user_id)

    return {"id": user_id, "token": token, "github_login": "testuser"}


@pytest.fixture
def user_without_github(app):
    """
    User without a linked GitHub account.
    Returns a dict with ``id`` and ``token`` (JWT).
    """
    from app.models.user import User

    with app.app_context():
        u = User(
            id=uuid.uuid4(),
            full_name="No GitHub",
            email="nogithub@example.com",
            password_hash="$2b$12$placeholder",
        )
        _db.session.add(u)
        _db.session.commit()
        user_id = str(u.id)

    with app.app_context():
        token = create_access_token(identity=user_id)

    return {"id": user_id, "token": token}


# ─────────────────────────────────────────────────────────────────────────────
# Project-seeding fixture
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def seed_public_projects(app, user_with_github):
    """
    Insert 3 public + 2 private projects owned by user_with_github.

    Returns a list of the 3 public project IDs (strings), in insertion order:
    ["<Fermat-id>", "<Goldbach-id>", "<Collatz-id>"]
    """
    from app.models.project import Project
    from app.models.node import Node

    owner_id = uuid.UUID(user_with_github["id"])

    with app.app_context():
        public_ids = []

        for name in ("Fermat", "Goldbach", "Collatz"):
            p = Project(
                name=name,
                goal=f"theorem {name}_root : True := trivial",
                visibility="public",
                url=f"https://github.com/testuser/coproof-{name.lower()}",
                remote_repo_url=(
                    f"https://github.com/testuser/coproof-{name.lower()}.git"
                ),
                default_branch="main",
                author_id=owner_id,
            )
            _db.session.add(p)
            _db.session.flush()

            _db.session.add(Node(
                name="root",
                url=(
                    f"https://github.com/testuser/coproof-{name.lower()}"
                    f"/blob/main/root/main.lean"
                ),
                project_id=p.id,
                state="sorry",
                node_kind="proof",
            ))
            public_ids.append(str(p.id))

        for i in range(2):
            _db.session.add(Project(
                name=f"Private-{i}",
                goal="theorem private_root : True := trivial",
                visibility="private",
                url=f"https://github.com/testuser/private-{i}",
                remote_repo_url=f"https://github.com/testuser/private-{i}.git",
                default_branch="main",
                author_id=owner_id,
            ))

        _db.session.commit()
        return public_ids
