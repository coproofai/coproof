import uuid
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.sql import func
from app.extensions import db
from app.models.types import _ArrayColumn, _UuidColumn


project_visibility_enum = db.Enum(
    'public',
    'private',
    name='new_project_visibility_enum',
    metadata=db.metadata,
)


class Project(db.Model):
    __tablename__ = 'new_projects'

    id = db.Column(_UuidColumn(), primary_key=True, default=uuid.uuid4)
    name = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text, nullable=True)
    goal = db.Column(db.Text, nullable=False)
    goal_imports = db.Column(MutableList.as_mutable(_ArrayColumn(db.Text)), nullable=False, default=list)
    goal_definitions = db.Column(db.Text, nullable=True)
    visibility = db.Column(project_visibility_enum, nullable=False, default='private')

    url = db.Column(db.Text, nullable=False)
    remote_repo_url = db.Column(db.Text, nullable=False)
    default_branch = db.Column(db.Text, nullable=False, default='main')
    tags = db.Column(MutableList.as_mutable(_ArrayColumn(db.Text)), nullable=False, default=list)

    author_id = db.Column(
        _UuidColumn(),
        db.ForeignKey('users.id', ondelete='RESTRICT'),
        nullable=False,
        index=True,
    )
    contributor_ids = db.Column(
        MutableList.as_mutable(_ArrayColumn(_UuidColumn())),
        nullable=False,
        default=list,
    )

    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    author = db.relationship('User', backref=db.backref('projects_authored', lazy=True))
    nodes = db.relationship(
        'Node',
        back_populates='project',
        lazy='dynamic',
        cascade='all, delete-orphan',
    )

    def __repr__(self):
        return f"<Project {self.id}>"