from unittest.mock import patch
from app.services.project_service import ProjectService
from app.models.user import User

@patch('app.services.project_service.RepoPool.ensure_bare_repo')
def test_create_project_with_git(mock_git, init_db):
    # Setup User
    leader = User(full_name="L", email="l@p.com", password_hash="x")
    init_db.session.add(leader)
    init_db.session.commit()
    
    data = {
        "name": "Math Proj",
        "visibility": "public",
        "remote_repo_url": "https://github.com/math/proj.git"
    }
    
    proj = ProjectService.create_project(data, leader.id)
    
    assert proj.id is not None
    assert proj.visibility == "public"
    
    # Check if Git Engine was triggered with the Project UUID
    mock_git.assert_called_once_with(str(proj.id), "https://github.com/math/proj.git")