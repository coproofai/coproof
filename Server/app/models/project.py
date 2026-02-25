# app/models/project.py

import uuid
from sqlalchemy.dialects.postgresql import UUID, ENUM
from sqlalchemy.sql import func
from app.extensions import db

visibility_enum = ENUM(
    'public', 'private', 
    name='project_visibility_enum', 
    metadata=db.metadata
)

# Association Table
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
    visibility = db.Column(visibility_enum, default='private', nullable=False)
    
    leader_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'), nullable=False)
    
    remote_repo_url = db.Column(db.Text)
    default_branch = db.Column(db.Text, default='main', nullable=False)
    
    # GitHub App Integration
    github_installation_id = db.Column(db.Text, nullable=True)
    
    # NEW: Project-Level Commit Hash (The Snapshot)
    # Tracks the state of 'main' when the GraphNodes were last indexed.
    main_commit_sha = db.Column(db.String(40), nullable=True)
    
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    leader = db.relationship('User', backref=db.backref('projects_led', lazy=True))
    members = db.relationship('User', secondary=collaborators, lazy='subquery',
        backref=db.backref('projects_collaborated', lazy=True))

    def __repr__(self):
        return f"<Project {self.name}>"