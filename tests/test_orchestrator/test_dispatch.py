"""Tests for the refactored dispatch_task with agent routing and fallback."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from jarvis.agents.base import AgentError, BaseAgent
from jarvis.agents.registry import AgentRegistry
from jarvis.agents.router import AgentRouter
from jarvis.config import AgentsConfig
from jarvis.db.engine import Database
from jarvis.db.tables import Base
from jarvis.events import EventBus, EventType
from jarvis.models.task import Task, TaskStatus
from jarvis.orchestrator.orchestrator import Orchestrator
from jarvis.orchestrator.planner import BasicPlanner
from jarvis.services.agent_execution_service import AgentExecutionService
from jarvis.services.project_service import ProjectService
from jarvis.services.task_service import TaskService


class FakeAgent(BaseAgent):
    """Fake agent for tests."""

    def __init__(self, name: str = "claude_code", exit_code: int = 0) -> None:
        self._name = name
        self._exit_code = exit_code

    @property
    def agent_name(self) -> str:
        return self._name

    async def run(self, prompt: str, working_dir: str) -> tuple[int, str, str]:
        return self._exit_code, "output", ""

    async def cancel(self) -> None:
        pass

    def status(self) -> str:
        return "completed"

    def elapsed_seconds(self) -> float | None:
        return 1.0


def _raise_agent_error(msg: str) -> BaseAgent:
    raise AgentError(msg)


@pytest.fixture
async def dispatch_db() -> Database:
    database = Database(url="sqlite+aiosqlite://")
    async with database.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield database  # type: ignore[misc]
    await database.disconnect()


@pytest.fixture
async def session(dispatch_db: Database) -> AsyncSession:
    async with dispatch_db.session() as s:
        yield s  # type: ignore[misc]


def _make_registry(
    primary: BaseAgent | None = None,
    fallback: BaseAgent | None = None,
    primary_name: str = "claude_code",
    fallback_name: str = "antigravity",
    fail_primary: bool = False,
    fail_fallback: bool = False,
) -> AgentRegistry:
    registry = AgentRegistry()

    if fail_primary:
        msg = f"{primary_name} not found"
        registry.register(
            primary_name, lambda _cfg, m=msg: _raise_agent_error(m),
        )
    else:
        agent = primary or FakeAgent(primary_name)
        registry.register(primary_name, lambda _cfg, a=agent: a)

    if fail_fallback:
        msg = f"{fallback_name} not found"
        registry.register(
            fallback_name, lambda _cfg, m=msg: _raise_agent_error(m),
        )
    else:
        agent = fallback or FakeAgent(fallback_name)
        registry.register(fallback_name, lambda _cfg, a=agent: a)

    return registry


async def _setup_task(
    session: AsyncSession,
    bus: EventBus,
    request: str = "Fix a bug",
    metadata: dict[str, str] | None = None,
) -> tuple[Task, TaskService, ProjectService, AgentExecutionService]:
    """Create a task and supporting services, transition to PLANNING."""
    task_svc = TaskService(bus)
    project_svc = ProjectService(bus)
    exec_svc = AgentExecutionService(bus)

    # Create a project
    project = await project_svc.create_project(
        session, name="test-project", local_path="/tmp",
    )

    task = await task_svc.create_task(
        session,
        request=request,
        title="Test task",
        project_id=project.id,
        metadata=metadata,
    )
    await task_svc.transition_task(session, task.id, TaskStatus.PLANNING)
    await session.commit()

    return task, task_svc, project_svc, exec_svc


class TestDispatchRouting:
    @pytest.mark.asyncio
    async def test_dispatch_uses_router_default(
        self, session: AsyncSession,
    ) -> None:
        bus = EventBus()
        task, task_svc, project_svc, exec_svc = await _setup_task(
            session, bus,
        )

        registry = _make_registry()
        config = AgentsConfig()
        router = AgentRouter(registry, config)

        orch = Orchestrator(
            task_svc, BasicPlanner(), project_svc, exec_svc, config,
            agent_registry=registry, agent_router=router, event_bus=bus,
        )

        await orch.dispatch_task(session, task.id)
        updated = await task_svc.get_task(session, task.id)
        assert updated.status == TaskStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_dispatch_uses_metadata_agent_name(
        self, session: AsyncSession,
    ) -> None:
        bus = EventBus()
        task, task_svc, project_svc, exec_svc = await _setup_task(
            session, bus, metadata={"agent_name": "antigravity"},
        )

        ag_agent = FakeAgent("antigravity")
        registry = _make_registry(fallback=ag_agent)
        config = AgentsConfig()
        router = AgentRouter(registry, config)

        orch = Orchestrator(
            task_svc, BasicPlanner(), project_svc, exec_svc, config,
            agent_registry=registry, agent_router=router, event_bus=bus,
        )

        await orch.dispatch_task(session, task.id)

        execs = await exec_svc.list_executions_for_task(session, task.id)
        running_exec = [e for e in execs if e.exit_code is not None]
        assert len(running_exec) >= 1
        assert running_exec[0].agent_name == "antigravity"

    @pytest.mark.asyncio
    async def test_dispatch_keyword_selects_antigravity(
        self, session: AsyncSession,
    ) -> None:
        bus = EventBus()
        task, task_svc, project_svc, exec_svc = await _setup_task(
            session, bus, request="Take a screenshot of the homepage",
        )

        ag_agent = FakeAgent("antigravity")
        registry = _make_registry(fallback=ag_agent)
        config = AgentsConfig()
        router = AgentRouter(registry, config)

        orch = Orchestrator(
            task_svc, BasicPlanner(), project_svc, exec_svc, config,
            agent_registry=registry, agent_router=router, event_bus=bus,
        )

        await orch.dispatch_task(session, task.id)

        execs = await exec_svc.list_executions_for_task(session, task.id)
        running_exec = [e for e in execs if e.exit_code is not None]
        assert len(running_exec) >= 1
        assert running_exec[0].agent_name == "antigravity"


class TestDispatchFallback:
    @pytest.mark.asyncio
    async def test_fallback_on_primary_agent_failure(
        self, session: AsyncSession,
    ) -> None:
        bus = EventBus()
        task, task_svc, project_svc, exec_svc = await _setup_task(
            session, bus,
        )

        fallback_agent = FakeAgent("antigravity")
        registry = _make_registry(
            fail_primary=True, fallback=fallback_agent,
        )
        config = AgentsConfig()
        router = AgentRouter(registry, config)

        fallback_events: list[dict] = []
        bus.subscribe(
            EventType.AGENT_FALLBACK_TRIGGERED,
            lambda e: fallback_events.append(e.data),
        )

        orch = Orchestrator(
            task_svc, BasicPlanner(), project_svc, exec_svc, config,
            agent_registry=registry, agent_router=router, event_bus=bus,
        )

        await orch.dispatch_task(session, task.id)

        updated = await task_svc.get_task(session, task.id)
        assert updated.status == TaskStatus.COMPLETED

        # Fallback event should have been emitted
        assert len(fallback_events) == 1
        assert fallback_events[0]["primary_agent"] == "claude_code"
        assert fallback_events[0]["fallback_agent"] == "antigravity"

    @pytest.mark.asyncio
    async def test_both_agents_fail_results_in_task_failure(
        self, session: AsyncSession,
    ) -> None:
        bus = EventBus()
        task, task_svc, project_svc, exec_svc = await _setup_task(
            session, bus,
        )

        registry = _make_registry(
            fail_primary=True, fail_fallback=True,
        )
        config = AgentsConfig()
        router = AgentRouter(registry, config)

        orch = Orchestrator(
            task_svc, BasicPlanner(), project_svc, exec_svc, config,
            agent_registry=registry, agent_router=router, event_bus=bus,
        )

        await orch.dispatch_task(session, task.id)

        updated = await task_svc.get_task(session, task.id)
        assert updated.status == TaskStatus.FAILED

    @pytest.mark.asyncio
    async def test_no_fallback_available(
        self, session: AsyncSession,
    ) -> None:
        bus = EventBus()
        task, task_svc, project_svc, exec_svc = await _setup_task(
            session, bus,
        )

        # Registry with only claude_code that fails
        registry = AgentRegistry()
        registry.register(
            "claude_code",
            lambda _cfg: _raise_agent_error("not found"),
        )
        config = AgentsConfig()
        router = AgentRouter(registry, config)

        orch = Orchestrator(
            task_svc, BasicPlanner(), project_svc, exec_svc, config,
            agent_registry=registry, agent_router=router, event_bus=bus,
        )

        await orch.dispatch_task(session, task.id)

        updated = await task_svc.get_task(session, task.id)
        assert updated.status == TaskStatus.FAILED


class TestDispatchNonZeroExit:
    @pytest.mark.asyncio
    async def test_nonzero_exit_does_not_trigger_fallback(
        self, session: AsyncSession,
    ) -> None:
        bus = EventBus()
        task, task_svc, project_svc, exec_svc = await _setup_task(
            session, bus,
        )

        failing_agent = FakeAgent("claude_code", exit_code=1)
        registry = _make_registry(primary=failing_agent)
        config = AgentsConfig()
        router = AgentRouter(registry, config)

        fallback_events: list[dict] = []
        bus.subscribe(
            EventType.AGENT_FALLBACK_TRIGGERED,
            lambda e: fallback_events.append(e.data),
        )

        orch = Orchestrator(
            task_svc, BasicPlanner(), project_svc, exec_svc, config,
            agent_registry=registry, agent_router=router, event_bus=bus,
        )

        await orch.dispatch_task(session, task.id)

        updated = await task_svc.get_task(session, task.id)
        assert updated.status == TaskStatus.FAILED

        # No fallback should have been triggered
        assert len(fallback_events) == 0


class TestDispatchMissingDependencies:
    @pytest.mark.asyncio
    async def test_dispatch_without_registry_raises(
        self, session: AsyncSession,
    ) -> None:
        bus = EventBus()
        task, task_svc, project_svc, exec_svc = await _setup_task(
            session, bus,
        )

        orch = Orchestrator(
            task_svc, BasicPlanner(), project_svc, exec_svc,
        )

        with pytest.raises(
            RuntimeError, match="Agent registry not configured",
        ):
            await orch.dispatch_task(session, task.id)

    @pytest.mark.asyncio
    async def test_dispatch_without_router_raises(
        self, session: AsyncSession,
    ) -> None:
        bus = EventBus()
        task, task_svc, project_svc, exec_svc = await _setup_task(
            session, bus,
        )

        registry = _make_registry()
        orch = Orchestrator(
            task_svc, BasicPlanner(), project_svc, exec_svc,
            agent_registry=registry,
        )

        with pytest.raises(
            RuntimeError, match="Agent router not configured",
        ):
            await orch.dispatch_task(session, task.id)
