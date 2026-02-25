import requests
from app.models.project import Project
from app.extensions import db
from app.services.git_engine.repo_pool import RepoPool
from app.exceptions import CoProofError
from app.models.user import User
import re

class ProjectService:
    @staticmethod
    def create_project(data, leader_id):
        """
        Creates a project.
        1. Gets User from DB.
        2. Creates Private Repo on GitHub (using stored User token).
        3. Saves Project in DB.
        4. Clones Repo to Server /tmp.
        """
        # 1. Get User & Token
        leader = User.query.get(leader_id)
        if not leader:
            raise CoProofError("Leader user not found", code=404)
        
        # We need the token from the DB, not the request
        github_token = leader.github_access_token

        if not github_token:
            raise CoProofError("You must link your GitHub account to create a project.", code=400)

        # 2. Determine Remote URL (Create on GitHub)
        remote_url = data.get('remote_repo_url')
        
        if not remote_url:
            # Sanitize name: "My Project!" -> "coproof-my-project"
            clean_name = re.sub(r'[^a-zA-Z0-9]', '-', data['name'].lower()).strip('-')
            repo_name = f"coproof-{clean_name}"
            
            try:
                # Call GitHub API
                headers = {
                    "Authorization": f"token {github_token}",
                    "Accept": "application/vnd.github.v3+json"
                }
                payload = {
                    "name": repo_name,
                    "description": data.get('description', 'Created via CoProof'),
                    "private": data.get('visibility', 'private') == 'private',
                    "auto_init": True  # Creates README so we can clone immediately
                }
                
                resp = requests.post("https://api.github.com/user/repos", json=payload, headers=headers)
                
                if resp.status_code == 201:
                    repo_data = resp.json()
                    remote_url = repo_data['clone_url']
                elif resp.status_code == 401:
                    # Token invalid/expired
                    raise CoProofError("GitHub token expired. Please login again.", code=401)
                elif resp.status_code == 422:
                    raise CoProofError(f"Repository '{repo_name}' already exists on your GitHub.", code=400)
                else:
                    raise CoProofError(f"GitHub Error: {resp.text}", code=502)
                    
            except requests.RequestException as e:
                raise CoProofError(f"Failed to reach GitHub: {str(e)}", code=502)

        # 3. Save to DB
        new_project = Project(
            name=data['name'],
            description=data.get('description'),
            visibility=data.get('visibility', 'private'),
            remote_repo_url=remote_url,
            leader_id=leader_id
        )
        
        db.session.add(new_project)
        db.session.commit()
        
        # 4. Clone to Server (Initialize Cache)
        # We pass the token we retrieved from the DB so we can clone the private repo
        try:
            RepoPool.ensure_bare_repo(str(new_project.id), remote_url, auth_token=github_token)
        except Exception as e:
            # We log this, but we don't rollback the DB transaction because the 
            # project/repo creation was successful. The user can retry the "Clone" later 
            # (or the next request will trigger it).
            print(f"Warning: Initial server clone failed: {e}")
            
        return new_project


    @staticmethod
    def get_public_projects(page=1, per_page=20):
        pagination = Project.query.filter_by(visibility='public')\
            .order_by(Project.created_at.desc())\
            .paginate(page=page, per_page=per_page, error_out=False)
        return pagination