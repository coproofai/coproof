from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.services.project_service import ProjectService
from app.schemas import ProjectSchema
from app.extensions import cache

projects_bp = Blueprint('projects', __name__, url_prefix='/api/v1/projects')

# In use
@projects_bp.route('', methods=['POST'])
@jwt_required()
def create_project():
    current_user_id = get_jwt_identity()
    data = request.get_json() or {}
    
    # Service Orchestration
    new_project = ProjectService.create_project(data, leader_id=current_user_id)
    
    schema = ProjectSchema()
    return jsonify(schema.dump(new_project)), 201

@projects_bp.route('/public', methods=['GET'])
@cache.cached(timeout=60, query_string=True)
def list_public_projects():
    """
    Cached endpoint for public discovery.
    """
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    pagination = ProjectService.get_public_projects(page, per_page)
    
    schema = ProjectSchema(many=True)
    return jsonify({
        "projects": schema.dump(pagination.items),
        "total": pagination.total,
        "pages": pagination.pages,
        "current_page": page
    }), 200


@projects_bp.route('/accessible', methods=['GET'])
@jwt_required()
def list_accessible_projects():
    current_user_id = get_jwt_identity()
    projects = ProjectService.get_accessible_projects(current_user_id)

    schema = ProjectSchema(many=True)
    return jsonify({
        "projects": schema.dump(projects),
        "total": len(projects),
    }), 200