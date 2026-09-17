"""add agent executions table

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-09-15 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('agent_executions',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('task_id', sa.String(length=32), nullable=False),
    sa.Column('agent_name', sa.String(length=100), nullable=False),
    sa.Column('prompt', sa.Text(), nullable=False),
    sa.Column('project_path', sa.Text(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('exit_code', sa.Integer(), nullable=True),
    sa.Column('stdout', sa.Text(), nullable=True),
    sa.Column('stderr', sa.Text(), nullable=True),
    sa.Column('duration_ms', sa.Float(), nullable=True),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_agent_executions_task_id'), 'agent_executions', ['task_id'], unique=False)
    op.create_index(op.f('ix_agent_executions_status'), 'agent_executions', ['status'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_agent_executions_status'), table_name='agent_executions')
    op.drop_index(op.f('ix_agent_executions_task_id'), table_name='agent_executions')
    op.drop_table('agent_executions')
