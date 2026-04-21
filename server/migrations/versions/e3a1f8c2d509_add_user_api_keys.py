"""Add user_api_keys table

Revision ID: e3a1f8c2d509
Revises: 5b0d8f2c4a31
Create Date: 2026-04-18 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'e3a1f8c2d509'
down_revision = '5b0d8f2c4a31'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'user_api_keys',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('model_id', sa.Text(), nullable=False),
        sa.Column('api_key_enc', sa.Text(), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=True,
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'model_id', name='uq_user_api_keys_user_model'),
    )
    with op.batch_alter_table('user_api_keys', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_user_api_keys_user_id'), ['user_id'], unique=False
        )


def downgrade():
    with op.batch_alter_table('user_api_keys', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_user_api_keys_user_id'))
    op.drop_table('user_api_keys')
