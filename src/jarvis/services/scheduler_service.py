"""Scheduler service — manages scheduled task lifecycle with database persistence."""

import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jarvis.db.tables import ScheduledTaskRow
from jarvis.events import Event, EventBus, EventType
from jarvis.models.schedule import (
    CreateScheduledTaskRequest,
    ScheduledTask,
    ScheduledTaskNotFoundError,
    ScheduledTaskStatus,
    ScheduledTaskSummary,
    ScheduleType,
    UpdateScheduledTaskRequest,
)

logger = logging.getLogger(__name__)


def _row_to_scheduled_task(row: ScheduledTaskRow) -> ScheduledTask:
    return ScheduledTask(
        id=row.id,
        name=row.name,
        description=row.description,
        schedule_type=ScheduleType(row.schedule_type),
        cron_expression=row.cron_expression,
        interval_seconds=row.interval_seconds,
        run_at=row.run_at,
        condition=row.condition,
        task_request=row.task_request,
        task_priority=row.task_priority,
        project_id=row.project_id,
        status=ScheduledTaskStatus(row.status),
        last_run_at=row.last_run_at,
        next_run_at=row.next_run_at,
        run_count=row.run_count,
        max_runs=row.max_runs,
        failure_count=row.failure_count,
        max_failures=row.max_failures,
        last_task_id=row.last_task_id,
        metadata=row.metadata_ if isinstance(row.metadata_, dict) else {},
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _compute_next_run(
    schedule_type: ScheduleType,
    *,
    cron_expression: str | None = None,
    interval_seconds: int | None = None,
    run_at: datetime | None = None,
    base_time: datetime | None = None,
) -> datetime | None:
    """Calculate the next run time based on schedule type."""
    now = base_time or datetime.now(UTC)

    if schedule_type == ScheduleType.ONE_TIME:
        return run_at

    if schedule_type == ScheduleType.INTERVAL:
        if interval_seconds is None:
            return None
        return now + timedelta(seconds=interval_seconds)

    if schedule_type == ScheduleType.RECURRING:
        if cron_expression is None:
            return None
        try:
            from croniter import croniter
            cron = croniter(cron_expression, now)
            next_dt = cron.get_next(datetime)
            if next_dt.tzinfo is None:
                next_dt = next_dt.replace(tzinfo=UTC)
            return next_dt
        except Exception:
            logger.warning("Invalid cron expression: %s", cron_expression)
            return None

    if schedule_type == ScheduleType.CONDITIONAL:
        # Conditional schedules don't have a fixed next_run_at
        return None

    return None


class SchedulerService:
    """Manages scheduled task CRUD and lifecycle."""

    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus

    def _next_id(self) -> str:
        return f"SCHED-{uuid.uuid4().hex[:8]}"

    async def create_scheduled_task(
        self, session: AsyncSession, request: CreateScheduledTaskRequest
    ) -> ScheduledTask:
        now = datetime.now(UTC)
        sched_id = self._next_id()

        next_run = _compute_next_run(
            request.schedule_type,
            cron_expression=request.cron_expression,
            interval_seconds=request.interval_seconds,
            run_at=request.run_at,
        )

        row = ScheduledTaskRow(
            id=sched_id,
            name=request.name,
            description=request.description,
            schedule_type=request.schedule_type.value,
            cron_expression=request.cron_expression,
            interval_seconds=request.interval_seconds,
            run_at=request.run_at,
            condition=request.condition,
            task_request=request.task_request,
            task_priority=request.task_priority,
            project_id=request.project_id,
            status=ScheduledTaskStatus.ACTIVE.value,
            next_run_at=next_run,
            run_count=0,
            max_runs=request.max_runs,
            failure_count=0,
            max_failures=request.max_failures,
            metadata_=request.metadata,
            created_at=now,
            updated_at=now,
        )
        session.add(row)
        await session.flush()

        scheduled = _row_to_scheduled_task(row)
        self._event_bus.publish(
            Event(type=EventType.SCHEDULE_CREATED, task_id=sched_id)
        )
        return scheduled

    async def get_scheduled_task(
        self, session: AsyncSession, schedule_id: str
    ) -> ScheduledTask:
        row = await session.get(ScheduledTaskRow, schedule_id)
        if row is None:
            raise ScheduledTaskNotFoundError(schedule_id)
        return _row_to_scheduled_task(row)

    async def list_scheduled_tasks(
        self,
        session: AsyncSession,
        *,
        status: ScheduledTaskStatus | None = None,
        limit: int = 50,
    ) -> list[ScheduledTaskSummary]:
        stmt = select(ScheduledTaskRow)
        if status is not None:
            stmt = stmt.where(ScheduledTaskRow.status == status.value)
        stmt = stmt.order_by(ScheduledTaskRow.created_at.desc()).limit(limit)
        result = await session.execute(stmt)
        rows = result.scalars().all()
        return [
            ScheduledTaskSummary(
                id=r.id,
                name=r.name,
                schedule_type=ScheduleType(r.schedule_type),
                status=ScheduledTaskStatus(r.status),
                next_run_at=r.next_run_at,
                run_count=r.run_count,
                created_at=r.created_at,
            )
            for r in rows
        ]

    async def update_scheduled_task(
        self,
        session: AsyncSession,
        schedule_id: str,
        updates: UpdateScheduledTaskRequest,
    ) -> ScheduledTask:
        row = await session.get(ScheduledTaskRow, schedule_id)
        if row is None:
            raise ScheduledTaskNotFoundError(schedule_id)

        update_data = updates.model_dump(exclude_none=True)
        if "metadata" in update_data:
            update_data["metadata_"] = update_data.pop("metadata")

        for key, value in update_data.items():
            setattr(row, key, value)

        # Recompute next_run if schedule params changed
        if any(k in update_data for k in ("cron_expression", "interval_seconds", "run_at")):
            row.next_run_at = _compute_next_run(
                ScheduleType(row.schedule_type),
                cron_expression=row.cron_expression,
                interval_seconds=row.interval_seconds,
                run_at=row.run_at,
            )

        row.updated_at = datetime.now(UTC)
        await session.flush()

        self._event_bus.publish(
            Event(type=EventType.SCHEDULE_UPDATED, task_id=schedule_id)
        )
        return _row_to_scheduled_task(row)

    async def pause_scheduled_task(
        self, session: AsyncSession, schedule_id: str
    ) -> ScheduledTask:
        row = await session.get(ScheduledTaskRow, schedule_id)
        if row is None:
            raise ScheduledTaskNotFoundError(schedule_id)

        if ScheduledTaskStatus(row.status) != ScheduledTaskStatus.ACTIVE:
            raise ValueError(
                f"Can only pause active schedules. Current status: {row.status}"
            )

        row.status = ScheduledTaskStatus.PAUSED.value
        row.updated_at = datetime.now(UTC)
        await session.flush()

        self._event_bus.publish(
            Event(type=EventType.SCHEDULE_PAUSED, task_id=schedule_id)
        )
        return _row_to_scheduled_task(row)

    async def resume_scheduled_task(
        self, session: AsyncSession, schedule_id: str
    ) -> ScheduledTask:
        row = await session.get(ScheduledTaskRow, schedule_id)
        if row is None:
            raise ScheduledTaskNotFoundError(schedule_id)

        if ScheduledTaskStatus(row.status) != ScheduledTaskStatus.PAUSED:
            raise ValueError(
                f"Can only resume paused schedules. Current status: {row.status}"
            )

        row.status = ScheduledTaskStatus.ACTIVE.value
        row.next_run_at = _compute_next_run(
            ScheduleType(row.schedule_type),
            cron_expression=row.cron_expression,
            interval_seconds=row.interval_seconds,
            run_at=row.run_at,
        )
        row.updated_at = datetime.now(UTC)
        await session.flush()

        self._event_bus.publish(
            Event(type=EventType.SCHEDULE_RESUMED, task_id=schedule_id)
        )
        return _row_to_scheduled_task(row)

    async def cancel_scheduled_task(
        self, session: AsyncSession, schedule_id: str
    ) -> ScheduledTask:
        row = await session.get(ScheduledTaskRow, schedule_id)
        if row is None:
            raise ScheduledTaskNotFoundError(schedule_id)

        current = ScheduledTaskStatus(row.status)
        if current in (ScheduledTaskStatus.COMPLETED, ScheduledTaskStatus.CANCELLED):
            raise ValueError(
                f"Cannot cancel a schedule in terminal status: {row.status}"
            )

        row.status = ScheduledTaskStatus.CANCELLED.value
        row.next_run_at = None
        row.updated_at = datetime.now(UTC)
        await session.flush()

        self._event_bus.publish(
            Event(type=EventType.SCHEDULE_CANCELLED, task_id=schedule_id)
        )
        return _row_to_scheduled_task(row)

    async def get_due_tasks(
        self, session: AsyncSession
    ) -> list[ScheduledTask]:
        now = datetime.now(UTC)
        stmt = (
            select(ScheduledTaskRow)
            .where(ScheduledTaskRow.status == ScheduledTaskStatus.ACTIVE.value)
            .where(ScheduledTaskRow.next_run_at <= now)
            .order_by(ScheduledTaskRow.next_run_at)
        )
        result = await session.execute(stmt)
        return [_row_to_scheduled_task(r) for r in result.scalars().all()]

    async def record_run(
        self,
        session: AsyncSession,
        schedule_id: str,
        task_id: str,
        *,
        success: bool,
    ) -> ScheduledTask:
        row = await session.get(ScheduledTaskRow, schedule_id)
        if row is None:
            raise ScheduledTaskNotFoundError(schedule_id)

        now = datetime.now(UTC)
        row.last_run_at = now
        row.last_task_id = task_id
        row.run_count += 1
        row.updated_at = now

        if not success:
            row.failure_count += 1
            if row.failure_count >= row.max_failures:
                row.status = ScheduledTaskStatus.FAILED.value
                row.next_run_at = None
                await session.flush()
                self._event_bus.publish(
                    Event(type=EventType.SCHEDULE_FAILED, task_id=schedule_id)
                )
                return _row_to_scheduled_task(row)

        schedule_type = ScheduleType(row.schedule_type)

        # Check max_runs completion
        if row.max_runs is not None and row.run_count >= row.max_runs:
            row.status = ScheduledTaskStatus.COMPLETED.value
            row.next_run_at = None
        elif schedule_type == ScheduleType.ONE_TIME:
            row.status = ScheduledTaskStatus.COMPLETED.value
            row.next_run_at = None
        else:
            row.next_run_at = _compute_next_run(
                schedule_type,
                cron_expression=row.cron_expression,
                interval_seconds=row.interval_seconds,
                run_at=row.run_at,
            )

        await session.flush()
        return _row_to_scheduled_task(row)
