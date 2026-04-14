"""Align graph_index project foreign key to new_projects

Revision ID: a1f4d9c2b7e0
Revises: 7f1b2c9a0d4e
Create Date: 2026-03-18 00:00:00.000000

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'a1f4d9c2b7e0'
down_revision = '7f1b2c9a0d4e'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('graph_index', schema=None) as batch_op:
        batch_op.drop_constraint('graph_index_project_id_fkey', type_='foreignkey')
        batch_op.create_foreign_key(
            'graph_index_project_id_fkey',
            'new_projects',
            ['project_id'],
            ['id'],
            ondelete='CASCADE',
        )


def downgrade():
    with op.batch_alter_table('graph_index', schema=None) as batch_op:
        batch_op.drop_constraint('graph_index_project_id_fkey', type_='foreignkey')
        batch_op.create_foreign_key(
            'graph_index_project_id_fkey',
            'projects',
            ['project_id'],
            ['id'],
            ondelete='CASCADE',
        )
