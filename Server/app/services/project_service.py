from app.models.project import Project
from app.extensions import db
from app.services.git_engine.repo_pool import RepoPool
from app.exceptions import CoProofError

class ProjectService:
    @staticmethod
    def create_project(data, leader_id):
        """
        Creates a project in DB and initializes the Git Cache.
        """
        new_project = Project(
            name=data['name'],
            description=data.get('description'),
            visibility=data.get('visibility', 'private'),
            remote_repo_url=data.get('remote_repo_url'),
            leader_id=leader_id
        )
        
        db.session.add(new_project)
        db.session.commit()
        
        # Trigger Git Initialization (Clone or Check) if remote URL provided
        if new_project.remote_repo_url:
            try:
                # TODO:We do this synchronously for now, but in production 
                # this should be a background task (Phase 6)
                RepoPool.ensure_bare_repo(str(new_project.id), new_project.remote_repo_url)
            except Exception as e:
                # Log warning but don't fail the project creation
                # The user can retry syncing later
                pass
                
        return new_project

    @staticmethod
    def get_public_projects(page=1, per_page=20):
        pagination = Project.query.filter_by(visibility='public')\
            .order_by(Project.created_at.desc())\
            .paginate(page=page, per_page=per_page, error_out=False)
        return pagination