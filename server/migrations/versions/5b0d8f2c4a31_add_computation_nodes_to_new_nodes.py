"""Add computation node support to new nodes

Revision ID: 5b0d8f2c4a31
Revises: a1f4d9c2b7e0
Create Date: 2026-03-25 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '5b0d8f2c4a31'
down_revision = 'a1f4d9c2b7e0'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    new_node_kind_enum = postgresql.ENUM(
        'proof',
        'computation',
        name='new_node_kind_enum',
    )
    new_node_kind_enum.create(bind, checkfirst=True)

    with op.batch_alter_table('new_nodes', schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            'node_kind',
            postgresql.ENUM('proof', 'computation', name='new_node_kind_enum', create_type=False),
            nullable=False,
            server_default='proof',
        ))
        batch_op.add_column(sa.Column('computation_spec', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
        batch_op.add_column(sa.Column('last_computation_result', postgresql.JSONB(astext_type=sa.Text()), nullable=True))

    with op.batch_alter_table('new_nodes', schema=None) as batch_op:
        batch_op.alter_column('node_kind', server_default=None)


def downgrade():
    with op.batch_alter_table('new_nodes', schema=None) as batch_op:
        batch_op.drop_column('last_computation_result')
        batch_op.drop_column('computation_spec')
        batch_op.drop_column('node_kind')

    new_node_kind_enum = postgresql.ENUM('proof', 'computation', name='new_node_kind_enum')
    new_node_kind_enum.drop(op.get_bind(), checkfirst=True)