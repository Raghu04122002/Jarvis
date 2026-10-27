"""Task service — manages task lifecycle operations with database persistence.

All task business logic lives here, not in API route handlers.
"""

import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from jarvis.db.tables import TaskRow, TaskStepRow
from jarvis.events import Event, EventBus, EventType
from jarvis.models.step import StepStatus, TaskStep
from jarvis.models.task import (
    TERMINAL_STATES,
    InvalidTransitionError,
    Task,
    TaskPriority,
    TaskStatus,
    TaskSummary,
    validate_transition,
)

logger = logging.getLogger(__name__)


class TaskNotFoundError(Exception):
    def __init__(self, task_id: str) -> None:
        self.task_id = task_id
        super().__init__(f"Task not found: {task_id}")


def _row_to_task(row: TaskRow) -> Task:
    """Convert a database row to a Task domain model."""
    return Task(
        id=row.id,
        request=row.request,
        title=row.title,
        description=row.description,
        status=TaskStatus(row.status),
        priority=TaskPriority(row.priority),
        project_id=row.project_id,
        parent_task_id=row.parent_task_id,
        plan=row.plan if isinstance(row.plan, list) else [],
        current_step=row.current_step,
        result=row.result,
        error=row.error,
        metadata=row.metadata_ if isinstance(row.metadata_, dict) else {},
        version=row.version,
        created_at=row.created_at,
        updated_at=row.updated_at,
        started_at=row.started_at,
        completed_at=row.completed_at,
    )


def _step_row_to_step(row: TaskStepRow) -> TaskStep:
    """Convert a database row to a TaskStep domain model."""
    return TaskStep(
        id=row.id,
        task_id=row.task_id,
        sequence=row.sequence,
        description=row.description,
        status=StepStatus(row.status),
        depends_on=row.depends_on if isinstance(row.depends_on, list) else [],
        result=row.result,
        error=row.error,
        created_at=row.created_at,
        started_at=row.started_at,
        completed_at=row.completed_at,
    )


