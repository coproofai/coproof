from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models.project import Project
from app.models.graph_index import GraphNode
from app.models.async_job import AsyncJob
from app.schemas import AgentRequestSchema
from app.tasks.agent_tasks import run_agent_exploration
from app.extensions import db
from app.exceptions import CoProofError

# Define Blueprint
agent_bp = Blueprint('agent', __name__, url_prefix='/api/v1/projects')

@agent_bp.route('/<uuid:project_id>/nodes/<uuid:node_id>/agent/solve', methods=['POST'])
@jwt_required()
def request_proof_solution(project_id, node_id):
    """
    CDU-17: Trigger the AI Agent to solve a specific node.
    """
    user_id = get_jwt_identity()
    
    # 1. Validate Project & Node existence
    project = Project.query.get_or_404(project_id)
    node = GraphNode.query.filter_by(id=node_id, project_id=project_id).first_or_404()
    
    # 2. Validate Input (Strategy, Hints)
    schema = AgentRequestSchema()
    errors = schema.validate(request.get_json())
    if errors:
        return jsonify(errors), 400
    
    data = schema.load(request.get_json())
    strategy = data.get('strategy')
    hint = data.get('hint')

    # 3. Create Async Job Record
    job = AsyncJob(
        user_id=user_id,
        project_id=project_id,
        celery_task_id="pending",
        job_type="agent_exploration",
        status="queued"
    )
    db.session.add(job)
    db.session.commit()

    # 4. Prepare Context
    # We pass the Node ID. The Worker will fetch the text/dependencies 
    # from the DB/Index to build the context for the agent.
    context = {
        "node_id": str(node.id),
        "node_title": node.title,
        "node_type": node.node_type
        # Worker will fetch actual dependencies
    }

    # 5. Dispatch Task
    task = run_agent_exploration.delay(
        job_id=str(job.id),
        context=context,
        strategy=strategy,
        hint=hint
    )
    
    # Update Job with Task ID
    job.celery_task_id = task.id
    db.session.commit()

    return jsonify({
        "message": "Agent exploration started",
        "job_id": job.id,
        "status": "queued"
    }), 202