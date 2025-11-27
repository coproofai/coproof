import uuid
from sqlalchemy.dialects.postgresql import UUID, ENUM, JSONB
from sqlalchemy.sql import func
from app.extensions import db

job_status_enum = ENUM('queued', 'processing', 'completed', 'failed', name='job_status_enum', create_type=False)
job_type_enum = ENUM('git_push', 'git_clone', 'rag_sync', 'agent_exploration', 'cluster_experiment', name='job_type_enum', create_type=False)

class AsyncJob(db.Model):
    __tablename__ = 'async_jobs'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id', ondelete='SET NULL'))
    project_id = db.Column(UUID(as_uuid=True), db.ForeignKey('projects.id', ondelete='CASCADE'))
    
    celery_task_id = db.Column(db.Text, nullable=False)
    job_type = db.Column(job_type_enum, nullable=False)
    status = db.Column(job_status_enum, default='queued', nullable=False)
    
    result_metadata = db.Column(JSONB)
    error_log = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<Job {self.job_type} ({self.status})>"