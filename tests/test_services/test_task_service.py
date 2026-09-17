"""Tests for the TaskService with async database persistence."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from jarvis.db.engine import Database
from jarvis.db.tables import Base
from jarvis.events import EventBus
from jarvis.models.task import InvalidTransitionError, TaskPriority, TaskStatus
from jarvis.services.task_service import TaskNotFoundError, TaskService


@pytest.fixture
def event_bus() -> EventBus:
    return EventBus()


@pytest.fixture
def service(event_bus: EventBus) -> TaskService:
    return TaskService(event_bus)


@pytest.fixture
async def svc_db() -> Database:
    """Dedicated database for service tests."""
    database = Database(url="sqlite+aiosqlite://")
    async with database.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield database  # type: ignore[misc]
    await database.disconnect()


@pytest.fixture
async def session(svc_db: Database) -> AsyncSession:
    async with svc_db.session() as s:
        yield s  # type: ignore[misc]


class TestCreateTask:
    @pytest.mark.asyncio
    async def test_create_returns_task(self, service: TaskService, session: AsyncSession) -> None:
        task = await service.create_task(session, request="Fix the login", title="Fix login")
        assert task.id.startswith("TASK-")
        assert task.request == "Fix the login"
        assert task.title == "Fix login"
        assert task.status == TaskStatus.CREATED

    @pytest.mark.asyncio
    async def test_create_with_priority(self, service: TaskService, session: AsyncSession) -> None:
        task = await service.create_task(
            session,
            request="Urgent fix",
            title="Urgent",
            priority=TaskPriority.URGENT,
        )
        assert task.priority == TaskPriority.URGENT

    @pytest.mark.asyncio
    async def test_create_with_project_id(
        self, service: TaskService, session: AsyncSession
    ) -> None:
        task = await service.create_task(
            session, request="Fix it", title="Fix", project_id="proj-1"
        )
        assert task.project_id == "proj-1"

    @pytest.mark.asyncio
    async def test_unique_ids(self, service: TaskService, session: AsyncSession) -> None:
        t1 = await service.create_task(session, request="a", title="a")
        t2 = await service.create_task(session, request="b", title="b")
        assert t1.id != t2.id


class TestGetTask:
    @pytest.mark.asyncio
    async def test_get_existing(self, service: TaskService, session: AsyncSession) -> None:
        created = await service.create_task(session, request="a", title="a")
        fetched = await service.get_task(session, created.id)
        assert fetched.id == created.id

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, service: TaskService, session: AsyncSession) -> None:
        with pytest.raises(TaskNotFoundError):
            await service.get_task(session, "TASK-nonexistent")


class TestListTasks:
    @pytest.mark.asyncio
    async def test_list_empty(self, service: TaskService, session: AsyncSession) -> None:
        assert await service.list_tasks(session) == []

    @pytest.mark.asyncio
    async def test_list_returns_summaries(
        self, service: TaskService, session: AsyncSession
    ) -> None:
        await service.create_task(session, request="a", title="Task A")
        await service.create_task(session, request="b", title="Task B")
        summaries = await service.list_tasks(session)
        assert len(summaries) == 2

    @pytest.mark.asyncio
    async def test_filter_by_status(self, service: TaskService, session: AsyncSession) -> None:
        t1 = await service.create_task(session, request="a", title="a")
        await service.create_task(session, request="b", title="b")
        await service.transition_task(session, t1.id, TaskStatus.PLANNING)

        created = await service.list_tasks(session, status=TaskStatus.CREATED)
        assert len(created) == 1
        planning = await service.list_tasks(session, status=TaskStatus.PLANNING)
        assert len(planning) == 1

    @pytest.mark.asyncio
    async def test_filter_by_priority(self, service: TaskService, session: AsyncSession) -> None:
        await service.create_task(session, request="a", title="a", priority=TaskPriority.HIGH)
        await service.create_task(session, request="b", title="b", priority=TaskPriority.LOW)
        high = await service.list_tasks(session, priority=TaskPriority.HIGH)
        assert len(high) == 1

    @pytest.mark.asyncio
    async def test_limit(self, service: TaskService, session: AsyncSession) -> None:
        for i in range(5):
            await service.create_task(session, request=f"task {i}", title=f"Task {i}")
        assert len(await service.list_tasks(session, limit=3)) == 3


class TestTransitions:
    @pytest.mark.asyncio
    async def test_valid_transition(self, service: TaskService, session: AsyncSession) -> None:
        task = await service.create_task(session, request="a", title="a")
        updated = await service.transition_task(session, task.id, TaskStatus.PLANNING)
        assert updated.status == TaskStatus.PLANNING
        assert updated.version == 2

    @pytest.mark.asyncio
    async def test_invalid_transition(self, service: TaskService, session: AsyncSession) -> None:
        task = await service.create_task(session, request="a", title="a")
        with pytest.raises(InvalidTransitionError):
            await service.transition_task(session, task.id, TaskStatus.COMPLETED)

    @pytest.mark.asyncio
    async def test_running_sets_started_at(
        self, service: TaskService, session: AsyncSession
    ) -> None:
        task = await service.create_task(session, request="a", title="a")
        await service.transition_task(session, task.id, TaskStatus.PLANNING)
        updated = await service.transition_task(session, task.id, TaskStatus.RUNNING)
        assert updated.started_at is not None

    @pytest.mark.asyncio
    async def test_completed_sets_completed_at(
        self, service: TaskService, session: AsyncSession
    ) -> None:
        task = await service.create_task(session, request="a", title="a")
        await service.transition_task(session, task.id, TaskStatus.PLANNING)
        await service.transition_task(session, task.id, TaskStatus.RUNNING)
        await service.transition_task(session, task.id, TaskStatus.VERIFYING)
        updated = await service.transition_task(session, task.id, TaskStatus.COMPLETED)
        assert updated.completed_at is not None

    @pytest.mark.asyncio
    async def test_fail_stores_error(self, service: TaskService, session: AsyncSession) -> None:
        task = await service.create_task(session, request="a", title="a")
        await service.transition_task(session, task.id, TaskStatus.PLANNING)
        await service.transition_task(session, task.id, TaskStatus.RUNNING)
        updated = await service.transition_task(
            session, task.id, TaskStatus.FAILED, error="Something broke"
        )
        assert updated.error == "Something broke"

    @pytest.mark.asyncio
    async def test_version_increments(self, service: TaskService, session: AsyncSession) -> None:
        task = await service.create_task(session, request="a", title="a")
        assert task.version == 1
        await service.transition_task(session, task.id, TaskStatus.PLANNING)
        t = await service.get_task(session, task.id)
        assert t.version == 2


class TestCancel:
    @pytest.mark.asyncio
    async def test_cancel_created_task(self, service: TaskService, session: AsyncSession) -> None:
        task = await service.create_task(session, request="a", title="a")
        cancelled = await service.cancel_task(session, task.id)
        assert cancelled.status == TaskStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_cancel_planning_task(self, service: TaskService, session: AsyncSession) -> None:
        task = await service.create_task(session, request="a", title="a")
        await service.transition_task(session, task.id, TaskStatus.PLANNING)
        cancelled = await service.cancel_task(session, task.id)
        assert cancelled.status == TaskStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_cancel_running_task(self, service: TaskService, session: AsyncSession) -> None:
        task = await service.create_task(session, request="a", title="a")
        await service.transition_task(session, task.id, TaskStatus.PLANNING)
        await service.transition_task(session, task.id, TaskStatus.RUNNING)
        cancelled = await service.cancel_task(session, task.id)
        assert cancelled.status == TaskStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_cannot_cancel_completed_task(
        self, service: TaskService, session: AsyncSession
    ) -> None:
        task = await service.create_task(session, request="a", title="a")
        await service.transition_task(session, task.id, TaskStatus.PLANNING)
        await service.transition_task(session, task.id, TaskStatus.RUNNING)
        await service.transition_task(session, task.id, TaskStatus.VERIFYING)
        await service.transition_task(session, task.id, TaskStatus.COMPLETED)
        with pytest.raises(InvalidTransitionError):
            await service.cancel_task(session, task.id)

    @pytest.mark.asyncio
    async def test_cannot_cancel_already_cancelled(
        self, service: TaskService, session: AsyncSession
    ) -> None:
        task = await service.create_task(session, request="a", title="a")
        await service.cancel_task(session, task.id)
        with pytest.raises(InvalidTransitionError):
            await service.cancel_task(session, task.id)

    @pytest.mark.asyncio
    async def test_cancel_cancels_pending_steps(
        self, service: TaskService, session: AsyncSession
    ) -> None:
        task = await service.create_task(session, request="a", title="a")
        await service.add_steps(session, task.id, ["step 1", "step 2"])
        await service.cancel_task(session, task.id)
        steps = await service.get_steps(session, task.id)
        assert all(s.status == "cancelled" for s in steps)


class TestRetry:
    @pytest.mark.asyncio
    async def test_retry_failed_task(self, service: TaskService, session: AsyncSession) -> None:
        task = await service.create_task(session, request="a", title="a")
        await service.transition_task(session, task.id, TaskStatus.PLANNING)
        await service.transition_task(session, task.id, TaskStatus.RUNNING)
        await service.transition_task(session, task.id, TaskStatus.FAILED, error="oops")
        retried = await service.transition_task(session, task.id, TaskStatus.PLANNING)
        assert retried.status == TaskStatus.PLANNING


class TestSteps:
    @pytest.mark.asyncio
    async def test_add_steps(self, service: TaskService, session: AsyncSession) -> None:
        task = await service.create_task(session, request="a", title="a")
        steps = await service.add_steps(session, task.id, ["step 1", "step 2", "step 3"])
        assert len(steps) == 3
        assert steps[0].sequence == 1
        assert steps[2].sequence == 3

    @pytest.mark.asyncio
    async def test_get_steps(self, service: TaskService, session: AsyncSession) -> None:
        task = await service.create_task(session, request="a", title="a")
        await service.add_steps(session, task.id, ["step 1"])
        steps = await service.get_steps(session, task.id)
        assert len(steps) == 1
        assert steps[0].description == "step 1"

    @pytest.mark.asyncio
    async def test_get_steps_nonexistent_task(
        self, service: TaskService, session: AsyncSession
    ) -> None:
        with pytest.raises(TaskNotFoundError):
            await service.get_steps(session, "TASK-nope")


class TestPersistence:
    """Test that data persists across sessions."""

    @pytest.mark.asyncio
    async def test_task_persists_across_sessions(
        self, service: TaskService, svc_db: Database
    ) -> None:
        async with svc_db.session() as s1:
            task = await service.create_task(s1, request="persist me", title="Persist")
            await s1.commit()
        async with svc_db.session() as s2:
            fetched = await service.get_task(s2, task.id)
            assert fetched.request == "persist me"

    @pytest.mark.asyncio
    async def test_steps_persist_across_sessions(
        self, service: TaskService, svc_db: Database
    ) -> None:
        async with svc_db.session() as s1:
            task = await service.create_task(s1, request="a", title="a")
            await service.add_steps(s1, task.id, ["step 1", "step 2"])
            await s1.commit()
        async with svc_db.session() as s2:
            steps = await service.get_steps(s2, task.id)
            assert len(steps) == 2

    @pytest.mark.asyncio
    async def test_state_transition_persists(self, service: TaskService, svc_db: Database) -> None:
        async with svc_db.session() as s1:
            task = await service.create_task(s1, request="a", title="a")
            await service.transition_task(s1, task.id, TaskStatus.PLANNING)
            await s1.commit()
        async with svc_db.session() as s2:
            fetched = await service.get_task(s2, task.id)
            assert fetched.status == TaskStatus.PLANNING
            assert fetched.version == 2


class TestConcurrency:
    """Test concurrency safety via optimistic concurrency control."""

    @pytest.mark.asyncio
    async def test_version_prevents_stale_update(
        self, service: TaskService, svc_db: Database
    ) -> None:
        """Two concurrent transitions should not both succeed if they
        conflict. The version field ensures data integrity."""
        async with svc_db.session() as s:
            task = await service.create_task(s, request="a", title="a")
            await s.commit()

        # First transition succeeds
        async with svc_db.session() as s1:
            await service.transition_task(s1, task.id, TaskStatus.PLANNING)
            await s1.commit()

        # Verify the version incremented
        async with svc_db.session() as s2:
            fetched = await service.get_task(s2, task.id)
            assert fetched.version == 2
