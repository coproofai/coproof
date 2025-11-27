import os
import shutil
import pytest
from unittest.mock import patch, MagicMock
from app.services.git_engine.repo_pool import RepoPool

@pytest.fixture
def clean_storage():
    """Cleanup storage before/after tests."""
    storage = "/tmp/coproof-test-storage"
    if os.path.exists(storage):
        shutil.rmtree(storage)
    
    # Patch the config to use test storage
    with patch('config.Config.REPO_STORAGE_PATH', storage):
        yield storage
        
    if os.path.exists(storage):
        shutil.rmtree(storage)

def test_ensure_bare_repo_clone(clean_storage):
    """Test that it tries to clone if repo doesn't exist."""
    project_id = "proj-new"
    remote_url = "https://github.com/test/repo.git"
    
    with patch('git.Repo.clone_from') as mock_clone:
        RepoPool.ensure_bare_repo(project_id, remote_url)
        
        expected_path = os.path.join(clean_storage, 'repos', f"{project_id}.git")
        mock_clone.assert_called_once_with(remote_url, expected_path, bare=True)

def test_ensure_bare_repo_fetch(clean_storage):
    """Test that it fetches if repo exists."""
    project_id = "proj-exists"
    remote_url = "https://github.com/test/repo.git"
    
    # Create a fake dir to simulate existence
    repo_path = os.path.join(clean_storage, 'repos', f"{project_id}.git")
    os.makedirs(repo_path)
    
    with patch('git.Repo') as mock_repo_cls:
        mock_repo_instance = MagicMock()
        mock_repo_cls.return_value = mock_repo_instance
        
        RepoPool.ensure_bare_repo(project_id, remote_url)
        
        mock_repo_instance.remotes.origin.fetch.assert_called_once()