"""Scheduled task models for the Jarvis orchestration system."""

import enum
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class ScheduleType(enum.StrEnum):
    ONE_TIME = "one_time"
    RECURRING = "recurring"
    INTERVAL = "interval"
    CONDITIONAL = "conditional"


class ScheduledTaskStatus(enum.StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class ScheduledTask(BaseModel):
    """Full scheduled task representation."""

    id: str
    name: str
    description: str = ""
    schedule_type: ScheduleType
    cron_expression: str | None = None
    interval_seconds: int | None = None
    run_at: datetime | None = None
    condition: str | None = None
    task_request: str
    task_priority: str = "normal"
    project_id: str | None = None
    status: ScheduledTaskStatus = ScheduledTaskStatus.ACTIVE
    last_run_at: datetime | None = None
    next_run_at: datetime | None = None
    run_count: int = 0
    max_runs: int | None = None
    failure_count: int = 0
    max_failures: int = 3
    last_task_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ScheduledTaskSummary(BaseModel):
    """Lightweight scheduled task for list views."""

    id: str
    name: str
    schedule_type: ScheduleType
    status: ScheduledTaskStatus
    next_run_at: datetime | None = None
    run_count: int = 0
    created_at: datetime


class CreateScheduledTaskRequest(BaseModel):
    """API input for creating a scheduled task."""

    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    schedule_type: ScheduleType
    cron_expression: str | None = None
    interval_seconds: int | None = None
    run_at: datetime | None = None
    condition: str | None = None
    task_request: str = Field(min_length=1, max_length=5000)
    task_priority: str = "normal"
    project_id: str | None = None
    max_runs: int | None = None
    max_failures: int = 3
    metadata: dict[str, Any] = Field(default_factory=dict)


class UpdateScheduledTaskRequest(BaseModel):
    """API input for updating a scheduled task."""

    name: str | None = None
    description: str | None = None
    cron_expression: str | None = None
    interval_seconds: int | None = None
    run_at: datetime | None = None
    condition: str | None = None
    task_request: str | None = None
    task_priority: str | None = None
    max_runs: int | None = None
    max_failures: int | None = None
    metadata: dict[str, Any] | None = None


class ScheduledTaskNotFoundError(Exception):
    def __init__(self, schedule_id: str) -> None:
        self.schedule_id = schedule_id
        super().__init__(f"Scheduled task not found: {schedule_id}")
