import pytest
from config import get_config_class
from app import create_app
from app.extensions import db as _db


@pytest.fixture(scope="session")
def app():
    """
    Application fixture — uses TestingConfig (coproof_test_db).
    Creates all tables once per session, drops them after.
    """
    application = create_app(get_config_class("testing"))
    with application.app_context():
        _db.create_all()
        yield application
        _db.session.rollback()
        _db.session.execute(_db.text("DROP SCHEMA public CASCADE; CREATE SCHEMA public;"))
        _db.session.commit()


@pytest.fixture
def client(app):
    """Flask test client bound to the session-scoped app."""
    return app.test_client()
