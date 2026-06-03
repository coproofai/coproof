import uuid
from sqlalchemy import types as sa_types
from sqlalchemy.dialects import postgresql as pg_types
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.sql import func
from app.extensions import db


class _ArrayColumn(sa_types.TypeDecorator):
    """
    Portable list column.
    Compiles to ARRAY on PostgreSQL (production) and JSON on all other
    dialects (SQLite for unit tests).  MutableList change-tracking works
    transparently on both backends.
    """
    impl = sa_types.Text
    cache_ok = True

    def __init__(self, item_type=None):
        super().__init__()
        self._item_type = item_type or sa_types.Text()

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(pg_types.ARRAY(self._item_type))
        return dialect.type_descriptor(sa_types.JSON())

    def process_bind_param(self, value, dialect):
        return value  # impl (ARRAY or JSON) handles serialisation

    def process_result_value(self, value, dialect):
        return value  # impl (ARRAY or JSON) handles deserialisation


project_visibility_enum = db.Enum(
    'public',
    'private',
    name='new_project_visibility_enum',
    metadata=db.metadata,
)


class Project(db.Model):
    __tablename__ = 'new_projects'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
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
        UUID(as_uuid=True),
        db.ForeignKey('users.id', ondelete='RESTRICT'),
        nullable=False,
        index=True,
    )
    contributor_ids = db.Column(
        MutableList.as_mutable(_ArrayColumn(UUID(as_uuid=True))),
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