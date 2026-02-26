from flask import Blueprint, request, jsonify
from flask_caching import logger
from flask_jwt_extended import jwt_required, get_jwt_identity
import os
import re
import uuid
import requests
from urllib.parse import urlparse
from app.models.user import User
from app.services.auth_service import AuthService
from app.services.git_engine.reader import GitReader
from app.models.async_job import AsyncJob
from app.services.integrations.compiler_client import CompilerClient
from app.tasks.agent_tasks import task_translate_nl
from app.tasks.git_tasks import task_verify_lean_code
from app.models.graph_index import GraphNode
from app.models.project import Project
from app.models.new_project import NewProject
from app.models.new_node import NewNode
from app.services.git_engine import RepoPool, git_transaction, read_only_worktree
from app.services.graph_engine import GraphIndexer
from app.schemas import GraphNodeSchema
from app.exceptions import CoProofError
from app.extensions import db
from app.tasks.git_tasks import async_save_node

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


@nodes_bp.route('/<uuid:project_id>/graph/simple', methods=['GET'])
@jwt_required()
def get_project_graph_simple(project_id):
    """
    Simplified graph endpoint for new node model.
    Returns flat node list with parent linkage + state for frontend DAG rendering.
    """
    project = NewProject.query.get_or_404(project_id)
    nodes = NewNode.query.filter_by(project_id=project.id).order_by(NewNode.created_at.asc()).all()

    payload = [
        {
            "id": str(node.id),
            "name": node.name,
            "url": node.url,
            "project_id": str(node.project_id),
            "parent_node_id": str(node.parent_node_id) if node.parent_node_id else None,
            "state": node.state,
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


# @nodes_bp.route('/tools/translate', methods=['POST'])
# @jwt_required()
# def translate_preview():
#     """
#     Takes NL text -> Returns Async Job ID for translation.
#     Does NOT save to Git.
#     """
#     user_id = get_jwt_identity()
#     data = request.get_json()
#     nl_text = data.get('nl_text')
#     context = data.get('context', "")
    
#     # 1. Create Job Tracker
#     job = AsyncJob(
#         user_id=user_id,
#         celery_task_id="pending",
#         job_type="agent_exploration", # Or a new type 'translation'
#         status="queued"
#     )
#     db.session.add(job)
#     db.session.commit()
    
#     # 2. Dispatch Celery Task
#     task = task_translate_nl.delay(nl_text, context, str(job.id))
    
#     # 3. Update Task ID
#     job.celery_task_id = task.id
#     db.session.commit()
    
#     return jsonify({"job_id": job.id, "status": "queued"}), 202

# @nodes_bp.route('/tools/verify-snippet', methods=['POST'])
# @jwt_required()
# def verify_snippet_preview():
#     """
#     Takes Lean Code -> Returns Compilation Errors (Synchronous).
#     For quick syntax checks in the UI.
#     """
#     data = request.get_json()
#     code = data.get('code')
    
#     # We call the client directly (Synchronous) because syntax checks are usually fast.
#     # If this takes > 2 seconds, move to Celery.
#     try:
#         result = CompilerClient.verify_code_snippet(code)
#         return jsonify(result), 200
#     except Exception as e:
#         return jsonify({"error": str(e)}), 503


@nodes_bp.route('/tools/verify-snippet/public', methods=['POST'])
def verify_snippet_public():
    """
    Dev-only endpoint for end-to-end smoke testing:
    Client -> Backend -> Lean compiler service -> Backend -> Client.
    """
    if os.getenv('FLASK_ENV') != 'development':
        return jsonify({"error": "Public verify endpoint is disabled outside development"}), 403

    data = request.get_json() or {}
    code = data.get('code')

    if not code:
        return jsonify({"error": "No code provided"}), 400

    try:
        result = CompilerClient.verify_snippet(code)
        return jsonify({
            "flow": "client -> backend -> lean -> backend -> client",
            "result": result
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 503


@nodes_bp.route('/<uuid:project_id>/nodes/<uuid:node_id>/solve', methods=['POST'])
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
    lean_code = _normalize_lean_imports(lean_code)

    user = User.query.get_or_404(user_id)
    project = NewProject.query.get_or_404(project_id)
    node = NewNode.query.filter_by(id=node_id, project_id=project.id).first_or_404()

    github_token = AuthService.refresh_github_token_if_needed(user)
    if not github_token:
        raise CoProofError("You must link your GitHub account.", code=400)

    node_main_path = _extract_repo_path_from_node_url(node.url)
    if not node_main_path or not node_main_path.endswith('.lean'):
        raise CoProofError("Node URL does not map to a valid .lean file path.", code=400)

    bare_repo_path = RepoPool.ensure_repo_exists(str(project.id), project.remote_repo_url, auth_token=github_token)
    RepoPool.update_repo(str(project.id), project.remote_repo_url, auth_token=github_token)

    with read_only_worktree(bare_repo_path, branch=project.default_branch) as worktree_root:
        file_map = _collect_lean_files(worktree_root)
        file_map = _normalize_file_map_for_def_module(file_map)
        file_map[node_main_path] = lean_code
        def_context = _build_goaldef_from_project_goal(project.goal)
        verification_payload = _build_split_verification_payload(def_context, lean_code, project.goal)
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

    branch_name = f"solve-node-{str(node.id)[:8]}-{uuid.uuid4().hex[:6]}"
    with git_transaction(
        bare_repo_path,
        author_name=user.full_name,
        author_email=user.email,
        branch=branch_name,
        source_branch=project.default_branch,
    ) as worktree_root:
        if 'def.lean' in file_map:
            _write_text_file(worktree_root, 'def.lean', file_map['def.lean'])
        _write_text_file(worktree_root, node_main_path, lean_code)

    pr_title = f"Solve node {node.name} ({str(node.id)[:8]})"
    pr_body = (
        f"Action: solve_node\n"
        f"Project ID: {project.id}\n"
        f"Affected node ID: {node.id}\n"
        f"Affected node name: {node.name}\n"
    )

    pr_data = _open_pull_request(
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


@nodes_bp.route('/<uuid:project_id>/nodes/<uuid:node_id>/split', methods=['POST'])
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
    lean_code = _normalize_lean_imports(lean_code)

    user = User.query.get_or_404(user_id)
    project = NewProject.query.get_or_404(project_id)
    node = NewNode.query.filter_by(id=node_id, project_id=project.id).first_or_404()

    github_token = AuthService.refresh_github_token_if_needed(user)
    if not github_token:
        raise CoProofError("You must link your GitHub account.", code=400)

    node_main_path = _extract_repo_path_from_node_url(node.url)
    if not node_main_path or not node_main_path.endswith('.lean'):
        raise CoProofError("Node URL does not map to a valid .lean file path.", code=400)

    split_blocks = _extract_lemma_blocks(lean_code)
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

    updated_main = _build_split_main_content(lean_code, child_blocks)
    lemma_files, tex_files, lemma_names = _build_split_files(child_blocks)

    bare_repo_path = RepoPool.ensure_repo_exists(str(project.id), project.remote_repo_url, auth_token=github_token)
    RepoPool.update_repo(str(project.id), project.remote_repo_url, auth_token=github_token)

    with read_only_worktree(bare_repo_path, branch=project.default_branch) as worktree_root:
        file_map = _collect_lean_files(worktree_root)
        file_map = _normalize_file_map_for_def_module(file_map)
        file_map[node_main_path] = updated_main
        for path, content in lemma_files.items():
            file_map[path] = _normalize_lean_imports(content)

        def_context = _build_goaldef_from_project_goal(project.goal)
        verification_payload = _build_split_verification_payload(def_context, lean_code, project.goal)
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
    with git_transaction(
        bare_repo_path,
        author_name=user.full_name,
        author_email=user.email,
        branch=branch_name,
        source_branch=project.default_branch,
    ) as worktree_root:
        if 'def.lean' in file_map:
            _write_text_file(worktree_root, 'def.lean', file_map['def.lean'])
        _write_text_file(worktree_root, node_main_path, updated_main)
        for path, content in lemma_files.items():
            _write_text_file(worktree_root, path, content)
        for path, content in tex_files.items():
            _write_text_file(worktree_root, path, content)

    affected_nodes_text = ', '.join([node.name] + lemma_names)
    pr_title = f"Split node {node.name} ({str(node.id)[:8]}) into: {', '.join(lemma_names)}"
    pr_body = (
        f"Action: split_node\n"
        f"Project ID: {project.id}\n"
        f"Affected nodes: {affected_nodes_text}\n"
        f"Base node ID: {node.id}\n"
    )

    pr_data = _open_pull_request(
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


@nodes_bp.route('/<uuid:project_id>/pulls/<int:pr_number>/merge', methods=['POST'])
@jwt_required()
def merge_pull_request(project_id, pr_number):
    user_id = get_jwt_identity()
    user = User.query.get_or_404(user_id)
    project = NewProject.query.get_or_404(project_id)

    github_token = AuthService.refresh_github_token_if_needed(user)
    if not github_token:
        raise CoProofError("You must link your GitHub account.", code=400)

    pr_info = _get_pull_request(project.remote_repo_url, github_token, pr_number)
    if pr_info.get('base', {}).get('ref') != project.default_branch:
        raise CoProofError("PR base branch does not match project default branch.", code=400)

    if pr_info.get('merged'):
        metadata = _parse_pr_metadata(pr_info.get('body', ''))
        updates = _apply_post_merge_db_updates(project, metadata)
        db.session.commit()
        return jsonify({
            "status": "already_merged",
            "project_id": str(project.id),
            "pr_number": pr_number,
            "db_updates": updates,
        }), 200

    merge_result = _merge_pull_request(project.remote_repo_url, github_token, pr_number)
    metadata = _parse_pr_metadata(pr_info.get('body', ''))
    updates = _apply_post_merge_db_updates(project, metadata)
    db.session.commit()

    return jsonify({
        "status": "merged",
        "project_id": str(project.id),
        "pr_number": pr_number,
        "merge": merge_result,
        "db_updates": updates,
    }), 200


@nodes_bp.route('/<uuid:project_id>/nodes/<uuid:node_id>/verify', methods=['POST'])
@jwt_required()
def verify_node_import_tree(project_id, node_id):
    user_id = get_jwt_identity()
    user = User.query.get_or_404(user_id)
    project = NewProject.query.get_or_404(project_id)
    node = NewNode.query.filter_by(id=node_id, project_id=project.id).first_or_404()

    github_token = AuthService.refresh_github_token_if_needed(user)
    if not github_token:
        raise CoProofError("You must link your GitHub account.", code=400)

    entry_file = _extract_repo_path_from_node_url(node.url)
    if not entry_file or not entry_file.endswith('.lean'):
        raise CoProofError("Node URL does not map to a valid .lean file path.", code=400)

    bare_repo_path = RepoPool.ensure_repo_exists(str(project.id), project.remote_repo_url, auth_token=github_token)
    RepoPool.update_repo(str(project.id), project.remote_repo_url, auth_token=github_token)

    with read_only_worktree(bare_repo_path, branch=project.default_branch) as worktree_root:
        all_lean_files = _collect_lean_files(worktree_root)
        all_lean_files = _normalize_file_map_for_def_module(all_lean_files)

    if entry_file not in all_lean_files:
        raise CoProofError(f"Entry file not found in repo: {entry_file}", code=404)

    reachable_files, parent_map = _resolve_import_tree(entry_file, all_lean_files)
    reachable_map = {path: all_lean_files[path] for path in reachable_files if path in all_lean_files}

    verification = CompilerClient.verify_project_files(file_map=reachable_map, entry_file=entry_file)
    sorry_locations = _collect_sorry_locations(reachable_map)
    sorry_traces = _build_sorry_traces(entry_file, sorry_locations, parent_map)

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


@nodes_bp.route('/<uuid:project_id>/nodes/<uuid:node_id>/file', methods=['GET'])
@jwt_required()
def get_node_file_content(project_id, node_id):
    user_id = get_jwt_identity()
    user = User.query.get_or_404(user_id)
    project = NewProject.query.get_or_404(project_id)
    node = NewNode.query.filter_by(id=node_id, project_id=project.id).first_or_404()

    github_token = AuthService.refresh_github_token_if_needed(user)
    if not github_token:
        raise CoProofError("You must link your GitHub account.", code=400)

    node_main_path = _extract_repo_path_from_node_url(node.url)
    if not node_main_path or not node_main_path.endswith('.lean'):
        raise CoProofError("Node URL does not map to a valid .lean file path.", code=400)

    bare_repo_path = RepoPool.ensure_repo_exists(str(project.id), project.remote_repo_url, auth_token=github_token)
    RepoPool.update_repo(str(project.id), project.remote_repo_url, auth_token=github_token)

    with read_only_worktree(bare_repo_path, branch=project.default_branch) as worktree_root:
        file_map = _collect_lean_files(worktree_root)

    if node_main_path not in file_map:
        raise CoProofError(f"Node file not found in repo: {node_main_path}", code=404)

    return jsonify({
        "project_id": str(project.id),
        "node_id": str(node.id),
        "path": node_main_path,
        "content": file_map[node_main_path],
    }), 200


@nodes_bp.route('/<uuid:project_id>/pulls/open', methods=['GET'])
@jwt_required()
def list_open_pull_requests(project_id):
    user_id = get_jwt_identity()
    user = User.query.get_or_404(user_id)
    project = NewProject.query.get_or_404(project_id)

    github_token = AuthService.refresh_github_token_if_needed(user)
    if not github_token:
        raise CoProofError("You must link your GitHub account.", code=400)

    pulls = _list_open_pull_requests(project.remote_repo_url, github_token, project.default_branch)
    return jsonify({
        "project_id": str(project.id),
        "count": len(pulls),
        "pulls": pulls,
    }), 200


def _extract_repo_path_from_node_url(node_url):
    parsed = urlparse(node_url)
    marker = '/blob/'
    if marker not in parsed.path:
        return None
    _, blob_part = parsed.path.split(marker, 1)
    split_idx = blob_part.find('/')
    if split_idx == -1:
        return None
    return blob_part[split_idx + 1:]


def _module_to_relpath(module_name):
    module_name = module_name.strip()
    if not module_name:
        return None

    parts = [part.strip() for part in module_name.split('.') if part.strip()]
    cleaned_parts = []
    for part in parts:
        if part.startswith('«') and part.endswith('»'):
            part = part[1:-1]
        cleaned_parts.append(part)

    if not cleaned_parts:
        return None

    return '/'.join(cleaned_parts) + '.lean'


def _parse_import_modules(lean_content):
    modules = []
    for raw_line in lean_content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith('--'):
            continue
        if not line.startswith('import '):
            continue

        trailing = line[len('import '):].strip()
        if not trailing:
            continue
        modules.extend([part for part in trailing.split() if part])
    return modules


def _resolve_import_tree(entry_file, file_map):
    visited = set()
    stack = [entry_file]
    parent_map = {entry_file: None}

    while stack:
        current = stack.pop()
        if current in visited:
            continue
        visited.add(current)

        content = file_map.get(current)
        if content is None:
            continue

        for module in _parse_import_modules(content):
            rel_path = _module_to_relpath(module)
            if rel_path and rel_path in file_map and rel_path not in visited:
                if rel_path not in parent_map:
                    parent_map[rel_path] = current
                stack.append(rel_path)

    return visited, parent_map


def _build_path_to_file(target_file, parent_map):
    if target_file not in parent_map:
        return [target_file]

    path = []
    current = target_file
    while current is not None:
        path.append(current)
        current = parent_map.get(current)

    path.reverse()
    return path


def _build_sorry_traces(entry_file, sorry_locations, parent_map):
    traces = []
    for location in sorry_locations:
        target_file = location.get("file")
        path = _build_path_to_file(target_file, parent_map)
        traces.append({
            "file": target_file,
            "line": location.get("line"),
            "snippet": location.get("snippet", ""),
            "import_trace": path,
            "depth": max(0, len(path) - 1),
            "starts_at_entry": len(path) > 0 and path[0] == entry_file,
        })
    return traces


def _collect_sorry_locations(file_map):
    locations = []
    for rel_path, content in file_map.items():
        for line_no, line in enumerate(content.splitlines(), start=1):
            if re.search(r'\bsorry\b', line):
                locations.append({
                    "file": rel_path,
                    "line": line_no,
                    "snippet": line.strip(),
                })
    return locations


def _collect_lean_files(worktree_root):
    file_map = {}
    for root, _, files in os.walk(worktree_root):
        for file_name in files:
            if not file_name.endswith('.lean'):
                continue
            full_path = os.path.join(root, file_name)
            rel_path = os.path.relpath(full_path, worktree_root).replace('\\\\', '/')
            with open(full_path, 'r', encoding='utf-8') as file_handle:
                file_map[rel_path] = file_handle.read()
    return file_map


def _write_text_file(worktree_root, rel_path, content):
    full_path = os.path.join(worktree_root, rel_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, 'w', encoding='utf-8') as file_handle:
        file_handle.write(content)


def _extract_lemma_blocks(lean_code):
    pattern = re.compile(
        r'(^\s*(?:lemma|theorem)\s+([A-Za-z_][A-Za-z0-9_\']*)[\s\S]*?:=\s*by[\s\S]*?(?=^\s*(?:theorem|lemma|def|example)\s+[A-Za-z_]|\Z))',
        re.MULTILINE,
    )
    matches = pattern.findall(lean_code)
    blocks = []
    for raw_block, lemma_name in matches:
        blocks.append({
            'name': lemma_name,
            'content': raw_block.strip(),
        })
    return blocks


def _build_split_main_content(lean_code, lemma_blocks):
    updated_main = lean_code
    import_lines = []

    for lemma in lemma_blocks:
        updated_main = updated_main.replace(lemma['content'], '')
        folder_segment = _to_node_folder_segment(lemma['name'])
        lemma_rel_main = f"{folder_segment}/main.lean"
        module_name = _lean_module_from_path(lemma_rel_main)
        import_lines.append(f"import {module_name}")

    import_header = '\n'.join(import_lines)
    return _normalize_lean_imports(f"{import_header}\n\n{updated_main.strip()}\n")


def _build_split_files(lemma_blocks):
    lean_files = {}
    tex_files = {}
    lemma_names = []
    used_folder_names = set()

    for lemma in lemma_blocks:
        lemma_name = lemma['name']
        lemma_names.append(lemma_name)
        normalized_decl = _normalize_lemma_to_theorem(lemma['content'])
        folder_segment = _to_unique_node_folder_segment(lemma_name, used_folder_names)
        lemma_main_path = f"{folder_segment}/main.lean"
        lemma_tex_path = f"{folder_segment}/main.tex"

        lean_files[lemma_main_path] = f"import def\n\n{normalized_decl}\n"
        tex_files[lemma_tex_path] = (
            "\\begin{theorem}[" + lemma_name + "]\n"
            "Auto-generated lemma extracted from split operation.\n"
            "\\end{theorem}\n\n"
            "\\begin{proof}\n"
            "By \\texttt{sorry}.\n"
            "\\end{proof}\n"
        )

    return lean_files, tex_files, lemma_names


def _normalize_lean_imports(lean_code):
    normalized = re.sub(r'(?m)^\s*import\s+Def\s*$', 'import def', lean_code)
    return normalized


def _build_split_verification_payload(def_content, split_lean_code, project_goal=None):
    cleaned_split = re.sub(r'(?m)^\s*import\s+\S+\s*$', '', split_lean_code).strip()
    cleaned_split = _normalize_lemma_to_theorem(cleaned_split)
    expanded_split = _expand_goaldef_in_split_code(cleaned_split, project_goal)
    if expanded_split is not None:
        return expanded_split

    def_block = def_content.strip()

    if not def_block:
        return cleaned_split

    return f"{def_block}\n\n{cleaned_split}\n"


def _normalize_lemma_to_theorem(code):
    return re.sub(r'(?m)^(\s*)lemma(\s+)', r'\1theorem\2', code)


def _expand_goaldef_in_split_code(split_code, project_goal):
    if ': GoalDef' not in split_code:
        return None

    binder = _extract_goal_binder(project_goal)
    if binder is None:
        return None

    name, typ, proposition = binder
    rewritten = re.sub(
        r"theorem\s+root\s*:\s*GoalDef\s*:=\s*by",
        f"theorem root ({name} : {typ}) : {proposition} := by",
        split_code,
        count=1,
    )

    rewritten = re.sub(
        rf"(?m)^\s*intro\s+{re.escape(name)}\s*$\n?",
        "",
        rewritten,
        count=1,
    )

    return rewritten.strip() + "\n"


def _extract_goal_binder(project_goal):
    expr = _normalize_goal_expression((project_goal or '').strip())

    match = re.match(r"^∀\s*\(([^:]+):\s*([^\)]+)\),\s*(.+)$", expr, re.DOTALL)
    if match:
        return match.group(1).strip(), match.group(2).strip(), match.group(3).strip()

    match = re.match(r"^([A-Za-z_][A-Za-z0-9_']*)\s*:\s*([^,]+),\s*(.+)$", expr, re.DOTALL)
    if match:
        return match.group(1).strip(), match.group(2).strip(), match.group(3).strip()

    return None


def _build_goaldef_from_project_goal(project_goal):
    goal_expr = _normalize_goal_expression((project_goal or '').strip())
    if not goal_expr:
        return ""
    return "-- Generated from project goal\nabbrev GoalDef : Prop := " + goal_expr + "\n"


def _normalize_goaldef_file_content(content):
    text = content.strip()

    by_exact_pattern = re.compile(
        r"def\s+GoalDef\s*:\s*Prop\s*:=\s*by\s*exact\s*\((.*?)\)",
        re.DOTALL,
    )
    direct_pattern = re.compile(
        r"def\s+GoalDef\s*:\s*Prop\s*:=\s*(.+)",
        re.DOTALL,
    )

    goal_expr = None
    match = by_exact_pattern.search(text)
    if match:
        goal_expr = match.group(1).strip()
    else:
        match = direct_pattern.search(text)
        if match:
            goal_expr = match.group(1).strip()

    if not goal_expr:
        return content

    goal_expr = _normalize_goal_expression(goal_expr)
    return "-- Generated from goal prompt\ndef GoalDef : Prop := " + goal_expr + "\n"


def _normalize_goal_expression(goal_expr):
    expr = goal_expr.strip()

    full_decl_match = re.search(
        r"def\s+GoalDef\s*:\s*Prop\s*:=\s*(.*)",
        expr,
        re.DOTALL,
    )
    if full_decl_match:
        expr = full_decl_match.group(1).strip()

    by_exact_decl_match = re.search(
        r"by\s*exact\s*\((.*)\)",
        expr,
        re.DOTALL,
    )
    if by_exact_decl_match:
        expr = by_exact_decl_match.group(1).strip()

    expr = re.sub(r"^--.*$", "", expr, flags=re.MULTILINE).strip()

    exact_match = re.match(r"^exact\s*\((.*)\)$", expr, re.DOTALL)
    if exact_match:
        expr = exact_match.group(1).strip()

    if expr.startswith('(') and expr.endswith(')'):
        inner = expr[1:-1].strip()
        if inner:
            expr = inner

    if expr.startswith('∀'):
        expr = _canonicalize_forall_binders(expr)
        return expr
    if expr.lower().startswith('forall '):
        expr = '∀ ' + expr[7:].strip()
        expr = _canonicalize_forall_binders(expr)
        return expr
    if re.match(r"^[A-Za-z_][A-Za-z0-9_']*\s*:\s*[^,]+,\s*.+$", expr):
        expr = f"∀ {expr}"
        expr = _canonicalize_forall_binders(expr)
        return expr
    return expr


def _canonicalize_forall_binders(expr):
    # Converts "∀ n : Nat, ..." into "∀ (n : Nat), ..." for compatibility.
    match = re.match(r"^∀\s*([A-Za-z_][A-Za-z0-9_']*)\s*:\s*([^,]+),\s*(.+)$", expr, re.DOTALL)
    if not match:
        return expr

    name = match.group(1).strip()
    typ = match.group(2).strip()
    rest = match.group(3).strip()
    return f"∀ ({name} : {typ}), {rest}"


def _normalize_file_map_for_def_module(file_map):
    normalized = {}
    for rel_path, content in file_map.items():
        normalized[rel_path] = _normalize_lean_imports(content)

    def_content = normalized.get('def.lean')
    if def_content is None and 'Def.lean' in normalized:
        def_content = normalized['Def.lean']

    if def_content is not None:
        normalized['def.lean'] = _normalize_goaldef_file_content(def_content)

    return normalized


def _lean_module_from_path(rel_lean_path):
    path_no_ext = rel_lean_path[:-5] if rel_lean_path.endswith('.lean') else rel_lean_path
    parts = [part for part in path_no_ext.replace('\\\\', '/').split('/') if part]

    module_parts = []
    for part in parts:
        if re.match(r'^[A-Z][A-Za-z0-9_]*$', part):
            module_parts.append(part)
        else:
            module_parts.append(f"«{part}»")

    return '.'.join(module_parts)


def _to_node_folder_segment(name):
    cleaned = re.sub(r"[^A-Za-z0-9_]", "_", name).strip("_")
    if not cleaned:
        cleaned = "Node"
    cleaned = cleaned.lower()
    if cleaned[0].isdigit():
        cleaned = f"node_{cleaned}"
    return cleaned


def _to_unique_node_folder_segment(name, used_folder_names):
    base = _to_node_folder_segment(name)
    candidate = base
    counter = 2
    while candidate in used_folder_names:
        candidate = f"{base}{counter}"
        counter += 1
    used_folder_names.add(candidate)
    return candidate


def _extract_github_full_name(remote_repo_url):
    parsed = urlparse(remote_repo_url)
    repo_path = parsed.path.strip('/')
    if repo_path.endswith('.git'):
        repo_path = repo_path[:-4]
    if '/' not in repo_path:
        raise CoProofError("Invalid GitHub remote URL format.", code=400)
    return repo_path


def _github_headers(token):
    return {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }


def _get_pull_request(remote_repo_url, token, pr_number):
    full_name = _extract_github_full_name(remote_repo_url)
    response = requests.get(
        f"https://api.github.com/repos/{full_name}/pulls/{pr_number}",
        headers=_github_headers(token),
        timeout=20,
    )

    if response.status_code == 200:
        return response.json()
    if response.status_code == 404:
        raise CoProofError(f"PR #{pr_number} not found in repository.", code=404)
    if response.status_code in (401, 403):
        raise CoProofError("GitHub authentication failed while reading PR.", code=401)

    raise CoProofError(f"GitHub PR read failed: {response.text}", code=502)


def _list_open_pull_requests(remote_repo_url, token, base_branch):
    full_name = _extract_github_full_name(remote_repo_url)
    response = requests.get(
        f"https://api.github.com/repos/{full_name}/pulls",
        headers=_github_headers(token),
        params={"state": "open", "base": base_branch, "per_page": 100},
        timeout=20,
    )

    if response.status_code == 200:
        pulls = response.json()
        return [
            {
                "number": pr.get("number"),
                "title": pr.get("title"),
                "url": pr.get("html_url"),
                "head": pr.get("head", {}).get("ref"),
                "base": pr.get("base", {}).get("ref"),
                "author": (pr.get("user") or {}).get("login"),
                "created_at": pr.get("created_at"),
                "updated_at": pr.get("updated_at"),
            }
            for pr in pulls
        ]
    if response.status_code in (401, 403):
        raise CoProofError("GitHub authentication failed while listing PRs.", code=401)

    raise CoProofError(f"GitHub PR list failed: {response.text}", code=502)


def _merge_pull_request(remote_repo_url, token, pr_number):
    full_name = _extract_github_full_name(remote_repo_url)
    response = requests.put(
        f"https://api.github.com/repos/{full_name}/pulls/{pr_number}/merge",
        headers=_github_headers(token),
        json={"merge_method": "merge"},
        timeout=20,
    )

    if response.status_code == 200:
        return response.json()
    if response.status_code == 405:
        raise CoProofError("PR is not mergeable (possibly conflicts or already merged).", code=409)
    if response.status_code in (401, 403):
        raise CoProofError("GitHub authentication failed while merging PR.", code=401)
    if response.status_code == 404:
        raise CoProofError(f"PR #{pr_number} not found in repository.", code=404)

    raise CoProofError(f"GitHub PR merge failed: {response.text}", code=502)


def _parse_pr_metadata(pr_body):
    body = pr_body or ""
    metadata = {
        "action": None,
        "base_node_id": None,
        "affected_nodes": [],
        "affected_node_id": None,
    }

    action_match = re.search(r"(?im)^Action:\s*(.+)$", body)
    if action_match:
        metadata["action"] = action_match.group(1).strip()

    base_match = re.search(r"(?im)^Base node ID:\s*([0-9a-fA-F\-]{36})$", body)
    if base_match:
        metadata["base_node_id"] = base_match.group(1).strip()

    affected_nodes_match = re.search(r"(?im)^Affected nodes:\s*(.+)$", body)
    if affected_nodes_match:
        metadata["affected_nodes"] = [
            part.strip() for part in affected_nodes_match.group(1).split(',') if part.strip()
        ]

    affected_node_id_match = re.search(r"(?im)^Affected node ID:\s*([0-9a-fA-F\-]{36})$", body)
    if affected_node_id_match:
        metadata["affected_node_id"] = affected_node_id_match.group(1).strip()

    return metadata


def _apply_post_merge_db_updates(project, metadata):
    action = metadata.get("action")
    updates = {
        "action": action,
        "updated_nodes": [],
        "created_nodes": [],
    }

    if action == 'solve_node':
        target_id = metadata.get("affected_node_id")
        if target_id:
            target = NewNode.query.filter_by(id=target_id, project_id=project.id).first()
            if target:
                target.state = 'validated'
                updates["updated_nodes"].append({
                    "id": str(target.id),
                    "name": target.name,
                    "state": target.state,
                })
        return updates

    if action == 'split_node':
        base_node_id = metadata.get("base_node_id")
        base_node = None
        if base_node_id:
            base_node = NewNode.query.filter_by(id=base_node_id, project_id=project.id).first()
            if base_node:
                base_node.state = 'sorry'
                updates["updated_nodes"].append({
                    "id": str(base_node.id),
                    "name": base_node.name,
                    "state": base_node.state,
                })

        affected_nodes = metadata.get("affected_nodes") or []
        if not base_node or not affected_nodes:
            return updates

        child_names = [name for name in affected_nodes if name.lower() != base_node.name.lower()]
        used_folder_names = set()

        for child_name in child_names:
            existing = NewNode.query.filter_by(
                project_id=project.id,
                parent_node_id=base_node.id,
                name=child_name,
            ).first()
            if existing:
                existing.state = 'sorry'
                updates["updated_nodes"].append({
                    "id": str(existing.id),
                    "name": existing.name,
                    "state": existing.state,
                })
                continue

            folder_segment = _to_unique_node_folder_segment(child_name, used_folder_names)
            node_url = f"{project.url}/blob/{project.default_branch}/{folder_segment}/main.lean"
            new_child = NewNode(
                name=child_name,
                url=node_url,
                project_id=project.id,
                parent_node_id=base_node.id,
                state='sorry',
            )
            db.session.add(new_child)
            db.session.flush()
            updates["created_nodes"].append({
                "id": str(new_child.id),
                "name": new_child.name,
                "state": new_child.state,
                "url": new_child.url,
            })

    return updates


def _open_pull_request(remote_repo_url, token, title, body, head_branch, base_branch):
    full_name = _extract_github_full_name(remote_repo_url)
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    payload = {
        "title": title,
        "body": body,
        "head": head_branch,
        "base": base_branch,
    }

    response = requests.post(
        f"https://api.github.com/repos/{full_name}/pulls",
        json=payload,
        headers=headers,
        timeout=20,
    )

    if response.status_code in (200, 201):
        return response.json()
    if response.status_code == 422:
        raise CoProofError(f"Unable to create PR: {response.text}", code=400)
    if response.status_code in (401, 403):
        raise CoProofError("GitHub authentication failed while creating PR.", code=401)

    raise CoProofError(f"GitHub PR creation failed: {response.text}", code=502)
    


# @nodes_bp.route('/tools/verify-code', methods=['POST'])
# @jwt_required()
# def verify_code_async():
#     """
#     Takes Lean Code -> Returns Async Job ID for verification.
#     Allows user to check "Truthness" of manual edits without saving to Git.
#     """
#     user_id = get_jwt_identity()
#     data = request.get_json()
    
#     code = data.get('code')
#     # Optional: list of dependency names if the microservice needs them to build context
#     dependencies = data.get('dependencies', []) 
    
#     if not code:
#         return jsonify({"error": "No code provided"}), 400

#     # 1. Create Job Tracker
#     job = AsyncJob(
#         user_id=user_id,
#         celery_task_id="pending",
#         job_type="git_clone", # We can reuse an enum or add 'code_verification' to the DB Enum later
#         status="queued"
#     )
#     db.session.add(job)
#     db.session.commit()
    
#     # 2. Dispatch Celery Task (The new one in git_tasks)
#     task = task_verify_lean_code.delay(str(job.id), code, dependencies)
    
#     # 3. Update Task ID
#     job.celery_task_id = task.id
#     db.session.commit()
    
#     return jsonify({
#         "job_id": job.id, 
#         "status": "queued",
#         "message": "Verification started"
#     }), 202