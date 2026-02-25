# app/models/proposed_node.py

import uuid
from sqlalchemy.dialects.postgresql import UUID, ENUM, JSONB
from sqlalchemy.sql import func
from app.extensions import db
from app.models.graph_index import node_type_enum

# UPDATED: Status Enum matching GitHub PR flow
proposal_status_enum = ENUM(
    'draft',            # Editing locally
    'verifying',        # Ephemeral DAG build & Compilation running
    'valid',            # PR Created: Compiles, NO sorry
    'valid_sorry',      # PR Created: Compiles, HAS sorry (Trusted)
    'invalid',          # Failed verification (No PR created)
    'merged',           # PR Merged into Main
    'closed',           # PR Closed/Rejected
    name='proposal_status_enum',
    metadata=db.metadata
)

class ProposedNode(db.Model):
    """
    PR CANDIDATE.
    Represents a contribution originating from a specific parent statement.
    """
    __tablename__ = 'proposed_nodes'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = db.Column(UUID(as_uuid=True), db.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    
    # Metadata
    title = db.Column(db.Text, nullable=False)
    node_type = db.Column(node_type_enum, nullable=False)
    
    # NEW: Attachment Point
    # Every proposal must branch off a specific canonical statement
    parent_statement_id = db.Column(UUID(as_uuid=True), nullable=False, index=True)
    
    # NEW: GitHub Integration Fields
    fork_repo_full_name = db.Column(db.Text, nullable=True) # e.g. "user/project-fork"
    branch_name = db.Column(db.Text, nullable=False)        # e.g. "user/123/proposal_abc"
    github_pr_number = db.Column(db.Integer, nullable=True) # Populated if valid/valid_sorry
    commit_sha = db.Column(db.String(40), nullable=True)    # The specific commit verified
    
    # Files
    lean_file_path = db.Column(db.Text, nullable=False)
    latex_file_path = db.Column(db.Text, nullable=True)
    
    # Dependencies (JSON List of Titles or Statement IDs)
    proposed_dependencies = db.Column(JSONB, default=list)
    
    # Lifecycle
    status = db.Column(proposal_status_enum, default='draft', nullable=False)
    verification_log = db.Column(db.Text)
    
    # Removed: merged_graph_node_id (Re-indexing handles this association)
    # Removed: is_exposed (Implicitly exposed if valid PR exists)
    
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    project = db.relationship('Project', backref='proposals')
    user = db.relationship('User', backref='proposals')

    def __repr__(self):
        return f"<ProposedNode {self.title} PR#{self.github_pr_number}>"