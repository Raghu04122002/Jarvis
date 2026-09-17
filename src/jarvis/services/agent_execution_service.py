"""Agent execution service — manages agent execution records with database persistence."""

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jarvis.db.tables import AgentExecutionRow
from jarvis.events import Event, EventBus, EventType
from jarvis.models.agent import AgentExecution, AgentExecutionNotFoundError, AgentExecutionStatus

logger = logging.getLogger(__name__)


def _row_to_execution(row: AgentExecutionRow) -> AgentExecution:
    """Convert a database row to an AgentExecution domain model."""
    return AgentExecution(
        id=row.id,
        task_id=row.task_id,
        agent_name=row.agent_name,
        prompt=row.prompt,
        project_path=row.project_path,
        status=AgentExecutionStatus(row.status),
        exit_code=row.exit_code,
        stdout=row.stdout,
        stderr=row.stderr,
        duration_ms=row.duration_ms,
        error=row.error,
        created_at=row.created_at,
        started_at=row.started_at,
        completed_at=row.completed_at,
    )


class AgentExecutionService:
    """Manages agent execution record creation, updates, and retrieval.

    Uses async database persistence via SQLAlchemy.
    """

    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus

    def _next_id(self) -> str:
        return f"EXEC-{uuid.uuid4().hex[:8]}"

    async def create_execution(
        self,
        session: AsyncSession,
        task_id: str,
        agent_name: str,
        prompt: str,
        project_path: str,
    ) -> AgentExecution:
        now = datetime.now(UTC)
        exec_id = self._next_id()
        row = AgentExecutionRow(
            id=exec_id,
            task_id=task_id,
            agent_name=agent_name,
            prompt=prompt,
            project_path=project_path,
            status=AgentExecutionStatus.PENDING.value,
            created_at=now,
        )
        session.add(row)
        await session.flush()
        return _row_to_execution(row)

    async def mark_running(
        self,
        session: AsyncSession,
        execution_id: str,
    ) -> AgentExecution:
        row = await session.get(AgentExecutionRow, execution_id)
        if row is None:
            raise AgentExecutionNotFoundError(execution_id)
        now = datetime.now(UTC)
        row.status = AgentExecutionStatus.RUNNING.value
        row.started_at = now
        await session.flush()
        self._event_bus.publish(
            Event(
                type=EventType.AGENT_EXECUTION_STARTED,
                task_id=row.task_id,
                data={"execution_id": execution_id},
            )
        )
        return _row_to_execution(row)

    async def complete_execution(
        self,
        session: AsyncSession,
        execution_id: str,
        *,
        exit_code: int,
        stdout: str,
        stderr: str,
        duration_ms: float,
    ) -> AgentExecution:
        row = await session.get(AgentExecutionRow, execution_id)
        if row is None:
            raise AgentExecutionNotFoundError(execution_id)
        now = datetime.now(UTC)
        row.exit_code = exit_code
        row.stdout = stdout
        row.stderr = stderr
        row.duration_ms = duration_ms
        row.completed_at = now
        row.status = (
            AgentExecutionStatus.COMPLETED.value
            if exit_code == 0
            else AgentExecutionStatus.FAILED.value
        )
        await session.flush()
        self._event_bus.publish(
            Event(
                type=EventType.AGENT_EXECUTION_COMPLETED,
                task_id=row.task_id,
                data={
                    "execution_id": execution_id,
                    "exit_code": exit_code,
                    "status": row.status,
                },
            )
        )
        return _row_to_execution(row)

    async def fail_execution(
        self,
        session: AsyncSession,
        execution_id: str,
        *,
        error: str,
        duration_ms: float | None = None,
        status: AgentExecutionStatus = AgentExecutionStatus.FAILED,
    ) -> AgentExecution:
        row = await session.get(AgentExecutionRow, execution_id)
        if row is None:
            raise AgentExecutionNotFoundError(execution_id)
        now = datetime.now(UTC)
        row.status = status.value
        row.error = error
        row.completed_at = now
        if duration_ms is not None:
            row.duration_ms = duration_ms
        await session.flush()
        self._event_bus.publish(
            Event(
                type=EventType.AGENT_EXECUTION_COMPLETED,
                task_id=row.task_id,
                data={"execution_id": execution_id, "status": row.status, "error": error},
            )
        )
        return _row_to_execution(row)

    async def get_execution(
        self,
        session: AsyncSession,
        execution_id: str,
    ) -> AgentExecution:
        row = await session.get(AgentExecutionRow, execution_id)
        if row is None:
            raise AgentExecutionNotFoundError(execution_id)
        return _row_to_execution(row)

    async def list_executions_for_task(
        self,
        session: AsyncSession,
        task_id: str,
    ) -> list[AgentExecution]:
        stmt = (
            select(AgentExecutionRow)
            .where(AgentExecutionRow.task_id == task_id)
            .order_by(AgentExecutionRow.created_at.desc())
        )
        result = await session.execute(stmt)
        return [_row_to_execution(r) for r in result.scalars().all()]
