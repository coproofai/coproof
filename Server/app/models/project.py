import uuid
from sqlalchemy.dialects.postgresql import UUID, ENUM
from sqlalchemy.sql import func
from app.extensions import db

# FIX: Bind ENUM to db.metadata so create_all/drop_all handles it automatically
visibility_enum = ENUM(
    'public', 'private', 
    name='project_visibility_enum', 
    metadata=db.metadata  # <--- THIS FIXES THE ERROR
)

# Association Table for Many-to-Many
collaborators = db.Table('collaborators',
    db.Column('project_id', UUID(as_uuid=True), db.ForeignKey('projects.id', ondelete='CASCADE'), primary_key=True),
    db.Column('user_id', UUID(as_uuid=True), db.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
    db.Column('joined_at', db.DateTime(timezone=True), server_default=func.now())
)

class Project(db.Model):
    __tablename__ = 'projects'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text)
    # Use the bound enum
    visibility = db.Column(visibility_enum, default='private', nullable=False)
    
    # Foreign Keys
    leader_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'), nullable=False)
    
    # Git Config
    remote_repo_url = db.Column(db.Text)
    default_branch = db.Column(db.Text, default='main', nullable=False)
    
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    leader = db.relationship('User', backref=db.backref('projects_led', lazy=True))
    members = db.relationship('User', secondary=collaborators, lazy='subquery',
        backref=db.backref('projects_collaborated', lazy=True))

    def __repr__(self):
        return f"<Project {self.name} ({self.visibility})>"