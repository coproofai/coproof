# app/models/graph_index.py

import uuid
from sqlalchemy.dialects.postgresql import UUID, ENUM
from sqlalchemy.sql import func
from app.extensions import db

node_type_enum = ENUM(
    'global_goal', 'theorem', 'lemma', 'corollary', 'definition', 'numerical_eval', 
    name='node_type_enum', 
    metadata=db.metadata
)

# Edge Table (Kept for DAG traversal efficiency)
dependencies = db.Table('dependencies',
    db.Column('source_id', UUID(as_uuid=True), db.ForeignKey('graph_index.id', ondelete='CASCADE'), primary_key=True),
    db.Column('target_id', UUID(as_uuid=True), db.ForeignKey('graph_index.id', ondelete='CASCADE'), primary_key=True)
)

class GraphNode(db.Model):
    """
    CANONICAL STATEMENT INDEX.
    One row = One immutable statement file in the main branch.
    Derived from: /statements/<statement_id>.lean
    """
    __tablename__ = 'graph_index'
    __table_args__ = (
        db.UniqueConstraint('project_id', 'title', name='uniq_project_node_title'),
        db.UniqueConstraint('project_id', 'statement_id', name='uniq_project_statement_id'),
    )

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = db.Column(UUID(as_uuid=True), db.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False)
    
    # Metadata
    title = db.Column(db.Text, nullable=False)
    node_type = db.Column(node_type_enum, nullable=False)
    
    # NEW: Immutable Statement Identifier (From File Header)
    statement_id = db.Column(UUID(as_uuid=True), nullable=False, index=True)
    
    # NEW: Logic Topology (From File Header)
    # The raw UUID from the file header
    parent_statement_id = db.Column(UUID(as_uuid=True), nullable=True)
    
    # NEW: Relational Link (Optimized)
    # FK to the actual DB row of the parent (resolved by Indexer)
    parent_id = db.Column(UUID(as_uuid=True), db.ForeignKey('graph_index.id'), nullable=True)
    
    # NEW: Proof Resolution
    # If this node was 'unresolved' (sorry), which child node ID proves it?
    proven_by_statement_id = db.Column(UUID(as_uuid=True), nullable=True)
    is_resolved = db.Column(db.Boolean, default=False, nullable=False)

    # NEW: Relative Paths (Strict structure: statements/<uuid>.lean)
    lean_relative_path = db.Column(db.Text, nullable=False)
    latex_relative_path = db.Column(db.Text, nullable=True)
    
    # Removed: commit_hash (Tracked at Project Level)
    # Removed: status (Implicitly 'canonical')
    
    # RAG Sync status
    rag_synced_at = db.Column(db.DateTime(timezone=True))
    
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    prerequisites = db.relationship(
        'GraphNode', secondary=dependencies,
        primaryjoin=(id == dependencies.c.source_id),
        secondaryjoin=(id == dependencies.c.target_id),
        backref=db.backref('dependents', lazy='dynamic'),
        lazy='dynamic'
    )
    
    children = db.relationship(
        'GraphNode', 
        backref=db.backref('parent', remote_side=[id]),
        lazy='dynamic'
    )

    def __repr__(self):
        return f"<GraphNode {self.title} ({self.statement_id})>"