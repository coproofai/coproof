import uuid
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.sql import func
from app.extensions import db


new_node_state_enum = ENUM(
    'validated',
    'sorry',
    name='new_node_state_enum',
    metadata=db.metadata,
)


class NewNode(db.Model):
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

    state = db.Column(new_node_state_enum, nullable=False, default='sorry')

    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    project = db.relationship('NewProject', back_populates='nodes')
    parent = db.relationship('NewNode', remote_side=[id], backref=db.backref('children', lazy='dynamic'))

    def __repr__(self):
        return f"<NewNode {self.id} state={self.state}>"
