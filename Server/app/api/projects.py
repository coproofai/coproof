from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models.project import Project
from app.extensions import db, cache

projects_bp = Blueprint('projects', __name__, url_prefix='/api/v1/projects')

@projects_bp.route('', methods=['POST'])
@jwt_required()
def create_project():
    current_user_id = get_jwt_identity()
    data = request.get_json()
    
    new_project = Project(
        nombre=data['nombre'],
        descripcion=data.get('descripcion'),
        visibilidad=data['visibilidad'],
        lider_id=current_user_id
    )
    db.session.add(new_project)
    db.session.commit()
    return jsonify(new_project.to_dict()), 201

@projects_bp.route('/public', methods=['GET'])
@cache.cached(timeout=60, query_string=True) # Cache public list for 60s
def get_public_projects():
    # Implementation for searching/filtering public projects
    page = request.args.get('page', 1, type=int)
    query = Project.query.filter_by(visibilidad='publico')
    pagination = query.paginate(page=page, per_page=20)
    
    return jsonify({
        'projects': [p.to_dict() for p in pagination.items],
        'total': pagination.total
    }), 200

@projects_bp.route('/<uuid:project_id>/graph', methods=['GET'])
@jwt_required()
def get_project_graph(project_id):
    # Logic to fetch nodes and edges would be in a Service
    # Simplified here:
    project = Project.query.get_or_404(project_id)
    # Security check: is user collaborator or is project public?
    
    return jsonify({"nodes": [], "edges": []}), 200