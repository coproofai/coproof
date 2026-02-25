# app/tasks/merge_tasks.py

import logging
import git
from app.services.git_engine import file_service
from app.extensions import celery, db
from app.models.project import Project
from app.models.proposed_node import ProposedNode
from app.models.graph_index import GraphNode
from app.services.auth_service import AuthService
from app.services.git_engine import transaction, locking, repo_pool
from app.services.verification_service import VerificationService
from app.services.integrations import CompilerClient

logger = logging.getLogger(__name__)

@celery.task(bind=True)
def async_merge_proposal(self, proposal_id):
    """
    Promotes a ProposedNode to Canonical.
    Strictly follows: Lock -> Update -> Verify (with main) -> Merge -> Promote.
    """
    # 1. Load Data
    proposal = ProposedNode.query.get(proposal_id)
    if not proposal: return {"error": "Proposal not found"}
    
    project = Project.query.get(proposal.project_id)
    if not project.github_installation_id: return {"error": "GitHub App not installed"}
        
    app_token = AuthService.get_installation_access_token(project.github_installation_id)

    # 2. PROJECT LOCK
    with locking.acquire_project_lock(str(project.id)):
        
        try:
            # 3. Update Repo (Issue 3 Fix)
            # Ensure we have the absolute latest state from GitHub before doing anything
            repo_pool.RepoPool.update_repo(str(project.id), project.remote_repo_url, app_token)
            bare_path = repo_pool.RepoPool.get_storage_path(str(project.id))

            # 4. Re-Verification & Compilation (Decoupled from Merge)
            dag = VerificationService.build_ephemeral_dag(project.id, target_proposal=proposal)
            cycle_res = VerificationService.check_cycles(dag)
            if cycle_res['has_cycle']:
                return _fail_proposal(proposal, "Merge Aborted: Cycle detected")

            ordered_paths = VerificationService.get_topological_order(dag)
            
            # 5. Build Synthetic State (Issue 1 & 2 Fix)
            # Use read-only worktree. Do NOT push. 
            # Merge origin/main LOCALLY to verify integration.
            full_code = ""
            with transaction.read_only_worktree(bare_path, branch=proposal.branch_name) as wt_path:
                wt_repo = git.Repo(wt_path)
                
                # Fetch and Merge Main into this temporary worktree
                # This ensures we compile against the latest reality
                try:
                    wt_repo.remotes.origin.fetch('main')
                    wt_repo.git.merge('origin/main', '--no-edit')
                except git.GitCommandError as e:
                    return _fail_proposal(proposal, f"Merge Aborted: Conflict with main. {e}")

                # Generate File
                main_path = file_service.FileOps.generate_main_file(wt_path, ordered_paths)
                with open(main_path, 'r') as f:
                    full_code = f.read()

            # 6. Compiler Call (Issue 6 Fix)
            # Happens outside any git transaction
            res = CompilerClient.verify_project_content(full_code)
            
            if not res['compile_success']:
                return _fail_proposal(proposal, f"Merge Aborted: Compilation failed. {res.get('errors')}")

            # 7. GIT MERGE (The Real Operation)
            # returns the real hash (Issue 4 Fix)
            merge_commit_sha = transaction.merge_branch_to_main(
                str(project.id), 
                project.remote_repo_url, 
                app_token, 
                proposal.branch_name
            )
            
            # 8. DB PROMOTION
            canonical = GraphNode(
                project_id=project.id,
                title=proposal.title,
                node_type=proposal.node_type,
                file_path=proposal.lean_file_path,
                latex_file_path=proposal.latex_file_path,
                commit_hash=merge_commit_sha, # Store real hash
                # Dependencies resolved by Indexer later, or manually here
            )
            db.session.add(canonical)
            
            proposal.status = 'merged'
            proposal.merged_node = canonical
            db.session.commit()
            
            # 9. Trigger Re-Indexing
            from app.tasks.git_tasks import async_reindex_project
            async_reindex_project.delay(str(project.id))
            
            return {"status": "merged", "commit": merge_commit_sha}

        except Exception as e:
            logger.error(f"Merge failed: {e}")
            db.session.rollback()
            return _fail_proposal(proposal, f"System Error: {str(e)}")

def _fail_proposal(proposal, msg):
    # Issue 5 Fix: Robust status update
    proposal.verification_log = msg
    proposal.status = 'invalid' 
    db.session.commit()
    return {"status": "failed", "error": msg}