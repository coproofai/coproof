import logging
from Server.app.models.async_job import AsyncJob
from Server.app.services.graph_engine.indexer import GraphIndexer
from app.extensions import celery, db
from app.models.project import Project
from app.services.git_engine import RepoPool
from app.services.integrations import CompilerClient
from app.exceptions import GitOperationError

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