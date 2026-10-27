"""Workflow models — request, step result, and final result."""

import enum

from pydantic import BaseModel, Field


class WorkflowStepStatus(enum.StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class WorkflowStatus(enum.StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"
    NEEDS_HUMAN = "needs_human"


class WorkflowStepResult(BaseModel):
    """Per-step tracking for a workflow execution."""

    name: str
    status: WorkflowStepStatus
    agent: str | None = None
    tool: str | None = None
    output: str = ""
    error: str | None = None
    duration_ms: float = 0


class WorkflowResult(BaseModel):
    """Final structured summary of a workflow execution."""

    task_id: str
    issue_number: int
    repo: str
    status: WorkflowStatus
    branch: str | None = None
    pr_url: str | None = None
    ci_status: str | None = None
    changes_summary: str = ""
    test_summary: str = ""
    steps: list[WorkflowStepResult] = Field(default_factory=list)
    error: str | None = None


class DevWorkflowRequest(BaseModel):
    """API input for starting a dev workflow."""

    issue_number: int
    project_id: str
    priority: str = "normal"
