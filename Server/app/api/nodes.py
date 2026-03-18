from flask import Blueprint, request, jsonify
from flask_caching import logger
from flask_jwt_extended import jwt_required, get_jwt_identity
import re
import uuid
from app.models.user import User
from app.services.auth_service import AuthService
from app.services.integrations.compiler_client import CompilerClient
from app.services.github_service import GitHubService
from app.services.lean_service import LeanService
from app.models.project import Project
from app.models.node import Node
from app.exceptions import CoProofError
from app.extensions import db

nodes_bp = Blueprint('nodes', __name__, url_prefix='/api/v1/nodes')


# @nodes_bp.route('/<uuid:project_id>/<uuid:node_id>/details', methods=['GET'])
# @jwt_required()
# def get_node_details(project_id, node_id):
#     """
#     Retrieves metadata and file content.
#     Delegates Git logic to GitReader service.
#     """
#     # 1. Auth & Metadata
#     user_id = get_jwt_identity()
#     user = User.query.get(user_id)
#     token = AuthService.refresh_github_token_if_needed(user)
    
#     node = GraphNode.query.filter_by(id=node_id, project_id=project_id).first_or_404()
#     project = Project.query.get_or_404(project_id)
    
#     # 2. Call Service (Synchronous)
#     content_data = { "lean": "", "latex": "" }
    
#     try:
#         #TODO must be an internal net REST call for git microservice
#         content_data = GitReader.read_node_files(
#             project_id=str(project.id),
#             remote_url=project.remote_repo_url,
#             token=token,
#             file_path=node.file_path,
#             latex_path=node.latex_file_path,
#             commit_hash=node.commit_hash
#         )
#     except Exception as e:
#         # Log error but return metadata (Graceful degradation)
#         logger.error(f"Git Read Error: {e}")
    
#     # 3. Serialize
#     schema = GraphNodeSchema()
#     data = schema.dump(node)
    
#     return jsonify({
#         "node": data,
#         "content": content_data
#     }), 200


# @nodes_bp.route('/tools/verify-snippet/public', methods=['POST'])
# def verify_snippet_public():
#     """
#     Dev-only endpoint for end-to-end smoke testing:
#     Client -> Backend -> Lean compiler service -> Backend -> Client.
#     """
#     if os.getenv('FLASK_ENV') != 'development':
#         return jsonify({"error": "Public verify endpoint is disabled outside development"}), 403

#     data = request.get_json() or {}
#     code = data.get('code')

#     if not code:
#         return jsonify({"error": "No code provided"}), 400

#     try:
#         result = CompilerClient.verify_snippet(code)
#         return jsonify({
#             "flow": "client -> backend -> lean -> backend -> client",
#             "result": result
#         }), 200
#     except Exception as e:
#         return jsonify({"error": str(e)}), 503


