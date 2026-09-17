"""Tests for PermissionGate."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from jarvis.events import EventBus
from jarvis.models.approval import RiskLevel
from jarvis.permissions.gate import (
    ApprovalRequiredError,
    PermissionDeniedError,
    PermissionGate,
)
from jarvis.services.approval_service import ApprovalService


class TestPermissionGate:
    def test_safe_always_passes(self) -> None:
        gate = PermissionGate()
        gate.check("tool", "op", RiskLevel.SAFE)  # no exception

    def test_blocked_always_raises(self) -> None:
        gate = PermissionGate()
        with pytest.raises(PermissionDeniedError) as exc_info:
            gate.check("tool", "op", RiskLevel.BLOCKED)
        assert exc_info.value.tool_name == "tool"
        assert exc_info.value.operation == "op"

    def test_requires_approval_without_pre_approval(self) -> None:
        gate = PermissionGate()
        with pytest.raises(ApprovalRequiredError) as exc_info:
            gate.check("tool", "op", RiskLevel.REQUIRES_APPROVAL)
        assert exc_info.value.tool_name == "tool"
        assert exc_info.value.operation == "op"

    def test_requires_approval_with_pre_approval(self) -> None:
        gate = PermissionGate()
        gate.pre_approve("tool", "op")
        gate.check("tool", "op", RiskLevel.REQUIRES_APPROVAL)  # no exception

    def test_is_approved_false_by_default(self) -> None:
        gate = PermissionGate()
        assert gate.is_approved("tool", "op") is False

    def test_is_approved_after_pre_approve(self) -> None:
        gate = PermissionGate()
        gate.pre_approve("tool", "op")
        assert gate.is_approved("tool", "op") is True

    def test_pre_approve_is_specific(self) -> None:
        gate = PermissionGate()
        gate.pre_approve("git", "push")
        assert gate.is_approved("git", "push") is True
        assert gate.is_approved("git", "commit") is False
        assert gate.is_approved("github", "push") is False

    def test_blocked_ignores_pre_approval(self) -> None:
        gate = PermissionGate()
        gate.pre_approve("tool", "op")
        with pytest.raises(PermissionDeniedError):
            gate.check("tool", "op", RiskLevel.BLOCKED)

    def test_approval_required_error_message(self) -> None:
        err = ApprovalRequiredError("git", "push", "pushing to remote")
        assert "git.push" in str(err)
        assert "pushing to remote" in str(err)

    def test_approval_required_error_no_description(self) -> None:
        err = ApprovalRequiredError("git", "push")
        assert "git.push" in str(err)


class TestCheckWithApproval:
    @pytest.mark.asyncio
    async def test_safe_passes(self, db_session: AsyncSession) -> None:
        gate = PermissionGate()
        await gate.check_with_approval(
            db_session, "TASK-1", "git", "status", RiskLevel.SAFE
        )

    @pytest.mark.asyncio
    async def test_blocked_raises(self, db_session: AsyncSession) -> None:
        gate = PermissionGate()
        with pytest.raises(PermissionDeniedError):
            await gate.check_with_approval(
                db_session, "TASK-1", "tool", "op", RiskLevel.BLOCKED
            )

    @pytest.mark.asyncio
    async def test_requires_approval_raises_without_db(
        self, db_session: AsyncSession
    ) -> None:
        gate = PermissionGate()
        with pytest.raises(ApprovalRequiredError):
            await gate.check_with_approval(
                db_session, "TASK-1", "git", "push", RiskLevel.REQUIRES_APPROVAL
            )

    @pytest.mark.asyncio
    async def test_requires_approval_passes_with_pre_approve(
        self, db_session: AsyncSession
    ) -> None:
        gate = PermissionGate()
        gate.pre_approve("git", "push")
        await gate.check_with_approval(
            db_session, "TASK-1", "git", "push", RiskLevel.REQUIRES_APPROVAL
        )

    @pytest.mark.asyncio
    async def test_requires_approval_passes_with_db_approval(
        self, db_session: AsyncSession
    ) -> None:
        event_bus = EventBus()
        approval_service = ApprovalService(event_bus)
        gate = PermissionGate(approval_service=approval_service)

        req = await approval_service.create_request(
            db_session, "TASK-1", "git", "push", RiskLevel.REQUIRES_APPROVAL
        )
        await approval_service.approve(db_session, req.id)

        # Should not raise
        await gate.check_with_approval(
            db_session, "TASK-1", "git", "push", RiskLevel.REQUIRES_APPROVAL
        )
