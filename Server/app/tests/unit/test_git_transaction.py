import os
import pytest
from unittest.mock import patch, MagicMock
from app.services.git_engine.transaction import git_transaction

@patch('app.services.git_engine.transaction.RepoPool.ensure_bare_repo')
@patch('app.services.git_engine.transaction.git.Repo')
@patch('app.services.git_engine.transaction.acquire_project_lock')
def test_transaction_flow(mock_lock, mock_repo, mock_ensure_bare, tmp_path):
    """
    Test the full transaction flow:
    Lock -> Ensure Bare -> Worktree Add -> Yield -> Commit -> Push -> Cleanup
    """
    # Setup Mocks
    mock_lock.return_value.__enter__.return_value = None
    mock_ensure_bare.return_value = "/tmp/bare/repo.git"
    
    mock_bare_instance = MagicMock()
    mock_wt_instance = MagicMock()
    
    # git.Repo() returns bare instance first, then worktree instance
    mock_repo.side_effect = [mock_bare_instance, mock_wt_instance]
    
    # Simulate Dirty State
    mock_wt_instance.is_dirty.return_value = True
    
    # Run Transaction
    with git_transaction("proj-1", "http://url", "User", "user@mail.com"):
        pass # Simulate file writing here
        
    # Assertions
    
    # 1. Worktree created
    mock_bare_instance.git.worktree.assert_called()
    
    # 2. Changes added and committed
    mock_wt_instance.git.add.assert_called_with(A=True)
    mock_wt_instance.index.commit.assert_called()
    
    # 3. Pushed
    mock_wt_instance.remotes.origin.push.assert_called()
    
    # 4. Pruned (Cleanup)
    mock_bare_instance.git.worktree.assert_called_with('prune')