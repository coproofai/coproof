import pytest
from app.schemas import ProjectSchema, UserSchema, AgentRequestSchema, AgentResponseSchema
from app.models.user import User
from app.models.project import Project

def test_user_schema_security():
    """Ensure UserSchema excludes password_hash."""
    user = User(full_name="Test", email="t@t.com", password_hash="secret")
    schema = UserSchema()
    result = schema.dump(user)
    
    assert "email" in result
    assert "password_hash" not in result

def test_project_schema_nested(init_db):
    """
    Test that ProjectSchema correctly serializes the nested Leader User.
    This verifies that fields.Nested("UserSchema") resolves correctly across files.
    """
    # Create DB objects
    leader = User(full_name="Leader", email="lead@t.com", password_hash="x")
    init_db.session.add(leader)
    init_db.session.commit()
    
    project = Project(
        name="Nested Proj", 
        visibility="public", 
        leader_id=leader.id,
        remote_repo_url="https://github.com/test.git"
    )
    init_db.session.add(project)
    init_db.session.commit()
    
    # Serialize
    schema = ProjectSchema()
    result = schema.dump(project)
    
    # Assertions
    assert result['name'] == "Nested Proj"
    assert result['remote_repo_url'] == "https://github.com/test.git"
    
    # Check Nested Leader
    assert 'leader' in result
    assert result['leader']['email'] == "lead@t.com"
    # Ensure ID is present in nested object
    assert 'id' in result['leader']

def test_agent_request_validation():
    """Test validation logic in AgentRequestSchema."""
    schema = AgentRequestSchema()
    
    # Valid Case
    valid_data = {"strategy": "contradiction", "hint": "Use Lemma 2"}
    errors = schema.validate(valid_data)
    assert not errors
    
    # Invalid Case (Wrong Strategy)
    invalid_data = {"strategy": "magic_wand"}
    errors = schema.validate(invalid_data)
    assert "strategy" in errors
    assert "Must be one of" in str(errors["strategy"])