"""Approval service — manages approval request lifecycle with database persistence."""

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jarvis.db.tables import ApprovalRequestRow
from jarvis.events import Event, EventBus, EventType
from jarvis.models.approval import (
    ApprovalAlreadyDecidedError,
    ApprovalNotFoundError,
    ApprovalRequestFull,
    ApprovalStatus,
    ApprovalSummary,
    RiskLevel,
)

logger = logging.getLogger(__name__)


def _row_to_full(row: ApprovalRequestRow) -> ApprovalRequestFull:
    """Convert a database row to an ApprovalRequestFull domain model."""
    return ApprovalRequestFull(
        id=row.id,
        task_id=row.task_id,
        tool_name=row.tool_name,
        operation=row.operation,
        risk_level=RiskLevel(row.risk_level),
        description=row.description or "",
        context=row.context if isinstance(row.context, dict) else {},
        status=ApprovalStatus(row.status),
        decided_by=row.decided_by,
        decision_reason=row.decision_reason,
        expires_at=row.expires_at,
        created_at=row.created_at,
        decided_at=row.decided_at,
    )


def _row_to_summary(row: ApprovalRequestRow) -> ApprovalSummary:
    """Convert a database row to an ApprovalSummary."""
    return ApprovalSummary(
        id=row.id,
        task_id=row.task_id,
        tool_name=row.tool_name,
        operation=row.operation,
        risk_level=RiskLevel(row.risk_level),
        description=row.description or "",
        status=ApprovalStatus(row.status),
        expires_at=row.expires_at,
        created_at=row.created_at,
    )


class ApprovalService:
    """Manages approval request creation, decisions, and queries.

    Uses async database persistence via SQLAlchemy.
    """

    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus

    def _next_id(self) -> str:
        return f"APPR-{uuid.uuid4().hex[:8]}"

    async def create_request(
        self,
        session: AsyncSession,
        task_id: str,
        tool_name: str,
        operation: str,
        risk_level: RiskLevel,
        description: str = "",
        *,
        context: dict[str, object] | None = None,
        expires_at: datetime | None = None,
    ) -> ApprovalRequestFull:
        """Create a new pending approval request."""
        now = datetime.now(UTC)
        approval_id = self._next_id()
        row = ApprovalRequestRow(
            id=approval_id,
            task_id=task_id,
            tool_name=tool_name,
            operation=operation,
            risk_level=risk_level.value,
            description=description,
            context=context or {},
            status=ApprovalStatus.PENDING.value,
            expires_at=expires_at,
            created_at=now,
        )
        session.add(row)
        await session.flush()

        self._event_bus.publish(
            Event(
                type=EventType.APPROVAL_REQUESTED,
                task_id=task_id,
                data={
                    "approval_id": approval_id,
                    "tool_name": tool_name,
                    "operation": operation,
                    "risk_level": risk_level.value,
                },
            )
        )
        return _row_to_full(row)

    async def get_request(self, session: AsyncSession, approval_id: str) -> ApprovalRequestFull:
        """Get an approval request by ID. Raises ApprovalNotFoundError if missing."""
        row = await session.get(ApprovalRequestRow, approval_id)
        if row is None:
            raise ApprovalNotFoundError(approval_id)
        return _row_to_full(row)

    async def list_requests(
        self,
        session: AsyncSession,
        *,
        status: ApprovalStatus | None = None,
        task_id: str | None = None,
        limit: int = 50,
    ) -> list[ApprovalSummary]:
        """List approval requests with optional filtering."""
        stmt = select(ApprovalRequestRow)
        if status is not None:
            stmt = stmt.where(ApprovalRequestRow.status == status.value)
        if task_id is not None:
            stmt = stmt.where(ApprovalRequestRow.task_id == task_id)
        stmt = stmt.order_by(ApprovalRequestRow.created_at.desc()).limit(limit)
        result = await session.execute(stmt)
        return [_row_to_summary(r) for r in result.scalars().all()]

    async def approve(
        self,
        session: AsyncSession,
        approval_id: str,
        *,
        decided_by: str | None = None,
        reason: str | None = None,
    ) -> ApprovalRequestFull:
        """Approve a pending request."""
        row = await session.get(ApprovalRequestRow, approval_id)
        if row is None:
            raise ApprovalNotFoundError(approval_id)
        if row.status != ApprovalStatus.PENDING.value:
            raise ApprovalAlreadyDecidedError(approval_id, ApprovalStatus(row.status))

        now = datetime.now(UTC)
        row.status = ApprovalStatus.APPROVED.value
        row.decided_by = decided_by
        row.decision_reason = reason
        row.decided_at = now
        await session.flush()

        self._event_bus.publish(
            Event(
                type=EventType.APPROVAL_APPROVED,
                task_id=row.task_id,
                data={"approval_id": approval_id, "decided_by": decided_by or ""},
            )
        )
        return _row_to_full(row)

    async def deny(
        self,
        session: AsyncSession,
        approval_id: str,
        *,
        decided_by: str | None = None,
        reason: str | None = None,
    ) -> ApprovalRequestFull:
        """Deny a pending request."""
        row = await session.get(ApprovalRequestRow, approval_id)
        if row is None:
            raise ApprovalNotFoundError(approval_id)
        if row.status != ApprovalStatus.PENDING.value:
            raise ApprovalAlreadyDecidedError(approval_id, ApprovalStatus(row.status))

        now = datetime.now(UTC)
        row.status = ApprovalStatus.DENIED.value
        row.decided_by = decided_by
        row.decision_reason = reason
        row.decided_at = now
        await session.flush()

        self._event_bus.publish(
            Event(
                type=EventType.APPROVAL_DENIED,
                task_id=row.task_id,
                data={"approval_id": approval_id, "decided_by": decided_by or ""},
            )
        )
        return _row_to_full(row)

    async def is_approved(
        self,
        session: AsyncSession,
        task_id: str,
        tool_name: str,
        operation: str,
    ) -> bool:
        """Check if there is an approved request for this task/tool/operation combo."""
        stmt = (
            select(ApprovalRequestRow)
            .where(ApprovalRequestRow.task_id == task_id)
            .where(ApprovalRequestRow.tool_name == tool_name)
            .where(ApprovalRequestRow.operation == operation)
            .where(ApprovalRequestRow.status == ApprovalStatus.APPROVED.value)
            .limit(1)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def expire_stale(self, session: AsyncSession) -> int:
        """Mark expired pending requests. Returns the count of expired requests."""
        now = datetime.now(UTC)
        stmt = (
            select(ApprovalRequestRow)
            .where(ApprovalRequestRow.status == ApprovalStatus.PENDING.value)
            .where(ApprovalRequestRow.expires_at.isnot(None))
            .where(ApprovalRequestRow.expires_at < now)
        )
        result = await session.execute(stmt)
        rows = result.scalars().all()

        count = 0
        for row in rows:
            row.status = ApprovalStatus.EXPIRED.value
            row.decided_at = now
            count += 1
            self._event_bus.publish(
                Event(
                    type=EventType.APPROVAL_EXPIRED,
                    task_id=row.task_id,
                    data={"approval_id": row.id},
                )
            )

        if count > 0:
            await session.flush()
        return count
