import pytest
from app import create_app
from app.extensions import db
from config import TestingConfig

@pytest.fixture(scope='module')
def app():
    """
    Creates a Flask app instance for testing.
    Scope: Module (created once per test file to save time).
    """
    app = create_app(TestingConfig)
    
    # Push an application context for the tests
    with app.app_context():
        yield app

@pytest.fixture(scope='module')
def client(app):
    """
    Creates a test client to make HTTP requests.
    """
    return app.test_client()

@pytest.fixture(scope='function')
def init_db(app):
    """
    Setup and teardown the database for each test function.
    Ensures tests are isolated.
    """
    db.create_all()
    yield db
    db.session.remove()
    db.drop_all()

@pytest.fixture(scope='function')
def mock_redis(mocker):
    """
    Mocks Redis for tests that don't need a real Redis connection.
    Uses 'pytest-mock' (needs to be installed via requirements).
    """
    mock = mocker.patch('app.extensions.socketio')
    return mock