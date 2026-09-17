"""Tests for AgentExecutionService."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from jarvis.events import EventBus
from jarvis.models.agent import (
    AgentExecutionNotFoundError,
    AgentExecutionStatus,
)
from jarvis.services.agent_execution_service import AgentExecutionService


@pytest.fixture
def event_bus() -> EventBus:
    return EventBus()


@pytest.fixture
def service(event_bus: EventBus) -> AgentExecutionService:
    return AgentExecutionService(event_bus)


class TestCreateExecution:
    @pytest.mark.asyncio
    async def test_create(
        self,
        service: AgentExecutionService,
        db_session: AsyncSession,
    ) -> None:
        execution = await service.create_execution(
            db_session,
            task_id="TASK-abc",
            agent_name="claude_code",
            prompt="fix the bug",
            project_path="/projects/test",
        )

        assert execution.id.startswith("EXEC-")
        assert execution.task_id == "TASK-abc"
        assert execution.agent_name == "claude_code"
        assert execution.prompt == "fix the bug"
        assert execution.project_path == "/projects/test"
        assert execution.status == AgentExecutionStatus.PENDING
        assert execution.exit_code is None


class TestMarkRunning:
    @pytest.mark.asyncio
    async def test_mark_running(
        self,
        service: AgentExecutionService,
        db_session: AsyncSession,
    ) -> None:
        execution = await service.create_execution(
            db_session,
            task_id="TASK-abc",
            agent_name="claude_code",
            prompt="fix",
            project_path="/tmp",
        )

        updated = await service.mark_running(
            db_session, execution.id,
        )

        assert updated.status == AgentExecutionStatus.RUNNING
        assert updated.started_at is not None

    @pytest.mark.asyncio
    async def test_mark_running_not_found(
        self,
        service: AgentExecutionService,
        db_session: AsyncSession,
    ) -> None:
        with pytest.raises(AgentExecutionNotFoundError):
            await service.mark_running(db_session, "EXEC-nonexist")


class TestCompleteExecution:
    @pytest.mark.asyncio
    async def test_complete_success(
        self,
        service: AgentExecutionService,
        db_session: AsyncSession,
    ) -> None:
        execution = await service.create_execution(
            db_session,
            task_id="TASK-abc",
            agent_name="claude_code",
            prompt="fix",
            project_path="/tmp",
        )
        await service.mark_running(db_session, execution.id)

        completed = await service.complete_execution(
            db_session,
            execution.id,
            exit_code=0,
            stdout="done",
            stderr="",
            duration_ms=1500.0,
        )

        assert completed.status == AgentExecutionStatus.COMPLETED
        assert completed.exit_code == 0
        assert completed.stdout == "done"
        assert completed.duration_ms == 1500.0
        assert completed.completed_at is not None

    @pytest.mark.asyncio
    async def test_complete_failure(
        self,
        service: AgentExecutionService,
        db_session: AsyncSession,
    ) -> None:
        execution = await service.create_execution(
            db_session,
            task_id="TASK-abc",
            agent_name="claude_code",
            prompt="fix",
            project_path="/tmp",
        )
        await service.mark_running(db_session, execution.id)

        completed = await service.complete_execution(
            db_session,
            execution.id,
            exit_code=1,
            stdout="",
            stderr="error occurred",
            duration_ms=500.0,
        )

        assert completed.status == AgentExecutionStatus.FAILED
        assert completed.exit_code == 1
        assert completed.stderr == "error occurred"

    @pytest.mark.asyncio
    async def test_complete_not_found(
        self,
        service: AgentExecutionService,
        db_session: AsyncSession,
    ) -> None:
        with pytest.raises(AgentExecutionNotFoundError):
            await service.complete_execution(
                db_session,
                "EXEC-nope",
                exit_code=0,
                stdout="",
                stderr="",
                duration_ms=0,
            )


class TestFailExecution:
    @pytest.mark.asyncio
    async def test_fail(
        self,
        service: AgentExecutionService,
        db_session: AsyncSession,
    ) -> None:
        execution = await service.create_execution(
            db_session,
            task_id="TASK-abc",
            agent_name="claude_code",
            prompt="fix",
            project_path="/tmp",
        )

        failed = await service.fail_execution(
            db_session,
            execution.id,
            error="timeout",
            duration_ms=30000.0,
            status=AgentExecutionStatus.TIMEOUT,
        )

        assert failed.status == AgentExecutionStatus.TIMEOUT
        assert failed.error == "timeout"
        assert failed.duration_ms == 30000.0

    @pytest.mark.asyncio
    async def test_fail_not_found(
        self,
        service: AgentExecutionService,
        db_session: AsyncSession,
    ) -> None:
        with pytest.raises(AgentExecutionNotFoundError):
            await service.fail_execution(
                db_session, "EXEC-nope", error="fail",
            )


class TestGetExecution:
    @pytest.mark.asyncio
    async def test_get(
        self,
        service: AgentExecutionService,
        db_session: AsyncSession,
    ) -> None:
        execution = await service.create_execution(
            db_session,
            task_id="TASK-abc",
            agent_name="claude_code",
            prompt="fix",
            project_path="/tmp",
        )

        fetched = await service.get_execution(
            db_session, execution.id,
        )

        assert fetched.id == execution.id
        assert fetched.task_id == "TASK-abc"

    @pytest.mark.asyncio
    async def test_get_not_found(
        self,
        service: AgentExecutionService,
        db_session: AsyncSession,
    ) -> None:
        with pytest.raises(AgentExecutionNotFoundError):
            await service.get_execution(db_session, "EXEC-nope")


class TestListExecutionsForTask:
    @pytest.mark.asyncio
    async def test_list(
        self,
        service: AgentExecutionService,
        db_session: AsyncSession,
    ) -> None:
        await service.create_execution(
            db_session,
            task_id="TASK-abc",
            agent_name="claude_code",
            prompt="fix 1",
            project_path="/tmp",
        )
        await service.create_execution(
            db_session,
            task_id="TASK-abc",
            agent_name="claude_code",
            prompt="fix 2",
            project_path="/tmp",
        )
        await service.create_execution(
            db_session,
            task_id="TASK-other",
            agent_name="claude_code",
            prompt="other",
            project_path="/tmp",
        )

        results = await service.list_executions_for_task(
            db_session, "TASK-abc",
        )

        assert len(results) == 2
        assert all(r.task_id == "TASK-abc" for r in results)

    @pytest.mark.asyncio
    async def test_list_empty(
        self,
        service: AgentExecutionService,
        db_session: AsyncSession,
    ) -> None:
        results = await service.list_executions_for_task(
            db_session, "TASK-nonexist",
        )
        assert results == []
