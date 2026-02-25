import logging
import os
from app.models.async_job import AsyncJob
from app.services.auth_service import AuthService
from app.services.graph_engine.indexer import GraphIndexer
from app.extensions import celery, db
from app.models.project import Project
from app.models.user import User
from app.services.git_engine import RepoPool
from app.services.integrations import CompilerClient
from app.exceptions import GitOperationError
from app.services.git_engine import git_transaction
from app.services.git_engine import repo_pool, transaction, locking


logger = logging.getLogger(__name__)

@celery.task(bind=True, max_retries=3)
def async_clone_repo(self, project_id, remote_url):
    """
    Background task to warm up the Git Cache (/tmp/repos).
    Triggered when a project is created or accessed.
    """
    try:
        logger.info(f"Starting async clone for project {project_id}")
        RepoPool.ensure_bare_repo(project_id, remote_url)
        logger.info(f"Async clone finished for {project_id}")
    except Exception as e:
        logger.error(f"Async clone failed: {e}")
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=2 ** self.request.retries)

@celery.task(bind=True)
def async_push_changes(self, project_id):
    """
    Background task to push changes if the synchronous push failed
    or if we implement a 'lazy push' strategy later.
    """
    # Implementation depends on how we handle the 'dirty' state.
    # For the 'Stateless Transaction' model, push happens inline.
    # This is reserved for retry mechanisms or batching.
    pass


@celery.task(bind=True, max_retries=3)
def async_save_node(self, project_id, user_id, file_path, content, branch='main'):
    """
    Background Microservice Task:
    1. Locks Project
    2. Pulls/Resets Git State
    3. Writes File -> Commit -> Push
    4. Updates Postgres Index
    """
    logger.info(f"Starting async save for {file_path} on branch {branch}")
    
    # 1. Fetch Metadata (Must happen inside task context)
    project = Project.query.get(project_id)
    user = User.query.get(user_id)

    
    if not project or not user:
        logger.error("Project or User not found in async task")
        return {"status": "failed", "error": "Metadata missing"}

    if not project.remote_repo_url:
        return {"status": "failed", "error": "No remote URL configured"}

    # git_token = AuthService.refresh_github_token_if_needed(user)
    git_token = user.github_access_token
    if git_token:
        logger.info(f"User {user.id} has GitHub token (Length: {len(git_token)})")
    else:
        logger.error(f"User {user.id} HAS NO GITHUB TOKEN. Git operations will likely fail.")


    try:
        # 1. Acquire Lock (Ensures atomicity for the whole block)
        with locking.acquire_project_lock(project_id):
            
            # 2. Ensure Repo Exists and is Updated (OUTSIDE transaction)
            # Step 2a: Ensure it's cloned
            bare_repo_path = repo_pool.RepoPool.ensure_repo_exists(
                project_id, project.remote_repo_url, auth_token=git_token
            )
        
        with locking.acquire_branch_lock(project_id, branch):

            try: 
            # Step 2b: Fetch latest updates
                repo_pool.RepoPool.update_repo(
                    project_id, project.remote_repo_url, auth_token=git_token
                )
            except Exception as e:
                logger.error(f"Fetch failed inside branch lock: {e}")
                raise e
            
            # 3. Start the Transaction (NO fetching happens inside)
            with transaction.git_transaction(
                bare_repo_path,
                author_name=user.full_name,
                author_email=user.email,
                branch=branch
            ) as worktree_root:
                
                # 4. Write File
                full_path = os.path.join(worktree_root, file_path)
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                with open(full_path, 'w') as f:
                    f.write(content)
            
        # 5. Index Update (After successful transaction)
        GraphIndexer.index_file_content(str(project.id), file_path, "latest", content)
        
        logger.info(f"Async save successful for {file_path}")
        
        return {"status": "success", "file": file_path}

    except Exception as e:
        logger.error(f"Async save failed: {e}")
        raise self.retry(exc=e, countdown=5)

@celery.task(bind=True)
def async_compile_project(self, remote_url, commit_hash):
    """
    Triggers the external Compiler Service to verify the whole repo.
    """
    try:
        # Call the integration client implemented previously
        result = CompilerClient.compile_project_repo(remote_url, commit_hash)
        return result
    except Exception as e:
        logger.error(f"Project compilation request failed: {e}")
        return {"error": str(e)}
    

@celery.task(bind=True)
def task_verify_lean_code(self, job_id, lean_code, dependencies):
    """
    Validates "Truthness" of raw Lean code submitted by the user.
    Used for the "Check" button in the frontend editor.
    """
    job = AsyncJob.query.get(job_id)
    if not job:
        return

    try:
        job.status = 'processing'
        db.session.commit()
        
        # Call the existing Compiler Client
        # This sends the code to your external Microservice
        result = CompilerClient.verify_code_snippet(lean_code, dependencies)
        
        job.status = 'completed'
        job.result_metadata = result # e.g. {"valid": False, "errors": ["Type mismatch at line 4"]}
        db.session.commit()
        
    except Exception as e:
        logger.error(f"Manual verification failed: {e}")
        job.status = 'failed'
        job.error_log = str(e)
        db.session.commit()


@celery.task(bind=True)
def async_reindex_project(self, project_id):
    """
    Full Sync: Pulls latest from Remote and Re-indexes all files.
    Triggered by Webhook or Manual Sync.
    """
    try:
        project = Project.query.get(project_id)
        if not project or not project.remote_repo_url:
            return

        logger.info(f"Re-indexing project {project_id}")

        # 1. Update the Bare Repo (Fetch)
        repo_path = RepoPool.ensure_bare_repo(str(project.id), project.remote_repo_url)
        
        # 2. Iterate over files in the repo (HEAD)
        # We use GitPython to read the tree of the default branch
        import git
        repo = git.Repo(repo_path)
        head = repo.head.commit
        
        # Walk the tree
        for item in head.tree.traverse():
            if item.type == 'blob' and item.path.endswith('.lean'):
                # Read content directly from Git Object (No worktree needed)
                content = item.data_stream.read().decode('utf-8')
                
                # 3. Call Indexer
                GraphIndexer.index_file_content(
                    str(project.id),
                    item.path,
                    str(head.hexsha),
                    content
                )
        
        logger.info(f"Project {project_id} re-indexed successfully at {head.hexsha}")

    except Exception as e:
        logger.error(f"Re-index failed: {e}")
        # In a robust system, we might update a 'sync_status' on the Project model