class TaskService:
    """Manages task creation, retrieval, and state transitions.

    Uses async database persistence via SQLAlchemy.
    Concurrency safety: uses version-based optimistic concurrency control.
    """

    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus

    def _next_id(self) -> str:
        return f"TASK-{uuid.uuid4().hex[:8]}"

    def _step_id(self) -> str:
        return f"STEP-{uuid.uuid4().hex[:8]}"

    async def create_task(
        self,
        session: AsyncSession,
        request: str,
        title: str,
        *,
        description: str = "",
        project_id: str | None = None,
        priority: TaskPriority = TaskPriority.NORMAL,
        metadata: dict[str, str] | None = None,
    ) -> Task:
        now = datetime.now(UTC)
        task_id = self._next_id()
        row = TaskRow(
            id=task_id,
            request=request,
            title=title,
            description=description,
            status=TaskStatus.CREATED.value,
            priority=priority.value,
            project_id=project_id,
            plan=[],
            metadata_=metadata or {},
            version=1,
            created_at=now,
            updated_at=now,
        )
        session.add(row)
        await session.flush()
        task = _row_to_task(row)
        self._event_bus.publish(
            Event(
                type=EventType.TASK_CREATED,
                task_id=task_id,
                data={"title": title, "project_id": project_id or ""},
            )
        )
        return task

    async def get_task(self, session: AsyncSession, task_id: str) -> Task:
        row = await session.get(TaskRow, task_id)
        if row is None:
            raise TaskNotFoundError(task_id)
        return _row_to_task(row)

    async def list_tasks(
        self,
        session: AsyncSession,
        *,
        status: TaskStatus | None = None,
        priority: TaskPriority | None = None,
        project_id: str | None = None,
        query: str | None = None,
        limit: int = 50,
    ) -> list[TaskSummary]:
        stmt = select(TaskRow)
        if status is not None:
            stmt = stmt.where(TaskRow.status == status.value)
        if priority is not None:
            stmt = stmt.where(TaskRow.priority == priority.value)
        if project_id is not None:
            stmt = stmt.where(TaskRow.project_id == project_id)
        if query:
            like = f"%{query.strip()}%"
            stmt = stmt.where(or_(TaskRow.title.ilike(like), TaskRow.request.ilike(like)))
        stmt = stmt.order_by(TaskRow.created_at.desc()).limit(limit)
        result = await session.execute(stmt)
        rows = result.scalars().all()
        return [
            TaskSummary(
                id=r.id,
                title=r.title,
                status=TaskStatus(r.status),
                priority=TaskPriority(r.priority),
                project_id=r.project_id,
                error=r.error,
                agent_name=(r.metadata_ or {}).get("agent_name"),
                conversation_id=(r.metadata_ or {}).get("conversation_id"),
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
            for r in rows
        ]

    async def fail_stale_tasks(
        self, session: AsyncSession, *, planning_timeout: timedelta
    ) -> list[str]:
        """Fail tasks stuck in PLANNING longer than ``planning_timeout``.

        A task only sits in PLANNING until it is dispatched, so one that is
        still there after the timeout lost its dispatch (e.g. a restart).
        Returns the ids of the tasks that were failed.
        """
        cutoff = datetime.now(UTC) - planning_timeout
        stmt = select(TaskRow.id, TaskRow.updated_at).where(
            TaskRow.status == TaskStatus.PLANNING.value
        )
        rows = (await session.execute(stmt)).all()
        stale = [
            task_id
            for task_id, updated in rows
            # SQLite returns naive datetimes; treat them as UTC.
            if (updated if updated.tzinfo else updated.replace(tzinfo=UTC)) < cutoff
        ]
        minutes = int(planning_timeout.total_seconds() // 60)
        for task_id in stale:
            await self.transition_task(
                session,
                task_id,
                TaskStatus.FAILED,
                error=f"Stale: stuck in planning for over {minutes} min and was never "
                "dispatched. Retry to run it again.",
            )
        return stale

    async def transition_task(
        self,
        session: AsyncSession,
        task_id: str,
        target_status: TaskStatus,
        *,
        error: str | None = None,
        result: str | None = None,
    ) -> Task:
        """Transition a task to a new status, enforcing the state machine.

        Uses optimistic concurrency control via the version field.
        """
        row = await session.get(TaskRow, task_id)
        if row is None:
            raise TaskNotFoundError(task_id)

        current_status = TaskStatus(row.status)
        validate_transition(current_status, target_status)

        now = datetime.now(UTC)
        row.status = target_status.value
        row.updated_at = now
        row.version += 1

        if target_status == TaskStatus.RUNNING and row.started_at is None:
            row.started_at = now
        if target_status in TERMINAL_STATES or target_status == TaskStatus.FAILED:
            row.completed_at = now
        if error is not None:
            row.error = error
        if result is not None:
            row.result = result

        await session.flush()

        event_type = {
            TaskStatus.COMPLETED: EventType.TASK_COMPLETED,
            TaskStatus.FAILED: EventType.TASK_FAILED,
            TaskStatus.CANCELLED: EventType.TASK_CANCELLED,
        }.get(target_status, EventType.TASK_STATE_CHANGED)

        self._event_bus.publish(
            Event(
                type=event_type,
                task_id=task_id,
                data={"from": current_status.value, "to": target_status.value},
            )
        )
        return _row_to_task(row)

    async def cancel_task(self, session: AsyncSession, task_id: str) -> Task:
        """Cancel a task if it's in a cancellable state."""
        row = await session.get(TaskRow, task_id)
        if row is None:
            raise TaskNotFoundError(task_id)
        current_status = TaskStatus(row.status)
        if current_status in TERMINAL_STATES:
            raise InvalidTransitionError(current_status, TaskStatus.CANCELLED)

        # Cancel pending/running steps
        stmt = select(TaskStepRow).where(TaskStepRow.task_id == task_id)
        result = await session.execute(stmt)
        for step_row in result.scalars().all():
            if step_row.status in (StepStatus.PENDING.value, StepStatus.RUNNING.value):
                step_row.status = StepStatus.CANCELLED.value
                step_row.completed_at = datetime.now(UTC)

        return await self.transition_task(session, task_id, TaskStatus.CANCELLED)

    async def complete_task(self, session: AsyncSession, task_id: str, result: str = "") -> Task:
        return await self.transition_task(session, task_id, TaskStatus.COMPLETED, result=result)

    async def fail_task(self, session: AsyncSession, task_id: str, error: str) -> Task:
        return await self.transition_task(session, task_id, TaskStatus.FAILED, error=error)

    # --- Steps ---

    async def add_steps(
        self, session: AsyncSession, task_id: str, descriptions: list[str]
    ) -> list[TaskStep]:
        """Create execution steps for a task."""
        row = await session.get(TaskRow, task_id)
        if row is None:
            raise TaskNotFoundError(task_id)

        now = datetime.now(UTC)
        steps: list[TaskStep] = []
        for i, desc in enumerate(descriptions):
            step_row = TaskStepRow(
                id=self._step_id(),
                task_id=task_id,
                sequence=i + 1,
                description=desc,
                status=StepStatus.PENDING.value,
                depends_on=[],
                created_at=now,
            )
            session.add(step_row)
            steps.append(_step_row_to_step(step_row))
        await session.flush()
        return steps

    async def get_steps(self, session: AsyncSession, task_id: str) -> list[TaskStep]:
        row = await session.get(TaskRow, task_id)
        if row is None:
            raise TaskNotFoundError(task_id)
        stmt = (
            select(TaskStepRow)
            .where(TaskStepRow.task_id == task_id)
            .order_by(TaskStepRow.sequence)
        )
        result = await session.execute(stmt)
        return [_step_row_to_step(r) for r in result.scalars().all()]

    async def update_task_plan(self, session: AsyncSession, task_id: str, plan: list[str]) -> Task:
        """Store a plan on the task."""
        row = await session.get(TaskRow, task_id)
        if row is None:
            raise TaskNotFoundError(task_id)
        row.plan = list(plan)
        row.updated_at = datetime.now(UTC)
        await session.flush()
        return _row_to_task(row)
