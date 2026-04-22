from flask import Blueprint, request, jsonify
from flask_caching import logger
from flask_jwt_extended import jwt_required, get_jwt_identity
import re
import uuid
from app.models.user import User
from app.models.user_api_key import UserApiKey
from app.services.computation_service import ComputationService
from app.services.auth_service import AuthService
from app.services.integrations.computation_client import ComputationClient
from app.services.integrations.compiler_client import CompilerClient
from app.services.integrations.translate_client import TranslateClient
from app.services.github_service import GitHubService
from app.services.lean_service import LeanService
from app.models.project import Project
from app.models.node import Node
from app.exceptions import CoProofError
from app.extensions import db

nodes_bp = Blueprint('nodes', __name__, url_prefix='/api/v1/nodes')

# System prompt used when generating a .tex from a solved Lean theorem.
# Uses the same **Theorem.** / *Proof.* Markdown bold/italic format as the
# create-project FL2NL preview, so the workspace TeX renderer renders them
# consistently with <strong> / <em>.
_SOLVE_FL2NL_SYSTEM_PROMPT = (
    "You are an expert in formal mathematics and mathematical writing. "
    "Given a Lean 4 theorem with its proof, produce a structured mathematical exposition in natural language. "
    "For EACH theorem or lemma found in the input, output exactly the following structure:\n\n"
    "**Theorem.** <state the mathematical claim clearly, using LaTeX notation ($...$ inline, $$...$$ display)>\n\n"
    "*Proof.* <explain the proof strategy and key steps in natural language, using LaTeX where appropriate. "
    "If the proof body contains `sorry` or is otherwise unsolved, write exactly \"Unsolved.\" instead.>\n\n"
    "Rules:\n"
    "- Capture the mathematical ESSENCE of what the Lean statement expresses. Do NOT attempt to re-prove anything.\n"
    "- Do NOT reproduce any Lean 4 syntax in your output.\n"
    "- Do NOT add commentary outside the Theorem/Proof blocks.\n"
    "- If there are multiple theorems, repeat the Theorem/Proof block for each one in order."
)


def _try_generate_tex(user_id: str, lean_code: str) -> str | None:
    """
    Attempt FL→NL tex generation using the user's first available saved API key.
    Returns a LaTeX string on success, None if no key is available or generation fails.
    """
    record = UserApiKey.query.filter_by(user_id=user_id).order_by(UserApiKey.model_id).first()
    if not record:
        return None
    try:
        api_key = record.decrypt_key().strip()
    except Exception as exc:
        logger.warning('_try_generate_tex: key decryption failed: %s', exc)
        return None

    natural_text = TranslateClient.fl2nl_synchronous(
        payload={
            'lean_code': lean_code,
            'model_id': record.model_id,
            'api_key': api_key,
            'system_prompt': _SOLVE_FL2NL_SYSTEM_PROMPT,
        },
        timeout=120,
    )
    return natural_text or None


# System prompt for split child nodes — they have `sorry` proofs, so the proof
# section should say "Unsolved." while still describing the claim.
# The label (derived from the Lean name) is injected by the caller as a comment
# in the .tex file; the model itself is instructed to echo it in the header.
_SPLIT_CHILD_FL2NL_SYSTEM_PROMPT = (
    "You are an expert in formal mathematics and mathematical writing. "
    "Given a Lean 4 theorem or lemma (its proof may be `sorry` or incomplete), "
    "produce a structured mathematical exposition in natural language. "
    "For EACH theorem or lemma found in the input, output exactly the following structure:\n\n"
    "**Theorem (*<Name>*).** <state the mathematical claim clearly, using LaTeX notation ($...$ inline, $$...$$ display)>\n\n"
    "*Proof.* <If the proof body contains `sorry` or is otherwise unsolved, write exactly \"Unsolved.\" "
    "Otherwise explain the proof strategy and key steps in natural language with LaTeX where appropriate.>\n\n"
    "Rules:\n"
    "- Replace *<Name>* with a short human-readable name derived from the Lean theorem/lemma identifier "
    "(split on underscores and camelCase, title-case each word — e.g. `myLemmaFoo` → `My Lemma Foo`).\n"
    "- The name MUST appear in italics inside the parentheses, immediately after **Theorem**, e.g. **Theorem (*My Lemma Foo*)**.\n"
    "- Do NOT reproduce any Lean 4 syntax in your output.\n"
    "- Do NOT add commentary outside the Theorem/Proof blocks.\n"
    "- If there are multiple theorems, repeat the block for each one in order."
)


