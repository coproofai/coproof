"""
Fixtures for TCD-05 (Agents API) unit tests.

Infrastructure follows TCD-01/02/03/04 conventions:
  - coproof_test_db + NullPool + pg_terminate_backend + os.environ patch
  - TRUNCATE users CASCADE before each test for isolation

Additional fixtures
  - auth_user     : plain User row + JWT (for TC-05-04: authenticated, no saved key)
  - user_with_key : User + UserApiKey for 'openai/gpt-4o' (for TC-05-05)
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
# Minimal testing configuration (identical to TCD-01/02/03/04)
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
        from sqlalchemy import text as sa_text
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
    Terminate zombie connections and truncate all test data BEFORE each test.
    Post-test cleanup is omitted to avoid killing pytest-flask's teardown connection.
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
def auth_user(app):
    """
    A basic authenticated user (no saved API key).
    Returns ``{id, token}``.
    """
    from app.models.user import User

    with app.app_context():
        u = User(
            id=uuid.uuid4(),
            full_name="Agents Tester",
            email="agents@example.com",
            password_hash="$2b$12$placeholder",
        )
        _db.session.add(u)
        _db.session.commit()
        user_id = str(u.id)

    with app.app_context():
        token = create_access_token(identity=user_id)

    return {"id": user_id, "token": token}


@pytest.fixture
def user_with_key(app):
    """
    An authenticated user with a saved UserApiKey for 'openai/gpt-4o'.
    Returns ``{id, token, raw_key}``.
    """
    from app.models.user import User
    from app.models.user_api_key import UserApiKey

    raw_key = "sk-agents-saved-key"

    with app.app_context():
        u = User(
            id=uuid.uuid4(),
            full_name="Key Holder Agents",
            email="keyholder_agents@example.com",
            password_hash="$2b$12$placeholder",
        )
        _db.session.add(u)
        _db.session.flush()

        record = UserApiKey.create(
            user_id=u.id,
            model_id="openai/gpt-4o",
            raw_key=raw_key,
        )
        _db.session.add(record)
        _db.session.commit()
        user_id = str(u.id)

    with app.app_context():
        token = create_access_token(identity=user_id)

    return {"id": user_id, "token": token, "raw_key": raw_key}
