"""Memory models for persistent context across sessions."""

import enum
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class MemoryType(enum.StrEnum):
    PROJECT_MEMORY = "project_memory"
    USER_PREFERENCE = "user_preference"
    TASK_HISTORY = "task_history"
    DECISION = "decision"
    CONVERSATION_SUMMARY = "conversation_summary"


class MemoryScope(enum.StrEnum):
    GLOBAL = "global"
    PROJECT = "project"


class Memory(BaseModel):
    """Full memory representation."""

    id: str
    memory_type: MemoryType
    scope: MemoryScope
    project_id: str | None = None
    key: str
    content: str
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    version: int = 1
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class MemorySummary(BaseModel):
    """Lightweight memory representation for list views."""

    id: str
    memory_type: MemoryType
    scope: MemoryScope
    project_id: str | None
    key: str
    tags: list[str]
    created_at: datetime
    updated_at: datetime


class CreateMemoryRequest(BaseModel):
    """Input model for creating a memory."""

    memory_type: MemoryType
    key: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1)
    project_id: str | None = None
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class UpdateMemoryRequest(BaseModel):
    """Input model for updating a memory. All fields optional."""

    content: str | None = Field(default=None, min_length=1)
    tags: list[str] | None = None
    metadata: dict[str, Any] | None = None


class MemoryNotFoundError(Exception):
    """Raised when a memory is not found."""

    def __init__(self, memory_id: str) -> None:
        self.memory_id = memory_id
        super().__init__(f"Memory not found: {memory_id}")
