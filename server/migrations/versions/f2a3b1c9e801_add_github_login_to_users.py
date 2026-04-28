"""Add github_login column to users

Revision ID: f2a3b1c9e801
Revises: e3a1f8c2d509
Create Date: 2026-04-27 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'f2a3b1c9e801'
down_revision = 'e3a1f8c2d509'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('github_login', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('users', 'github_login')
