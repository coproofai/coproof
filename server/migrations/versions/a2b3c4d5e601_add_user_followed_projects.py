"""Add user_followed_projects table

Revision ID: a2b3c4d5e601
Revises: e3a1f8c2d509
Create Date: 2026-04-29 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a2b3c4d5e601'
down_revision = 'f2a3b1c9e801'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'user_followed_projects',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('project_id', sa.UUID(), nullable=False),
        sa.Column(
            'followed_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['new_projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'project_id', name='uq_user_followed_project'),
    )
    with op.batch_alter_table('user_followed_projects', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_user_followed_projects_user_id'), ['user_id'], unique=False
        )
        batch_op.create_index(
            batch_op.f('ix_user_followed_projects_project_id'), ['project_id'], unique=False
        )


def downgrade():
    with op.batch_alter_table('user_followed_projects', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_user_followed_projects_project_id'))
        batch_op.drop_index(batch_op.f('ix_user_followed_projects_user_id'))
    op.drop_table('user_followed_projects')
