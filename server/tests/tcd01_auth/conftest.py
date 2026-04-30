"""
Fixtures for TCD-01 (Auth API) unit tests.

Uses SQLite in-memory so no PostgreSQL container is required to run these tests.
SocketIO.init_app is patched out to prevent Redis message-queue connection attempts.

Test isolation strategy
───────────────────────
• `app`    — module-scoped: the Flask app and SQLite schema are created once.
• `client` — function-scoped: a fresh test client per test.
• `clean_users` — autouse, function-scoped: wipes the users table before and
  after every test so rows created in one test never bleed into the next.
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
# Minimal testing configuration (no external services)
# ─────────────────────────────────────────────────────────────────────────────

class UnitTestConfig:
    """Test configuration backed by a dedicated PostgreSQL test database."""

    TESTING = True
    DEBUG = True
    SECRET_KEY = "unit-test-secret"
    SQLALCHEMY_DATABASE_URI = "postgresql://coproof:coproofpass@localhost:5432/coproof_test_db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # JWT — disable expiry so token helpers work without freezing time
    JWT_SECRET_KEY = "unit-test-jwt-secret-key-32-bytes!"
    JWT_ACCESS_TOKEN_EXPIRES = False
    JWT_REFRESH_TOKEN_EXPIRES = False

    # Caching — null backend, no Redis needed
    CACHE_TYPE = "NullCache"

    # Redis URL is read by create_app but SocketIO.init_app is patched out
    REDIS_URL = "redis://localhost:6379/0"

    # Celery — in-memory broker so tasks never leave the process
    CELERY_BROKER_URL = "memory://"
    CELERY_RESULT_BACKEND = "cache+memory://"
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_LEAN_QUEUE = "lean_queue"
    CELERY_COMPUTATION_QUEUE = "computation_queue"
    CELERY_CLUSTER_COMPUTATION_QUEUE = "cluster_computation_queue"
    CELERY_GIT_ENGINE_QUEUE = "git_engine_queue"
    CELERY_NL2FL_QUEUE = "nl2fl_queue"
    CELERY_AGENTS_QUEUE = "agents_queue"

    # Misc
    REPO_STORAGE_PATH = "/tmp/coproof-test"
    GITHUB_CLIENT_ID = "test_client_id"
    GITHUB_CLIENT_SECRET = "test_client_secret"
    GITHUB_OAUTH_SCOPES = "repo,read:user,user:email"
    WTF_CSRF_ENABLED = False
    # Use NullPool: every connection is opened fresh and closed immediately,
    # so there are no stale pooled connections between tests.
    SQLALCHEMY_ENGINE_OPTIONS = {"poolclass": NullPool}


# ─────────────────────────────────────────────────────────────────────────────
# Core fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def app():
    """
    Module-scoped Flask application backed by a dedicated test database.

    NullPool is configured in UnitTestConfig so every DB operation uses a
    fresh connection — no stale pooled connections between tests.
    """
    from app import extensions
    from sqlalchemy import text as sa_text

    # Patch os.environ so auth_service.py reads test values instead of real ones
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
def clean_users(app):
    """
    Wipe all test data BEFORE each test only.

    Post-test cleanup is intentionally omitted: pg_terminate_backend would kill
    the connection that pytest-flask's context teardown (ctx.pop → session.remove
    → rollback) still holds, causing spurious OperationalError in teardown.

    Each test starts with a clean DB because the pre-test truncation of the
    *next* test cleans up after the current one. The schema is dropped entirely
    in the module-level app fixture teardown.
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
# User / token helper fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def user_with_github(app):
    """
    Persisted user with a linked GitHub account.
    Returns ``(jwt_access_token: str, user_id: str)``.
    """
    from app.models.user import User

    uid = uuid.uuid4()
    with app.app_context():
        user = User(
            id=uid,
            full_name="Bob Tester",
            email="bob@example.com",
            password_hash="oauth_provider",
            github_id="67890",
            github_login="bobtester",
            github_access_token="gho_bob_valid_token",
            is_verified=True,
        )
        _db.session.add(user)
        _db.session.commit()
        token = create_access_token(identity=str(uid))
    return token, str(uid)


@pytest.fixture
def user_without_github(app):
    """
    Persisted user with NO linked GitHub account (github_access_token=None).
    Returns ``(jwt_access_token: str, user_id: str)``.
    """
    from app.models.user import User

    uid = uuid.uuid4()
    with app.app_context():
        user = User(
            id=uid,
            full_name="Charlie Nohub",
            email="charlie@example.com",
            password_hash="oauth_provider",
            github_id=None,
            github_access_token=None,
            is_verified=True,
        )
        _db.session.add(user)
        _db.session.commit()
        token = create_access_token(identity=str(uid))
    return token, str(uid)


@pytest.fixture
def existing_github_user(app):
    """
    Persisted user with ``github_id='12345'``.
    Used by TC-01-04 to verify the upsert path does not create duplicates.
    Returns the ``user_id`` as a string.
    """
    from app.models.user import User

    uid = uuid.uuid4()
    with app.app_context():
        user = User(
            id=uid,
            full_name="Alice Smith",
            email="alice@example.com",
            password_hash="oauth_provider",
            github_id="12345",
            github_login="alicesmith",
            github_access_token="old_gho_token",
            is_verified=True,
        )
        _db.session.add(user)
        _db.session.commit()
    return str(uid)