@nodes_bp.route('/<uuid:project_id>/<uuid:node_id>/solve', methods=['POST'])
@jwt_required()
def solve_node(project_id, node_id):
    """
    Receives a complete Lean solution for a node main.lean, verifies it, writes it in a feature branch,
    and opens a PR targeting main/default branch.
    """
    user_id = get_jwt_identity()
    data = request.get_json() or {}
    lean_code = data.get('lean_code') or data.get('code')

    if not lean_code:
        return jsonify({"error": "Missing payload: lean_code"}), 400
    lean_code = LeanService.normalize_lean_imports(lean_code)

    user = User.query.get_or_404(user_id)
    project = Project.query.get_or_404(project_id)
    node = Node.query.filter_by(id=node_id, project_id=project.id).first_or_404()

    github_token = AuthService.refresh_github_token_if_needed(user)
    if not github_token:
        raise CoProofError("You must link your GitHub account.", code=400)

    node_main_path = GitHubService.extract_repo_path_from_node_url(node.url)
    if not node_main_path or not node_main_path.endswith('.lean'):
        raise CoProofError("Node URL does not map to a valid .lean file path.", code=400)

    file_map = GitHubService.get_repository_files_map(
        remote_repo_url=project.remote_repo_url,
        token=github_token,
        branch=project.default_branch,
        extensions=('.lean',),
    )
    file_map = LeanService.normalize_file_map_for_def_module(file_map)
    current_node_content = file_map.get(node_main_path, '')
    file_map[node_main_path] = lean_code

    reachable_files, parent_map = LeanService.resolve_import_tree(node_main_path, file_map)
    reachable_map = {path: file_map[path] for path in reachable_files if path in file_map}
    verification_payload = LeanService.build_verify_payload_from_reachable_map(
        reachable_map=reachable_map,
        entry_file=node_main_path,
        parent_map=parent_map,
        project_goal=project.goal,
    )
    verification = CompilerClient.verify_snippet(verification_payload)

    if not verification.get('valid'):
        payload_preview = '\n'.join(verification_payload.splitlines()[:20])
        return jsonify({
            "status": "compile_error",
            "node_id": str(node.id),
            "errors": verification.get('errors', []),
            "verification": verification,
            "verification_payload_preview": payload_preview,
        }), 400

    # If solve content is already in main/default branch, avoid creating a no-op PR.
    # Persist validation state directly in DB and propagate to ancestors.
    if LeanService.lean_text_equivalent(current_node_content, lean_code):
        updates = {
            "action": "solve_node",
            "updated_nodes": [],
            "created_nodes": [],
        }
        node.state = 'validated'
        LeanService.append_updated_node(updates, node)
        LeanService.propagate_parent_states(node.parent, updates, Node)
        db.session.commit()

        return jsonify({
            "status": "already_solved",
            "action": "solve_node",
            "project_id": str(project.id),
            "node_id": str(node.id),
            "message": "No code changes detected; node state was saved directly in DB.",
            "db_updates": updates,
        }), 200

    branch_name = f"solve-node-{str(node.id)[:8]}-{uuid.uuid4().hex[:6]}"
    files_to_commit = {node_main_path: lean_code}
    for definitions_path in LeanService.definition_file_paths(file_map):
        files_to_commit[definitions_path] = file_map[definitions_path]

    GitHubService.create_branch(
        remote_repo_url=project.remote_repo_url,
        token=github_token,
        new_branch=branch_name,
        from_branch=project.default_branch,
    )
    GitHubService.commit_files(
        remote_repo_url=project.remote_repo_url,
        token=github_token,
        branch=branch_name,
        files=files_to_commit,
        commit_message=f"Solve node {node.name} ({str(node.id)[:8]}) via CoProof",
    )

    pr_title = f"Solve node {node.name} ({str(node.id)[:8]})"
    pr_body = (
        f"Action: solve_node\n"
        f"Project ID: {project.id}\n"
        f"Affected node ID: {node.id}\n"
        f"Affected node name: {node.name}\n"
    )

    pr_data = GitHubService.open_pull_request(
        remote_repo_url=project.remote_repo_url,
        token=github_token,
        title=pr_title,
        body=pr_body,
        head_branch=branch_name,
        base_branch=project.default_branch,
    )

    return jsonify({
        "status": "ok",
        "action": "solve_node",
        "project_id": str(project.id),
        "node_id": str(node.id),
        "branch": branch_name,
        "pull_request": {
            "number": pr_data.get('number'),
            "title": pr_data.get('title'),
            "url": pr_data.get('html_url'),
        },
    }), 201


