"""Approval API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from jarvis.api.dependencies import get_approval_service, get_session
from jarvis.models.approval import (
    ApprovalAlreadyDecidedError,
    ApprovalDecision,
    ApprovalNotFoundError,
    ApprovalRequestFull,
    ApprovalStatus,
    ApprovalSummary,
)

router = APIRouter()


@router.get("/approvals")
async def list_approvals(
    status: ApprovalStatus | None = None,
    task_id: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
) -> list[ApprovalSummary]:
    """List approval requests with optional filtering."""
    service = get_approval_service()
    return await service.list_requests(session, status=status, task_id=task_id, limit=limit)


@router.get("/approvals/{approval_id}")
async def get_approval(
    approval_id: str,
    session: AsyncSession = Depends(get_session),
) -> ApprovalRequestFull:
    """Get full details of an approval request."""
    service = get_approval_service()
    try:
        return await service.get_request(session, approval_id)
    except ApprovalNotFoundError:
        raise HTTPException(status_code=404, detail=f"Approval request not found: {approval_id}")


@router.post("/approvals/{approval_id}/approve")
async def approve_request(
    approval_id: str,
    decision: ApprovalDecision,
    session: AsyncSession = Depends(get_session),
) -> ApprovalRequestFull:
    """Approve a pending approval request."""
    service = get_approval_service()
    try:
        return await service.approve(
            session,
            approval_id,
            decided_by=decision.decided_by,
            reason=decision.reason,
        )
    except ApprovalNotFoundError:
        raise HTTPException(status_code=404, detail=f"Approval request not found: {approval_id}")
    except ApprovalAlreadyDecidedError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/approvals/{approval_id}/reject")
async def reject_request(
    approval_id: str,
    decision: ApprovalDecision,
    session: AsyncSession = Depends(get_session),
) -> ApprovalRequestFull:
    """Reject a pending approval request."""
    service = get_approval_service()
    try:
        return await service.deny(
            session,
            approval_id,
            decided_by=decision.decided_by,
            reason=decision.reason,
        )
    except ApprovalNotFoundError:
        raise HTTPException(status_code=404, detail=f"Approval request not found: {approval_id}")
    except ApprovalAlreadyDecidedError as e:
        raise HTTPException(status_code=409, detail=str(e))
