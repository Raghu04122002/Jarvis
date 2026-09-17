"""add approval requests table

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-09-16 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('approval_requests',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('task_id', sa.String(length=32), nullable=False),
    sa.Column('tool_name', sa.String(length=100), nullable=False),
    sa.Column('operation', sa.String(length=100), nullable=False),
    sa.Column('risk_level', sa.String(length=30), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('context', sa.JSON(), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('decided_by', sa.String(length=100), nullable=True),
    sa.Column('decision_reason', sa.String(length=500), nullable=True),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_approval_requests_task_id'), 'approval_requests', ['task_id'], unique=False)
    op.create_index(op.f('ix_approval_requests_status'), 'approval_requests', ['status'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_approval_requests_status'), table_name='approval_requests')
    op.drop_index(op.f('ix_approval_requests_task_id'), table_name='approval_requests')
    op.drop_table('approval_requests')
