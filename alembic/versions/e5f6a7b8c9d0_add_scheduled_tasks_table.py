"""add scheduled tasks table

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-09-23 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, Sequence[str], None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('scheduled_tasks',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('schedule_type', sa.String(length=30), nullable=False),
    sa.Column('cron_expression', sa.String(length=100), nullable=True),
    sa.Column('interval_seconds', sa.Integer(), nullable=True),
    sa.Column('run_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('condition', sa.Text(), nullable=True),
    sa.Column('task_request', sa.Text(), nullable=False),
    sa.Column('task_priority', sa.String(length=20), nullable=False),
    sa.Column('project_id', sa.String(length=100), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('last_run_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('next_run_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('run_count', sa.Integer(), nullable=False),
    sa.Column('max_runs', sa.Integer(), nullable=True),
    sa.Column('failure_count', sa.Integer(), nullable=False),
    sa.Column('max_failures', sa.Integer(), nullable=False),
    sa.Column('last_task_id', sa.String(length=32), nullable=True),
    sa.Column('metadata', sa.JSON(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_scheduled_tasks_status'), 'scheduled_tasks', ['status'], unique=False)
    op.create_index(op.f('ix_scheduled_tasks_schedule_type'), 'scheduled_tasks', ['schedule_type'], unique=False)
    op.create_index(op.f('ix_scheduled_tasks_next_run_at'), 'scheduled_tasks', ['next_run_at'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_scheduled_tasks_next_run_at'), table_name='scheduled_tasks')
    op.drop_index(op.f('ix_scheduled_tasks_schedule_type'), table_name='scheduled_tasks')
    op.drop_index(op.f('ix_scheduled_tasks_status'), table_name='scheduled_tasks')
    op.drop_table('scheduled_tasks')
