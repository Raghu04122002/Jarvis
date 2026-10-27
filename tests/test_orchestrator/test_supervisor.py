"""Tests for the AI supervisor: planning, agent choice, and result review."""

import json
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from jarvis.agents.base import BaseAgent
from jarvis.agents.registry import AgentRegistry
from jarvis.agents.router import AgentRouter
from jarvis.config import AgentsConfig
from jarvis.db.engine import Database
from jarvis.db.tables import Base
from jarvis.events import Event, EventBus, EventType
from jarvis.models.task import ChatRequest, TaskStatus
from jarvis.orchestrator.orchestrator import Orchestrator
from jarvis.orchestrator.planner import BasicPlanner
from jarvis.orchestrator.supervisor import Supervisor, parse_json_object
from jarvis.services.agent_execution_service import AgentExecutionService
from jarvis.services.ai_service import AIServiceError
from jarvis.services.project_service import ProjectService
from jarvis.services.task_service import TaskService


class FakeAI:
    """Stands in for AIService.complete(): returns queued replies in order."""

    def __init__(self, *replies: object, available: bool = True) -> None:
        self.replies = list(replies)
        self.available = available
        self.calls: list[dict[str, Any]] = []

    async def complete(
        self, system: str, message: str, *, model: str | None = None, json_mode: bool = False
    ) -> str:
        self.calls.append({"system": system, "message": message, "model": model})
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply if isinstance(reply, str) else json.dumps(reply)


class ScriptedAgent(BaseAgent):
    """Agent that returns queued outputs and records the prompts it got."""

    def __init__(self, *outputs: str, name: str = "claude_code") -> None:
        self.outputs = list(outputs)
        self.prompts: list[str] = []
        self._name = name

    @property
    def agent_name(self) -> str:
        return self._name

    async def run(self, prompt: str, working_dir: str) -> tuple[int, str, str]:
        self.prompts.append(prompt)
        return 0, self.outputs.pop(0), ""

    async def cancel(self) -> None:
        pass

    def status(self) -> str:
        return "completed"

    def elapsed_seconds(self) -> float | None:
        return 1.0


def _supervisor(ai: FakeAI, model: str | None = None) -> Supervisor:
    return Supervisor(ai, ["antigravity", "claude_code"], model=model)  # type: ignore[arg-type]


PLAN = {
    "title": "Add login page",
    "steps": ["Create form", "Wire API", "Add tests"],
    "agent": "claude_code",
    "reason": "Code change in repo",
}
DONE = {"done": True, "summary": "Login page added, tests pass.", "follow_up": ""}
NOT_DONE = {"done": False, "summary": "Tests still fail.", "follow_up": "Fix test_login."}


# ---------- Supervisor unit tests ----------

class TestPlan:
    async def test_plan_parsed(self) -> None:
        ai = FakeAI(PLAN)
        plan = await _supervisor(ai, model="gpt-oss:120b").plan("add login", "Project: x")
        assert plan is not None
        assert plan.title == "Add login page"
        assert plan.steps == ["Create form", "Wire API", "Add tests"]
        assert plan.agent == "claude_code"
        assert "claude_code" in ai.calls[0]["system"]
        assert "Project: x" in ai.calls[0]["message"]
        assert ai.calls[0]["model"] == "gpt-oss:120b"

    async def test_unknown_agent_left_to_router(self) -> None:
        plan = await _supervisor(FakeAI({**PLAN, "agent": "gemini"})).plan("x")
        assert plan is not None and plan.agent is None

    async def test_fenced_json_accepted(self) -> None:
        plan = await _supervisor(FakeAI("Sure:\n```json\n" + json.dumps(PLAN) + "\n```")).plan("x")
        assert plan is not None and plan.agent == "claude_code"

    @pytest.mark.parametrize("reply", [
        "not json at all",
        {"title": "t", "steps": []},
        AIServiceError("Ollama Cloud usage limit reached"),
    ])
    async def test_unusable_reply_returns_none(self, reply: object) -> None:
        assert await _supervisor(FakeAI(reply)).plan("x") is None

    async def test_unavailable_ai_skips_call(self) -> None:
        ai = FakeAI(available=False)
        assert await _supervisor(ai).plan("x") is None
        assert ai.calls == []


class TestReview:
    async def test_done(self) -> None:
        review = await _supervisor(FakeAI(DONE)).review("task", "claude_code", "out")
        assert review is not None and review.done and review.summary.startswith("Login")

    async def test_not_done_gets_follow_up(self) -> None:
        review = await _supervisor(FakeAI({"done": "false", "summary": "Missing tests"})).review(
            "task", "claude_code", "out"
        )
        assert review is not None and not review.done
        assert review.follow_up == "Missing tests"

    async def test_long_output_truncated_to_tail(self) -> None:
        ai = FakeAI(DONE)
        await _supervisor(ai).review("task", "claude_code", "A" * 20000 + "FINAL")
        msg = ai.calls[0]["message"]
        assert "FINAL" in msg and len(msg) < 7000

    async def test_missing_done_returns_none(self) -> None:
        assert await _supervisor(FakeAI({"summary": "?"})).review("t", "a", "o") is None


