"""add projects table

Revision ID: a1b2c3d4e5f6
Revises: f4c660d7f079
Create Date: 2026-09-15 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'f4c660d7f079'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('projects',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('local_path', sa.Text(), nullable=False),
    sa.Column('github_repo', sa.String(length=200), nullable=True),
    sa.Column('default_branch', sa.String(length=100), nullable=False),
    sa.Column('stack', sa.JSON(), nullable=False),
    sa.Column('preferred_agent', sa.String(length=100), nullable=True),
    sa.Column('deployment', sa.JSON(), nullable=False),
    sa.Column('instructions', sa.Text(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_projects_name'), 'projects', ['name'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_projects_name'), table_name='projects')
    op.drop_table('projects')
