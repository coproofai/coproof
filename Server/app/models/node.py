import uuid
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import func
from app.extensions import db


node_state_enum = ENUM(
    'validated',
    'sorry',
    name='new_node_state_enum',
    metadata=db.metadata,
)

node_kind_enum = ENUM(
    'proof',
    'computation',
    name='new_node_kind_enum',
    metadata=db.metadata,
)


class Node(db.Model):
    __tablename__ = 'new_nodes'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = db.Column(db.Text, nullable=False, default='root')
    url = db.Column(db.Text, nullable=False)

    project_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey('new_projects.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    parent_node_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey('new_nodes.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )

    state = db.Column(node_state_enum, nullable=False, default='sorry')
    node_kind = db.Column(node_kind_enum, nullable=False, default='proof')
    computation_spec = db.Column(MutableDict.as_mutable(postgresql.JSONB(astext_type=db.Text())), nullable=True)
    last_computation_result = db.Column(MutableDict.as_mutable(postgresql.JSONB(astext_type=db.Text())), nullable=True)

    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    project = db.relationship('Project', back_populates='nodes')
    parent = db.relationship('Node', remote_side=[id], backref=db.backref('children', lazy='dynamic'))

    def __repr__(self):
        return f"<Node {self.id} kind={self.node_kind} state={self.state}>"