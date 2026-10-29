"""Approval workflow models."""

import enum
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ApprovalStatus(enum.StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"


class RiskLevel(enum.StrEnum):
    SAFE = "safe"
    REQUIRES_APPROVAL = "requires_approval"
    BLOCKED = "blocked"


class ApprovalRequest(BaseModel):
    """A request for user approval before executing a risky action."""

    id: str
    task_id: str
    action: str
    risk_level: RiskLevel
    description: str = ""
    status: ApprovalStatus = ApprovalStatus.PENDING
    requested_at: datetime = Field(default_factory=datetime.utcnow)
    responded_at: datetime | None = None


class ApprovalRequestFull(BaseModel):
    """Full representation of an approval request with all DB fields."""

    id: str
    task_id: str
    tool_name: str
    operation: str
    risk_level: RiskLevel
    description: str = ""
    context: dict[str, Any] = Field(default_factory=dict)
    status: ApprovalStatus = ApprovalStatus.PENDING
    decided_by: str | None = None
    decision_reason: str | None = None
    expires_at: datetime | None = None
    created_at: datetime
    decided_at: datetime | None = None


class ApprovalSummary(BaseModel):
    """Lightweight approval request summary for list endpoints."""

    id: str
    task_id: str
    tool_name: str
    operation: str
    risk_level: RiskLevel = RiskLevel.REQUIRES_APPROVAL
    description: str = ""
    status: ApprovalStatus
    expires_at: datetime | None = None
    created_at: datetime


class CreateApprovalRequest(BaseModel):
    """Internal model for creating approval requests."""

    task_id: str
    tool_name: str
    operation: str
    risk_level: RiskLevel
    description: str = ""
    context: dict[str, Any] = Field(default_factory=dict)


class ApprovalDecision(BaseModel):
    """Request body for approve/reject API endpoints."""

    decided_by: str | None = None
    reason: str | None = None


class ApprovalNotFoundError(Exception):
    """Raised when an approval request is not found."""

    def __init__(self, approval_id: str) -> None:
        self.approval_id = approval_id
        super().__init__(f"Approval request not found: {approval_id}")


class ApprovalAlreadyDecidedError(Exception):
    """Raised when trying to approve/deny a non-pending request."""

    def __init__(self, approval_id: str, current_status: ApprovalStatus) -> None:
        self.approval_id = approval_id
        self.current_status = current_status
        super().__init__(f"Approval request {approval_id} already decided: {current_status}")
