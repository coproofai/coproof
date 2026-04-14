"""Add goal context fields to new projects

Revision ID: 7f1b2c9a0d4e
Revises: c8c8f9b1d2aa
Create Date: 2026-03-05 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '7f1b2c9a0d4e'
down_revision = 'c8c8f9b1d2aa'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('new_projects', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'goal_imports',
                postgresql.ARRAY(sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::text[]"),
            )
        )
        batch_op.add_column(sa.Column('goal_definitions', sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table('new_projects', schema=None) as batch_op:
        batch_op.drop_column('goal_definitions')
        batch_op.drop_column('goal_imports')
