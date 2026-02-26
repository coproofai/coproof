import base64
import re
import uuid
import requests
from app.models.new_project import NewProject
from app.models.new_node import NewNode
from app.extensions import db
from app.services.git_engine.repo_pool import RepoPool
from app.exceptions import CoProofError
from app.models.user import User

class ProjectService:
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

        raw_contributors = data.get('contributor_ids') or []
        if not isinstance(raw_contributors, list):
            raise CoProofError("contributor_ids must be a list", code=400)

        # 1. User + Token
        leader = User.query.get(leader_id)
        if not leader:
            raise CoProofError("Leader user not found", code=404)

        github_token = leader.github_access_token
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
        goal = data['goal'].strip()
        def_content = ProjectService._generate_def_lean_from_prompt(goal)
        main_lean = ProjectService._generate_root_main_lean()
        main_tex = ProjectService._generate_root_main_tex(goal)

        ProjectService._create_or_update_repo_file(
            github_token, full_name, 'def.lean', def_content,
            'Initialize def.lean with project goal', default_branch,
        )
        ProjectService._create_or_update_repo_file(
            github_token, full_name, 'Def.lean', def_content,
            'Initialize Def.lean compatibility module', default_branch,
        )
        ProjectService._create_or_update_repo_file(
            github_token, full_name, 'root/main.lean', main_lean,
            'Initialize root/main.lean', default_branch,
        )
        ProjectService._create_or_update_repo_file(
            github_token, full_name, 'root/main.tex', main_tex,
            'Initialize root/main.tex', default_branch,
        )

        # 4. Persist NewProject + root NewNode
        new_project = NewProject(
            name=data['name'],
            description=data.get('description'),
            goal=goal,
            visibility=visibility,
            url=html_url,
            remote_repo_url=clone_url,
            default_branch=default_branch,
            tags=tags,
            author_id=author_id,
            contributor_ids=contributor_ids,
        )
        db.session.add(new_project)
        db.session.flush()

        root_node_url = f"{html_url}/blob/{default_branch}/root/main.lean"
        root_node = NewNode(
            name='root',
            url=root_node_url,
            project_id=new_project.id,
            parent_node_id=None,
            state='sorry',
        )
        db.session.add(root_node)
        db.session.commit()

        # 5. Warm Git cache
        try:
            RepoPool.ensure_bare_repo(str(new_project.id), clone_url, auth_token=github_token)
        except Exception as e:
            print(f"Warning: Initial server clone failed: {e}")

        return new_project


    @staticmethod
    def get_public_projects(page=1, per_page=20):
        pagination = NewProject.query.filter_by(visibility='public')\
            .order_by(NewProject.created_at.desc())\
            .paginate(page=page, per_page=per_page, error_out=False)
        return pagination

    @staticmethod
    def _build_repo_name(project_name):
        clean_name = re.sub(r'[^a-zA-Z0-9]', '-', project_name.lower()).strip('-')
        return f"coproof-{clean_name}"

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

        try:
            resp = requests.post("https://api.github.com/user/repos", json=payload, headers=headers, timeout=20)
        except requests.RequestException as e:
            raise CoProofError(f"Failed to reach GitHub: {str(e)}", code=502)

        if resp.status_code == 201:
            return resp.json()
        if resp.status_code == 401:
            raise CoProofError("GitHub token expired. Please login again.", code=401)
        if resp.status_code == 422:
            raise CoProofError(f"Repository '{repo_name}' already exists on your GitHub.", code=400)

        raise CoProofError(f"GitHub Error: {resp.text}", code=502)

    @staticmethod
    def _create_or_update_repo_file(github_token, full_name, path, content, message, branch):
        headers = ProjectService._github_headers(github_token)
        b64_content = base64.b64encode(content.encode('utf-8')).decode('utf-8')

        get_resp = requests.get(
            f"https://api.github.com/repos/{full_name}/contents/{path}",
            headers=headers,
            params={"ref": branch},
            timeout=20,
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
            raise CoProofError(f"Failed to inspect '{path}' in GitHub repo: {get_resp.text}", code=502)

        put_resp = requests.put(
            f"https://api.github.com/repos/{full_name}/contents/{path}",
            headers=headers,
            json=payload,
            timeout=20,
        )

        if put_resp.status_code not in (200, 201):
            raise CoProofError(f"Failed to write '{path}' in GitHub repo: {put_resp.text}", code=502)

    @staticmethod
    def _generate_def_lean_from_prompt(goal):
        goal_expr = ProjectService._normalize_goal_expression(goal)
        return (
            "-- Generated from goal prompt\n"
            f"def GoalDef : Prop := {goal_expr}\n"
        )

    @staticmethod
    def _generate_root_main_lean():
        return (
            "import Def\n\n"
            "theorem root : GoalDef := by\n"
            "  sorry\n"
        )

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