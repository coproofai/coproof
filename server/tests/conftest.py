import pytest
from config import get_config_class
from app import create_app
from app.extensions import db as _db


@pytest.fixture(scope="session")
def app():
    """
    Application fixture — uses TestingConfig.
    Creates all tables once per session, drops them after.
    The db service is started automatically by docker compose as a
    dependency of the web service.
    """
    application = create_app(get_config_class("testing"))
    with application.app_context():
        _db.create_all()
        yield application
        _db.drop_all()


@pytest.fixture
def client(app):
    """Flask test client bound to the session-scoped app."""
    return app.test_client()
