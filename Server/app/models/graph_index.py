import uuid
from sqlalchemy.dialects.postgresql import UUID, ENUM
from sqlalchemy.sql import func
from app.extensions import db

# FIX: Bind ENUMs to db.metadata
node_status_enum = ENUM(
    'pending', 'in_review', 'verified', 'error', 
    name='node_status_enum', 
    metadata=db.metadata
)

node_type_enum = ENUM(
    'global_goal', 'theorem', 'lemma', 'corollary', 'definition', 'numerical_eval', 
    name='node_type_enum', 
    metadata=db.metadata
)

# Edge Table
dependencies = db.Table('dependencies',
    db.Column('source_id', UUID(as_uuid=True), db.ForeignKey('graph_index.id', ondelete='CASCADE'), primary_key=True),
    db.Column('target_id', UUID(as_uuid=True), db.ForeignKey('graph_index.id', ondelete='CASCADE'), primary_key=True)
)

class GraphNode(db.Model):
    __tablename__ = 'graph_index'
    __table_args__ = (
        db.UniqueConstraint('project_id', 'title', name='uniq_project_node_title'),
    )

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = db.Column(UUID(as_uuid=True), db.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False)
    
    # Metadata
    title = db.Column(db.Text, nullable=False)
    node_type = db.Column(node_type_enum, nullable=False)
    status = db.Column(node_status_enum, default='pending', nullable=False)
    
    # Git Pointers
    file_path = db.Column(db.Text, nullable=False, index=True)
    start_line = db.Column(db.Integer)
    end_line = db.Column(db.Integer)
    commit_hash = db.Column(db.Text)
    
    # RAG Sync
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

    def __repr__(self):
        return f"<Node {self.title} ({self.node_type})>"