# app/tasks/draft_tasks.py

import logging
import uuid
import os
from app.extensions import celery, db
from app.models.project import Project
from app.models.user import User
from app.models.proposed_node import ProposedNode
from app.services.git_engine import repo_pool, transaction, locking, file_ops, file_service
from app.services.verification_service import VerificationService
from app.services.auth_service import AuthService
from app.services.integrations import CompilerClient, GitHubService

logger = logging.getLogger(__name__)

@celery.task(bind=True, max_retries=3)
def async_save_draft(self, project_id, user_id, node_payload):
    """
    Main Orchestrator for Draft Creation/Update.
    """
    try:
        # 1. Prepare Metadata & DB Record
        proposal, git_token, new_stmt_id, context = _prepare_proposal_metadata(
            project_id, user_id, node_payload
        )

        # 2. Sync Git (Fork & Upstream)
        fork_info = _sync_and_branch(context['project'], context['user'], git_token)
        proposal.fork_repo_full_name = fork_info['full_name']
        db.session.commit()

        # 3. Write Scaffold to Feature Branch
        _write_scaffold_to_fork(context, proposal, new_stmt_id, node_payload, git_token)

        # 4. Verify & Compile
        compiler_result = _verify_ephemeral_dag_and_compile(
            context['project'], proposal, git_token
        )

        # 5. Handle Status & PR
        _finalize_proposal_status(proposal, compiler_result, fork_info, git_token)

        return {"status": proposal.status, "id": str(proposal.id)}

    except Exception as e:
        logger.error(f"Draft task failed: {e}", exc_info=True)
        return _handle_failure(node_payload.get('proposal_id'), str(e))


# --- Sub-Functions ---

def _prepare_proposal_metadata(project_id, user_id, payload):
    """
    Validates inputs, generates UUIDs, and creates/updates the ProposedNode in DB.
    """
    project = Project.query.get(project_id)
    user = User.query.get(user_id)
    git_token = AuthService.refresh_github_token_if_needed(user)
    
    if not git_token:
        raise ValueError("GitHub Auth required")

    # Extract UUIDs (Enforce consistency)
    parent_id = payload.get('parent_statement_id') # UUID String
    dep_ids = payload.get('dependency_ids', [])    # List of UUID Strings
    
    # Generate new ID
    new_stmt_id = str(uuid.uuid4())

    # DB Logic
    proposal_id = payload.get('proposal_id')
    proposal = None
    
    if proposal_id:
        proposal = ProposedNode.query.get(proposal_id)
    
    if not proposal:
        branch_name = f"user/{user.github_id}/prop-{new_stmt_id[:8]}"
        path_data = file_service.FileService.generate_paths(new_stmt_id)
        
        proposal = ProposedNode(
            project_id=project_id,
            user_id=user_id,
            title=payload.get('title'),
            node_type=payload.get('node_type', 'lemma'),
            branch_name=branch_name,
            lean_file_path=path_data['lean'],
            latex_file_path=path_data['tex'],
            parent_statement_id=parent_id
        )
        db.session.add(proposal)
    
    # Update Fields
    proposal.proposed_dependencies = dep_ids # Store UUIDs
    proposal.status = 'verifying'
    proposal.verification_log = "Initializing..."
    db.session.commit()

    context = {'project': project, 'user': user}
    return proposal, git_token, new_stmt_id, context


def _sync_and_branch(project, user, token):
    """
    Ensures fork exists and is synced with upstream/main.
    """
    # Parse Upstream
    parts = project.remote_repo_url.rstrip('.git').split('/')
    upstream_owner, upstream_repo = parts[-2], parts[-1]

    # Ensure Fork
    fork_name, fork_url = GitHubService.ensure_fork_exists(token, upstream_owner, upstream_repo)
    
    # Sync Fork with Upstream (Critical for fresh base)
    GitHubService.sync_fork_with_upstream(token, fork_name, project.default_branch)
    
    return {'full_name': fork_name, 'clone_url': fork_url, 'upstream': f"{upstream_owner}/{upstream_repo}"}