def _split_parent_fl2nl_system_prompt(child_labels: list[str]) -> str:
    """
    Build the system prompt for the parent node after a split.
    The parent proof should explicitly reference the child lemmas by their labels.
    Labels are stable identifiers derived from Lean theorem names so they remain
    consistent across later solve/split operations on the child nodes.
    """
    child_ref_hint = ', '.join(f'\\textbf{{{label}}}' for label in child_labels)
    return (
        "You are an expert in formal mathematics and mathematical writing. "
        "Given a Lean 4 theorem whose proof delegates to child lemmas, "
        "produce a structured mathematical exposition in natural language. "
        "For EACH theorem or lemma found in the input, output exactly the following structure:\n\n"
        "**Theorem.** <state the mathematical claim clearly, using LaTeX notation ($...$ inline, $$...$$ display)>\n\n"
        "*Proof.* <explain how the proof follows from the child lemmas. "
        f"You MUST reference the following sub-results by their labels: {child_ref_hint}. "
        "Use LaTeX where appropriate.>\n\n"
        "Rules:\n"
        "- Do NOT reproduce any Lean 4 syntax in your output.\n"
        "- Do NOT add commentary outside the Theorem/Proof blocks.\n"
        "- Reference each child lemma label exactly as given (they are stable identifiers).\n"
        "- If there are multiple theorems, repeat the block for each one in order."
    )


def _lean_name_to_label(lean_name: str) -> str:
    """
    Convert a Lean theorem/lemma name to a stable human-readable label.
    E.g. 'myLemmaFoo' -> 'My Lemma Foo', 'my_lemma_foo' -> 'My Lemma Foo'.
    This label is used as the \\textbf{} reference in parent .tex files and
    as the display name in child .tex files, so it remains consistent regardless
    of future operations (solve/split) on the child node.
    """
    # Split on underscores and camelCase boundaries
    import re as _re
    s = lean_name.replace('_', ' ')
    s = _re.sub(r'([a-z])([A-Z])', r'\1 \2', s)
    return s.title()


def _resolve_api_key(user_id: str, model_id: str, api_key_body: str) -> str | None:
    """Resolve api_key from request body or user's saved key. Returns None if unavailable."""
    if api_key_body:
        return api_key_body
    record = UserApiKey.query.filter_by(user_id=user_id, model_id=model_id).first()
    if not record:
        return None
    try:
        return record.decrypt_key().strip() or None
    except Exception as exc:
        logger.warning('_resolve_api_key: decryption failed: %s', exc)
        return None


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


@nodes_bp.route('/tools/verify-snippet', methods=['POST'])
def verify_snippet_public():
    """
    Public endpoint: dispatches a Lean 4 snippet for verification.
    Accepts JSON { "code": "..." } or multipart .lean file.
    Returns { task_id } immediately (non-blocking).
    """
    code = None

    if request.content_type and 'multipart/form-data' in request.content_type:
        file = request.files.get('file')
        if not file:
            return jsonify({"error": "No file provided"}), 400
        filename = file.filename or 'upload.lean'
        if not filename.endswith('.lean'):
            return jsonify({"error": "Only .lean files are accepted"}), 400
        code = file.read().decode('utf-8', errors='replace')
    else:
        data = request.get_json(silent=True) or {}
        code = data.get('code', '').strip()

    if not code:
        return jsonify({"error": "No Lean code provided"}), 400

    if len(code) > 100_000:
        return jsonify({"error": "Code exceeds maximum allowed size (100 KB)"}), 413

    try:
        celery_app = CompilerClient._get_celery()
        task = celery_app.send_task(
            'tasks.verify_snippet',
            args=[code, 'snippet.lean'],
            queue=CompilerClient.LEAN_QUEUE_NAME,
        )
        return jsonify({"task_id": task.id}), 202
    except Exception as e:
        return jsonify({"error": str(e)}), 503


