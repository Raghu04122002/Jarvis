"""add memories table

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-09-16 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('memories',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('memory_type', sa.String(length=30), nullable=False),
    sa.Column('scope', sa.String(length=20), nullable=False),
    sa.Column('project_id', sa.String(length=32), nullable=True),
    sa.Column('key', sa.String(length=200), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('embedding', sa.JSON(), nullable=True),
    sa.Column('tags', sa.JSON(), nullable=True),
    sa.Column('metadata', sa.JSON(), nullable=True),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_memories_memory_type'), 'memories', ['memory_type'], unique=False)
    op.create_index(op.f('ix_memories_scope'), 'memories', ['scope'], unique=False)
    op.create_index(op.f('ix_memories_project_id'), 'memories', ['project_id'], unique=False)
    op.create_index(op.f('ix_memories_key'), 'memories', ['key'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_memories_key'), table_name='memories')
    op.drop_index(op.f('ix_memories_project_id'), table_name='memories')
    op.drop_index(op.f('ix_memories_scope'), table_name='memories')
    op.drop_index(op.f('ix_memories_memory_type'), table_name='memories')
    op.drop_table('memories')
