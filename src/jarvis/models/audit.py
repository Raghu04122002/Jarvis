"""Audit log models."""

from datetime import datetime

from pydantic import BaseModel, Field


class AuditEntry(BaseModel):
    """A single audit log entry recording a Jarvis action."""

    id: str
    task_id: str | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    agent: str | None = None
    tool: str | None = None
    action: str
    args_metadata: dict[str, str] = Field(default_factory=dict)
    result_summary: str = ""
    success: bool = True
    duration_ms: int | None = None
    approval_state: str | None = None
