from flask import Blueprint, request, jsonify
from flask_caching import logger
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models.user import User
from app.services.auth_service import AuthService
from app.services.git_engine.reader import GitReader
from app.models.async_job import AsyncJob
from app.services.integrations.compiler_client import CompilerClient
from app.tasks.agent_tasks import task_translate_nl
from app.tasks.git_tasks import task_verify_lean_code
from app.models.graph_index import GraphNode
from app.models.project import Project
from app.services.git_engine import git_transaction
from app.services.graph_engine import GraphIndexer
from app.schemas import GraphNodeSchema
from app.exceptions import CoProofError
from app.extensions import db
from app.tasks.git_tasks import async_save_node
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
    API Gateway Endpoint:
    Receives save request, validates payload, and dispatches to Git Microservice (Celery).
    Non-blocking.
    """
    user_id = get_jwt_identity()
    data = request.get_json()
    
    file_path = data.get('file_path')
    content = data.get('content')
    branch = data.get('branch', 'main') # Support different branches
    
    # 1. Basic Validation
    if not file_path or content is None:
        return jsonify({"error": "Missing payload (file_path or content)"}), 400

    # 2. Dispatch to Celery (Microservice Layer)
    # We pass IDs (strings) because Celery arguments must be JSON serializable
    task = async_save_node.delay(
        project_id=str(project_id),
        user_id=user_id,
        file_path=file_path,
        content=content,
        branch=branch
    )
    
    # 3. Return 202 Accepted
    # The client can poll /jobs/<task_id> if we implement a generic job status endpoint,
    # or listen via WebSockets for completion.
    return jsonify({
        "message": "Save operation queued",
        "task_id": task.id,
        "status": "processing",
        "branch": branch
    }), 202


@nodes_bp.route('/<uuid:project_id>/nodes/<uuid:node_id>', methods=['GET'])
@jwt_required()
def get_node_details(project_id, node_id):
    """
    Retrieves metadata and file content.
    Delegates Git logic to GitReader service.
    """
    # 1. Auth & Metadata
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    token = AuthService.refresh_github_token_if_needed(user)
    
    node = GraphNode.query.filter_by(id=node_id, project_id=project_id).first_or_404()
    project = Project.query.get_or_404(project_id)
    
    # 2. Call Service (Synchronous)
    content_data = { "lean": "", "latex": "" }
    
    try:
        #TODO must be an internal net REST call for git microservice
        content_data = GitReader.read_node_files(
            project_id=str(project.id),
            remote_url=project.remote_repo_url,
            token=token,
            file_path=node.file_path,
            latex_path=node.latex_file_path,
            commit_hash=node.commit_hash
        )
    except Exception as e:
        # Log error but return metadata (Graceful degradation)
        logger.error(f"Git Read Error: {e}")
    
    # 3. Serialize
    schema = GraphNodeSchema()
    data = schema.dump(node)
    
    return jsonify({
        "node": data,
        "content": content_data
    }), 200


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