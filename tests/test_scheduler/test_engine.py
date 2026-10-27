"""Tests for the SchedulerEngine."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from jarvis.db.engine import Database
from jarvis.db.tables import Base
from jarvis.events import Event, EventBus, EventType
from jarvis.models.schedule import (
    CreateScheduledTaskRequest,
    ScheduleType,
)
from jarvis.models.task import ChatResponse, TaskPriority
from jarvis.scheduler.engine import SchedulerEngine
from jarvis.services.notification_service import NotificationService
from jarvis.services.scheduler_service import SchedulerService


@pytest.fixture
def event_bus() -> EventBus:
    return EventBus()


@pytest.fixture
async def database() -> Database:
    db = Database(url="sqlite+aiosqlite://")
    async with db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield db  # type: ignore[misc]
    await db.disconnect()


@pytest.fixture
def scheduler_service(event_bus: EventBus) -> SchedulerService:
    return SchedulerService(event_bus)


@pytest.fixture
def notification_service(event_bus: EventBus) -> NotificationService:
    return NotificationService(event_bus)


@pytest.fixture
def fake_orchestrator() -> AsyncMock:
    orchestrator = AsyncMock()
    orchestrator.handle_chat = AsyncMock(
        return_value=ChatResponse(
            task_id="TASK-triggered",
            title="Test Task",
            status="planning",
            plan=["Step 1"],
            message="Task created and dispatching.",
        )
    )
    return orchestrator


@pytest.fixture
def engine(
    scheduler_service: SchedulerService,
    fake_orchestrator: AsyncMock,
    database: Database,
    event_bus: EventBus,
    notification_service: NotificationService,
) -> SchedulerEngine:
    return SchedulerEngine(
        scheduler_service,
        fake_orchestrator,
        database,
        event_bus,
        notification_service,
        poll_interval_seconds=1,
    )


class TestSchedulerEngine:
    @pytest.mark.asyncio
    async def test_start_stop(self, engine: SchedulerEngine) -> None:
        engine.start()
        assert engine._running is True
        assert engine._task is not None
        await engine.stop()
        assert engine._running is False

    @pytest.mark.asyncio
    async def test_tick_triggers_due_tasks(
        self,
        engine: SchedulerEngine,
        scheduler_service: SchedulerService,
        database: Database,
        fake_orchestrator: AsyncMock,
    ) -> None:
        # Create a due task
        async with database.session() as session:
            await scheduler_service.create_scheduled_task(
                session,
                CreateScheduledTaskRequest(
                    name="Due Task",
                    schedule_type=ScheduleType.ONE_TIME,
                    task_request="Do something",
                    run_at=datetime.now(UTC) - timedelta(minutes=1),
                ),
            )
            await session.commit()

        await engine._tick()

        fake_orchestrator.handle_chat.assert_called_once()

    @pytest.mark.asyncio
    async def test_tick_does_not_trigger_future_tasks(
        self,
        engine: SchedulerEngine,
        scheduler_service: SchedulerService,
        database: Database,
        fake_orchestrator: AsyncMock,
    ) -> None:
        async with database.session() as session:
            await scheduler_service.create_scheduled_task(
                session,
                CreateScheduledTaskRequest(
                    name="Future Task",
                    schedule_type=ScheduleType.ONE_TIME,
                    task_request="Do something later",
                    run_at=datetime.now(UTC) + timedelta(hours=24),
                ),
            )
            await session.commit()

        await engine._tick()

        fake_orchestrator.handle_chat.assert_not_called()

    @pytest.mark.asyncio
    async def test_tick_handles_orchestrator_error(
        self,
        engine: SchedulerEngine,
        scheduler_service: SchedulerService,
        database: Database,
        fake_orchestrator: AsyncMock,
    ) -> None:
        fake_orchestrator.handle_chat.side_effect = RuntimeError("Orchestrator broke")

        async with database.session() as session:
            created = await scheduler_service.create_scheduled_task(
                session,
                CreateScheduledTaskRequest(
                    name="Error Task",
                    schedule_type=ScheduleType.ONE_TIME,
                    task_request="Will fail",
                    run_at=datetime.now(UTC) - timedelta(minutes=1),
                ),
            )
            await session.commit()
            sched_id = created.id

        await engine._tick()

        # Verify the failure was recorded
        async with database.session() as session:
            sched = await scheduler_service.get_scheduled_task(session, sched_id)
            assert sched.failure_count == 1

    @pytest.mark.asyncio
    async def test_notification_sent_on_trigger(
        self,
        engine: SchedulerEngine,
        scheduler_service: SchedulerService,
        database: Database,
        event_bus: EventBus,
    ) -> None:
        events: list[Event] = []
        event_bus.subscribe(EventType.SCHEDULE_TRIGGERED, events.append)

        async with database.session() as session:
            await scheduler_service.create_scheduled_task(
                session,
                CreateScheduledTaskRequest(
                    name="Notify Task",
                    schedule_type=ScheduleType.ONE_TIME,
                    task_request="Check something",
                    run_at=datetime.now(UTC) - timedelta(minutes=1),
                ),
            )
            await session.commit()

        await engine._tick()

        assert len(events) == 1
        assert events[0].data["success"] is True

    @pytest.mark.asyncio
    async def test_triggered_task_uses_handle_chat(
        self,
        engine: SchedulerEngine,
        scheduler_service: SchedulerService,
        database: Database,
        fake_orchestrator: AsyncMock,
    ) -> None:
        """Verify that triggered tasks go through handle_chat for permission enforcement."""
        async with database.session() as session:
            await scheduler_service.create_scheduled_task(
                session,
                CreateScheduledTaskRequest(
                    name="Permission Test",
                    schedule_type=ScheduleType.ONE_TIME,
                    task_request="Deploy to production",
                    run_at=datetime.now(UTC) - timedelta(minutes=1),
                    task_priority="high",
                ),
            )
            await session.commit()

        await engine._tick()

        call_args = fake_orchestrator.handle_chat.call_args
        chat_request = call_args[0][1]  # second positional arg
        assert chat_request.message == "Deploy to production"
        assert chat_request.priority == TaskPriority.HIGH
