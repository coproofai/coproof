import uuid
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.sql import func
from app.extensions import db


new_project_visibility_enum = db.Enum(
    'public',
    'private',
    name='new_project_visibility_enum',
    metadata=db.metadata,
)


class NewProject(db.Model):
    __tablename__ = 'new_projects'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text, nullable=True)
    goal = db.Column(db.Text, nullable=False)
    visibility = db.Column(new_project_visibility_enum, nullable=False, default='private')

    url = db.Column(db.Text, nullable=False)
    remote_repo_url = db.Column(db.Text, nullable=False)
    default_branch = db.Column(db.Text, nullable=False, default='main')
    tags = db.Column(MutableList.as_mutable(ARRAY(db.Text)), nullable=False, default=list)

    author_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey('users.id', ondelete='RESTRICT'),
        nullable=False,
        index=True,
    )
    contributor_ids = db.Column(
        MutableList.as_mutable(ARRAY(UUID(as_uuid=True))),
        nullable=False,
        default=list,
    )

    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    author = db.relationship('User', backref=db.backref('new_projects_authored', lazy=True))
    nodes = db.relationship(
        'NewNode',
        back_populates='project',
        lazy='dynamic',
        cascade='all, delete-orphan',
    )

    def __repr__(self):
        return f"<NewProject {self.id}>"