def _write_scaffold_to_fork(context, proposal, stmt_id, payload, token):
    """
    Generates content and pushes to the feature branch.
    """
    project = context['project']
    user = context['user']

    # Generate Content (UUID enforced)
    scaffold = file_service.FileService.generate_lean_scaffold(
        statement_id=stmt_id,
        parent_statement_id=str(proposal.parent_statement_id) if proposal.parent_statement_id else None,
        statement_type=proposal.node_type,
        statement_name=proposal.title,
        statement_signature=payload.get('signature', 'True'),
        proof_body=payload.get('content', 'sorry'),
        dependency_ids=proposal.proposed_dependencies # UUIDs
    )

    # Git Transaction
    # Lock Project to clone/update local cache
    with locking.acquire_project_lock(str(project.id)):
        repo_pool.RepoPool.ensure_repo_exists(str(project.id), project.remote_repo_url, token)
        # We need to fetch the FORK as well if it's different, but we push to fork_url
        # Ideally we add the fork as a remote. For simplicity, we assume RepoPool handles credentials.

    # Branch Lock
    with locking.acquire_branch_lock(str(project.id), proposal.branch_name):
        with transaction.git_transaction(
            repo_pool.RepoPool.get_storage_path(str(project.id)),
            user.full_name,
            user.email,
            branch=proposal.branch_name
        ) as worktree:
            
            # Sync Logic: Merge origin/main (Upstream state) into this branch
            # This ensures we are building on top of the latest Canonical state
            import git
            repo = git.Repo(worktree)
            try:
                repo.remotes.origin.fetch(project.default_branch)
                repo.git.merge(f"origin/{project.default_branch}", '--no-edit')
            except Exception as e:
                raise ValueError(f"Failed to merge upstream main into feature branch: {e}")

            # Write file
            full_path = os.path.join(worktree, proposal.lean_file_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, 'w') as f:
                f.write(scaffold)


def _verify_ephemeral_dag_and_compile(project, proposal, token):
    """
    Builds DAG, Checks Cycles, Concatenates Files, Calls Compiler.
    """
    # 1. Structural Verification
    ordered_paths = VerificationService.validate_and_order(project.id, proposal)

    # 2. File Generation
    # We need a read-only worktree of the feature branch to read all files
    bare_path = repo_pool.RepoPool.get_storage_path(str(project.id))
    
    with transaction.read_only_worktree(bare_path, branch=proposal.branch_name) as wt:
        main_path = file_ops.FileOps.generate_main_file(wt, ordered_paths)
        with open(main_path, 'r') as f:
            code = f.read()

    # 3. Compiler Service
    return CompilerClient.verify_project_content(code)


def _finalize_proposal_status(proposal, compiler_res, fork_info, token):
    """
    Updates DB status and Creates/Updates PR if valid.
    """
    if not compiler_res['compile_success']:
        proposal.status = 'invalid'
        proposal.verification_log = f"Compilation Errors: {compiler_res.get('errors')}"
    else:
        proposal.status = 'valid_with_sorry' if compiler_res['contains_sorry'] else 'valid'
        proposal.verification_log = "Verification Successful."

        # PR Management
        try:
            pr_num = GitHubService.create_or_update_pr(
                token,
                fork_info['upstream'], # Upstream owner/repo
                head_branch=proposal.branch_name,
                base_branch='main',
                title=f"Proposal: {proposal.title}",
                body="Auto-generated by CoProof."
            )
            proposal.github_pr_number = pr_num
        except Exception as e:
            logger.error(f"PR Creation failed: {e}")
            proposal.verification_log += f"\nPR Error: {e}"

    db.session.commit()


def _handle_failure(proposal_id, error_msg):
    if proposal_id:
        p = ProposedNode.query.get(proposal_id)
        if p:
            p.status = 'invalid'
            p.verification_log = error_msg
            db.session.commit()
    return {"status": "failed", "error": error_msg}