def test_parse_json_object() -> None:
    assert parse_json_object('{"a": 1}') == {"a": 1}
    assert parse_json_object('text {"a": 1} more') == {"a": 1}
    assert parse_json_object("[1, 2]") is None


# ---------- Orchestrator integration ----------

@pytest.fixture
async def session() -> AsyncSession:
    db = Database(url="sqlite+aiosqlite://")
    async with db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with db.session() as s:
        yield s  # type: ignore[misc]
    await db.disconnect()


async def _setup(
    session: AsyncSession, agent: BaseAgent, ai: FakeAI, rounds: int = 1
) -> tuple[Orchestrator, TaskService, AgentExecutionService, str, list[Event]]:
    bus = EventBus()
    events: list[Event] = []
    bus.subscribe(EventType.TASK_REVIEWED, events.append)
    task_svc = TaskService(bus)
    project_svc = ProjectService(bus)
    exec_svc = AgentExecutionService(bus)
    project = await project_svc.create_project(session, name="p", local_path="/tmp")
    task = await task_svc.create_task(
        session, request="Add login", title="t", project_id=project.id
    )
    await task_svc.transition_task(session, task.id, TaskStatus.PLANNING)
    await session.commit()

    registry = AgentRegistry()
    registry.register(agent.agent_name, lambda _cfg: agent)
    orch = Orchestrator(
        task_svc, BasicPlanner(), project_svc, exec_svc, AgentsConfig(),
        agent_registry=registry, agent_router=AgentRouter(registry, AgentsConfig()),
        event_bus=bus, supervisor=_supervisor(ai), review_max_rounds=rounds,
    )
    return orch, task_svc, exec_svc, task.id, events


class TestOrchestratorSupervision:
    async def test_review_passes_first_time(self, session: AsyncSession) -> None:
        agent = ScriptedAgent("did it")
        orch, task_svc, exec_svc, task_id, events = await _setup(session, agent, FakeAI(DONE))
        await orch.dispatch_task(session, task_id)

        task = await task_svc.get_task(session, task_id)
        assert task.status == TaskStatus.COMPLETED
        assert task.result is not None and task.result.startswith("Supervisor: Login page added")
        assert len(agent.prompts) == 1
        assert [e.data["done"] for e in events] == [True]

    async def test_follow_up_then_done(self, session: AsyncSession) -> None:
        agent = ScriptedAgent("half done", "all done")
        orch, task_svc, exec_svc, task_id, events = await _setup(
            session, agent, FakeAI(NOT_DONE, DONE)
        )
        await orch.dispatch_task(session, task_id)

        task = await task_svc.get_task(session, task_id)
        assert task.status == TaskStatus.COMPLETED
        assert len(agent.prompts) == 2
        assert "Fix test_login." in agent.prompts[1]
        assert "Add login" in agent.prompts[1]
        assert len(await exec_svc.list_executions_for_task(session, task_id)) == 2
        assert [e.data["done"] for e in events] == [False, True]

    async def test_fails_after_max_rounds(self, session: AsyncSession) -> None:
        agent = ScriptedAgent("nope", "still nope")
        orch, task_svc, _, task_id, _ = await _setup(
            session, agent, FakeAI(NOT_DONE, NOT_DONE), rounds=1
        )
        await orch.dispatch_task(session, task_id)

        task = await task_svc.get_task(session, task_id)
        assert task.status == TaskStatus.FAILED
        assert task.error is not None and "Tests still fail." in task.error
        assert len(agent.prompts) == 2

    async def test_review_unavailable_completes_with_raw_output(
        self, session: AsyncSession
    ) -> None:
        agent = ScriptedAgent("did it")
        orch, task_svc, _, task_id, _ = await _setup(
            session, agent, FakeAI(AIServiceError("402"))
        )
        await orch.dispatch_task(session, task_id)

        task = await task_svc.get_task(session, task_id)
        assert task.status == TaskStatus.COMPLETED
        assert task.result == "did it"

    async def test_handle_chat_uses_supervisor_plan_and_agent(
        self, session: AsyncSession
    ) -> None:
        agent = ScriptedAgent()
        orch, task_svc, _, _, _ = await _setup(
            session, agent, FakeAI({**PLAN, "agent": "antigravity"})
        )
        resp = await orch.handle_chat(session, ChatRequest(message="add a login page"))

        assert resp.plan == PLAN["steps"]
        assert resp.title == "Add login page"
        task = await task_svc.get_task(session, resp.task_id or "")
        assert task.metadata["agent_name"] == "antigravity"
        assert task.metadata["planned_by"] == "supervisor"

    async def test_handle_chat_falls_back_to_basic_planner(
        self, session: AsyncSession
    ) -> None:
        orch, _, _, _, _ = await _setup(session, ScriptedAgent(), FakeAI("garbage"))
        resp = await orch.handle_chat(session, ChatRequest(message="add a login page"))
        assert resp.plan == BasicPlanner().create_plan("x").steps
