import pytest
from app import create_app
from config import TestingConfig
from app.exceptions import GitLockError

def test_config_loading(app):
    """Test if the app loads the correct configuration."""
    assert app.config['TESTING'] is True
    assert app.config['SQLALCHEMY_DATABASE_URI'] == TestingConfig.SQLALCHEMY_DATABASE_URI

def test_health_check(client):
    """Test the health check endpoint."""
    response = client.get('/health')
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'healthy'

def test_custom_exception():
    """
    Test that custom exceptions return JSON.
    Uses a fresh app instance to avoid 'setup method' errors.
    """
    # 1. Create a fresh app just for this test
    app = create_app(TestingConfig)
    
    # 2. Register the route BEFORE any request is handled
    @app.route('/raise-error')
    def raise_error():
        raise GitLockError("Locked resource")
        
    # 3. Create a client for this specific app
    client = app.test_client()
    
    # 4. Perform the request
    response = client.get('/raise-error')
    assert response.status_code == 409
    data = response.get_json()
    assert data['message'] == "Locked resource"
    assert data['error_code'] == 409