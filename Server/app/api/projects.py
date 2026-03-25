from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.services.project_service import ProjectService
from app.services.auth_service import AuthService
from app.services.github_service import GitHubService
from app.services.lean_service import LeanService
from app.schemas import ProjectSchema, GraphNodeSchema
from app.models.graph_node import GraphNode
from app.models.user import User
from app.models.project import Project
from app.models.node import Node
from app.extensions import cache, db
from app.exceptions import CoProofError


def _compact_last_computation_result(payload):
    if not isinstance(payload, dict):
        return payload

    compact = {
        "completed": payload.get("completed"),
        "sufficient": payload.get("sufficient"),
        "summary": payload.get("summary"),
        "error": payload.get("error"),
        "processing_time_seconds": payload.get("processing_time_seconds"),
        "roundtrip_time_seconds": payload.get("roundtrip_time_seconds"),
        "timing_source": payload.get("timing_source"),
        "records_count": payload.get("records_count"),
        "evidence_preview": payload.get("evidence_preview"),
    }
    return compact

projects_bp = Blueprint('projects', __name__, url_prefix='/api/v1/projects')

# In use
@projects_bp.route('', methods=['POST'])
@jwt_required()
def create_project():
    current_user_id = get_jwt_identity()
    data = request.get_json() or {}
    
    # Service Orchestration
    project = ProjectService.create_project(data, leader_id=current_user_id)
    
    schema = ProjectSchema()
    return jsonify(schema.dump(project)), 201

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


@projects_bp.route('/<uuid:project_id>/graph', methods=['GET'])
@jwt_required()
def get_project_graph(project_id):
    """Return the indexed project graph from PostgreSQL."""
    nodes = GraphNode.query.filter_by(project_id=project_id).all()
    schema = GraphNodeSchema(many=True)
    return jsonify(schema.dump(nodes)), 200


@projects_bp.route('/<uuid:project_id>/graph/simple', methods=['GET'])
@jwt_required()
def get_project_graph_simple(project_id):
    """Return a simplified graph payload for frontend DAG rendering."""
    project = Project.query.get_or_404(project_id)
    nodes = Node.query.filter_by(project_id=project.id).order_by(Node.created_at.asc()).all()

    payload = [
        {
            "id": str(node.id),
            "name": node.name,
            "url": node.url,
            "project_id": str(node.project_id),
            "parent_node_id": str(node.parent_node_id) if node.parent_node_id else None,
            "state": node.state,
            "node_kind": node.node_kind,
            "computation_spec": node.computation_spec,
            "last_computation_result": _compact_last_computation_result(node.last_computation_result),
            "created_at": node.created_at.isoformat() if node.created_at else None,
            "updated_at": node.updated_at.isoformat() if node.updated_at else None,
        }
        for node in nodes
    ]

    return jsonify({
        "project_id": str(project.id),
        "project_name": project.name,
        "count": len(payload),
        "nodes": payload,
    }), 200


@projects_bp.route('/<uuid:project_id>/definitions', methods=['GET'])
@jwt_required()
def get_project_definitions_file(project_id):
    """Return the project definitions Lean file content from the default branch."""
    user_id = get_jwt_identity()
    user = User.query.get_or_404(user_id)
    project = Project.query.get_or_404(project_id)

    github_token = AuthService.refresh_github_token_if_needed(user)
    if not github_token:
        raise CoProofError("You must link your GitHub account.", code=400)

    file_map = GitHubService.get_repository_files_map(
        remote_repo_url=project.remote_repo_url,
        token=github_token,
        branch=project.default_branch,
        extensions=('.lean',),
    )
    file_map = LeanService.normalize_file_map_for_def_module(file_map)

    for path in ('Definitions.lean', 'definitions.lean', 'def.lean', 'Def.lean'):
        if path in file_map:
            return jsonify({
                "project_id": str(project.id),
                "path": path,
                "content": file_map[path],
            }), 200

    raise CoProofError("Definitions file not found (Definitions.lean).", code=404)


@projects_bp.route('/<uuid:project_id>/pulls/open', methods=['GET'])
@jwt_required()
def list_open_pull_requests(project_id):
    """List open pull requests targeting the project default branch."""
    user_id = get_jwt_identity()
    user = User.query.get_or_404(user_id)
    project = Project.query.get_or_404(project_id)

    github_token = AuthService.refresh_github_token_if_needed(user)
    if not github_token:
        raise CoProofError("You must link your GitHub account.", code=400)

    pulls = GitHubService.list_open_pull_requests(project.remote_repo_url, github_token, project.default_branch)
    return jsonify({
        "project_id": str(project.id),
        "count": len(pulls),
        "pulls": pulls,
    }), 200


