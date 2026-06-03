"""
Portable SQLAlchemy column type decorators.

Each decorator dispatches to the native PostgreSQL type in production and falls
back to a SQLite-compatible equivalent in the test environment, without any
change to application code or Alembic migrations.
"""
import uuid as _uuid_mod

from sqlalchemy import types as sa_types
from sqlalchemy.dialects import postgresql as pg_types


class _UuidColumn(sa_types.TypeDecorator):
    """
    Portable UUID primary-key / foreign-key column.
    - PostgreSQL: native UUID (binary, indexed efficiently)
    - SQLite: CHAR(36) string representation
    Accepts both uuid.UUID objects and hyphenated UUID strings on write.
    Always returns uuid.UUID objects on read.
    """
    impl = sa_types.String(36)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(pg_types.UUID(as_uuid=True))
        return dialect.type_descriptor(sa_types.String(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if not isinstance(value, _uuid_mod.UUID):
            value = _uuid_mod.UUID(str(value))
        if dialect.name == 'postgresql':
            return value          # UUID(as_uuid=True) expects a uuid.UUID object
        return str(value)         # SQLite String(36) expects a plain string

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if isinstance(value, _uuid_mod.UUID):
            return value
        return _uuid_mod.UUID(str(value))


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
        return value

    def process_result_value(self, value, dialect):
        return value


class _JsonbColumn(sa_types.TypeDecorator):
    """
    Portable JSONB column.
    Compiles to JSONB on PostgreSQL (production) and JSON on all other
    dialects (SQLite for unit tests).
    """
    impl = sa_types.Text
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(pg_types.JSONB(astext_type=sa_types.Text()))
        return dialect.type_descriptor(sa_types.JSON())

    def process_bind_param(self, value, dialect):
        return value

    def process_result_value(self, value, dialect):
        return value
