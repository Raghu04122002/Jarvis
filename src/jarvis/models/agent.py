"""Agent execution models for tracking agent runs."""

import enum
from datetime import UTC, datetime

from pydantic import BaseModel, Field


class AgentExecutionStatus(enum.StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class AgentExecution(BaseModel):
    """Record of a single agent execution against a task."""

    id: str
    task_id: str
    agent_name: str
    prompt: str
    project_path: str
    status: AgentExecutionStatus = AgentExecutionStatus.PENDING
    exit_code: int | None = None
    stdout: str | None = None
    stderr: str | None = None
    duration_ms: float | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    completed_at: datetime | None = None


class AgentExecutionNotFoundError(Exception):
    def __init__(self, execution_id: str) -> None:
        self.execution_id = execution_id
        super().__init__(f"Agent execution not found: {execution_id}")