@nodes_bp.route('/tools/verify-snippet/<task_id>/result', methods=['GET'])
def get_snippet_result(task_id):
    """
    Polls the result of a previously submitted snippet verification.
    Returns the VerifyCompilerResult when ready, or { status: 'pending' } with HTTP 202.
    """
    try:
        celery_app = CompilerClient._get_celery()
        async_result = celery_app.AsyncResult(task_id)
        if async_result.ready():
            if async_result.successful():
                return jsonify(async_result.result), 200
            return jsonify({"error": "Lean verification task failed"}), 500
        return jsonify({"status": "pending"}), 202
    except Exception as e:
        return jsonify({"error": str(e)}), 503


@nodes_bp.route('/<uuid:project_id>/<uuid:node_id>/solve', methods=['POST'])
@jwt_required()
def solve_node(project_id, node_id):
    """
    Receives a complete Lean solution for a node main.lean, verifies it, writes it in a feature branch,
    and opens a PR targeting main/default branch. Also runs FL→NL to generate an updated .tex file
    which is included in the same PR. model_id is required for this step.
    """
    user_id = get_jwt_identity()
    data = request.get_json() or {}
    lean_code = data.get('lean_code') or data.get('code')
    model_id = (data.get('model_id') or '').strip()
    api_key_body = (data.get('api_key') or '').strip()

    if not lean_code:
        return jsonify({"error": "Missing payload: lean_code"}), 400
    if not model_id:
        return jsonify({"error": "Missing payload: model_id (required to generate .tex)"}), 400
    lean_code = LeanService.normalize_lean_imports(lean_code)

    user = User.query.get_or_404(user_id)
    project = Project.query.get_or_404(project_id)
    node = Node.query.filter_by(id=node_id, project_id=project.id).first_or_404()
    ComputationService.ensure_proof_node(node)

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

    # If the submitted code declared top-level imports (e.g. `import Mathlib`) that
    # build_verify_payload strips out, but the payload doesn't already start with
    # those imports, prepend them so the compiler context matches what NL2FL verified.
    submitted_imports = re.findall(r'(?m)^\s*(import\s+\S+)\s*$', lean_code)
    payload_import_set = set(re.findall(r'(?m)^\s*(import\s+\S+)\s*$', verification_payload))
    missing_imports = [imp for imp in submitted_imports
                       if imp not in payload_import_set
                       and 'Definitions' not in imp]
    if missing_imports:
        verification_payload = '\n'.join(missing_imports) + '\n\n' + verification_payload

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

    # Resolve API key: prefer request body, fall back to user's saved key for this model.
    api_key = _resolve_api_key(user_id, model_id, api_key_body)

    if not api_key:
        return jsonify({
            "error": "api_key is required (provide in body or save one for this model via /api/v1/translate/api-key)"
        }), 400

    # Generate updated .tex — this is mandatory; we do not open the PR if it fails.
    tex_path = node_main_path.rsplit('/', 1)[0] + '/main.tex' if '/' in node_main_path else 'main.tex'
    generated_tex = TranslateClient.fl2nl_synchronous(
        payload={
            'lean_code': lean_code,
            'model_id': model_id,
            'api_key': api_key,
            'system_prompt': _SOLVE_FL2NL_SYSTEM_PROMPT,
        },
        timeout=120,
    )
    if not generated_tex:
        return jsonify({
            "error": "FL→NL generation failed or timed out. The .tex could not be produced. "
                     "Check that the model and API key are correct and the NL2FL worker is running."
        }), 502

    files_to_commit[tex_path] = generated_tex
    logger.info('solve_node: included generated .tex at %s', tex_path)

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
        f"Includes: updated main.tex (generated via FL→NL)\n"
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
        "tex_generated": True,
        "pull_request": {
            "number": pr_data.get('number'),
            "title": pr_data.get('title'),
            "url": pr_data.get('html_url'),
        },
    }), 201


