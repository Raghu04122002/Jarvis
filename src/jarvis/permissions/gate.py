"""Permission gate for controlling tool execution based on risk level."""

from __future__ import annotations

from typing import TYPE_CHECKING

from jarvis.models.approval import RiskLevel

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from jarvis.services.approval_service import ApprovalService


class ApprovalRequiredError(Exception):
    """Raised when an operation requires user approval before execution."""

    def __init__(self, tool_name: str, operation: str, description: str = "") -> None:
        self.tool_name = tool_name
        self.operation = operation
        self.description = description
        msg = f"Approval required for {tool_name}.{operation}"
        if description:
            msg += f": {description}"
        super().__init__(msg)


class PermissionDeniedError(Exception):
    """Raised when an operation is permanently blocked."""

    def __init__(self, tool_name: str, operation: str) -> None:
        self.tool_name = tool_name
        self.operation = operation
        super().__init__(f"Operation permanently blocked: {tool_name}.{operation}")


class PermissionGate:
    """Checks whether a tool operation is allowed to execute.

    SAFE operations always pass. REQUIRES_APPROVAL operations raise
    ApprovalRequiredError unless pre-approved. BLOCKED operations always
    raise PermissionDeniedError.
    """

    def __init__(
        self,
        approval_service: ApprovalService | None = None,
    ) -> None:
        self._pre_approved: set[tuple[str, str]] = set()
        self._approval_service = approval_service

    def check(self, tool_name: str, operation: str, risk_level: RiskLevel) -> None:
        """Check if the operation is permitted.

        Raises ApprovalRequiredError or PermissionDeniedError as needed.
        """
        if risk_level == RiskLevel.SAFE:
            return

        if risk_level == RiskLevel.BLOCKED:
            raise PermissionDeniedError(tool_name, operation)

        # REQUIRES_APPROVAL
        if not self.is_approved(tool_name, operation):
            raise ApprovalRequiredError(tool_name, operation)

    async def check_with_approval(
        self,
        session: AsyncSession,
        task_id: str,
        tool_name: str,
        operation: str,
        risk_level: RiskLevel,
    ) -> None:
        """Check permission with DB-backed approval lookup.

        1. SAFE -> pass
        2. BLOCKED -> raise PermissionDeniedError
        3. REQUIRES_APPROVAL -> check in-memory first, then DB via ApprovalService
        """
        if risk_level == RiskLevel.SAFE:
            return

        if risk_level == RiskLevel.BLOCKED:
            raise PermissionDeniedError(tool_name, operation)

        # REQUIRES_APPROVAL — fast path: in-memory check
        if self.is_approved(tool_name, operation):
            return

        # Slow path: check DB
        if self._approval_service is not None:
            if await self._approval_service.is_approved(session, task_id, tool_name, operation):
                return

        raise ApprovalRequiredError(tool_name, operation)

    def pre_approve(self, tool_name: str, operation: str) -> None:
        """Mark an operation as pre-approved."""
        self._pre_approved.add((tool_name, operation))

    def is_approved(self, tool_name: str, operation: str) -> bool:
        """Return whether the operation has been pre-approved."""
        return (tool_name, operation) in self._pre_approved
