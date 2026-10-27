"""Integration tests for smart chat routing in the orchestrator."""

from unittest.mock import MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from jarvis.db.engine import Database
from jarvis.db.tables import Base
from jarvis.events import EventBus, EventType
from jarvis.models.task import ChatRequest
from jarvis.orchestrator.orchestrator import Orchestrator
from jarvis.orchestrator.planner import BasicPlanner
from jarvis.services.project_service import ProjectService
from jarvis.services.task_service import TaskService


@pytest.fixture
async def smart_db() -> Database:
    database = Database(url="sqlite+aiosqlite://")
    async with database.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield database  # type: ignore[misc]
    await database.disconnect()


@pytest.fixture
async def session(smart_db: Database) -> AsyncSession:
    async with smart_db.session() as s:
        yield s  # type: ignore[misc]


class TestQueryRouting:
    @pytest.mark.asyncio
    async def test_query_returns_direct_answer(self, session: AsyncSession) -> None:
        bus = EventBus()
        task_service = TaskService(bus)
        project_service = ProjectService(bus)
        orch = Orchestrator(
            task_service, BasicPlanner(), project_service=project_service, event_bus=bus
        )
        resp = await orch.handle_chat(session, ChatRequest(message="check my projects"))
        assert resp.status == "answered"
        assert resp.answer is not None
        assert resp.task_id is None

    @pytest.mark.asyncio
    async def test_query_does_not_create_task(self, session: AsyncSession) -> None:
        bus = EventBus()
        task_service = TaskService(bus)
        orch = Orchestrator(task_service, BasicPlanner(), event_bus=bus)
        resp = await orch.handle_chat(session, ChatRequest(message="what's broken?"))
        assert resp.task_id is None
        # No tasks should exist
        tasks = await task_service.list_tasks(session)
        assert len(tasks) == 0

    @pytest.mark.asyncio
    async def test_query_publishes_event(self, session: AsyncSession) -> None:
        bus = EventBus()
        events: list[object] = []
        bus.subscribe(EventType.QUERY_ANSWERED, events.append)
        orch = Orchestrator(TaskService(bus), BasicPlanner(), event_bus=bus)
        await orch.handle_chat(session, ChatRequest(message="status"))
        assert len(events) == 1


class TestActionRouting:
    @pytest.mark.asyncio
    async def test_action_creates_task(self, session: AsyncSession) -> None:
        bus = EventBus()
        task_service = TaskService(bus)
        orch = Orchestrator(task_service, BasicPlanner(), event_bus=bus)
        resp = await orch.handle_chat(session, ChatRequest(message="deploy staging"))
        assert resp.task_id is not None
        assert resp.status == "planning"
        assert len(resp.plan) > 0

    @pytest.mark.asyncio
    async def test_action_stores_intent_metadata(self, session: AsyncSession) -> None:
        bus = EventBus()
        task_service = TaskService(bus)
        orch = Orchestrator(task_service, BasicPlanner(), event_bus=bus)
        resp = await orch.handle_chat(session, ChatRequest(message="deploy staging"))
        assert resp.task_id is not None
        task = await task_service.get_task(session, resp.task_id)
        assert task.metadata.get("intent") == "action"

    @pytest.mark.asyncio
    async def test_action_with_background_tasks(
        self, session: AsyncSession, smart_db: Database
    ) -> None:
        bus = EventBus()
        task_service = TaskService(bus)
        bg = MagicMock()
        orch = Orchestrator(
            task_service, BasicPlanner(), event_bus=bus, db=smart_db
        )
        resp = await orch.handle_chat(
            session, ChatRequest(message="run tests"), background_tasks=bg
        )
        assert resp.task_id is not None
        bg.add_task.assert_called_once()


class TestWorkflowRouting:
    @pytest.mark.asyncio
    async def test_workflow_creates_task_with_issue(self, session: AsyncSession) -> None:
        bus = EventBus()
        task_service = TaskService(bus)
        orch = Orchestrator(task_service, BasicPlanner(), event_bus=bus)
        resp = await orch.handle_chat(session, ChatRequest(message="fix issue #42"))
        assert resp.task_id is not None
        task = await task_service.get_task(session, resp.task_id)
        assert task.metadata.get("intent") == "workflow"
        assert task.metadata.get("issue_number") == "42"

    @pytest.mark.asyncio
    async def test_workflow_triggers_background(
        self, session: AsyncSession, smart_db: Database
    ) -> None:
        bus = EventBus()
        task_service = TaskService(bus)
        bg = MagicMock()
        orch = Orchestrator(
            task_service, BasicPlanner(), event_bus=bus, db=smart_db
        )
        resp = await orch.handle_chat(
            session, ChatRequest(message="resolve #99"), background_tasks=bg
        )
        assert resp.task_id is not None
        bg.add_task.assert_called_once()


class TestProjectResolution:
    @pytest.mark.asyncio
    async def test_project_hint_resolved(self, session: AsyncSession) -> None:
        bus = EventBus()
        task_service = TaskService(bus)
        project_service = ProjectService(bus)
        project = await project_service.create_project(
            session, name="MinaarTech", local_path="/projects/minaartech"
        )
        orch = Orchestrator(
            task_service, BasicPlanner(), project_service=project_service, event_bus=bus
        )
        resp = await orch.handle_chat(session, ChatRequest(message="test MinaarTech"))
        assert resp.task_id is not None
        task = await task_service.get_task(session, resp.task_id)
        assert task.project_id == project.id

    @pytest.mark.asyncio
    async def test_missing_project_doesnt_crash(self, session: AsyncSession) -> None:
        bus = EventBus()
        task_service = TaskService(bus)
        project_service = ProjectService(bus)
        orch = Orchestrator(
            task_service, BasicPlanner(), project_service=project_service, event_bus=bus
        )
        resp = await orch.handle_chat(
            session, ChatRequest(message="test UnknownProject")
        )
        assert resp.task_id is not None
