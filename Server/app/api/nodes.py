from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from Server.app.models.async_job import AsyncJob
from Server.app.services.integrations.compiler_client import CompilerClient
from Server.app.tasks.agent_tasks import task_translate_nl
from Server.app.tasks.git_tasks import task_verify_lean_code
from app.models.graph_index import GraphNode
from app.models.project import Project
from app.services.git_engine import git_transaction
from app.services.graph_engine import GraphIndexer
from app.schemas import GraphNodeSchema
from app.exceptions import CoProofError
from app.extensions import db
import os

nodes_bp = Blueprint('nodes', __name__, url_prefix='/api/v1/projects')

@nodes_bp.route('/<uuid:project_id>/graph', methods=['GET'])
@jwt_required()
def get_project_graph(project_id):
    """
    CDU-15: Visualizar grafo.
    Reads purely from PostgreSQL Index. Fast.
    """
    # 1. Fetch Nodes
    nodes = GraphNode.query.filter_by(project_id=project_id).all()
    
    # 2. Serialize
    schema = GraphNodeSchema(many=True)
    return jsonify(schema.dump(nodes)), 200

@nodes_bp.route('/<uuid:project_id>/nodes', methods=['POST'])
@jwt_required()
def create_or_update_node(project_id):
    """
    Writes content to Git (Stateless Transaction) -> Updates Index.
    """
    user_id = get_jwt_identity()
    # TODO: Fetch user details for Git Author (Name/Email) from DB
    
    data = request.get_json()
    file_path = data.get('file_path')
    content = data.get('content')
    
    project = Project.query.get_or_404(project_id)
    
    if not project.remote_repo_url:
        raise CoProofError("Project has no remote repo configured", code=400)

    # 1. GIT TRANSACTION (Stateless)
    # This clones/pulls -> creates worktree -> yields path -> commits -> pushes
    with git_transaction(
        str(project.id), 
        project.remote_repo_url, 
        author_name="User " + str(user_id), # Placeholder
        author_email="user@coproof.com"
    ) as worktree_root:
        
        # 2. Write File to Ephemeral Worktree
        full_path = os.path.join(worktree_root, file_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        with open(full_path, 'w') as f:
            f.write(content)
            
    # 3. INDEX UPDATE (Sync)
    # Ideally, we get the commit hash from the transaction return, 
    # but for now we re-parse.
    # TODO: Pass commit hash from transaction to indexer.
    GraphIndexer.index_file_content(str(project_id), file_path, "latest", content)
    
    return jsonify({"message": "Node saved and indexed", "file": file_path}), 201



@nodes_bp.route('/tools/translate', methods=['POST'])
@jwt_required()
def translate_preview():
    """
    Takes NL text -> Returns Async Job ID for translation.
    Does NOT save to Git.
    """
    user_id = get_jwt_identity()
    data = request.get_json()
    nl_text = data.get('nl_text')
    context = data.get('context', "")
    
    # 1. Create Job Tracker
    job = AsyncJob(
        user_id=user_id,
        celery_task_id="pending",
        job_type="agent_exploration", # Or a new type 'translation'
        status="queued"
    )
    db.session.add(job)
    db.session.commit()
    
    # 2. Dispatch Celery Task
    task = task_translate_nl.delay(nl_text, context, str(job.id))
    
    # 3. Update Task ID
    job.celery_task_id = task.id
    db.session.commit()
    
    return jsonify({"job_id": job.id, "status": "queued"}), 202

@nodes_bp.route('/tools/verify-snippet', methods=['POST'])
@jwt_required()
def verify_snippet_preview():
    """
    Takes Lean Code -> Returns Compilation Errors (Synchronous).
    For quick syntax checks in the UI.
    """
    data = request.get_json()
    code = data.get('code')
    
    # We call the client directly (Synchronous) because syntax checks are usually fast.
    # If this takes > 2 seconds, move to Celery.
    try:
        result = CompilerClient.verify_code_snippet(code)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 503
    


@nodes_bp.route('/tools/verify-code', methods=['POST'])
@jwt_required()
def verify_code_async():
    """
    Takes Lean Code -> Returns Async Job ID for verification.
    Allows user to check "Truthness" of manual edits without saving to Git.
    """
    user_id = get_jwt_identity()
    data = request.get_json()
    
    code = data.get('code')
    # Optional: list of dependency names if the microservice needs them to build context
    dependencies = data.get('dependencies', []) 
    
    if not code:
        return jsonify({"error": "No code provided"}), 400

    # 1. Create Job Tracker
    job = AsyncJob(
        user_id=user_id,
        celery_task_id="pending",
        job_type="git_clone", # We can reuse an enum or add 'code_verification' to the DB Enum later
        status="queued"
    )
    db.session.add(job)
    db.session.commit()
    
    # 2. Dispatch Celery Task (The new one in git_tasks)
    task = task_verify_lean_code.delay(str(job.id), code, dependencies)
    
    # 3. Update Task ID
    job.celery_task_id = task.id
    db.session.commit()
    
    return jsonify({
        "job_id": job.id, 
        "status": "queued",
        "message": "Verification started"
    }), 202