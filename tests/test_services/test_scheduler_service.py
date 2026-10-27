"""Tests for the SchedulerService with async database persistence."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from jarvis.db.engine import Database
from jarvis.db.tables import Base
from jarvis.events import Event, EventBus, EventType
from jarvis.models.schedule import (
    CreateScheduledTaskRequest,
    ScheduledTaskNotFoundError,
    ScheduledTaskStatus,
    ScheduleType,
    UpdateScheduledTaskRequest,
)
from jarvis.services.scheduler_service import SchedulerService


@pytest.fixture
def event_bus() -> EventBus:
    return EventBus()


@pytest.fixture
def service(event_bus: EventBus) -> SchedulerService:
    return SchedulerService(event_bus)


@pytest.fixture
async def svc_db() -> Database:
    database = Database(url="sqlite+aiosqlite://")
    async with database.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield database  # type: ignore[misc]
    await database.disconnect()


@pytest.fixture
async def session(svc_db: Database) -> AsyncSession:
    async with svc_db.session() as s:
        yield s  # type: ignore[misc]


def _one_time_request(**kwargs: object) -> CreateScheduledTaskRequest:
    defaults = {
        "name": "Test Schedule",
        "schedule_type": ScheduleType.ONE_TIME,
        "task_request": "Check production status",
        "run_at": datetime.now(UTC) + timedelta(hours=1),
    }
    defaults.update(kwargs)
    return CreateScheduledTaskRequest(**defaults)  # type: ignore[arg-type]


def _interval_request(**kwargs: object) -> CreateScheduledTaskRequest:
    defaults = {
        "name": "Interval Schedule",
        "schedule_type": ScheduleType.INTERVAL,
        "task_request": "Check metrics",
        "interval_seconds": 3600,
    }
    defaults.update(kwargs)
    return CreateScheduledTaskRequest(**defaults)  # type: ignore[arg-type]


def _recurring_request(**kwargs: object) -> CreateScheduledTaskRequest:
    defaults = {
        "name": "Recurring Schedule",
        "schedule_type": ScheduleType.RECURRING,
        "task_request": "Weekly summary",
        "cron_expression": "0 9 * * 1",
    }
    defaults.update(kwargs)
    return CreateScheduledTaskRequest(**defaults)  # type: ignore[arg-type]


class TestCreateScheduledTask:
    @pytest.mark.asyncio
    async def test_create_one_time(
        self, service: SchedulerService, session: AsyncSession
    ) -> None:
        req = _one_time_request()
        sched = await service.create_scheduled_task(session, req)
        assert sched.id.startswith("SCHED-")
        assert sched.schedule_type == ScheduleType.ONE_TIME
        assert sched.status == ScheduledTaskStatus.ACTIVE
        assert sched.next_run_at == req.run_at

    @pytest.mark.asyncio
    async def test_create_interval(
        self, service: SchedulerService, session: AsyncSession
    ) -> None:
        sched = await service.create_scheduled_task(session, _interval_request())
        assert sched.schedule_type == ScheduleType.INTERVAL
        assert sched.next_run_at is not None
        assert sched.interval_seconds == 3600

    @pytest.mark.asyncio
    async def test_create_recurring(
        self, service: SchedulerService, session: AsyncSession
    ) -> None:
        sched = await service.create_scheduled_task(session, _recurring_request())
        assert sched.schedule_type == ScheduleType.RECURRING
        assert sched.cron_expression == "0 9 * * 1"
        assert sched.next_run_at is not None

    @pytest.mark.asyncio
    async def test_create_conditional(
        self, service: SchedulerService, session: AsyncSession
    ) -> None:
        req = CreateScheduledTaskRequest(
            name="Conditional",
            schedule_type=ScheduleType.CONDITIONAL,
            task_request="Check if deploy needed",
            condition="deploy_pending",
        )
        sched = await service.create_scheduled_task(session, req)
        assert sched.schedule_type == ScheduleType.CONDITIONAL
        assert sched.next_run_at is None


class TestGetScheduledTask:
    @pytest.mark.asyncio
    async def test_get_existing(
        self, service: SchedulerService, session: AsyncSession
    ) -> None:
        created = await service.create_scheduled_task(session, _one_time_request())
        fetched = await service.get_scheduled_task(session, created.id)
        assert fetched.id == created.id
        assert fetched.name == "Test Schedule"

    @pytest.mark.asyncio
    async def test_get_not_found(
        self, service: SchedulerService, session: AsyncSession
    ) -> None:
        with pytest.raises(ScheduledTaskNotFoundError):
            await service.get_scheduled_task(session, "SCHED-nonexist")


class TestListScheduledTasks:
    @pytest.mark.asyncio
    async def test_list_all(
        self, service: SchedulerService, session: AsyncSession
    ) -> None:
        await service.create_scheduled_task(session, _one_time_request())
        await service.create_scheduled_task(session, _interval_request())
        items = await service.list_scheduled_tasks(session)
        assert len(items) == 2

    @pytest.mark.asyncio
    async def test_filter_by_status(
        self, service: SchedulerService, session: AsyncSession
    ) -> None:
        created = await service.create_scheduled_task(session, _one_time_request())
        await service.pause_scheduled_task(session, created.id)
        active = await service.list_scheduled_tasks(
            session, status=ScheduledTaskStatus.ACTIVE
        )
        paused = await service.list_scheduled_tasks(
            session, status=ScheduledTaskStatus.PAUSED
        )
        assert len(paused) == 1
        # Only one was created (the other was paused from the one)
        assert len(active) == 0

    @pytest.mark.asyncio
    async def test_limit(
        self, service: SchedulerService, session: AsyncSession
    ) -> None:
        for i in range(5):
            await service.create_scheduled_task(
                session, _one_time_request(name=f"Schedule {i}")
            )
        items = await service.list_scheduled_tasks(session, limit=3)
        assert len(items) == 3


class TestUpdateScheduledTask:
    @pytest.mark.asyncio
    async def test_update_name(
        self, service: SchedulerService, session: AsyncSession
    ) -> None:
        created = await service.create_scheduled_task(session, _one_time_request())
        updated = await service.update_scheduled_task(
            session, created.id, UpdateScheduledTaskRequest(name="New Name")
        )
        assert updated.name == "New Name"

    @pytest.mark.asyncio
    async def test_update_interval_recomputes_next_run(
        self, service: SchedulerService, session: AsyncSession
    ) -> None:
        created = await service.create_scheduled_task(session, _interval_request())
        old_next = created.next_run_at
        updated = await service.update_scheduled_task(
            session, created.id, UpdateScheduledTaskRequest(interval_seconds=7200)
        )
        assert updated.interval_seconds == 7200
        assert updated.next_run_at != old_next


class TestPauseResumeScheduledTask:
    @pytest.mark.asyncio
    async def test_pause_active(
        self, service: SchedulerService, session: AsyncSession
    ) -> None:
        created = await service.create_scheduled_task(session, _one_time_request())
        paused = await service.pause_scheduled_task(session, created.id)
        assert paused.status == ScheduledTaskStatus.PAUSED

    @pytest.mark.asyncio
    async def test_pause_non_active_raises(
        self, service: SchedulerService, session: AsyncSession
    ) -> None:
        created = await service.create_scheduled_task(session, _one_time_request())
        await service.pause_scheduled_task(session, created.id)
        with pytest.raises(ValueError, match="Can only pause active"):
            await service.pause_scheduled_task(session, created.id)

    @pytest.mark.asyncio
    async def test_resume_paused(
        self, service: SchedulerService, session: AsyncSession
    ) -> None:
        created = await service.create_scheduled_task(session, _one_time_request())
        await service.pause_scheduled_task(session, created.id)
        resumed = await service.resume_scheduled_task(session, created.id)
        assert resumed.status == ScheduledTaskStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_resume_non_paused_raises(
        self, service: SchedulerService, session: AsyncSession
    ) -> None:
        created = await service.create_scheduled_task(session, _one_time_request())
        with pytest.raises(ValueError, match="Can only resume paused"):
            await service.resume_scheduled_task(session, created.id)


class TestCancelScheduledTask:
    @pytest.mark.asyncio
    async def test_cancel_active(
        self, service: SchedulerService, session: AsyncSession
    ) -> None:
        created = await service.create_scheduled_task(session, _one_time_request())
        cancelled = await service.cancel_scheduled_task(session, created.id)
        assert cancelled.status == ScheduledTaskStatus.CANCELLED
        assert cancelled.next_run_at is None

    @pytest.mark.asyncio
    async def test_cancel_paused(
        self, service: SchedulerService, session: AsyncSession
    ) -> None:
        created = await service.create_scheduled_task(session, _one_time_request())
        await service.pause_scheduled_task(session, created.id)
        cancelled = await service.cancel_scheduled_task(session, created.id)
        assert cancelled.status == ScheduledTaskStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_cancel_completed_raises(
        self, service: SchedulerService, session: AsyncSession
    ) -> None:
        created = await service.create_scheduled_task(session, _one_time_request())
        # Simulate completion via record_run for one-time
        await service.record_run(session, created.id, "TASK-abc", success=True)
        with pytest.raises(ValueError, match="Cannot cancel"):
            await service.cancel_scheduled_task(session, created.id)


class TestGetDueTasks:
    @pytest.mark.asyncio
    async def test_returns_due_tasks(
        self, service: SchedulerService, session: AsyncSession
    ) -> None:
        req = _one_time_request(run_at=datetime.now(UTC) - timedelta(minutes=5))
        await service.create_scheduled_task(session, req)
        due = await service.get_due_tasks(session)
        assert len(due) == 1

    @pytest.mark.asyncio
    async def test_excludes_future_tasks(
        self, service: SchedulerService, session: AsyncSession
    ) -> None:
        req = _one_time_request(run_at=datetime.now(UTC) + timedelta(hours=24))
        await service.create_scheduled_task(session, req)
        due = await service.get_due_tasks(session)
        assert len(due) == 0

    @pytest.mark.asyncio
    async def test_excludes_paused_tasks(
        self, service: SchedulerService, session: AsyncSession
    ) -> None:
        req = _one_time_request(run_at=datetime.now(UTC) - timedelta(minutes=5))
        created = await service.create_scheduled_task(session, req)
        await service.pause_scheduled_task(session, created.id)
        due = await service.get_due_tasks(session)
        assert len(due) == 0


class TestRecordRun:
    @pytest.mark.asyncio
    async def test_increments_run_count(
        self, service: SchedulerService, session: AsyncSession
    ) -> None:
        created = await service.create_scheduled_task(session, _interval_request())
        updated = await service.record_run(
            session, created.id, "TASK-001", success=True
        )
        assert updated.run_count == 1
        assert updated.last_task_id == "TASK-001"

    @pytest.mark.asyncio
    async def test_one_time_completes(
        self, service: SchedulerService, session: AsyncSession
    ) -> None:
        created = await service.create_scheduled_task(session, _one_time_request())
        updated = await service.record_run(
            session, created.id, "TASK-001", success=True
        )
        assert updated.status == ScheduledTaskStatus.COMPLETED
        assert updated.next_run_at is None

    @pytest.mark.asyncio
    async def test_max_runs_completion(
        self, service: SchedulerService, session: AsyncSession
    ) -> None:
        req = _interval_request(max_runs=2)
        created = await service.create_scheduled_task(session, req)
        await service.record_run(session, created.id, "TASK-001", success=True)
        updated = await service.record_run(
            session, created.id, "TASK-002", success=True
        )
        assert updated.status == ScheduledTaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_failure_counting(
        self, service: SchedulerService, session: AsyncSession
    ) -> None:
        created = await service.create_scheduled_task(session, _interval_request())
        updated = await service.record_run(
            session, created.id, "TASK-001", success=False
        )
        assert updated.failure_count == 1
        assert updated.status == ScheduledTaskStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_max_failures_marks_failed(
        self, service: SchedulerService, session: AsyncSession
    ) -> None:
        req = _interval_request(max_failures=2)
        created = await service.create_scheduled_task(session, req)
        await service.record_run(session, created.id, "", success=False)
        updated = await service.record_run(session, created.id, "", success=False)
        assert updated.status == ScheduledTaskStatus.FAILED
        assert updated.next_run_at is None


class TestEventPublishing:
    @pytest.mark.asyncio
    async def test_create_publishes_event(
        self, service: SchedulerService, session: AsyncSession, event_bus: EventBus
    ) -> None:
        events: list[Event] = []
        event_bus.subscribe(EventType.SCHEDULE_CREATED, events.append)
        await service.create_scheduled_task(session, _one_time_request())
        assert len(events) == 1
        assert events[0].type == EventType.SCHEDULE_CREATED

    @pytest.mark.asyncio
    async def test_pause_publishes_event(
        self, service: SchedulerService, session: AsyncSession, event_bus: EventBus
    ) -> None:
        events: list[Event] = []
        event_bus.subscribe(EventType.SCHEDULE_PAUSED, events.append)
        created = await service.create_scheduled_task(session, _one_time_request())
        await service.pause_scheduled_task(session, created.id)
        assert len(events) == 1

    @pytest.mark.asyncio
    async def test_cancel_publishes_event(
        self, service: SchedulerService, session: AsyncSession, event_bus: EventBus
    ) -> None:
        events: list[Event] = []
        event_bus.subscribe(EventType.SCHEDULE_CANCELLED, events.append)
        created = await service.create_scheduled_task(session, _one_time_request())
        await service.cancel_scheduled_task(session, created.id)
        assert len(events) == 1

    @pytest.mark.asyncio
    async def test_resume_publishes_event(
        self, service: SchedulerService, session: AsyncSession, event_bus: EventBus
    ) -> None:
        events: list[Event] = []
        event_bus.subscribe(EventType.SCHEDULE_RESUMED, events.append)
        created = await service.create_scheduled_task(session, _one_time_request())
        await service.pause_scheduled_task(session, created.id)
        await service.resume_scheduled_task(session, created.id)
        assert len(events) == 1

    @pytest.mark.asyncio
    async def test_failed_schedule_publishes_event(
        self, service: SchedulerService, session: AsyncSession, event_bus: EventBus
    ) -> None:
        events: list[Event] = []
        event_bus.subscribe(EventType.SCHEDULE_FAILED, events.append)
        req = _interval_request(max_failures=1)
        created = await service.create_scheduled_task(session, req)
        await service.record_run(session, created.id, "", success=False)
        assert len(events) == 1
