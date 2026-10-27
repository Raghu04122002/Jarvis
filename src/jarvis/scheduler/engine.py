"""Scheduler engine — asyncio background loop that polls for due tasks."""

import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from jarvis.db.engine import Database
from jarvis.events import Event, EventBus, EventType
from jarvis.models.schedule import ScheduledTask
from jarvis.models.task import ChatRequest, TaskPriority
from jarvis.orchestrator.orchestrator import Orchestrator
from jarvis.services.notification_service import NotificationService
from jarvis.services.scheduler_service import SchedulerService

logger = logging.getLogger(__name__)


class SchedulerEngine:
    """Background scheduler that triggers due tasks."""

    def __init__(
        self,
        scheduler_service: SchedulerService,
        orchestrator: Orchestrator,
        database: Database,
        event_bus: EventBus,
        notification_service: NotificationService,
        poll_interval_seconds: int = 30,
    ) -> None:
        self._scheduler_service = scheduler_service
        self._orchestrator = orchestrator
        self._database = database
        self._event_bus = event_bus
        self._notification_service = notification_service
        self._poll_interval = poll_interval_seconds
        self._task: asyncio.Task[None] | None = None
        self._running = False

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("Scheduler engine started (poll interval: %ds)", self._poll_interval)

    async def stop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Scheduler engine stopped")

    async def _loop(self) -> None:
        while self._running:
            try:
                await self._tick()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Scheduler tick error")
            await asyncio.sleep(self._poll_interval)

    async def _tick(self) -> None:
        async with self._database.session() as session:
            due_tasks = await self._scheduler_service.get_due_tasks(session)
            for scheduled in due_tasks:
                try:
                    await self._trigger(session, scheduled)
                except Exception:
                    logger.exception(
                        "Failed to trigger scheduled task %s", scheduled.id
                    )
                    await self._scheduler_service.record_run(
                        session, scheduled.id, "", success=False
                    )
            await session.commit()

    async def _trigger(
        self,
        session: AsyncSession,
        scheduled: ScheduledTask,
    ) -> None:
        """Trigger a scheduled task through the normal orchestrator flow."""
        logger.info("Triggering scheduled task %s: %s", scheduled.id, scheduled.name)

        # Build a ChatRequest from the scheduled task config
        priority = TaskPriority.NORMAL
        try:
            priority = TaskPriority(scheduled.task_priority)
        except ValueError:
            pass

        chat = ChatRequest(
            message=scheduled.task_request,
            project_id=scheduled.project_id,
            priority=priority,
        )

        try:
            response = await self._orchestrator.handle_chat(session, chat)
            success = True
            task_id = response.task_id or ""
        except Exception:
            logger.exception(
                "Orchestrator failed for scheduled task %s", scheduled.id
            )
            success = False
            task_id = ""

        await self._scheduler_service.record_run(
            session, scheduled.id, task_id, success=success
        )

        self._event_bus.publish(
            Event(
                type=EventType.SCHEDULE_TRIGGERED,
                task_id=scheduled.id,
                data={"created_task_id": task_id, "success": success},
            )
        )

        # Send notification
        if success:
            await self._notification_service.notify(
                title=f"Scheduled: {scheduled.name}",
                body=f"Task {task_id} created from schedule {scheduled.id}",
                metadata={"schedule_id": scheduled.id, "task_id": task_id},
            )