@projects_bp.route('/<uuid:project_id>/pulls/<int:pr_number>/merge', methods=['POST'])
@jwt_required()
def merge_pull_request(project_id, pr_number):
    """Merge a pull request and apply post-merge project graph updates."""
    user_id = get_jwt_identity()
    user = User.query.get_or_404(user_id)
    project = Project.query.get_or_404(project_id)

    github_token = AuthService.refresh_github_token_if_needed(user)
    if not github_token:
        raise CoProofError("You must link your GitHub account.", code=400)

    pr_info = GitHubService.get_pull_request(project.remote_repo_url, github_token, pr_number)
    if pr_info.get('base', {}).get('ref') != project.default_branch:
        raise CoProofError("PR base branch does not match project default branch.", code=400)

    if pr_info.get('merged'):
        metadata = GitHubService.parse_pr_metadata(pr_info.get('body', ''))
        updates = _apply_post_merge_db_updates(project, metadata)
        db.session.commit()
        return jsonify({
            "status": "already_merged",
            "project_id": str(project.id),
            "pr_number": pr_number,
            "db_updates": updates,
        }), 200

    merge_result = GitHubService.merge_pull_request(project.remote_repo_url, github_token, pr_number)
    metadata = GitHubService.parse_pr_metadata(pr_info.get('body', ''))
    updates = _apply_post_merge_db_updates(project, metadata)
    db.session.commit()

    return jsonify({
        "status": "merged",
        "project_id": str(project.id),
        "pr_number": pr_number,
        "merge": merge_result,
        "db_updates": updates,
    }), 200


def _apply_post_merge_db_updates(project, metadata):
    """Apply node state updates in DB after a merged solve/split PR."""
    action = metadata.get("action")
    updates = {
        "action": action,
        "updated_nodes": [],
        "created_nodes": [],
    }

    if action in ('solve_node', 'compute_node'):
        target_id = metadata.get("affected_node_id")
        if target_id:
            target = Node.query.filter_by(id=target_id, project_id=project.id).first()
            if target:
                target.state = 'validated'
                LeanService.append_updated_node(updates, target)
                LeanService.propagate_parent_states(target.parent, updates, Node)
        return updates

    if action == 'split_node':
        base_node_id = metadata.get("base_node_id")
        base_node = None
        if base_node_id:
            base_node = Node.query.filter_by(id=base_node_id, project_id=project.id).first()
            if base_node:
                base_node.state = 'sorry'
                LeanService.append_updated_node(updates, base_node)
                LeanService.propagate_parent_states(base_node.parent, updates, Node)

        affected_nodes = metadata.get("affected_nodes") or []
        if not base_node or not affected_nodes:
            return updates

        child_names = [name for name in affected_nodes if name.lower() != base_node.name.lower()]
        used_folder_names = set()

        for child_name in child_names:
            existing = Node.query.filter_by(
                project_id=project.id,
                parent_node_id=base_node.id,
                name=child_name,
            ).first()
            if existing:
                existing.state = 'sorry'
                LeanService.append_updated_node(updates, existing)
                continue

            folder_segment = LeanService.to_unique_node_folder_segment(child_name, used_folder_names)
            node_url = f"{project.url}/blob/{project.default_branch}/{folder_segment}/main.lean"
            child_node = Node(
                name=child_name,
                url=node_url,
                project_id=project.id,
                parent_node_id=base_node.id,
                state='sorry',
                node_kind='proof',
            )
            db.session.add(child_node)
            db.session.flush()
            updates["created_nodes"].append({
                "id": str(child_node.id),
                "name": child_node.name,
                "state": child_node.state,
                "node_kind": child_node.node_kind,
                "url": child_node.url,
            })

    if action == 'create_computation_node':
        base_node_id = metadata.get("base_node_id")
        base_node = None
        if base_node_id:
            base_node = Node.query.filter_by(id=base_node_id, project_id=project.id).first()
            if base_node:
                base_node.state = 'sorry'
                LeanService.append_updated_node(updates, base_node)
                LeanService.propagate_parent_states(base_node.parent, updates, Node)

        affected_nodes = metadata.get("affected_nodes") or []
        if not base_node or not affected_nodes:
            return updates

        child_names = [name for name in affected_nodes if name.lower() != base_node.name.lower()]
        if not child_names:
            return updates

        child_name = child_names[0]
        existing = Node.query.filter_by(
            project_id=project.id,
            parent_node_id=base_node.id,
            name=child_name,
        ).first()
        if existing:
            existing.state = 'sorry'
            existing.node_kind = 'computation'
            LeanService.append_updated_node(updates, existing)
            return updates

        child_folder = metadata.get("child_folder")
        if not child_folder:
            used_folder_names = set()
            siblings = Node.query.filter_by(project_id=project.id, parent_node_id=base_node.id).all()
            for sibling in siblings:
                sibling_path = GitHubService.extract_repo_path_from_node_url(sibling.url) or ''
                if '/' in sibling_path:
                    used_folder_names.add(sibling_path.rsplit('/', 2)[-2])
            child_folder = LeanService.to_unique_node_folder_segment(child_name, used_folder_names)

        node_url = f"{project.url}/blob/{project.default_branch}/{child_folder}/main.lean"
        child_node = Node(
            name=child_name,
            url=node_url,
            project_id=project.id,
            parent_node_id=base_node.id,
            state='sorry',
            node_kind='computation',
        )
        db.session.add(child_node)
        db.session.flush()
        updates["created_nodes"].append({
            "id": str(child_node.id),
            "name": child_node.name,
            "state": child_node.state,
            "node_kind": child_node.node_kind,
            "url": child_node.url,
        })

    return updates