import pytest
from app.services.auth_service import AuthService
from app.exceptions import CoProofError
from app.models.user import User

def test_register_and_login_flow(init_db):
    # 1. Register
    data = {
        "full_name": "Test User",
        "email": "test@auth.com",
        "password": "strongpassword"
    }
    user = AuthService.register_user(data)
    assert user.id is not None
    assert user.email == "test@auth.com"
    
    # 2. Login Success
    result = AuthService.login_user("test@auth.com", "strongpassword")
    assert "access_token" in result
    
    # 3. Login Fail
    with pytest.raises(CoProofError) as excinfo:
        AuthService.login_user("test@auth.com", "wrongpass")
    assert excinfo.value.code == 401

def test_duplicate_registration(init_db):
    data = {"full_name": "User", "email": "dup@test.com", "password": "123"}
    AuthService.register_user(data)
    
    with pytest.raises(CoProofError) as excinfo:
        AuthService.register_user(data)
    assert excinfo.value.code == 400