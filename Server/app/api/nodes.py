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
        verification = CompilerClient.verify_project_files(file_map=file_map, entry_file=node_main_path)

    if not verification.get('valid'):
        return jsonify({
            "status": "compile_error",
            "node_id": str(node.id),
            "errors": verification.get('errors', []),
            "verification": verification,
        }), 400

    branch_name = f"solve-node-{str(node.id)[:8]}-{uuid.uuid4().hex[:6]}"
    with git_transaction(
        bare_repo_path,
        author_name=user.full_name,
        author_email=user.email,
        branch=branch_name,
        source_branch=project.default_branch,
    ) as worktree_root:
        if 'Def.lean' in file_map:
            _write_text_file(worktree_root, 'Def.lean', file_map['Def.lean'])
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

    lemma_blocks = _extract_lemma_blocks(lean_code)
    if not lemma_blocks:
        return jsonify({"error": "No lemma blocks found in lean_code for split operation."}), 400

    updated_main = _build_split_main_content(lean_code, lemma_blocks)
    lemma_files, tex_files, lemma_names = _build_split_files(lemma_blocks)

    bare_repo_path = RepoPool.ensure_repo_exists(str(project.id), project.remote_repo_url, auth_token=github_token)
    RepoPool.update_repo(str(project.id), project.remote_repo_url, auth_token=github_token)

    with read_only_worktree(bare_repo_path, branch=project.default_branch) as worktree_root:
        file_map = _collect_lean_files(worktree_root)
        file_map = _normalize_file_map_for_def_module(file_map)
        file_map[node_main_path] = updated_main
        for path, content in lemma_files.items():
            file_map[path] = _normalize_lean_imports(content)

        verification = CompilerClient.verify_project_files(
            file_map=file_map,
            entry_file=node_main_path,
        )

    if not verification.get('valid'):
        return jsonify({
            "status": "compile_error",
            "node_id": str(node.id),
            "errors": verification.get('errors', []),
            "verification": verification,
        }), 400

    branch_name = f"split-node-{str(node.id)[:8]}-{uuid.uuid4().hex[:6]}"
    with git_transaction(
        bare_repo_path,
        author_name=user.full_name,
        author_email=user.email,
        branch=branch_name,
        source_branch=project.default_branch,
    ) as worktree_root:
        if 'Def.lean' in file_map:
            _write_text_file(worktree_root, 'Def.lean', file_map['Def.lean'])
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
        r'(^\s*lemma\s+([A-Za-z_][A-Za-z0-9_\']*)[\s\S]*?:=\s*by[\s\S]*?(?=^\s*(theorem|lemma|def|example)\s+[A-Za-z_]|\Z))',
        re.MULTILINE,
    )
    matches = pattern.findall(lean_code)
    blocks = []
    for raw_block, lemma_name, _ in matches:
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
        module_segment = _to_module_segment(lemma['name'])
        lemma_rel_module = f"Lemmas/{module_segment}.lean"
        module_name = _lean_module_from_path(lemma_rel_module)
        import_lines.append(f"import {module_name}")

    import_header = '\n'.join(import_lines)
    return _normalize_lean_imports(f"{import_header}\n\n{updated_main.strip()}\n")


def _build_split_files(lemma_blocks):
    lean_files = {}
    tex_files = {}
    lemma_names = []
    namespace_imports = []

    for lemma in lemma_blocks:
        lemma_name = lemma['name']
        lemma_names.append(lemma_name)
        module_segment = _to_module_segment(lemma_name)
        lemma_main_path = f"Lemmas/{module_segment}/Main.lean"
        lemma_module_path = f"Lemmas/{module_segment}.lean"
        lemma_tex_path = f"Lemmas/{module_segment}/main.tex"
        lemma_main_module = _lean_module_from_path(lemma_main_path)
        lemma_module = _lean_module_from_path(lemma_module_path)

        lean_files[lemma_main_path] = f"import Def\n\n{lemma['content']}\n"
        lean_files[lemma_module_path] = f"import {lemma_main_module}\n"
        namespace_imports.append(f"import {lemma_module}")
        tex_files[lemma_tex_path] = (
            "\\begin{theorem}[" + lemma_name + "]\n"
            "Auto-generated lemma extracted from split operation.\n"
            "\\end{theorem}\n\n"
            "\\begin{proof}\n"
            "By \\texttt{sorry}.\n"
            "\\end{proof}\n"
        )

    if namespace_imports:
        lean_files['Lemmas.lean'] = '\n'.join(namespace_imports) + '\n'

    return lean_files, tex_files, lemma_names


def _normalize_lean_imports(lean_code):
    return re.sub(r'(?m)^\s*import\s+def\s*$', 'import Def', lean_code)


def _normalize_goaldef_file_content(content):
    pattern = re.compile(r"def\s+GoalDef\s*:\s*Prop\s*:=\s*by\s*exact\s*\((.*?)\)\s*$", re.DOTALL)
    match = pattern.search(content.strip())
    if not match:
        return content

    goal_expr = match.group(1).strip()
    if re.match(r"^[A-Za-z_][A-Za-z0-9_']*\s*:\s*[^,]+,\s*.+$", goal_expr):
        goal_expr = f"∀ {goal_expr}"

    return "-- Generated from goal prompt\ndef GoalDef : Prop := " + goal_expr + "\n"


def _normalize_file_map_for_def_module(file_map):
    normalized = {}
    for rel_path, content in file_map.items():
        normalized[rel_path] = _normalize_lean_imports(content)

    def_content = normalized.get('Def.lean')
    if def_content is None and 'def.lean' in normalized:
        def_content = normalized['def.lean']

    if def_content is not None:
        normalized['Def.lean'] = _normalize_goaldef_file_content(def_content)

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


def _to_module_segment(name):
    cleaned = re.sub(r"[^A-Za-z0-9_]", "_", name).strip("_")
    if not cleaned:
        cleaned = "Lemma"
    if cleaned[0].isdigit():
        cleaned = f"L_{cleaned}"

    parts = [part for part in cleaned.split('_') if part]
    if not parts:
        return "Lemma"

    return ''.join(part[:1].upper() + part[1:] for part in parts)


def _extract_github_full_name(remote_repo_url):
    parsed = urlparse(remote_repo_url)
    repo_path = parsed.path.strip('/')
    if repo_path.endswith('.git'):
        repo_path = repo_path[:-4]
    if '/' not in repo_path:
        raise CoProofError("Invalid GitHub remote URL format.", code=400)
    return repo_path


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