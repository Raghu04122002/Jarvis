"""Task models for the Jarvis orchestration system."""

import enum
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class TaskStatus(enum.StrEnum):
    CREATED = "created"
    PLANNING = "planning"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    RUNNING = "running"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(enum.StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


# Centralized state transition table.
# Maps current status -> set of valid next statuses.
VALID_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.CREATED: {TaskStatus.PLANNING, TaskStatus.CANCELLED},
    TaskStatus.PLANNING: {
        TaskStatus.WAITING_FOR_APPROVAL,
        TaskStatus.RUNNING,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.WAITING_FOR_APPROVAL: {
        TaskStatus.RUNNING,
        TaskStatus.CANCELLED,
    },
    TaskStatus.RUNNING: {
        TaskStatus.VERIFYING,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.VERIFYING: {
        TaskStatus.COMPLETED,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.COMPLETED: set(),
    TaskStatus.FAILED: {TaskStatus.PLANNING},  # retry goes back to planning
    TaskStatus.CANCELLED: set(),
}

# Terminal states — tasks in these states cannot transition further
# (except FAILED which allows retry).
TERMINAL_STATES: frozenset[TaskStatus] = frozenset(
    {
        TaskStatus.COMPLETED,
        TaskStatus.CANCELLED,
    }
)


class InvalidTransitionError(Exception):
    """Raised when a task state transition is not allowed."""

    def __init__(self, current: TaskStatus, target: TaskStatus) -> None:
        self.current = current
        self.target = target
        super().__init__(f"Cannot transition from {current!r} to {target!r}")


def validate_transition(current: TaskStatus, target: TaskStatus) -> None:
    """Raise InvalidTransitionError if the transition is not valid."""
    allowed = VALID_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise InvalidTransitionError(current, target)


class ChatTurn(BaseModel):
    """One earlier message in the conversation, sent for context."""

    role: Literal["user", "assistant"]
    content: str = Field(max_length=20000)


class ChatRequest(BaseModel):
    """Input model for a natural-language user request."""

    message: str = Field(min_length=1, max_length=5000)
    project_id: str | None = None
    priority: TaskPriority = TaskPriority.NORMAL
    # Earlier turns of the same conversation (oldest first), for context.
    history: list[ChatTurn] = Field(default_factory=list, max_length=100)
    # Client-side conversation id; stored on tasks so they link back to the chat.
    conversation_id: str | None = Field(default=None, max_length=100)


class Task(BaseModel):
    """Full task representation."""

    id: str
    request: str
    title: str
    description: str = ""
    status: TaskStatus = TaskStatus.CREATED
    priority: TaskPriority = TaskPriority.NORMAL
    project_id: str | None = None
    parent_task_id: str | None = None
    plan: list[str] = Field(default_factory=list)
    current_step: int | None = None
    result: str | None = None
    error: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)
    version: int = 1  # optimistic concurrency control
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    completed_at: datetime | None = None


class ChatResponse(BaseModel):
    """Response from the orchestrator's handle_chat method."""

    task_id: str | None = None
    title: str
    status: str
    plan: list[str] = Field(default_factory=list)
    answer: str | None = None
    message: str
    # Tools the model ran: {id, name, label, args, status, output}.
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)


class TaskSummary(BaseModel):
    """Lightweight task representation for list views."""

    id: str
    title: str
    status: TaskStatus
    priority: TaskPriority
    created_at: datetime
    updated_at: datetime