@nodes_bp.route('/<uuid:project_id>/<uuid:node_id>/split', methods=['POST'])
@jwt_required()
def split_node(project_id, node_id):
    """
    Receives a Lean split with new lemmas (using sorry), verifies it with imports,
    creates lemma folders/files, updates node main.lean imports, and opens a PR.
    """
    user_id = get_jwt_identity()
    data = request.get_json() or {}
    lean_code = data.get('lean_code') or data.get('code')

    if not lean_code:
        return jsonify({"error": "Missing payload: lean_code"}), 400
    lean_code = LeanService.normalize_lean_imports(lean_code)

    user = User.query.get_or_404(user_id)
    project = Project.query.get_or_404(project_id)
    node = Node.query.filter_by(id=node_id, project_id=project.id).first_or_404()

    github_token = AuthService.refresh_github_token_if_needed(user)
    if not github_token:
        raise CoProofError("You must link your GitHub account.", code=400)

    node_main_path = GitHubService.extract_repo_path_from_node_url(node.url)
    if not node_main_path or not node_main_path.endswith('.lean'):
        raise CoProofError("Node URL does not map to a valid .lean file path.", code=400)

    split_blocks = LeanService.extract_lemma_blocks(lean_code)
    if not split_blocks:
        return jsonify({"error": "No lemma/theorem blocks found in lean_code for split operation."}), 400

    target_name = (node.name or '').strip().lower()
    base_block = next((block for block in split_blocks if block['name'].strip().lower() == target_name), None)
    if base_block is None:
        return jsonify({
            "error": f"The split payload must include a theorem/lemma named '{node.name}' as the base node proof.",
        }), 400

    child_blocks = [block for block in split_blocks if block is not base_block]
    if not child_blocks:
        return jsonify({"error": "Split requires at least one child theorem/lemma besides the base node theorem."}), 400

    base_content = base_block['content']
    missing_child_refs = [
        block['name']
        for block in child_blocks
        if not re.search(rf"\b{re.escape(block['name'])}\b", base_content)
    ]
    if missing_child_refs:
        return jsonify({
            "error": "Base theorem must use all child nodes.",
            "missing_child_references": missing_child_refs,
        }), 400

    updated_main = LeanService.build_split_main_content(lean_code, child_blocks)
    lemma_files, tex_files, lemma_names = LeanService.build_split_files(child_blocks)

    file_map = GitHubService.get_repository_files_map(
        remote_repo_url=project.remote_repo_url,
        token=github_token,
        branch=project.default_branch,
        extensions=('.lean',),
    )
    file_map = LeanService.normalize_file_map_for_def_module(file_map)
    file_map[node_main_path] = updated_main
    for path, content in lemma_files.items():
        file_map[path] = LeanService.normalize_lean_imports(content)

    def_context = LeanService.build_goaldef_context_from_project(project)
    verification_payload = LeanService.build_split_verification_payload(def_context, lean_code, project.goal)
    verification = CompilerClient.verify_snippet(verification_payload)

    if not verification.get('valid'):
        payload_preview = '\n'.join(verification_payload.splitlines()[:20])
        return jsonify({
            "status": "compile_error",
            "node_id": str(node.id),
            "errors": verification.get('errors', []),
            "verification": verification,
            "verification_payload_preview": payload_preview,
        }), 400

    branch_name = f"split-node-{str(node.id)[:8]}-{uuid.uuid4().hex[:6]}"
    files_to_commit = {node_main_path: updated_main}
    for definitions_path in LeanService.definition_file_paths(file_map):
        files_to_commit[definitions_path] = file_map[definitions_path]
    files_to_commit.update(lemma_files)
    files_to_commit.update(tex_files)

    GitHubService.create_branch(
        remote_repo_url=project.remote_repo_url,
        token=github_token,
        new_branch=branch_name,
        from_branch=project.default_branch,
    )
    GitHubService.commit_files(
        remote_repo_url=project.remote_repo_url,
        token=github_token,
        branch=branch_name,
        files=files_to_commit,
        commit_message=f"Split node {node.name} ({str(node.id)[:8]}) via CoProof",
    )

    affected_nodes_text = ', '.join([node.name] + lemma_names)
    pr_title = f"Split node {node.name} ({str(node.id)[:8]}) into: {', '.join(lemma_names)}"
    pr_body = (
        f"Action: split_node\n"
        f"Project ID: {project.id}\n"
        f"Affected nodes: {affected_nodes_text}\n"
        f"Base node ID: {node.id}\n"
    )

    pr_data = GitHubService.open_pull_request(
        remote_repo_url=project.remote_repo_url,
        token=github_token,
        title=pr_title,
        body=pr_body,
        head_branch=branch_name,
        base_branch=project.default_branch,
    )

    return jsonify({
        "status": "ok",
        "action": "split_node",
        "project_id": str(project.id),
        "node_id": str(node.id),
        "created_lemmas": lemma_names,
        "branch": branch_name,
        "pull_request": {
            "number": pr_data.get('number'),
            "title": pr_data.get('title'),
            "url": pr_data.get('html_url'),
        },
    }), 201


