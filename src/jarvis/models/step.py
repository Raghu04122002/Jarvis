"""Execution step models for task plans."""

import enum
from datetime import UTC, datetime

from pydantic import BaseModel, Field


class StepStatus(enum.StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class TaskStep(BaseModel):
    """A single execution step within a task plan."""

    id: str
    task_id: str
    sequence: int
    description: str
    status: StepStatus = StepStatus.PENDING
    depends_on: list[str] = Field(default_factory=list)
    result: str | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    completed_at: datetime | None = None