@nodes_bp.route('/<uuid:project_id>/<uuid:node_id>/children/computation', methods=['POST'])
@jwt_required()
def create_computation_child_node(project_id, node_id):
    """Create a computation child node through a feature-branch PR, mirroring split/solve workflow."""
    user_id = get_jwt_identity()
    data = request.get_json() or {}

    user = User.query.get_or_404(user_id)
    project = Project.query.get_or_404(project_id)
    parent_node = Node.query.filter_by(id=node_id, project_id=project.id).first_or_404()
    ComputationService.ensure_proof_node(parent_node)
    child_name = ComputationService.build_computation_child_name(parent_node.name)

    github_token = AuthService.refresh_github_token_if_needed(user)
    if not github_token:
        raise CoProofError("You must link your GitHub account.", code=400)

    existing = Node.query.filter_by(
        project_id=project.id,
        parent_node_id=parent_node.id,
        node_kind='computation',
    ).first()
    if existing:
        return jsonify({
            "error": "The selected parent already has a computation child.",
            "node_id": str(existing.id),
        }), 409

    parent_main_path = GitHubService.extract_repo_path_from_node_url(parent_node.url)
    if not parent_main_path or not parent_main_path.endswith('.lean'):
        raise CoProofError("Parent node URL does not map to a valid .lean file path.", code=400)

    used_folder_names = set()
    siblings = Node.query.filter_by(project_id=project.id, parent_node_id=parent_node.id).all()
    for sibling in siblings:
        sibling_path = GitHubService.extract_repo_path_from_node_url(sibling.url) or ''
        if '/' in sibling_path:
            used_folder_names.add(sibling_path.rsplit('/', 2)[-2])

    folder_segment = LeanService.to_unique_node_folder_segment(child_name, used_folder_names)

    file_map = GitHubService.get_repository_files_map(
        remote_repo_url=project.remote_repo_url,
        token=github_token,
        branch=project.default_branch,
        extensions=('.lean',),
    )
    file_map = LeanService.normalize_file_map_for_def_module(file_map)

    if parent_main_path not in file_map:
        raise CoProofError(f"Parent Lean file not found in repo: {parent_main_path}", code=404)

    # Extract parent theorem signature from the parent's main.lean
    parent_main_content = file_map[parent_main_path]
    parent_signature_data = ComputationService.extract_theorem_signature_from_lean(
        parent_main_content, 
        parent_node.name
    )
    if not parent_signature_data:
        raise CoProofError(
            f"Could not extract theorem signature for '{parent_node.name}' from parent node. "
            "Parent must have a theorem/lemma with matching name followed by its type.",
            code=400
        )

    child_files = ComputationService.build_computation_child_artifacts(
        child_name=child_name,
        folder_segment=folder_segment,
        parent_theorem_signature=parent_signature_data['signature'],
    )

    parent_main_with_injection = ComputationService.inject_child_import_and_usage(
        parent_main_content,
        child_files['child_main_path'],
        child_files['theorem_name'],
        parent_signature_data['explicit_binder_names'],
    )

    # Verify the combined parent (with injection) + child axiom compile together
    verification_file_map = dict(file_map)
    verification_file_map[parent_main_path] = parent_main_with_injection
    verification_file_map[child_files['child_main_path']] = child_files['child_main_content']

    reachable_files, parent_map = LeanService.resolve_import_tree(parent_main_path, verification_file_map)
    reachable_map = {path: verification_file_map[path] for path in reachable_files if path in verification_file_map}
    verification_payload = LeanService.build_verify_payload_from_reachable_map(
        reachable_map=reachable_map,
        entry_file=parent_main_path,
        parent_map=parent_map,
        project_goal=project.goal,
    )
    verification = CompilerClient.verify_snippet(verification_payload)
    if not verification.get('valid'):
        return jsonify({
            "status": "compile_error",
            "action": "create_computation_node",
            "project_id": str(project.id),
            "parent_node_id": str(parent_node.id),
            "errors": verification.get('errors', []),
            "verification": verification,
        }), 400

    files_to_commit = {
        parent_main_path: parent_main_with_injection,
        child_files['child_main_path']: child_files['child_main_content'],
        child_files['child_tex_path']: child_files['child_tex_content'],
        child_files['child_program_path']: child_files['child_program_template'],
    }
    for definitions_path in LeanService.definition_file_paths(file_map):
        files_to_commit[definitions_path] = file_map[definitions_path]

    branch_name = f"create-compute-node-{str(parent_node.id)[:8]}-{uuid.uuid4().hex[:6]}"
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
        commit_message=f"Create computation node {child_name} under {parent_node.name} ({str(parent_node.id)[:8]}) via CoProof",
    )

    affected_nodes_text = f"{parent_node.name}, {child_name}"
    pr_title = f"Create computation node {child_name} under {parent_node.name}"
    pr_body = (
        f"Action: create_computation_node\n"
        f"Project ID: {project.id}\n"
        f"Affected nodes: {affected_nodes_text}\n"
        f"Base node ID: {parent_node.id}\n"
        f"Child folder: {folder_segment}\n"
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
        "action": "create_computation_node",
        "project_id": str(project.id),
        "parent_node_id": str(parent_node.id),
        "created_node": {
            "name": child_name,
            "node_kind": "computation",
            "folder": folder_segment,
            "url": f"{project.url}/blob/{project.default_branch}/{child_files['child_main_path']}",
            "parent_node_id": str(parent_node.id),
        },
        "branch": branch_name,
        "pull_request": {
            "number": pr_data.get('number'),
            "title": pr_data.get('title'),
            "url": pr_data.get('html_url'),
        },
    }), 201


