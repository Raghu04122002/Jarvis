"""Tests for the orchestrator with async database persistence."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from jarvis.db.engine import Database
from jarvis.db.tables import Base
from jarvis.events import EventBus
from jarvis.models.task import ChatRequest
from jarvis.orchestrator.orchestrator import Orchestrator
from jarvis.orchestrator.planner import BasicPlanner
from jarvis.services.task_service import TaskService


def _make_orchestrator() -> Orchestrator:
    bus = EventBus()
    service = TaskService(bus)
    planner = BasicPlanner()
    return Orchestrator(service, planner)


@pytest.fixture
async def orch_db() -> Database:
    database = Database(url="sqlite+aiosqlite://")
    async with database.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield database  # type: ignore[misc]
    await database.disconnect()


@pytest.fixture
async def session(orch_db: Database) -> AsyncSession:
    async with orch_db.session() as s:
        yield s  # type: ignore[misc]


class TestOrchestrator:
    @pytest.mark.asyncio
    async def test_handle_chat_creates_task(self, session: AsyncSession) -> None:
        orch = _make_orchestrator()
        resp = await orch.handle_chat(session, ChatRequest(message="Fix the login issue"))
        assert resp.task_id is not None
        assert resp.task_id.startswith("TASK-")
        assert resp.status == "planning"

    @pytest.mark.asyncio
    async def test_handle_chat_generates_plan(self, session: AsyncSession) -> None:
        orch = _make_orchestrator()
        resp = await orch.handle_chat(session, ChatRequest(message="Fix it"))
        assert len(resp.plan) > 0

    @pytest.mark.asyncio
    async def test_handle_chat_creates_steps(self, session: AsyncSession) -> None:
        orch = _make_orchestrator()
        resp = await orch.handle_chat(session, ChatRequest(message="Fix it"))
        assert resp.task_id is not None
        steps = await orch.task_service.get_steps(session, resp.task_id)
        assert len(steps) == len(resp.plan)
        assert steps[0].description == resp.plan[0]

    @pytest.mark.asyncio
    async def test_handle_chat_with_project_id(self, session: AsyncSession) -> None:
        orch = _make_orchestrator()
        resp = await orch.handle_chat(
            session, ChatRequest(message="Fix login", project_id="proj-1")
        )
        assert resp.task_id is not None
        task = await orch.task_service.get_task(session, resp.task_id)
        assert task.project_id == "proj-1"