@nodes_bp.route('/<uuid:project_id>/<uuid:node_id>/verify-import-tree', methods=['POST'])
@jwt_required()
def verify_node_import_tree(project_id, node_id):
    user_id = get_jwt_identity()
    user = User.query.get_or_404(user_id)
    project = Project.query.get_or_404(project_id)
    node = Node.query.filter_by(id=node_id, project_id=project.id).first_or_404()

    github_token = AuthService.refresh_github_token_if_needed(user)
    if not github_token:
        raise CoProofError("You must link your GitHub account.", code=400)

    entry_file = GitHubService.extract_repo_path_from_node_url(node.url)
    if not entry_file or not entry_file.endswith('.lean'):
        raise CoProofError("Node URL does not map to a valid .lean file path.", code=400)

    all_lean_files = GitHubService.get_repository_files_map(
        remote_repo_url=project.remote_repo_url,
        token=github_token,
        branch=project.default_branch,
        extensions=('.lean',),
    )
    all_lean_files = LeanService.normalize_file_map_for_def_module(all_lean_files)

    if entry_file not in all_lean_files:
        raise CoProofError(f"Entry file not found in repo: {entry_file}", code=404)

    reachable_files, parent_map = LeanService.resolve_import_tree(entry_file, all_lean_files)
    reachable_map = {path: all_lean_files[path] for path in reachable_files if path in all_lean_files}

    verification_payload = LeanService.build_verify_payload_from_reachable_map(
        reachable_map=reachable_map,
        entry_file=entry_file,
        parent_map=parent_map,
        project_goal=project.goal,
    )
    verification = CompilerClient.verify_snippet(verification_payload)
    sorry_locations = LeanService.collect_sorry_locations(reachable_map)
    sorry_traces = LeanService.build_sorry_traces(entry_file, sorry_locations, parent_map)

    return jsonify({
        "status": "ok",
        "project_id": str(project.id),
        "node_id": str(node.id),
        "entry_file": entry_file,
        "reachable_file_count": len(reachable_map),
        "reachable_files": sorted(reachable_map.keys()),
        "verification": verification,
        "has_sorry": len(sorry_locations) > 0,
        "sorry_locations": sorry_locations,
        "sorry_traces": sorry_traces,
    }), 200


@nodes_bp.route('/<uuid:project_id>/<uuid:node_id>/file-content', methods=['GET'])
@jwt_required()
def get_node_file_content(project_id, node_id):
    user_id = get_jwt_identity()
    user = User.query.get_or_404(user_id)
    project = Project.query.get_or_404(project_id)
    node = Node.query.filter_by(id=node_id, project_id=project.id).first_or_404()

    github_token = AuthService.refresh_github_token_if_needed(user)
    if not github_token:
        raise CoProofError("You must link your GitHub account.", code=400)

    node_main_path = GitHubService.extract_repo_path_from_node_url(node.url)
    if not node_main_path or not node_main_path.endswith('.lean'):
        raise CoProofError("Node URL does not map to a valid .lean file path.", code=400)

    content = GitHubService.get_file_content(
        remote_repo_url=project.remote_repo_url,
        token=github_token,
        path=node_main_path,
        branch=project.default_branch,
    )

    return jsonify({
        "project_id": str(project.id),
        "node_id": str(node.id),
        "path": node_main_path,
        "content": content,
    }), 200
    