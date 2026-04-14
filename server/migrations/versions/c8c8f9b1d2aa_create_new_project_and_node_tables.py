"""Create new project and node tables

Revision ID: c8c8f9b1d2aa
Revises: 46c7ac45000f
Create Date: 2026-02-26 12:10:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'c8c8f9b1d2aa'
down_revision = '46c7ac45000f'
branch_labels = None
depends_on = None


def upgrade():
    new_project_visibility_enum = postgresql.ENUM(
        'public',
        'private',
        name='new_project_visibility_enum',
    )
    new_node_state_enum = postgresql.ENUM(
        'validated',
        'sorry',
        name='new_node_state_enum',
    )

    new_project_visibility_enum.create(op.get_bind(), checkfirst=True)
    new_node_state_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        'new_projects',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('goal', sa.Text(), nullable=False),
        sa.Column('visibility', postgresql.ENUM('public', 'private', name='new_project_visibility_enum', create_type=False), nullable=False),
        sa.Column('url', sa.Text(), nullable=False),
        sa.Column('remote_repo_url', sa.Text(), nullable=False),
        sa.Column('default_branch', sa.Text(), nullable=False),
        sa.Column('tags', postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column('author_id', sa.UUID(), nullable=False),
        sa.Column('contributor_ids', postgresql.ARRAY(sa.UUID()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['author_id'], ['users.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('new_projects', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_new_projects_author_id'), ['author_id'], unique=False)

    op.create_table(
        'new_nodes',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('url', sa.Text(), nullable=False),
        sa.Column('project_id', sa.UUID(), nullable=False),
        sa.Column('parent_node_id', sa.UUID(), nullable=True),
        sa.Column('state', postgresql.ENUM('validated', 'sorry', name='new_node_state_enum', create_type=False), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['parent_node_id'], ['new_nodes.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['project_id'], ['new_projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('new_nodes', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_new_nodes_parent_node_id'), ['parent_node_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_new_nodes_project_id'), ['project_id'], unique=False)


def downgrade():
    with op.batch_alter_table('new_nodes', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_new_nodes_project_id'))
        batch_op.drop_index(batch_op.f('ix_new_nodes_parent_node_id'))

    op.drop_table('new_nodes')

    with op.batch_alter_table('new_projects', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_new_projects_author_id'))

    op.drop_table('new_projects')

    new_node_state_enum = postgresql.ENUM('validated', 'sorry', name='new_node_state_enum')
    new_project_visibility_enum = postgresql.ENUM('public', 'private', name='new_project_visibility_enum')

    new_node_state_enum.drop(op.get_bind(), checkfirst=True)
    new_project_visibility_enum.drop(op.get_bind(), checkfirst=True)