@nodes_bp.route('/<uuid:project_id>/<uuid:node_id>/compute', methods=['POST'])
@jwt_required()
def compute_node(project_id, node_id):
    """Execute a computation node, persist evidence, and open a PR with Lean-consumable artifacts."""
    user_id = get_jwt_identity()
    data = request.get_json() or {}

    user = User.query.get_or_404(user_id)
    project = Project.query.get_or_404(project_id)
    node = Node.query.filter_by(id=node_id, project_id=project.id).first_or_404()
    ComputationService.ensure_computation_node(node)

    github_token = AuthService.refresh_github_token_if_needed(user)
    if not github_token:
        raise CoProofError("You must link your GitHub account.", code=400)

    node_main_path = GitHubService.extract_repo_path_from_node_url(node.url)
    if not node_main_path or not node_main_path.endswith('.lean'):
        raise CoProofError("Node URL does not map to a valid .lean file path.", code=400)

    request_data = ComputationService.normalize_execution_request(data)
    computation_result = ComputationClient.run_computation(request_data)
    computation_summary = ComputationService.summarize_computation_result(computation_result)
    node.computation_spec = ComputationService.build_persisted_spec(request_data)
    node.last_computation_result = computation_summary

    if not computation_result.get('completed'):
        db.session.commit()
        return jsonify({
            "status": "execution_error",
            "action": "compute_node",
            "project_id": str(project.id),
            "node_id": str(node.id),
            "computation": computation_summary,
        }), 400

    if not computation_result.get('sufficient'):
        db.session.commit()
        return jsonify({
            "status": "insufficient_evidence",
            "action": "compute_node",
            "project_id": str(project.id),
            "node_id": str(node.id),
            "computation": computation_summary,
        }), 200

    artifact_bundle = ComputationService.build_artifact_bundle(
        node_main_path=node_main_path,
        node_name=node.name,
        request_data=request_data,
        computation_result=computation_result,
    )

    lean_file_map = GitHubService.get_repository_files_map(
        remote_repo_url=project.remote_repo_url,
        token=github_token,
        branch=project.default_branch,
        extensions=('.lean',),
    )
    lean_file_map = LeanService.normalize_file_map_for_def_module(lean_file_map)
    lean_file_map[node_main_path] = artifact_bundle[node_main_path]

    reachable_files, parent_map = LeanService.resolve_import_tree(node_main_path, lean_file_map)
    reachable_map = {path: lean_file_map[path] for path in reachable_files if path in lean_file_map}
    verification_payload = LeanService.build_verify_payload_from_reachable_map(
        reachable_map=reachable_map,
        entry_file=node_main_path,
        parent_map=parent_map,
        project_goal=project.goal,
    )
    lean_verification = CompilerClient.verify_snippet(verification_payload)

    if not lean_verification.get('valid'):
        db.session.commit()
        return jsonify({
            "status": "lean_wrapper_error",
            "action": "compute_node",
            "project_id": str(project.id),
            "node_id": str(node.id),
            "computation": computation_summary,
            "lean_wrapper_verification": lean_verification,
        }), 400

    repository_files = GitHubService.get_repository_files_map(
        remote_repo_url=project.remote_repo_url,
        token=github_token,
        branch=project.default_branch,
        extensions=('.lean', '.py', '.json', '.tex'),
    )
    has_changes = any(repository_files.get(path) != content for path, content in artifact_bundle.items())

    if not has_changes:
        updates = {
            "action": "compute_node",
            "updated_nodes": [],
            "created_nodes": [],
        }
        node.state = 'validated'
        LeanService.append_updated_node(updates, node)
        LeanService.propagate_parent_states(node.parent, updates, Node)
        db.session.commit()

        return jsonify({
            "status": "already_computed",
            "action": "compute_node",
            "project_id": str(project.id),
            "node_id": str(node.id),
            "message": "No repository changes detected; node state was saved directly in DB.",
            "computation": computation_summary,
            "lean_wrapper_verification": lean_verification,
            "db_updates": updates,
        }), 200

    branch_name = f"compute-node-{str(node.id)[:8]}-{uuid.uuid4().hex[:6]}"
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
        files=artifact_bundle,
        commit_message=f"Compute node {node.name} ({str(node.id)[:8]}) via CoProof",
    )

    pr_title = f"Compute node {node.name} ({str(node.id)[:8]})"
    pr_body = (
        f"Action: compute_node\n"
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
    db.session.commit()

    return jsonify({
        "status": "ok",
        "action": "compute_node",
        "project_id": str(project.id),
        "node_id": str(node.id),
        "branch": branch_name,
        "computation": computation_summary,
        "lean_wrapper_verification": lean_verification,
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
    Also regenerates .tex for parent and all child nodes via FL→NL.
    model_id is required for tex generation.
    """
    user_id = get_jwt_identity()
    data = request.get_json() or {}
    lean_code = data.get('lean_code') or data.get('code')
    model_id = (data.get('model_id') or '').strip()
    api_key_body = (data.get('api_key') or '').strip()

    if not lean_code:
        return jsonify({"error": "Missing payload: lean_code"}), 400
    if not model_id:
        return jsonify({"error": "Missing payload: model_id (required to generate .tex files)"}), 400
    lean_code = LeanService.normalize_lean_imports(lean_code)

    user = User.query.get_or_404(user_id)
    project = Project.query.get_or_404(project_id)
    node = Node.query.filter_by(id=node_id, project_id=project.id).first_or_404()
    ComputationService.ensure_proof_node(node)

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
    lemma_files, _static_tex_files, lemma_names = LeanService.build_split_files(child_blocks)

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

    # ── FL→NL tex generation ──────────────────────────────────────────────────
    api_key = _resolve_api_key(user_id, model_id, api_key_body)
    if not api_key:
        return jsonify({
            "error": "api_key is required (provide in body or save one for this model via /api/v1/translate/api-key)"
        }), 400

    # Build stable child labels from Lean theorem names — these are used both
    # in the child .tex title lines and in the parent's proof references, so
    # they remain consistent even if the child is later solved or split further.
    child_labels = {block['name']: _lean_name_to_label(block['name']) for block in child_blocks}

    # Generate child .tex files (proofs are sorry at this stage → "Unsolved.")
    tex_files: dict[str, str] = {}
    for block in child_blocks:
        folder_segment = LeanService.to_unique_node_folder_segment(block['name'], set())
        child_tex_path = f"{folder_segment}/main.tex"
        # Use the existing lean file path derived from build_split_files
        child_lean_code = lemma_files.get(f"{folder_segment}/main.lean", block['content'])
        label = child_labels[block['name']]
        child_tex = TranslateClient.fl2nl_synchronous(
            payload={
                'lean_code': child_lean_code,
                'model_id': model_id,
                'api_key': api_key,
                'system_prompt': _SPLIT_CHILD_FL2NL_SYSTEM_PROMPT,
            },
            timeout=120,
        )
        if not child_tex:
            return jsonify({
                "error": f"FL→NL generation failed for child lemma '{block['name']}'. "
                         "Check that the model/API key are correct and the NL2FL worker is running."
            }), 502
        # Prepend a stable label header so the child .tex is self-identifying
        tex_files[child_tex_path] = f"% Label: {label}\n{child_tex}"

    # Generate parent .tex — its proof should reference the child labels
    parent_tex_path = node_main_path.rsplit('/', 1)[0] + '/main.tex' if '/' in node_main_path else 'main.tex'
    parent_tex = TranslateClient.fl2nl_synchronous(
        payload={
            'lean_code': base_block['content'],
            'model_id': model_id,
            'api_key': api_key,
            'system_prompt': _split_parent_fl2nl_system_prompt(list(child_labels.values())),
        },
        timeout=120,
    )
    if not parent_tex:
        return jsonify({
            "error": "FL→NL generation failed for the parent (base) theorem. "
                     "Check that the model/API key are correct and the NL2FL worker is running."
        }), 502
    tex_files[parent_tex_path] = parent_tex

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
        "tex_generated": True,
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


@nodes_bp.route('/<uuid:project_id>/<uuid:node_id>/tex-content', methods=['GET'])
@jwt_required()
def get_node_tex_content(project_id, node_id):
    user_id = get_jwt_identity()
    user = User.query.get_or_404(user_id)
    project = Project.query.get_or_404(project_id)
    node = Node.query.filter_by(id=node_id, project_id=project.id).first_or_404()

    github_token = AuthService.refresh_github_token_if_needed(user)
    if not github_token:
        raise CoProofError("You must link your GitHub account.", code=400)

    node_lean_path = GitHubService.extract_repo_path_from_node_url(node.url)
    if not node_lean_path or not node_lean_path.endswith('.lean'):
        raise CoProofError("Node URL does not map to a valid .lean file path.", code=400)

    tex_path = node_lean_path[:-len('.lean')] + '.tex'

    content = GitHubService.get_file_content(
        remote_repo_url=project.remote_repo_url,
        token=github_token,
        path=tex_path,
        branch=project.default_branch,
    )

    return jsonify({
        "project_id": str(project.id),
        "node_id": str(node.id),
        "path": tex_path,
        "content": content,
    }), 200
    