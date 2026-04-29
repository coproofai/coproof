import base64
import re
import time
import uuid
import requests
from sqlalchemy import or_
from app.models.project import Project
from app.models.node import Node
from app.extensions import db
from app.services.integrations.compiler_client import CompilerClient
from app.services.auth_service import AuthService
from app.exceptions import CoProofError
from app.models.user import User

class ProjectService:
    GITHUB_RETRY_STATUS = {409, 422, 500, 502, 503, 504}

    @staticmethod
    def create_project(data, leader_id):
        required_fields = ('name', 'goal')
        missing = [field for field in required_fields if not data.get(field)]
        if missing:
            raise CoProofError(f"Missing required fields: {', '.join(missing)}", code=400)

        visibility = data.get('visibility', 'private')
        if visibility not in ('public', 'private'):
            raise CoProofError("visibility must be either 'public' or 'private'", code=400)

        tags = data.get('tags') or []
        if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
            raise CoProofError("tags must be a list of strings", code=400)

        goal_imports = ProjectService._normalize_goal_imports(data.get('goal_imports'))
        goal_definitions = ProjectService._normalize_goal_definitions(data.get('goal_definitions'))
        goal = data['goal'].strip()

        # Validate user-provided goal context before creating a GitHub repository.
        ProjectService._validate_goal_context(
            goal,
            goal_imports=goal_imports,
            goal_definitions=goal_definitions,
        )

        raw_contributors = data.get('contributor_ids') or []
        if not isinstance(raw_contributors, list):
            raise CoProofError("contributor_ids must be a list", code=400)

        # 1. User + Token
        leader = User.query.get(leader_id)
        if not leader:
            raise CoProofError("Leader user not found", code=404)

        github_token = AuthService.refresh_github_token_if_needed(leader)
        if not github_token:
            raise CoProofError("You must link your GitHub account to create a project.", code=400)

        author_id = uuid.UUID(str(leader_id))
        contributor_ids = []
        for value in raw_contributors:
            contributor_ids.append(uuid.UUID(str(value)))

        # 2. Create repo on GitHub
        repo_name = ProjectService._build_repo_name(data['name'])
        repo_data = ProjectService._create_github_repo(
            github_token=github_token,
            repo_name=repo_name,
            description=data.get('description', 'Created via CoProof'),
            visibility=visibility,
        )

        default_branch = repo_data.get('default_branch') or 'main'
        full_name = repo_data['full_name']
        clone_url = repo_data['clone_url']
        html_url = repo_data['html_url']

        # 3. Generate and push initial files
        def_content = ProjectService._generate_def_lean_from_prompt(
            goal,
            goal_imports=goal_imports,
            goal_definitions=goal_definitions,
        )
        main_lean = ProjectService._generate_root_main_lean(goal)
        main_tex = data.get('goal_tex') or ProjectService._generate_root_main_tex(goal)

        ProjectService._create_or_update_repo_file(
            github_token, full_name, 'Definitions.lean', def_content,
            'Initialize Definitions.lean with project goal', default_branch,
        )
        ProjectService._create_or_update_repo_file(
            github_token, full_name, 'root/main.lean', main_lean,
            'Initialize root/main.lean', default_branch,
        )
        ProjectService._create_or_update_repo_file(
            github_token, full_name, 'root/main.tex', main_tex,
            'Initialize root/main.tex', default_branch,
        )

        # 4. Persist Project + root Node
        project = Project(
            name=data['name'],
            description=data.get('description'),
            goal=goal,
            goal_imports=goal_imports,
            goal_definitions=goal_definitions,
            visibility=visibility,
            url=html_url,
            remote_repo_url=clone_url,
            default_branch=default_branch,
            tags=tags,
            author_id=author_id,
            contributor_ids=contributor_ids,
        )
        db.session.add(project)
        db.session.flush()

        root_node_url = f"{html_url}/blob/{default_branch}/root/main.lean"
        root_node = Node(
            name='root',
            url=root_node_url,
            project_id=project.id,
            parent_node_id=None,
            state='sorry',
            node_kind='proof',
        )
        db.session.add(root_node)
        db.session.commit()

        return project


    @staticmethod
    def get_public_projects(page=1, per_page=20):
        pagination = Project.query.filter_by(visibility='public')\
            .order_by(Project.created_at.desc())\
            .paginate(page=page, per_page=per_page, error_out=False)
        return pagination

    @staticmethod
    def get_accessible_projects(user_id):
        try:
            user_uuid = uuid.UUID(str(user_id))
        except (ValueError, TypeError):
            raise CoProofError("Invalid user id in token.", code=400)

        from app.models.user_followed_project import UserFollowedProject
        followed_rows = UserFollowedProject.query.filter_by(user_id=user_uuid).all()
        followed_ids = [r.project_id for r in followed_rows]

        return Project.query.filter(
            or_(
                Project.id.in_(followed_ids),
                Project.author_id == user_uuid,
                Project.contributor_ids.contains([user_uuid]),
            )
        ).order_by(Project.created_at.desc()).all()

    @staticmethod
    def _build_repo_name(project_name):
        clean_name = re.sub(r'[^a-zA-Z0-9]', '-', project_name.lower()).strip('-')
        return f"coproof-{clean_name}"

    @staticmethod
    def _normalize_goal_imports(raw_imports):
        if raw_imports is None:
            return []

        if isinstance(raw_imports, str):
            values = raw_imports.splitlines()
        elif isinstance(raw_imports, list) and all(isinstance(value, str) for value in raw_imports):
            values = raw_imports
        else:
            raise CoProofError("goal_imports must be a list of strings", code=400)

        normalized = []
        seen = set()

        for value in values:
            entry = value.strip()
            if not entry:
                continue

            if entry.startswith('import '):
                entry = entry[7:].strip()

            if not entry or entry in seen:
                continue

            seen.add(entry)
            normalized.append(entry)

        return normalized

    @staticmethod
    def _normalize_goal_definitions(raw_definitions):
        if raw_definitions is None:
            return None

        if not isinstance(raw_definitions, str):
            raise CoProofError("goal_definitions must be a string", code=400)

        cleaned = raw_definitions.strip()
        return cleaned or None

    @staticmethod
    def _github_headers(github_token):
        return {
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github.v3+json",
        }

    @staticmethod
    def _create_github_repo(github_token, repo_name, description, visibility):
        headers = ProjectService._github_headers(github_token)
        payload = {
            "name": repo_name,
            "description": description,
            "private": visibility == 'private',
            "auto_init": True,
        }

        resp = ProjectService._request_with_retries(
            method='post',
            url="https://api.github.com/user/repos",
            headers=headers,
            json=payload,
            timeout=20,
            retry_on_status={500, 502, 503, 504},
            max_attempts=3,
            backoff_seconds=1.0,
        )

        if resp.status_code == 201:
            return resp.json()
        if resp.status_code == 401:
            raise CoProofError("GitHub token expired. Please login again.", code=401)
        if resp.status_code == 403:
            raise CoProofError(f"GitHub rejected repository creation: {resp.text}", code=403)
        if resp.status_code == 422:
            raise CoProofError(f"Repository '{repo_name}' already exists on your GitHub.", code=400)

        raise CoProofError(f"GitHub repository creation failed ({resp.status_code}): {resp.text}", code=502)

    @staticmethod
    def _create_or_update_repo_file(github_token, full_name, path, content, message, branch):
        headers = ProjectService._github_headers(github_token)
        b64_content = base64.b64encode(content.encode('utf-8')).decode('utf-8')

        get_resp = ProjectService._request_with_retries(
            method='get',
            url=f"https://api.github.com/repos/{full_name}/contents/{path}",
            headers=headers,
            params={"ref": branch},
            timeout=20,
            retry_on_status={500, 502, 503, 504},
            max_attempts=3,
            backoff_seconds=0.8,
        )

        payload = {
            "message": message,
            "content": b64_content,
            "branch": branch,
        }

        if get_resp.status_code == 200:
            existing = get_resp.json()
            payload["sha"] = existing["sha"]
        elif get_resp.status_code not in (404,):
            raise CoProofError(
                f"Failed to inspect '{path}' in GitHub repo ({get_resp.status_code}): {get_resp.text}",
                code=502,
            )

        put_resp = ProjectService._request_with_retries(
            method='put',
            url=f"https://api.github.com/repos/{full_name}/contents/{path}",
            headers=headers,
            json=payload,
            timeout=20,
            retry_on_status=ProjectService.GITHUB_RETRY_STATUS,
            max_attempts=4,
            backoff_seconds=1.0,
        )

        if put_resp.status_code in (200, 201):
            return
        if put_resp.status_code == 401:
            raise CoProofError("GitHub token expired while writing project files. Please login again.", code=401)
        if put_resp.status_code == 403:
            raise CoProofError(f"GitHub rejected writing '{path}': {put_resp.text}", code=403)

        raise CoProofError(
            f"Failed to write '{path}' in GitHub repo ({put_resp.status_code}): {put_resp.text}",
            code=502,
        )

    @staticmethod
    def _request_with_retries(method, url, retry_on_status=None, max_attempts=3, backoff_seconds=1.0, **kwargs):
        retry_on_status = set(retry_on_status or [])
        response = None

        for attempt in range(1, max_attempts + 1):
            try:
                response = requests.request(method.upper(), url, **kwargs)
            except requests.RequestException as exc:
                if attempt >= max_attempts:
                    raise CoProofError(
                        f"Failed to reach GitHub after {max_attempts} attempt(s): {str(exc)}",
                        code=502,
                    )
                time.sleep(backoff_seconds * attempt)
                continue

            if response.status_code in retry_on_status and attempt < max_attempts:
                time.sleep(backoff_seconds * attempt)
                continue

            return response

        return response

    @staticmethod
    def _generate_def_lean_from_prompt(goal, goal_imports=None, goal_definitions=None):
        imports = goal_imports or []
        definitions = (goal_definitions or '').strip()

        sections = []
        if imports:
            sections.extend([f"import {module}" for module in imports])
            sections.append("")

        sections.append("-- Generated from goal prompt")

        if definitions:
            sections.append(definitions.rstrip())
            sections.append("")

        return "\n".join(sections).rstrip() + "\n"

    @staticmethod
    def _generate_root_main_lean(goal):
        goal_expr = ProjectService._normalize_goal_expression(goal)
        return (
            "import Definitions\n\n"
            f"theorem root : {goal_expr} := by\n"
            "  sorry\n"
        )

    @staticmethod
    def _validate_goal_context(goal, goal_imports=None, goal_definitions=None):
        def_content = ProjectService._generate_def_lean_from_prompt(
            goal,
            goal_imports=goal_imports,
            goal_definitions=goal_definitions,
        )
        goal_expr = ProjectService._normalize_goal_expression(goal)
        snippet = (
            f"{def_content}\n"
            f"theorem root : {goal_expr} := by\n"
            "  sorry\n"
        )

        verification = CompilerClient.verify_snippet(snippet)
        if verification.get('valid'):
            return

        formatted_errors = ProjectService._format_compiler_errors(verification.get('errors') or [])
        detail = formatted_errors or 'Lean could not validate the provided goal context.'
        raise CoProofError(
            f"Invalid goal imports/definitions. {detail}",
            code=400,
            payload={
                "validation_errors": verification.get('errors') or [],
                "verification": {
                    "valid": verification.get('valid', False),
                    "message_count": verification.get('message_count'),
                    "return_code": verification.get('return_code'),
                },
            },
        )

    @staticmethod
    def _format_compiler_errors(errors, limit=5):
        if not errors:
            return ''

        parts = []
        for err in errors[:limit]:
            line = err.get('line', '?')
            col = err.get('column', '?')
            msg = (err.get('message') or '').strip()
            if msg:
                parts.append(f"L{line}:C{col} {msg}")

        if len(errors) > limit:
            parts.append(f"... and {len(errors) - limit} more error(s)")

        return '; '.join(parts)

    @staticmethod
    def _normalize_goal_expression(goal):
        expr = goal.strip()
        if expr.startswith('∀'):
            return expr
        if expr.lower().startswith('forall '):
            return '∀ ' + expr[7:].strip()

        quantified_match = re.match(r"^[A-Za-z_][A-Za-z0-9_']*\s*:\s*[^,]+,\s*.+$", expr)
        if quantified_match:
            return f"∀ {expr}"

        return expr

    @staticmethod
    def _generate_root_main_tex(goal):
        return (
            "\\begin{theorem}[Root Goal]\n"
            f"${goal}$\n"
            "\\end{theorem}\n\n"
            "\\begin{proof}\n"
            "By \\texttt{sorry}.\n"
            "\\end{proof}\n"
        )