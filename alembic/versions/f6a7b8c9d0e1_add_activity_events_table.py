"""add activity events table

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-10-27 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, Sequence[str], None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('activity_events',
    sa.Column('id', sa.String(length=32), nullable=False),
    sa.Column('type', sa.String(length=50), nullable=False),
    sa.Column('task_id', sa.String(length=32), nullable=True),
    sa.Column('data', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_activity_events_type'), 'activity_events', ['type'], unique=False)
    op.create_index(op.f('ix_activity_events_task_id'), 'activity_events', ['task_id'], unique=False)
    op.create_index(op.f('ix_activity_events_created_at'), 'activity_events', ['created_at'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_activity_events_created_at'), table_name='activity_events')
    op.drop_index(op.f('ix_activity_events_task_id'), table_name='activity_events')
    op.drop_index(op.f('ix_activity_events_type'), table_name='activity_events')
    op.drop_table('activity_events')
