"""Schedule API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from jarvis.api.dependencies import get_scheduler_service, get_session
from jarvis.models.schedule import (
    CreateScheduledTaskRequest,
    ScheduledTask,
    ScheduledTaskNotFoundError,
    ScheduledTaskStatus,
    ScheduledTaskSummary,
    UpdateScheduledTaskRequest,
)

router = APIRouter()


def _not_found(schedule_id: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"Scheduled task not found: {schedule_id}")


@router.post("/schedules", status_code=201)
async def create_schedule(
    request: CreateScheduledTaskRequest,
    session: AsyncSession = Depends(get_session),
) -> ScheduledTask:
    service = get_scheduler_service()
    return await service.create_scheduled_task(session, request)


@router.get("/schedules")
async def list_schedules(
    status: ScheduledTaskStatus | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
) -> list[ScheduledTaskSummary]:
    service = get_scheduler_service()
    return await service.list_scheduled_tasks(session, status=status, limit=limit)


@router.get("/schedules/{schedule_id}")
async def get_schedule(
    schedule_id: str,
    session: AsyncSession = Depends(get_session),
) -> ScheduledTask:
    service = get_scheduler_service()
    try:
        return await service.get_scheduled_task(session, schedule_id)
    except ScheduledTaskNotFoundError:
        raise _not_found(schedule_id)


@router.patch("/schedules/{schedule_id}")
async def update_schedule(
    schedule_id: str,
    request: UpdateScheduledTaskRequest,
    session: AsyncSession = Depends(get_session),
) -> ScheduledTask:
    service = get_scheduler_service()
    try:
        return await service.update_scheduled_task(session, schedule_id, request)
    except ScheduledTaskNotFoundError:
        raise _not_found(schedule_id)


@router.post("/schedules/{schedule_id}/pause")
async def pause_schedule(
    schedule_id: str,
    session: AsyncSession = Depends(get_session),
) -> ScheduledTask:
    service = get_scheduler_service()
    try:
        return await service.pause_scheduled_task(session, schedule_id)
    except ScheduledTaskNotFoundError:
        raise _not_found(schedule_id)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/schedules/{schedule_id}/resume")
async def resume_schedule(
    schedule_id: str,
    session: AsyncSession = Depends(get_session),
) -> ScheduledTask:
    service = get_scheduler_service()
    try:
        return await service.resume_scheduled_task(session, schedule_id)
    except ScheduledTaskNotFoundError:
        raise _not_found(schedule_id)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/schedules/{schedule_id}/cancel")
async def cancel_schedule(
    schedule_id: str,
    session: AsyncSession = Depends(get_session),
) -> ScheduledTask:
    service = get_scheduler_service()
    try:
        return await service.cancel_scheduled_task(session, schedule_id)
    except ScheduledTaskNotFoundError:
        raise _not_found(schedule_id)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
