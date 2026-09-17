"""Tests for ApprovalService."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from jarvis.events import EventBus, EventType
from jarvis.models.approval import (
    ApprovalAlreadyDecidedError,
    ApprovalNotFoundError,
    ApprovalStatus,
    RiskLevel,
)
from jarvis.services.approval_service import ApprovalService


@pytest.fixture
def event_bus() -> EventBus:
    return EventBus()


@pytest.fixture
def service(event_bus: EventBus) -> ApprovalService:
    return ApprovalService(event_bus)


class TestCreateRequest:
    @pytest.mark.asyncio
    async def test_create(
        self, service: ApprovalService, db_session: AsyncSession
    ) -> None:
        req = await service.create_request(
            db_session,
            task_id="TASK-abc",
            tool_name="git",
            operation="push",
            risk_level=RiskLevel.REQUIRES_APPROVAL,
            description="Pushing to remote",
        )
        assert req.id.startswith("APPR-")
        assert req.task_id == "TASK-abc"
        assert req.tool_name == "git"
        assert req.operation == "push"
        assert req.status == ApprovalStatus.PENDING
        assert req.risk_level == RiskLevel.REQUIRES_APPROVAL
        assert req.description == "Pushing to remote"

    @pytest.mark.asyncio
    async def test_create_with_context(
        self, service: ApprovalService, db_session: AsyncSession
    ) -> None:
        req = await service.create_request(
            db_session,
            task_id="TASK-abc",
            tool_name="git",
            operation="push",
            risk_level=RiskLevel.REQUIRES_APPROVAL,
            context={"branch": "main"},
        )
        assert req.context == {"branch": "main"}

    @pytest.mark.asyncio
    async def test_create_with_expires_at(
        self, service: ApprovalService, db_session: AsyncSession
    ) -> None:
        exp = datetime.now(UTC) + timedelta(hours=1)
        req = await service.create_request(
            db_session,
            task_id="TASK-abc",
            tool_name="git",
            operation="push",
            risk_level=RiskLevel.REQUIRES_APPROVAL,
            expires_at=exp,
        )
        assert req.expires_at is not None

    @pytest.mark.asyncio
    async def test_create_publishes_event(
        self, service: ApprovalService, db_session: AsyncSession, event_bus: EventBus
    ) -> None:
        events: list[object] = []
        event_bus.subscribe(EventType.APPROVAL_REQUESTED, events.append)
        await service.create_request(
            db_session,
            task_id="TASK-abc",
            tool_name="git",
            operation="push",
            risk_level=RiskLevel.REQUIRES_APPROVAL,
        )
        assert len(events) == 1


class TestGetRequest:
    @pytest.mark.asyncio
    async def test_get_existing(
        self, service: ApprovalService, db_session: AsyncSession
    ) -> None:
        created = await service.create_request(
            db_session,
            task_id="TASK-abc",
            tool_name="git",
            operation="push",
            risk_level=RiskLevel.REQUIRES_APPROVAL,
        )
        fetched = await service.get_request(db_session, created.id)
        assert fetched.id == created.id
        assert fetched.tool_name == "git"

    @pytest.mark.asyncio
    async def test_get_not_found(
        self, service: ApprovalService, db_session: AsyncSession
    ) -> None:
        with pytest.raises(ApprovalNotFoundError):
            await service.get_request(db_session, "APPR-nonexist")


class TestListRequests:
    @pytest.mark.asyncio
    async def test_list_empty(
        self, service: ApprovalService, db_session: AsyncSession
    ) -> None:
        result = await service.list_requests(db_session)
        assert result == []

    @pytest.mark.asyncio
    async def test_list_all(
        self, service: ApprovalService, db_session: AsyncSession
    ) -> None:
        await service.create_request(
            db_session, "TASK-1", "git", "push", RiskLevel.REQUIRES_APPROVAL
        )
        await service.create_request(
            db_session, "TASK-2", "git", "commit", RiskLevel.REQUIRES_APPROVAL
        )
        result = await service.list_requests(db_session)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_list_filter_by_status(
        self, service: ApprovalService, db_session: AsyncSession
    ) -> None:
        req = await service.create_request(
            db_session, "TASK-1", "git", "push", RiskLevel.REQUIRES_APPROVAL
        )
        await service.approve(db_session, req.id)
        await service.create_request(
            db_session, "TASK-2", "git", "commit", RiskLevel.REQUIRES_APPROVAL
        )
        pending = await service.list_requests(db_session, status=ApprovalStatus.PENDING)
        assert len(pending) == 1
        assert pending[0].operation == "commit"

    @pytest.mark.asyncio
    async def test_list_filter_by_task_id(
        self, service: ApprovalService, db_session: AsyncSession
    ) -> None:
        await service.create_request(
            db_session, "TASK-1", "git", "push", RiskLevel.REQUIRES_APPROVAL
        )
        await service.create_request(
            db_session, "TASK-2", "git", "commit", RiskLevel.REQUIRES_APPROVAL
        )
        result = await service.list_requests(db_session, task_id="TASK-1")
        assert len(result) == 1
        assert result[0].task_id == "TASK-1"

    @pytest.mark.asyncio
    async def test_list_respects_limit(
        self, service: ApprovalService, db_session: AsyncSession
    ) -> None:
        for i in range(5):
            await service.create_request(
                db_session, f"TASK-{i}", "git", "push", RiskLevel.REQUIRES_APPROVAL
            )
        result = await service.list_requests(db_session, limit=3)
        assert len(result) == 3


class TestApprove:
    @pytest.mark.asyncio
    async def test_approve_pending(
        self, service: ApprovalService, db_session: AsyncSession
    ) -> None:
        req = await service.create_request(
            db_session, "TASK-1", "git", "push", RiskLevel.REQUIRES_APPROVAL
        )
        approved = await service.approve(
            db_session, req.id, decided_by="admin", reason="looks good"
        )
        assert approved.status == ApprovalStatus.APPROVED
        assert approved.decided_by == "admin"
        assert approved.decision_reason == "looks good"
        assert approved.decided_at is not None

    @pytest.mark.asyncio
    async def test_approve_already_approved(
        self, service: ApprovalService, db_session: AsyncSession
    ) -> None:
        req = await service.create_request(
            db_session, "TASK-1", "git", "push", RiskLevel.REQUIRES_APPROVAL
        )
        await service.approve(db_session, req.id)
        with pytest.raises(ApprovalAlreadyDecidedError):
            await service.approve(db_session, req.id)

    @pytest.mark.asyncio
    async def test_approve_not_found(
        self, service: ApprovalService, db_session: AsyncSession
    ) -> None:
        with pytest.raises(ApprovalNotFoundError):
            await service.approve(db_session, "APPR-nope")

    @pytest.mark.asyncio
    async def test_approve_publishes_event(
        self, service: ApprovalService, db_session: AsyncSession, event_bus: EventBus
    ) -> None:
        events: list[object] = []
        event_bus.subscribe(EventType.APPROVAL_APPROVED, events.append)
        req = await service.create_request(
            db_session, "TASK-1", "git", "push", RiskLevel.REQUIRES_APPROVAL
        )
        await service.approve(db_session, req.id)
        assert len(events) == 1


class TestDeny:
    @pytest.mark.asyncio
    async def test_deny_pending(
        self, service: ApprovalService, db_session: AsyncSession
    ) -> None:
        req = await service.create_request(
            db_session, "TASK-1", "git", "push", RiskLevel.REQUIRES_APPROVAL
        )
        denied = await service.deny(
            db_session, req.id, decided_by="admin", reason="too risky"
        )
        assert denied.status == ApprovalStatus.DENIED
        assert denied.decided_by == "admin"
        assert denied.decision_reason == "too risky"

    @pytest.mark.asyncio
    async def test_deny_already_denied(
        self, service: ApprovalService, db_session: AsyncSession
    ) -> None:
        req = await service.create_request(
            db_session, "TASK-1", "git", "push", RiskLevel.REQUIRES_APPROVAL
        )
        await service.deny(db_session, req.id)
        with pytest.raises(ApprovalAlreadyDecidedError):
            await service.deny(db_session, req.id)

    @pytest.mark.asyncio
    async def test_deny_publishes_event(
        self, service: ApprovalService, db_session: AsyncSession, event_bus: EventBus
    ) -> None:
        events: list[object] = []
        event_bus.subscribe(EventType.APPROVAL_DENIED, events.append)
        req = await service.create_request(
            db_session, "TASK-1", "git", "push", RiskLevel.REQUIRES_APPROVAL
        )
        await service.deny(db_session, req.id)
        assert len(events) == 1


class TestIsApproved:
    @pytest.mark.asyncio
    async def test_not_approved(
        self, service: ApprovalService, db_session: AsyncSession
    ) -> None:
        assert await service.is_approved(db_session, "TASK-1", "git", "push") is False

    @pytest.mark.asyncio
    async def test_approved_after_approval(
        self, service: ApprovalService, db_session: AsyncSession
    ) -> None:
        req = await service.create_request(
            db_session, "TASK-1", "git", "push", RiskLevel.REQUIRES_APPROVAL
        )
        await service.approve(db_session, req.id)
        assert await service.is_approved(db_session, "TASK-1", "git", "push") is True

    @pytest.mark.asyncio
    async def test_pending_not_considered_approved(
        self, service: ApprovalService, db_session: AsyncSession
    ) -> None:
        await service.create_request(
            db_session, "TASK-1", "git", "push", RiskLevel.REQUIRES_APPROVAL
        )
        assert await service.is_approved(db_session, "TASK-1", "git", "push") is False

    @pytest.mark.asyncio
    async def test_different_operation_not_approved(
        self, service: ApprovalService, db_session: AsyncSession
    ) -> None:
        req = await service.create_request(
            db_session, "TASK-1", "git", "push", RiskLevel.REQUIRES_APPROVAL
        )
        await service.approve(db_session, req.id)
        assert await service.is_approved(db_session, "TASK-1", "git", "commit") is False


class TestExpireStale:
    @pytest.mark.asyncio
    async def test_expire_stale(
        self, service: ApprovalService, db_session: AsyncSession
    ) -> None:
        past = datetime.now(UTC) - timedelta(hours=1)
        await service.create_request(
            db_session, "TASK-1", "git", "push", RiskLevel.REQUIRES_APPROVAL,
            expires_at=past,
        )
        count = await service.expire_stale(db_session)
        assert count == 1

    @pytest.mark.asyncio
    async def test_expire_stale_ignores_future(
        self, service: ApprovalService, db_session: AsyncSession
    ) -> None:
        future = datetime.now(UTC) + timedelta(hours=1)
        await service.create_request(
            db_session, "TASK-1", "git", "push", RiskLevel.REQUIRES_APPROVAL,
            expires_at=future,
        )
        count = await service.expire_stale(db_session)
        assert count == 0

    @pytest.mark.asyncio
    async def test_expire_stale_ignores_no_expiry(
        self, service: ApprovalService, db_session: AsyncSession
    ) -> None:
        await service.create_request(
            db_session, "TASK-1", "git", "push", RiskLevel.REQUIRES_APPROVAL,
        )
        count = await service.expire_stale(db_session)
        assert count == 0

    @pytest.mark.asyncio
    async def test_expire_publishes_event(
        self, service: ApprovalService, db_session: AsyncSession, event_bus: EventBus
    ) -> None:
        events: list[object] = []
        event_bus.subscribe(EventType.APPROVAL_EXPIRED, events.append)
        past = datetime.now(UTC) - timedelta(hours=1)
        await service.create_request(
            db_session, "TASK-1", "git", "push", RiskLevel.REQUIRES_APPROVAL,
            expires_at=past,
        )
        await service.expire_stale(db_session)
        assert len(events) == 1
